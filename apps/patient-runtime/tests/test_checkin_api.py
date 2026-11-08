"""Check-in endpoints wired in main.py: session, turns, summary to approve, approve and send (PV-04, PV-05, PV-06).

Speech, filter, model and the Sentinel client are fakes here; the real ones have their own tests, and
test_egress_gate.py also runs against the local service.
"""

import base64
import json
from contextlib import closing
from types import SimpleNamespace

from fastapi.testclient import TestClient
from nacl.public import PrivateKey, SealedBox

from sentinel_contract import SCHEMA_DIR, canonical, payload_sha256
from sentinel_contract.client import SendRejected, SendResult, SendRetryable, field_names
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
    """Shaped like SentinelClient: service-shaped config responses, records kept in `sent`.

    `org_key` is the care team's private key; None = its admin has not registered one yet (404, like the service).
    """

    def __init__(self, online=True, org_key=None):
        self.online, self.sent, self.alerts, self.fetches = online, [], [], 0
        self.org_key, self.envelopes, self.consents, self.calls = org_key, [], [], []

    def fetch_org_key(self, org_id):
        self.calls.append(("key", org_id))
        if not self.online:
            raise SendRetryable("no network")
        if self.org_key is None:
            raise SendRejected(404, {"error": "not_found"})
        return base64.b64encode(bytes(self.org_key.public_key)).decode()

    def send_envelope(self, envelope):
        if not self.online:
            raise SendRetryable("no network")
        self.calls.append(("envelope", envelope["envelope_id"]))
        self.envelopes.append(envelope)
        return SendResult("POST", "http://127.0.0.1:8000/v1/care-envelopes", 201, envelope["payload_sha256"],
                          field_names(envelope), {"envelope_id": envelope["envelope_id"],
                                                  "payload_sha256": envelope["payload_sha256"]})

    def send_consent(self, update):
        if not self.online:
            raise SendRetryable("no network")
        self.calls.append(("consent", update["share_care_team"], update["share_caregiver"]))
        self.consents.append(update)
        digest = payload_sha256(update)
        return SendResult("PUT", f"http://127.0.0.1:8000/v1/consent/{update['patient_ref']}", 200, digest,
                          field_names(update), {"patient_ref": update["patient_ref"]})

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

    def send_alert(self, alert):
        if not self.online:
            raise SendRetryable("no network")
        self.alerts.append(alert)
        self.calls.append(("alert", alert["alert_id"]))
        digest = payload_sha256(alert)
        return SendResult("POST", "http://127.0.0.1:8000/v1/alerts", 201, digest, field_names(alert),
                          {"alert_id": alert["alert_id"], "payload_sha256": digest})

    def send_record(self, record):
        if not self.online:
            raise SendRetryable("no network")
        self.sent.append(record)
        self.calls.append(("record", record["record_id"]))
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


def fake_rate(question, ask, text):
    """Stand-in for rating.rate_answer: 'um' = no answer, 'weather' = off topic, 'A | B' = rambling with B relevant."""
    if not text.strip() or text.strip(" .?") in ("um", "erm", "um erm"):
        return SimpleNamespace(rating="no_answer", relevant_text="", source="rules")
    if "|" in text:
        return SimpleNamespace(rating="rambling", relevant_text=text.split("|", 1)[1].strip(), source="rules")
    if "weather" in text:
        return SimpleNamespace(rating="off_topic", relevant_text="", source="rules")
    return SimpleNamespace(rating="complete", relevant_text=text, source="rules")


def make_client(tmp_path, **kw):
    pipeline = kw.get("pipeline", FakePipeline())
    sentinel = kw.get("sentinel", FakeClient())
    app = create_app(Settings(db_path=tmp_path / "patient.db", patient_ref=WALTER),
                     transcriber=EchoTranscriber(), speaker=kw.get("speaker", FakeSpeaker()),
                     redactor=pipeline.redact, extractor=pipeline.extract, rater=kw.get("rater", fake_rate),
                     sentinel_client=sentinel, retry_interval=None)
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
                        "extraction": "ok", "rating": "complete", "next": {"action": "next"}}
    assert pipeline.model_saw == ["[NAME] here, I have an itchy rash"]
    turns = rows(tmp_path, "SELECT question_id, attempt, prompt_text, transcript_text FROM answer_turn")
    assert turns == [{"question_id": "q1", "attempt": 0, "prompt_text": "How have you been feeling since yesterday?",
                      "transcript_text": "Walter here, I have an itchy rash"}]


def test_turn_keeps_transcript_when_the_model_is_down(tmp_path):
    c, _, _ = make_client(tmp_path, pipeline=FakePipeline(error=extract.ExtractionUnavailable("down")))
    with c:
        body = answer(c, start(c), "q2", "a rash").json()
    assert body == {"transcript": "a rash", "symptoms": None, "extraction": "unavailable", "rating": "complete",
                    "next": {"action": "next"}}


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


# ---------- rating and re-asking (VC-04 to VC-06) ----------

def test_unclear_answers_are_reasked_twice_then_given_up(tmp_path):
    c, pipeline, _ = make_client(tmp_path)
    with c:
        sid = start(c)
        first = answer(c, sid, "q2", "um").json()
        second = answer(c, sid, "q2", "erm", ask=1).json()
        third = answer(c, sid, "q2", "the weather is lovely", ask=2).json()
        summary = c.get(f"/checkin/sessions/{sid}/summary").json()
    assert (first["rating"], first["next"]) == ("no_answer", {"action": "reask", "ask": 1,
                                                              "text": "Any new rash, spots or nail changes?"})
    assert second["next"] == {"action": "reask", "ask": 2, "text": "Is it a rash, a nail problem, or nothing new?"}
    assert (third["rating"], third["next"]) == ("off_topic", {"action": "next", "unanswered": True})
    assert pipeline.model_saw == []  # nothing in those answers was worth extracting
    assert summary["unanswered_questions"] == 6 and summary["items"] == []
    assert [r["rating"] for r in rows(tmp_path, "SELECT rating FROM answer_turn ORDER BY turn_id")] == [
        "no_answer", "no_answer", "off_topic"]


def test_rambling_answer_keeps_only_the_part_that_answers(tmp_path):
    c, pipeline, _ = make_client(tmp_path)
    with c:
        sid = start(c)
        body = answer(c, sid, "q2", "Walter here, my grandson visited and we had cake | I have a rash").json()
        summary = c.get(f"/checkin/sessions/{sid}/summary").json()
    assert body["rating"] == "rambling" and body["next"] == {"action": "reask", "ask": 1,
                                                             "text": "Any new rash, spots or nail changes?"}
    assert pipeline.model_saw == ["I have a rash"]  # the model never saw the cake story
    assert [i["term_code"] for i in summary["items"]] == ["SE_RASH"]


def test_complete_answer_moves_on_and_a_reasked_complete_answer_counts(tmp_path):
    c, _, _ = make_client(tmp_path)
    with c:
        sid = start(c)
        assert answer(c, sid, "q1", "um").json()["next"]["action"] == "reask"
        done = answer(c, sid, "q1", "I feel fine", ask=1).json()
        summary = c.get(f"/checkin/sessions/{sid}/summary").json()
    assert (done["rating"], done["next"]) == ("complete", {"action": "next"})
    assert summary["unanswered_questions"] == 5


# ---------- voice commands, spoken summary and correction, severe alerts, offline retry (A6) ----------

def test_repeat_and_slower_are_commands_not_answers(tmp_path):
    c, pipeline, _ = make_client(tmp_path)
    with c:
        sid = start(c)
        again = answer(c, sid, "q2", "say that again", ask=1).json()
        slower = answer(c, sid, "q2", "slower please", ask=1).json()
    assert (again["command"], again["next"]) == ("repeat", {"action": "repeat", "ask": 1})
    assert (slower["command"], slower["next"]) == ("slower", {"action": "slower", "ask": 1})
    assert rows(tmp_path, "SELECT * FROM answer_turn") == [] and pipeline.model_saw == []


def test_summary_is_spoken_from_a_template_and_one_correction_is_allowed(tmp_path):
    speaker = FakeSpeaker()
    c, _, _ = make_client(tmp_path, speaker=speaker)
    with c:
        sid = start(c)
        answer(c, sid, "q2", "I am tired")
        first = c.get(f"/checkin/sessions/{sid}/summary").json()
        audio = c.get(f"/checkin/sessions/{sid}/summary/audio", params={"slow": "true"})
        fixed = c.post(f"/checkin/sessions/{sid}/correction", json={"term_code": "SE_FATIGUE", "severity": "moderate"})
        second = c.post(f"/checkin/sessions/{sid}/correction", json={"term_code": "SE_FATIGUE", "remove": True})
    assert first["correction_used"] is False and first["spoken"].startswith("Here is what I heard")
    assert audio.status_code == 200 and speaker.calls == [(first["spoken"], True)]
    assert fixed.status_code == 200 and fixed.json()["correction_used"] is True
    assert [(i["term_code"], i["severity"]) for i in fixed.json()["items"]] == [("SE_FATIGUE", "moderate")]
    assert second.status_code == 409


def test_spoken_correction_and_not_understood_does_not_use_it_up(tmp_path):
    c, _, _ = make_client(tmp_path)
    with c:
        sid = start(c)
        answer(c, sid, "q2", "I am tired")
        unclear = c.post(f"/checkin/sessions/{sid}/correction", content=b"hmm", headers=WEBM)
        spoken = c.post(f"/checkin/sessions/{sid}/correction", content=b"I'm not tired, I don't have that",
                        headers=WEBM)
    assert unclear.status_code == 422 and unclear.json()["detail"]["understood"] is False
    assert spoken.status_code == 200 and spoken.json()["items"] == [] and spoken.json()["correction_used"] is True


def test_severe_symptom_sends_a_minimal_alert_first_after_approval(tmp_path):
    c, _, sentinel = make_client(tmp_path)
    with c:
        sid = start(c)
        answer(c, sid, "q2", "I am tired")
        c.post(f"/checkin/sessions/{sid}/correction", json={"term_code": "SE_FATIGUE", "severity": "severe"})
        assert sentinel.alerts == []  # nothing before approval
        receipt = c.post(f"/checkin/sessions/{sid}/approve", json={}).json()
    assert receipt["alert"]["status"] == "sent" and len(sentinel.alerts) == 1 and len(sentinel.sent) == 1
    assert set(sentinel.alerts[0]) == {"schema_version", "alert_id", "patient_ref", "alert_type", "created_at"}
    assert sentinel.alerts[0]["alert_type"] == "severe"  # AL-03: no symptom details
    assert sorted(r["destination"] for r in rows(tmp_path, "SELECT destination FROM outbox")) == ["alert", "company_record"]


def test_severe_trigger_term_alerts_even_when_mild_and_no_alert_without_consent(tmp_path):
    class Breathless(FakePipeline):
        def extract(self, filtered_text):
            return [SimpleNamespace(term_code="SE_DYSPNEA", severity="mild", onset="today")]

    c, _, sentinel = make_client(tmp_path, pipeline=Breathless())
    with c:
        sid = start(c)
        answer(c, sid, "q2", "a bit out of breath")
        assert c.post(f"/checkin/sessions/{sid}/approve", json={}).json()["alert"]["status"] == "sent"
        with closing(connect(tmp_path / "patient.db")) as conn, conn:  # the patient withdraws all sharing
            conn.execute("INSERT INTO consent (share_care_team, emergency_consent, share_caregiver, caregiver_detail, "
                         "updated_at) VALUES (0, 0, 0, 'alerts_only', '2026-11-08T00:00:00Z')")
        sid2 = start(c)
        answer(c, sid2, "q2", "out of breath again")
        assert c.post(f"/checkin/sessions/{sid2}/approve", json={}).json()["alert"] is None
    assert len(sentinel.alerts) == 1


def test_offline_check_in_is_sent_by_the_retry_worker_when_back_online(tmp_path):
    sentinel = FakeClient()
    c, _, _ = make_client(tmp_path, sentinel=sentinel)
    with c:
        sid = start(c)
        sentinel.online = False  # network goes off mid check-in: everything keeps working locally
        answer(c, sid, "q2", "I am tired")
        queued = c.post(f"/checkin/sessions/{sid}/approve", json={}).json()
        assert queued["status"] == "queued" and c.get(f"/checkin/sessions/{sid}/receipt").json()["status"] == "queued"
        sentinel.online = True
        c.app.state.retry_worker.run_once()  # the background worker does this on its own every second
        now = c.get(f"/checkin/sessions/{sid}/receipt").json()
    assert now["status"] == "sent" and now["response_code"] == 201
    assert now["payload_sha256"] == queued["payload_sha256"] == payload_sha256(sentinel.sent[0])


# ---------- care envelope (NF-05) and consent switches (CN-01, CN-03) ----------

def check_in(c, answers=ANSWERS):
    sid = start(c)
    for qid, text in answers:
        assert answer(c, sid, qid, text).status_code == 200
    return sid


def opened(org_key, envelope):
    return json.loads(SealedBox(org_key).decrypt(base64.b64decode(envelope["ciphertext"])))


def test_approval_seals_the_doctor_copy_to_the_care_team_after_the_record(tmp_path):
    key = PrivateKey.generate()
    c, _, sentinel = make_client(tmp_path, sentinel=FakeClient(org_key=key))
    with c:
        sid = check_in(c)
        summary = c.get(f"/checkin/sessions/{sid}/summary").json()
        assert sentinel.envelopes == [] and ("key", "org_5e1a2b3c") not in sentinel.calls  # nothing before approval
        receipt = c.post(f"/checkin/sessions/{sid}/approve", json={}).json()
        later = c.get(f"/checkin/sessions/{sid}/receipt").json()

    care = summary["share"]["care"]
    assert care["org_id"] == "org_5e1a2b3c" and care["sealed"] and care["url"].endswith("/v1/care-envelopes")
    assert {"display_name", "checkin_date", "drug_name", "trend", "symptoms[].term_code"} <= set(care["fields"])

    [envelope] = sentinel.envelopes
    plain = opened(key, envelope)
    assert envelope["org_id"] == "org_5e1a2b3c" and envelope["patient_ref"] == WALTER
    assert plain["display_name"] == "Walter" and plain["drug_name"] == "Tagrisso" and plain["age_years"] == 92
    assert plain["trend"] == "unknown"  # first check-in on this device
    assert {s["term_code"]: s["severity"] for s in plain["symptoms"]} == {"SE_FATIGUE": "mild", "SE_RASH": "moderate"}
    assert set(plain) == {"schema_version", "patient_ref", "display_name", "drug_name", "drug_version",
                          "checkin_date", "status", "trend", "symptoms", "reporter", "age_years"}
    for local_only in ("1934-03-12", "555-0142", "itchy", "arms", "tablets"):
        assert local_only not in json.dumps(plain)  # coded fields only, even inside the seal
    assert "Walter" not in envelope["ciphertext"] and "Walter" not in json.dumps(sentinel.sent)

    # Hash over the plaintext: receipt, outbox and egress_log all show it (brief 26.13).
    digest = payload_sha256(plain)
    assert envelope["payload_sha256"] == digest == receipt["envelope"]["payload_sha256"]
    assert receipt["envelope"]["status"] == "sent" and receipt["envelope"]["destination"] == "care_envelope"
    assert receipt["envelope"]["envelope_id"] == envelope["envelope_id"] and later["envelope"]["status"] == "sent"
    assert rows(tmp_path, "SELECT payload_sha256 FROM egress_log WHERE outbox_id = ?", envelope["envelope_id"]) \
        == [{"payload_sha256": digest}]
    assert [k for k, *_ in sentinel.calls if k in ("record", "envelope")] == ["record", "envelope"]


def test_trend_compares_with_earlier_check_ins(tmp_path):
    key = PrivateKey.generate()
    c, _, sentinel = make_client(tmp_path, sentinel=FakeClient(org_key=key))
    with c:
        c.post(f"/checkin/sessions/{check_in(c)}/approve", json={})  # fatigue mild + rash moderate
        c.post(f"/checkin/sessions/{check_in(c, [('q2', 'nothing new')])}/approve", json={})  # no symptoms
    assert [opened(key, e)["trend"] for e in sentinel.envelopes] == ["unknown", "better"]


def test_envelope_waits_for_the_org_key_then_the_worker_seals_and_sends_it(tmp_path):
    sentinel = FakeClient()  # Northgate's admin has not registered a key yet
    c, _, _ = make_client(tmp_path, sentinel=sentinel)
    with c:
        sid = check_in(c)
        receipt = c.post(f"/checkin/sessions/{sid}/approve", json={}).json()
        assert receipt["status"] == "sent" and receipt["envelope"] == {"status": "waiting", "reason": "no_key"}
        assert rows(tmp_path, "SELECT * FROM outbox WHERE destination = 'care_envelope'") == []
        sentinel.org_key = key = PrivateKey.generate()
        c.app.state.retry_worker.run_once()
        now = c.get(f"/checkin/sessions/{sid}/receipt").json()
    assert now["envelope"]["status"] == "sent" and len(sentinel.envelopes) == 1
    assert opened(key, sentinel.envelopes[0])["display_name"] == "Walter"


def test_offline_envelope_is_sent_unchanged_when_back_online(tmp_path):
    key = PrivateKey.generate()
    sentinel = FakeClient(org_key=key)
    c, _, _ = make_client(tmp_path, sentinel=sentinel)
    with c:
        sid = check_in(c)
        sentinel.online = False
        assert c.post(f"/checkin/sessions/{sid}/approve", json={}).json()["envelope"] == \
            {"status": "waiting", "reason": "offline"}
        sentinel.online = True
        c.app.state.retry_worker.run_once()  # seals it now and queues it
        c.app.state.retry_worker.run_once()
        stored = rows(tmp_path, "SELECT payload FROM outbox WHERE destination = 'care_envelope'")
        now = c.get(f"/checkin/sessions/{sid}/receipt").json()
    assert now["envelope"]["status"] == "sent" and len(sentinel.envelopes) == 1
    assert canonical(sentinel.envelopes[0]).decode() == stored[0]["payload"]


def test_consent_switches_are_saved_at_once_and_sent_through_the_gate(tmp_path):
    c, _, sentinel = make_client(tmp_path, sentinel=FakeClient(org_key=PrivateKey.generate()))
    with c:
        state = c.get("/consent").json()
        assert state == {"share_care_team": True, "share_caregiver": True, "has_care_team": True,
                         "has_caregiver": True, "receipt": None}
        off = c.put("/consent", json={"share_care_team": False}).json()
        same = c.put("/consent", json={"share_care_team": False}).json()  # no change: nothing sent
        assert c.put("/consent", json={}).status_code == 422
    assert off["share_care_team"] is False and off["share_caregiver"] is True
    assert off["receipt"]["status"] == "sent" and off["receipt"]["method"] == "PUT"
    assert off["receipt"]["url"].endswith(f"/v1/consent/{WALTER}") and same["receipt"] == off["receipt"]
    [update] = sentinel.consents
    assert update["share_care_team"] is False and update["care_org_id"] == "org_5e1a2b3c"
    assert off["receipt"]["payload_sha256"] == payload_sha256(update)
    assert "Emergency services" not in json.dumps(update)  # contact labels stay on the device
    latest = rows(tmp_path, "SELECT share_care_team, share_caregiver FROM consent ORDER BY consent_id DESC LIMIT 1")
    assert latest == [{"share_care_team": 0, "share_caregiver": 1}]


def test_turning_the_doctor_off_stops_future_envelopes(tmp_path):
    key = PrivateKey.generate()
    c, _, sentinel = make_client(tmp_path, sentinel=FakeClient(org_key=key))
    with c:
        c.post(f"/checkin/sessions/{check_in(c)}/approve", json={})
        c.put("/consent", json={"share_care_team": False})
        sid = check_in(c)
        summary = c.get(f"/checkin/sessions/{sid}/summary").json()
        receipt = c.post(f"/checkin/sessions/{sid}/approve", json={}).json()
        c.app.state.retry_worker.run_once()
        c.put("/consent", json={"share_care_team": True})  # back on: only check-ins approved from now on
        c.app.state.retry_worker.run_once()
    assert summary["share"]["care"] is None and receipt["envelope"] is None
    assert summary["share"]["record"]["consent"]["care_team"] is False
    assert len(sentinel.envelopes) == 1  # only the check-in approved while sharing
    assert [k for k, *_ in sentinel.calls if k == "consent"] == ["consent", "consent"]


def test_consent_change_offline_takes_effect_now_and_is_sent_later(tmp_path):
    sentinel = FakeClient(org_key=PrivateKey.generate())
    c, _, _ = make_client(tmp_path, sentinel=sentinel)
    with c:
        start(c)  # download the survey once
        sentinel.online = False
        off = c.put("/consent", json={"share_caregiver": False}).json()
        assert off["share_caregiver"] is False and off["receipt"]["status"] == "queued"
        sentinel.online = True
        c.app.state.retry_worker.run_once()
        now = c.get("/consent").json()
    assert now["receipt"]["status"] == "sent" and sentinel.consents[0]["share_caregiver"] is False


def test_a_switch_cannot_be_turned_on_without_someone_to_share_with(tmp_path):
    c, _, sentinel = make_client(tmp_path)
    with c:
        c.put("/consent", json={"share_caregiver": False})
        with closing(connect(tmp_path / "patient.db")) as conn, conn:
            conn.execute("UPDATE patient_profile SET caregiver_id = NULL")
        assert c.get("/consent").json()["has_caregiver"] is False
        assert c.put("/consent", json={"share_caregiver": True}).status_code == 422
    assert len(sentinel.consents) == 1
