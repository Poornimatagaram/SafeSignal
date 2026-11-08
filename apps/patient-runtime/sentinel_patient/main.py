"""Patient runtime API on localhost:8001. Only patient-web (localhost:5173) calls it.

Run: uv run uvicorn sentinel_patient.main:app --port 8001   (uvicorn binds 127.0.0.1 by default; keep it that way)

Logs carry method, path and status only, never request bodies, audio, transcripts or patient words (26.12).
This module makes no outbound calls: every outbound byte goes through egress_gate.

Check-in: start (refreshes the survey and term list through the egress gate) -> one turn per answer: audio (in memory
only) -> stt -> transcript -> filter (identifiers removed) -> extract (local model, coded fields only) -> summary in
plain words with the exact record -> nothing leaves until the patient approves -> egress gate sends the record,
then the care envelope sealed on this device (NF-05) -> receipts.

Consent (CN-01, CN-03): GET/PUT /consent are the two switches. A change is saved on the device at once and sent as
a consent update through the egress gate; it is the only other thing the patient can send.
"""

from __future__ import annotations

from contextlib import asynccontextmanager, closing
from typing import Any, Callable

from fastapi import Body, FastAPI, HTTPException, Path, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from sentinel_contract import SCHEMA_VERSION, ContractError

from . import commands, consent, egress_gate, extract, rating, stt, summary, tts
from . import filter as pii_filter
from .checkin import (DESTINATION_LABEL, SYMPTOM_PURPOSES, AlreadyShared, CheckinStore, CorrectionUsed,
                      NeedsSeverity, NoTerms, UnknownQuestion, UnknownSession)
from .config import Settings
from .db import connect, init_db
from .survey import NoSurvey, latest_survey, term_labels

LOOPBACK_CLIENTS = {"127.0.0.1", "::1", "localhost"}
QUESTION_ID = r"^[a-z0-9_]{1,32}$"
SESSION_ID = r"^ses_[a-f0-9]{8}$"


def create_app(settings: Settings | None = None, *, transcriber: stt.Transcriber | None = None,
               speaker: tts.Speaker | None = None, redactor: Callable[[str], Any] | None = None,
               extractor: Callable[[str], list] | None = None, rater: Callable[..., Any] | None = None,
               sentinel_client: Any = None, retry_interval: float | None = 1.0) -> FastAPI:
    """Pass fakes for the speech, filter, model and service client in tests; by default they load lazily.
    `retry_interval` runs the outbox retry worker (PV-07); None turns it off (tests drive it by hand)."""
    settings = settings or Settings.from_env()
    store = CheckinStore(settings.db_path, settings.patient_ref)
    clients: list = [sentinel_client] if sentinel_client else []

    def get_client():
        if not clients:
            clients.append(egress_gate.make_client(settings))
        return clients[0]

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        init_db(settings.db_path, settings.patient_ref)
        if extractor is None:
            extract.ollama_host()  # fail fast: refuses a model server that is not on this device
        if redactor is None:
            await run_in_threadpool(pii_filter.warm_up)  # load spaCy now, not during the first answer
        if retry_interval:
            worker.start(retry_interval)  # PV-07: queued records and alerts go out by themselves once back online
        yield
        worker.stop()
        if clients and sentinel_client is None:
            clients[0].close()

    # The worker closes the client it gets after each pass, so it gets its own, never the shared one.
    worker = egress_gate.RetryWorker(settings.db_path, lambda: sentinel_client or egress_gate.make_client(settings),
                                     patient_ref=settings.patient_ref,
                                     state_path=settings.db_path.parent / "retry_state.json")
    app = FastAPI(title="Sentinel patient runtime", version=SCHEMA_VERSION, lifespan=lifespan)
    app.state.retry_worker = worker
    app.state.settings = settings
    app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins,
                       allow_methods=["GET", "POST", "PUT"], allow_headers=["Content-Type"])

    get_transcriber = (lambda: transcriber) if transcriber else stt.get_transcriber
    get_speaker = (lambda: speaker) if speaker else tts.get_speaker
    redact = redactor or pii_filter.redact
    extract_symptoms = extractor or extract.extract_symptoms
    rate_answer = rater or rating.rate_answer

    @app.get("/health")
    def health() -> dict:
        """Local checks only (no network): the database opens and holds this device's profile."""
        with closing(connect(settings.db_path)) as conn:
            meta = conn.execute("SELECT schema_version FROM schema_meta WHERE id = 1").fetchone()
            profile = conn.execute("SELECT 1 FROM patient_profile WHERE patient_ref = ?",
                                   (settings.patient_ref,)).fetchone()
        return {
            "status": "ok",
            "schema_version": meta["schema_version"] if meta else None,
            "patient_ref": settings.patient_ref,
            "profile_loaded": profile is not None,
        }

    # ---------- questions ----------

    def question_at(index: int, ask: int) -> dict:
        try:
            with closing(connect(settings.db_path)) as conn:
                _config_id, questions = latest_survey(conn, settings.patient_ref)
        except NoSurvey:
            raise HTTPException(503, "today's questions have not been downloaded yet")
        if index >= len(questions):
            raise HTTPException(404, "no more questions")
        q = questions[index]
        return {"index": index, "total": len(questions), "question_id": q["question_id"],
                "purpose": q["purpose"], "ask": ask, "text": q["asks"][ask]}

    @app.get("/checkin/question")
    def checkin_question(index: int = Query(0, ge=0), ask: int = Query(0, ge=0, le=2)) -> dict:
        """The question to show and speak (asks[0] first ask, asks[1] simpler, asks[2] choices; D-017)."""
        return question_at(index, ask)

    @app.get("/checkin/question/audio")
    def checkin_question_audio(index: int = Query(0, ge=0), ask: int = Query(0, ge=0, le=2),
                               slow: bool = False) -> Response:
        """The same question spoken by local text-to-speech (WAV). Never a cloud voice."""
        text = question_at(index, ask)["text"]
        try:
            wav = get_speaker().synthesize(text, slow=slow)
        except tts.TTSUnavailable:
            raise HTTPException(503, "text-to-speech unavailable")
        return Response(wav, media_type="audio/wav", headers={"Cache-Control": "no-store"})

    # ---------- check-in session ----------

    @app.post("/checkin/sessions", status_code=201)
    async def start_session() -> dict:
        """Refresh the survey and term list through the egress gate (offline keeps the cache), then start."""
        await run_in_threadpool(egress_gate.refresh_config, settings.db_path, settings.patient_ref,
                                client=get_client())
        try:
            session_id, total = await run_in_threadpool(store.start)
        except NoSurvey:
            raise HTTPException(503, "today's questions have not been downloaded yet; connect once and try again")
        return {"session_id": session_id, "total": total}

    @app.post("/checkin/turn")
    async def checkin_turn(request: Request, session_id: str = Query(..., pattern=SESSION_ID),
                           question_id: str = Query(..., pattern=QUESTION_ID),
                           ask: int = Query(0, ge=0, le=2)) -> dict:
        """One spoken answer: raw audio body from the local screen -> transcript and coded symptoms."""
        if not request.client or request.client.host not in LOOPBACK_CLIENTS:
            raise HTTPException(403, "audio is accepted from this device only")
        content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if not (content_type.startswith("audio/") or content_type in ("video/webm", "application/octet-stream")):
            raise HTTPException(415, "send the recording as audio")
        if int(request.headers.get("content-length") or 0) > stt.MAX_AUDIO_BYTES:
            raise HTTPException(413, "recording too large")
        _session_errors(store.check_open, session_id)
        question = _session_errors(store.question, session_id, question_id)
        audio = bytearray()
        async for chunk in request.stream():
            audio += chunk
            if len(audio) > stt.MAX_AUDIO_BYTES:
                raise HTTPException(413, "recording too large")
        if not audio:
            raise HTTPException(400, "no audio received")

        try:
            transcript = await run_in_threadpool(get_transcriber().transcribe, bytes(audio))
        except stt.ModelUnavailable:
            raise HTTPException(503, "speech model unavailable")
        except stt.TranscriptionError:
            raise HTTPException(422, "audio not understood")
        finally:
            audio.clear()  # PV-03: the recording is never written to disk and is dropped here

        command = commands.detect_command(transcript)  # VC-07: "repeat" / "slower" at any time; not an answer
        if command:
            return {"transcript": transcript, "symptoms": [], "extraction": "ok", "rating": None, "command": command,
                    "next": {"action": command, "ask": ask}}
        extraction, answer_text, found, rated = "ok", "", [], "no_answer"
        if transcript.strip():
            filtered = await run_in_threadpool(redact, transcript)  # PV-01: before any model sees anything
            r = await run_in_threadpool(rate_answer, question, ask, filtered.text)  # VC-04
            rated = r.rating
            # VC-06: from a rambling reply keep only the sentences that answer the question
            answer_text = r.relevant_text if rated == "rambling" else filtered.text
            if question["purpose"] in SYMPTOM_PURPOSES and rated not in ("off_topic", "no_answer") and answer_text:
                try:
                    found = await run_in_threadpool(extract_symptoms, answer_text)
                except extract.ExtractionError:
                    extraction, found = "unavailable", None
        accepted = await run_in_threadpool(_session_errors, store.record_turn, session_id, question_id, ask,
                                           transcript, answer_text, found, rated)
        labels = term_labels()
        symptoms = None if accepted is None else [
            {"term_code": s.term_code, "label": labels.get(s.term_code, s.term_code), "severity": s.severity,
             "onset": s.onset} for s in accepted]
        return {"transcript": transcript, "symptoms": symptoms, "extraction": extraction, "rating": rated,
                "next": store.next_step(question, ask, rated)}  # VC-05

    @app.get("/checkin/sessions/{session_id}/summary")
    def checkin_summary(session_id: str = Path(..., pattern=SESSION_ID)) -> dict:
        """What would be shared, in plain words and as the exact record. Sends nothing (PV-04)."""
        return _session_errors(store.summary, session_id, settings.sentinel_base_url)

    @app.get("/checkin/sessions/{session_id}/summary/audio")
    def checkin_summary_audio(session_id: str = Path(..., pattern=SESSION_ID), slow: bool = False) -> Response:
        """VC-08: the summary read back by local text-to-speech. Template text from coded fields, never model text."""
        text = _session_errors(store.summary, session_id, settings.sentinel_base_url)["spoken"]
        try:
            wav = get_speaker().synthesize(text, slow=slow)
        except tts.TTSUnavailable:
            raise HTTPException(503, "text-to-speech unavailable")
        return Response(wav, media_type="audio/wav", headers={"Cache-Control": "no-store"})

    @app.post("/checkin/sessions/{session_id}/correction")
    async def checkin_correction(request: Request, session_id: str = Path(..., pattern=SESSION_ID)) -> dict:
        """VC-08: one correction before sharing, tapped (JSON) or spoken (raw audio, like a turn)."""
        content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if content_type == "application/json":
            body = await request.json()
            if not isinstance(body, dict) or not isinstance(body.get("term_code"), str):
                raise HTTPException(422, "name the symptom to change")
            change = {"severity": body.get("severity"), "onset": body.get("onset"), "remove": bool(body.get("remove"))}
            term_code = body["term_code"]
        else:
            if not request.client or request.client.host not in LOOPBACK_CLIENTS:
                raise HTTPException(403, "audio is accepted from this device only")
            if not (content_type.startswith("audio/") or content_type in ("video/webm", "application/octet-stream")):
                raise HTTPException(415, "send the change as JSON or as audio")
            audio = await request.body()
            if not audio or len(audio) > stt.MAX_AUDIO_BYTES:
                raise HTTPException(413 if audio else 400, "recording too large" if audio else "no audio received")
            try:
                transcript = await run_in_threadpool(get_transcriber().transcribe, audio)
            except stt.ModelUnavailable:
                raise HTTPException(503, "speech model unavailable")
            except stt.TranscriptionError:
                raise HTTPException(422, "audio not understood")
            finally:
                audio = b""
            filtered = await run_in_threadpool(redact, transcript)
            items = _session_errors(store.correction_items, session_id)
            parsed = summary.parse_correction(filtered.text, items)
            if parsed is None:  # not understood: the one correction is not used up
                raise HTTPException(422, {"message": "I did not understand the change", "understood": False})
            term_code = parsed.term_code
            change = {"severity": parsed.severity, "onset": parsed.onset, "remove": parsed.remove}
        _session_errors(store.correct, session_id, term_code, **change)
        return _session_errors(store.summary, session_id, settings.sentinel_base_url)

    @app.post("/checkin/sessions/{session_id}/approve")
    def checkin_approve(session_id: str = Path(..., pattern=SESSION_ID),
                        severities: dict[str, str] = Body(default_factory=dict, embed=True)) -> dict:
        """The patient tapped "Share this": the only route that sends. Returns the egress receipt (PV-05)."""
        return _receipt(_session_errors(store.approve, session_id, severities, client=get_client()))

    @app.get("/checkin/sessions/{session_id}/receipt")
    def checkin_receipt(session_id: str = Path(..., pattern=SESSION_ID)) -> dict:
        """The receipt as it stands now: a queued record turns "sent" once the retry worker gets it through."""
        shared = _session_errors(store.receipts, session_id, settings.sentinel_base_url)
        if shared is None:
            raise HTTPException(404, "this check-in has not been shared")
        return _receipt(shared)

    # ---------- network log (PV-06) ----------

    @app.get("/network-log")
    def network_log(limit: int = Query(200, ge=1, le=1000)) -> dict:
        """Every request that reached the service, newest first: sends and configuration fetches (D-088)."""
        return {"entries": egress_gate.network_log(settings.db_path, limit=limit)}

    # ---------- consent switches (CN-01, CN-03) ----------

    @app.get("/consent")
    def consent_get() -> dict:
        """The two switches as they stand on this device, and the receipt of the latest consent update."""
        return consent.state(settings.db_path, settings.patient_ref, base_url=settings.sentinel_base_url)

    @app.put("/consent")
    def consent_put(share_care_team: bool | None = Body(None), share_caregiver: bool | None = Body(None)) -> dict:
        """The patient flipped a switch: saved on the device at once, then sent through the egress gate."""
        try:
            outbox_id = consent.change(settings.db_path, settings.patient_ref, share_care_team=share_care_team,
                                       share_caregiver=share_caregiver)
        except ValueError as e:  # includes NoRecipient; messages never carry patient content
            raise HTTPException(422, str(e))
        if outbox_id is not None:
            egress_gate.send_queued(settings.db_path, outbox_id, client=get_client())
        return consent.state(settings.db_path, settings.patient_ref, base_url=settings.sentinel_base_url)

    @app.put("/consent/setup")
    def consent_setup(choice: dict = Body(...)) -> dict:
        """The setup screen: care team, caregiver, emergency hospitals and contacts, saved and sent at once (CN-01).
        Contact labels stay on this device; the consent update sent through the egress gate never carries them."""
        try:
            outbox_id = consent.setup(settings.db_path, settings.patient_ref, choice)
        except ValueError as e:  # plain messages, never a phone number or label
            raise HTTPException(422, str(e))
        egress_gate.send_queued(settings.db_path, outbox_id, client=get_client())
        return consent.state(settings.db_path, settings.patient_ref, base_url=settings.sentinel_base_url)

    return app


def _receipt(shared) -> dict:
    record, alert, envelope = shared.record, shared.alert, shared.envelope
    return {"status": record.status, "record_id": record.outbox_id, "destination": DESTINATION_LABEL,
            "method": record.method, "url": record.url, "fields_sent": record.fields_sent,
            "payload_sha256": record.payload_sha256, "sent_at": record.sent_at, "response_code": record.response_code,
            "alert": None if alert is None else {"status": alert.status, "alert_id": alert.outbox_id,
                                                 "sent_at": alert.sent_at},
            "envelope": envelope, "envelopes": list(shared.envelopes)}


def _session_errors(fn, *args, **kwargs):
    """Map check-in errors to HTTP status codes (messages never carry patient content)."""
    try:
        return fn(*args, **kwargs)
    except UnknownSession:
        raise HTTPException(404, "unknown check-in")
    except AlreadyShared:
        raise HTTPException(409, "this check-in was already shared")
    except CorrectionUsed:
        raise HTTPException(409, "one change is allowed, and it was already made")
    except NeedsSeverity as e:
        raise HTTPException(409, {"message": "choose how bad each problem is before sharing",
                                  "needs_severity": e.term_codes})
    except (NoSurvey, NoTerms):
        raise HTTPException(503, "today's questions or term list have not been downloaded yet")
    except ContractError:
        raise HTTPException(422, "the record did not pass the contract check; nothing was sent")
    except UnknownQuestion:
        raise HTTPException(422, "unknown question for this check-in")
    except ValueError as e:
        raise HTTPException(422, str(e))


app = create_app()
