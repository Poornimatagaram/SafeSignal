"""Patient runtime API on localhost:8001. Only patient-web (localhost:5173) calls it.

Run: uv run uvicorn sentinel_patient.main:app --port 8001   (uvicorn binds 127.0.0.1 by default; keep it that way)

Logs carry method, path and status only, never request bodies, audio, transcripts or patient words (26.12).
This module makes no outbound calls: every outbound byte goes through egress_gate.

Check-in turn: audio (in memory only) -> stt -> transcript -> filter (identifiers removed) -> extract (local model,
coded fields only). The model never sees the raw transcript; the transcript goes back only to the local screen.
"""

from __future__ import annotations

from contextlib import asynccontextmanager, closing
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from sentinel_contract import SCHEMA_VERSION

from . import extract, stt, tts
from . import filter as pii_filter
from .config import Settings
from .db import connect, init_db
from .survey import current_questions, term_labels

LOOPBACK_CLIENTS = {"127.0.0.1", "::1", "localhost"}
QUESTION_ID = r"^[a-z0-9_]{1,32}$"


def create_app(settings: Settings | None = None, *, transcriber: stt.Transcriber | None = None,
               speaker: tts.Speaker | None = None, redactor: Callable[[str], Any] | None = None,
               extractor: Callable[[str], list] | None = None) -> FastAPI:
    """Pass fakes for the speech, filter and model parts in tests; by default they load lazily on first use."""
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        init_db(settings.db_path, settings.patient_ref)
        if extractor is None:
            extract.ollama_host()  # fail fast: refuses a model server that is not on this device
        if redactor is None:
            await run_in_threadpool(pii_filter.warm_up)  # load spaCy now, not during the first answer
        yield

    app = FastAPI(title="Sentinel patient runtime", version=SCHEMA_VERSION, lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins,
                       allow_methods=["GET", "POST", "PUT"], allow_headers=["Content-Type"])

    get_transcriber = (lambda: transcriber) if transcriber else stt.get_transcriber
    get_speaker = (lambda: speaker) if speaker else tts.get_speaker
    redact = redactor or pii_filter.redact
    extract_symptoms = extractor or extract.extract_symptoms

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

    def question_at(index: int, ask: int) -> dict:
        questions, _source = current_questions(settings.db_path, settings.patient_ref)
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

    @app.post("/checkin/turn")
    async def checkin_turn(request: Request, question_id: str | None = Query(None, pattern=QUESTION_ID),
                           ask: int = Query(0, ge=0, le=2)) -> dict:
        """One spoken answer: raw audio body from the local screen -> transcript and coded symptoms."""
        if not request.client or request.client.host not in LOOPBACK_CLIENTS:
            raise HTTPException(403, "audio is accepted from this device only")
        content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if not (content_type.startswith("audio/") or content_type in ("video/webm", "application/octet-stream")):
            raise HTTPException(415, "send the recording as audio")
        if int(request.headers.get("content-length") or 0) > stt.MAX_AUDIO_BYTES:
            raise HTTPException(413, "recording too large")
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

        symptoms: list[dict] | None = []
        extraction = "ok"
        if transcript.strip():
            try:
                filtered = await run_in_threadpool(redact, transcript)  # PV-01: before the model sees anything
                found = await run_in_threadpool(extract_symptoms, filtered.text)
                labels = term_labels()
                symptoms = [{"term_code": s.term_code, "label": labels.get(s.term_code, s.term_code),
                             "severity": s.severity, "onset": s.onset} for s in found]
            except extract.ExtractionError:
                symptoms, extraction = None, "unavailable"
        return {"transcript": transcript, "symptoms": symptoms, "extraction": extraction}

    return app


app = create_app()
