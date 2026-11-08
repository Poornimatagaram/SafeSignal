"""Check-in endpoints wired in main.py: session, turns, summary to approve, approve and send (PV-04, PV-05, PV-06).

Speech, filter, model and the Sentinel client are fakes here; the real ones have their own tests, and
test_egress_gate.py also runs against the local service.
"""

import json
from contextlib import closing
from types import SimpleNamespace

from fastapi.testclient import TestClient

from sentinel_contract import SCHEMA_DIR, payload_sha256
from sentinel_contract.client import SendResult, SendRetryable, field_names
from sentinel_patient import extract, stt, tts
from sentinel_patient.config import WALTER, Settings
from sentinel_patient.db import connect
from sentinel_patient.main import create_app

LOCAL = ("127.0.0.1", 50000)
WEBM = {"Content-Type": "audio/webm;codecs=opus"}
FAKE_WAV = b"RIFF\x24\x00\x00\x00WAVEfmt "
SURVEY = json.loads((SCHEMA_DIR / "examples" / "survey_config.valid.json").read_text())
TERMS = json.loads((SCHEMA_DIR / "terms.json").read_text())["terms"]


class FakeClient:
    """Shaped like SentinelClient: service-shaped config responses, records kept in `sent`."""

    def __init__(self, online=True):
        self.online, self.sent, self.fetches = online, [], 0

    def fetch_survey(self, cohort_id):
        self.fetches += 1
        if not self.online:
            raise SendRetryable("no network")
        return {"config_id": "cfg_cohort_b_v1", "cohort_id": cohort_id, "version": 1,
                "published_at": "2026-09-27T12:00:00Z", **SURVEY}

    def fetch_terms(self, program_id):
        if not self.online:
            raise SendRetryable("no network")
        return {"program_id": program_id, "drug_name": "Tagrisso",
                "terms": [{k: t[k] for k in ("term_code", "label_term", "everyday_words", "severe_trigger")}
                          | {"known_for_program": "Tagrisso" in t.get("drug_scope", [])} for t in TERMS]}

    def send_record(self, record):
        if not self.online:
            raise SendRetryable("no network")
        self.sent.append(record)
        digest = payload_sha256(record)
        return SendResult("POST", "http://127.0.0.1:8000/v1/records", 201, digest, field_names(record),
                          {"record_id": record["record_id"], "payload_sha256": digest})

    def close(self):
        pass


class EchoTranscriber:
    """The request body is the 'audio'; its text is the transcript."""

    def transcribe(self, audio: bytes) -> str:
        return audio.decode()


class FakeSpeaker:
    def __init__(self, error=None):
        self.error, self.calls = error, []

    def synthesize(self, text, *, slow=False):
        if self.error:
            raise self.error
        self.calls.append((text, slow))
        return FAKE_WAV


class FakePipeline:
    """Records what the model would see; 'codes' a few words so the flow has symptoms to carry."""

    def __init__(self, error=None):
        self.error, self.model_saw = error, []

    def redact(self, text):
        return SimpleNamespace(text=text.replace("Walter", "[NAME]"), entity_types=("NAME",))

    def extract(self, filtered_text):
        self.model_saw.append(filtered_text)
        if self.error:
            raise self.error
        found = []
        if "rash" in filtered_text:
            found.append(SimpleNamespace(term_code="SE_RASH", severity=None, onset="unknown"))
        if "tired" in filtered_text:
            found.append(SimpleNamespace(term_code="SE_FATIGUE", severity="mild", onset="today"))
        if "cough" in filtered_text or "started" in filtered_text:  # a model inventing symptoms, as llama3.2 does
            found.append(SimpleNamespace(term_code="SE_OTHER_REVIEW", severity=None, onset="unknown"))
        return found


def make_client(tmp_path, **kw):
    pipeline = kw.get("pipeline", FakePipeline())
    sentinel = kw.get("sentinel", FakeClient())
    app = create_app(Settings(db_path=tmp_path / "patient.db", patient_ref=WALTER),
                     transcriber=EchoTranscriber(), speaker=kw.get("speaker", FakeSpeaker()),
                     redactor=pipeline.redact, extractor=pipeline.extract, sentinel_client=sentinel)
    return TestClient(app, client=kw.get("client", LOCAL)), pipeline, sentinel


def start(c):
    r = c.post("/checkin/sessions")
    assert r.status_code == 201, r.text
    return r.json()["session_id"]


def answer(c, session_id, question_id, text, ask=0):
    return c.post("/checkin/turn", params={"session_id": session_id, "question_id": question_id, "ask": ask},
                  content=text.encode(), headers=WEBM)


ANSWERS = [("q1", "Not great, Walter here, I have been tired"), ("q2", "I have an itchy rash on my arms"),
           ("q3", "It's moderate"), ("q4", "It started two days ago"), ("q5", "Yes I took my tablets"),
           ("q6", "No, nothing new")]


def rows(tmp_path, sql, *args):
    with closing(connect(tmp_path / "patient.db")) as conn:
        return [dict(r) for r in conn.execute(sql, args)]


# ---------- questions and session start ----------

def test_no_questions_before_the_first_download(tmp_path):
    c, _, sentinel = make_client(tmp_path, sentinel=FakeClient(online=False))
    with c:
        assert c.get("/checkin/question").status_code == 503
        assert c.post("/checkin/sessions").status_code == 503
    assert sentinel.sent == []


def test_session_start_downloads_survey_and_terms_then_works_offline(tmp_path):
    sentinel = FakeClient()
    c, _, _ = make_client(tmp_path, sentinel=sentinel)
    with c:
        assert c.post("/checkin/sessions").json()["total"] == 6
        assert c.get("/checkin/question").json()["text"] == "How have you been feeling since yesterday?"
        sentinel.online = False  # cached survey keeps the check-in going (PV-07 groundwork)
        r = c.post("/checkin/sessions")
        assert r.status_code == 201 and r.json()["session_id"].startswith("ses_")
    assert len(rows(tmp_path, "SELECT * FROM term_cache")) == len(TERMS)


def test_question_bounds_and_audio(tmp_path):
    speaker = FakeSpeaker()
    c, _, _ = make_client(tmp_path, speaker=speaker)
    with c:
        start(c)
        assert c.get("/checkin/question", params={"index": 6}).status_code == 404
        assert c.get("/checkin/question", params={"ask": 3}).status_code == 422
        r = c.get("/checkin/question/audio", params={"index": 1, "slow": "true"})
    assert r.headers["content-type"] == "audio/wav" and r.content == FAKE_WAV
    assert speaker.calls == [("Have you noticed anything new on your skin or nails?", True)]


def test_question_audio_503_without_tts(tmp_path):
    c, _, _ = make_client(tmp_path, speaker=FakeSpeaker(error=tts.TTSUnavailable("no engine")))
    with c:
        start(c)
        assert c.get("/checkin/question/audio").status_code == 503


# ---------- turns ----------

def test_turn_filters_before_the_model_and_stores_the_answer_locally(tmp_path):
    c, pipeline, _ = make_client(tmp_path)
    with c:
        sid = start(c)
        r = answer(c, sid, "q1", "Walter here, I have an itchy rash")
    assert r.json() == {"transcript": "Walter here, I have an itchy rash",
                        "symptoms": [{"term_code": "SE_RASH", "label": "Rash", "severity": None, "onset": "unknown"}],
                        "extraction": "ok"}
    assert pipeline.model_saw == ["[NAME] here, I have an itchy rash"]
    turns = rows(tmp_path, "SELECT question_id, attempt, prompt_text, transcript_text FROM answer_turn")
    assert turns == [{"question_id": "q1", "attempt": 0, "prompt_text": "How have you been feeling since yesterday?",
                      "transcript_text": "Walter here, I have an itchy rash"}]


def test_turn_keeps_transcript_when_the_model_is_down(tmp_path):
    c, _, _ = make_client(tmp_path, pipeline=FakePipeline(error=extract.ExtractionUnavailable("down")))
    with c:
        body = answer(c, start(c), "q2", "a rash").json()
    assert body == {"transcript": "a rash", "symptoms": None, "extraction": "unavailable"}


def test_turn_rejects_bad_requests(tmp_path):
    c, _, _ = make_client(tmp_path)
    with c:
        sid = start(c)
        assert answer(c, sid, "q1", "").status_code == 400
        assert c.post("/checkin/turn", params={"session_id": sid, "question_id": "q1"}, content=b"x",
                      headers={"Content-Type": "text/plain"}).status_code == 415
        assert c.post("/checkin/turn", params={"session_id": sid, "question_id": "q1"},
                      content=b"x" * (stt.MAX_AUDIO_BYTES + 1), headers=WEBM).status_code == 413
        assert c.post("/checkin/turn", params={"question_id": "q1"}, content=b"x", headers=WEBM).status_code == 422
        assert answer(c, "ses_00000000", "q1", "hello").status_code == 404
        assert answer(c, sid, "q9", "hello").status_code == 422


def test_turn_accepts_audio_from_this_device_only(tmp_path):
    c, _, _ = make_client(tmp_path, client=("192.168.1.20", 50000))
    with c:
        sid = start(c)
        assert answer(c, sid, "q1", "hello").status_code == 403
    assert rows(tmp_path, "SELECT * FROM answer_turn") == []


# ---------- summary, approval, receipt ----------

def test_full_check_in_sends_nothing_until_approved_then_returns_a_matching_receipt(tmp_path):
    c, _, sentinel = make_client(tmp_path)
    with c:
        sid = start(c)
        for qid, text in ANSWERS:
            assert answer(c, sid, qid, text).status_code == 200
        summary = c.get(f"/checkin/sessions/{sid}/summary").json()
        assert sentinel.sent == []  # PV-04: a summary never sends
        receipt = c.post(f"/checkin/sessions/{sid}/approve", json={"severities": {}}).json()

    items = {i["term_code"]: (i["severity"], i["onset"], i["known_side_effect"]) for i in summary["items"]}
    assert items == {"SE_FATIGUE": ("mild", "today", True), "SE_RASH": ("moderate", "1_3_days", True)}
    assert summary["needs_severity"] == [] and summary["unanswered_questions"] == 0 and not summary["shared"]
    record = summary["share"]["record"]
    assert record["status"] == "completed" and record["patient_ref"] == WALTER
    assert summary["share"]["fields"] == field_names(record)

    assert sentinel.sent == [record]  # exactly what was shown is what was sent
    assert receipt["status"] == "sent" and receipt["response_code"] == 201 and receipt["record_id"] == record["record_id"]
    assert receipt["payload_sha256"] == payload_sha256(record) and receipt["fields_sent"] == field_names(record)
    assert receipt["sent_at"].endswith("Z") and receipt["url"].endswith("/v1/records")

    sent_json = json.dumps(sentinel.sent).lower()
    for local_only in ("walter", "1934-03-12", "555-0142", "itchy", "arms", "tablets"):
        assert local_only not in sent_json  # PV-08: coded fields and the random ID only
    assert [r["status"] for r in rows(tmp_path, "SELECT status FROM outbox")] == ["sent"]
    log = rows(tmp_path, "SELECT method, url, fields_sent, payload_sha256, response_code FROM egress_log")
    assert log == [{"method": "POST", "url": receipt["url"], "fields_sent": json.dumps(field_names(record)),
                    "payload_sha256": receipt["payload_sha256"], "response_code": 201}]
    assert len(rows(tmp_path, "SELECT * FROM symptom_event WHERE session_id = ?", sid)) == 2


def test_only_symptom_questions_add_symptoms_and_follow_ups_apply_to_the_latest_ones(tmp_path):
    c, pipeline, _ = make_client(tmp_path)
    with c:
        sid = start(c)
        answer(c, sid, "q1", "a rash")                       # wellbeing: rash, severity not said
        answer(c, sid, "q2", "I am tired")                   # symptom screen: fatigue (mild, today)
        answer(c, sid, "q3", "It's severe")                  # severity: refers to fatigue, which already has one
        onset = answer(c, sid, "q4", "It started two days ago").json()
        adherence = answer(c, sid, "q5", "Yes, and a cough").json()
        summary = c.get(f"/checkin/sessions/{sid}/summary").json()
    assert onset["symptoms"] == [] and adherence["symptoms"] == []  # nothing invented from follow-up answers
    assert pipeline.model_saw == ["a rash", "I am tired"]           # the model only runs for symptom questions
    items = {i["term_code"]: (i["severity"], i["onset"]) for i in summary["items"]}
    assert items == {"SE_RASH": (None, "unknown"), "SE_FATIGUE": ("mild", "today")}
    assert summary["needs_severity"] == ["SE_RASH"]  # never copied from an answer about another symptom


def test_missing_severity_is_chosen_by_the_patient_never_guessed(tmp_path):
    c, _, sentinel = make_client(tmp_path)
    with c:
        sid = start(c)
        answer(c, sid, "q2", "a rash on my arms")
        summary = c.get(f"/checkin/sessions/{sid}/summary").json()
        assert summary["needs_severity"] == ["SE_RASH"] and summary["share"]["record"] is None
        assert "symptoms[].severity" in summary["share"]["fields"]
        blocked = c.post(f"/checkin/sessions/{sid}/approve", json={"severities": {}})
        assert blocked.status_code == 409 and blocked.json()["detail"]["needs_severity"] == ["SE_RASH"]
        assert c.post(f"/checkin/sessions/{sid}/approve",
                      json={"severities": {"SE_RASH": "awful"}}).status_code == 422
        receipt = c.post(f"/checkin/sessions/{sid}/approve", json={"severities": {"SE_RASH": "mild"}}).json()
    assert receipt["status"] == "sent"
    assert sentinel.sent[0]["symptoms"][0]["severity"] == "mild" and sentinel.sent[0]["status"] == "partial"
    assert sentinel.sent[0]["unanswered_questions"] == 5


def test_approving_twice_never_sends_twice_and_answers_are_closed(tmp_path):
    c, _, sentinel = make_client(tmp_path)
    with c:
        sid = start(c)
        answer(c, sid, "q1", "fine thanks")
        first = c.post(f"/checkin/sessions/{sid}/approve", json={}).json()
        second = c.post(f"/checkin/sessions/{sid}/approve", json={}).json()
        assert answer(c, sid, "q2", "a rash").status_code == 409
        assert c.get(f"/checkin/sessions/{sid}/summary").json()["shared"] is True
    assert first == second and len(sentinel.sent) == 1
    assert sentinel.sent[0]["symptoms"] == []  # "no new problems" is still a record


def test_offline_approval_queues_and_a_later_approval_sends_the_same_payload(tmp_path):
    sentinel = FakeClient()
    c, _, _ = make_client(tmp_path, sentinel=sentinel)
    with c:
        sid = start(c)
        answer(c, sid, "q2", "I am tired")
        sentinel.online = False
        queued = c.post(f"/checkin/sessions/{sid}/approve", json={}).json()
        assert queued["status"] == "queued" and queued["sent_at"] is None and queued["response_code"] is None
        assert rows(tmp_path, "SELECT * FROM egress_log") == []  # nothing reached the service
        sentinel.online = True
        sent = c.post(f"/checkin/sessions/{sid}/approve", json={}).json()
    assert sent["status"] == "sent" and sent["record_id"] == queued["record_id"]
    assert sent["payload_sha256"] == queued["payload_sha256"] == payload_sha256(sentinel.sent[0])


def test_unknown_session_summary_and_approve(tmp_path):
    c, _, _ = make_client(tmp_path)
    with c:
        assert c.get("/checkin/sessions/ses_00000000/summary").status_code == 404
        assert c.post("/checkin/sessions/ses_00000000/approve", json={}).status_code == 404
        assert c.get("/checkin/sessions/not-a-session/summary").status_code == 422


def test_cors_preflight_from_patient_web(tmp_path):
    c, _, _ = make_client(tmp_path)
    with c:
        r = c.options("/checkin/sessions", headers={"Origin": "http://127.0.0.1:5173",
                                                    "Access-Control-Request-Method": "POST"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
