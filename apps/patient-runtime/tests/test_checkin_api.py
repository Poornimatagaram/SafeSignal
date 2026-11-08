"""Check-in endpoints wired in main.py, with fakes for speech, filter and model (the real ones have their own tests)."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from sentinel_patient import extract, stt, tts
from sentinel_patient.config import WALTER, Settings
from sentinel_patient.main import create_app

LOCAL = ("127.0.0.1", 50000)
WEBM = {"Content-Type": "audio/webm;codecs=opus"}
FAKE_WAV = b"RIFF\x24\x00\x00\x00WAVEfmt "


class FakeTranscriber:
    def __init__(self, text="My name is Walter and I have had a rash since two days ago", error=None):
        self.text, self.error, self.calls = text, error, 0

    def transcribe(self, audio: bytes) -> str:
        self.calls += 1
        if self.error:
            raise self.error
        return self.text


class FakeSpeaker:
    def __init__(self, error=None):
        self.error, self.calls = error, []

    def synthesize(self, text, *, slow=False):
        if self.error:
            raise self.error
        self.calls.append((text, slow))
        return FAKE_WAV


class FakePipeline:
    """Records what the model would see, so tests can prove the filter runs first."""

    def __init__(self, error=None):
        self.error, self.model_saw = error, []

    def redact(self, text):
        return SimpleNamespace(text=text.replace("Walter", "[NAME]"), entity_types=("NAME",))

    def extract(self, filtered_text):
        self.model_saw.append(filtered_text)
        if self.error:
            raise self.error
        return [SimpleNamespace(term_code="SE_RASH", severity=None, onset="1_3_days")]


def make_client(tmp_path, **fakes):
    pipeline = fakes.pop("pipeline", FakePipeline())
    app = create_app(Settings(db_path=tmp_path / "patient.db", patient_ref=WALTER),
                     transcriber=fakes.get("transcriber", FakeTranscriber()), speaker=fakes.get("speaker", FakeSpeaker()),
                     redactor=pipeline.redact, extractor=pipeline.extract)
    return TestClient(app, client=fakes.get("client", LOCAL)), pipeline


@pytest.fixture()
def c(tmp_path):
    client, _ = make_client(tmp_path)
    with client:
        yield client


def test_question_comes_from_the_example_survey_until_a4(c):
    assert c.get("/checkin/question").json() == {
        "index": 0, "total": 6, "question_id": "q1", "purpose": "wellbeing", "ask": 0,
        "text": "How have you been feeling since yesterday?"}
    assert c.get("/checkin/question", params={"index": 2, "ask": 1}).json()["text"] == "Is it mild, moderate or severe?"


def test_question_bounds(c):
    assert c.get("/checkin/question", params={"index": 6}).status_code == 404
    assert c.get("/checkin/question", params={"ask": 3}).status_code == 422
    assert c.get("/checkin/question", params={"index": -1}).status_code == 422


def test_question_audio_is_local_tts_wav(tmp_path):
    speaker = FakeSpeaker()
    client, _ = make_client(tmp_path, speaker=speaker)
    with client:
        r = client.get("/checkin/question/audio", params={"index": 1, "slow": "true"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav" and r.content == FAKE_WAV
    assert speaker.calls == [("Have you noticed anything new on your skin or nails?", True)]


def test_question_audio_503_without_tts(tmp_path):
    client, _ = make_client(tmp_path, speaker=FakeSpeaker(error=tts.TTSUnavailable("no engine")))
    with client:
        assert client.get("/checkin/question/audio").status_code == 503


def test_turn_returns_transcript_and_coded_symptoms_and_filters_before_the_model(tmp_path):
    client, pipeline = make_client(tmp_path)
    with client:
        r = client.post("/checkin/turn", params={"question_id": "q2"}, content=b"fake-opus", headers=WEBM)
    assert r.status_code == 200
    assert r.json() == {"transcript": "My name is Walter and I have had a rash since two days ago",
                        "symptoms": [{"term_code": "SE_RASH", "label": "Rash", "severity": None, "onset": "1_3_days"}],
                        "extraction": "ok"}
    assert pipeline.model_saw == ["My name is [NAME] and I have had a rash since two days ago"]


def test_turn_reports_extraction_unavailable_but_keeps_transcript(tmp_path):
    client, _ = make_client(tmp_path, pipeline=FakePipeline(error=extract.ExtractionUnavailable("model down")))
    with client:
        body = client.post("/checkin/turn", content=b"x", headers=WEBM).json()
    assert body["symptoms"] is None and body["extraction"] == "unavailable" and body["transcript"]


def test_turn_with_silence_skips_the_model(tmp_path):
    client, pipeline = make_client(tmp_path, transcriber=FakeTranscriber(text="  "))
    with client:
        body = client.post("/checkin/turn", content=b"x", headers=WEBM).json()
    assert body == {"transcript": "  ", "symptoms": [], "extraction": "ok"} and pipeline.model_saw == []


@pytest.mark.parametrize("error, status", [(stt.ModelUnavailable("not cached"), 503),
                                           (stt.TranscriptionError("bad audio"), 422)])
def test_turn_maps_speech_errors(tmp_path, error, status):
    client, _ = make_client(tmp_path, transcriber=FakeTranscriber(error=error))
    with client:
        assert client.post("/checkin/turn", content=b"x", headers=WEBM).status_code == status


def test_turn_rejects_bad_requests(c):
    assert c.post("/checkin/turn", content=b"", headers=WEBM).status_code == 400
    assert c.post("/checkin/turn", content=b"x", headers={"Content-Type": "text/plain"}).status_code == 415
    assert c.post("/checkin/turn", content=b"x" * (stt.MAX_AUDIO_BYTES + 1), headers=WEBM).status_code == 413
    assert c.post("/checkin/turn", params={"question_id": "Q 1!"}, content=b"x", headers=WEBM).status_code == 422


def test_turn_accepts_audio_from_this_device_only(tmp_path):
    transcriber = FakeTranscriber()
    client, _ = make_client(tmp_path, transcriber=transcriber, client=("192.168.1.20", 50000))
    with client:
        assert client.post("/checkin/turn", content=b"x", headers=WEBM).status_code == 403
    assert transcriber.calls == 0


def test_turn_cors_preflight_from_patient_web(c):
    r = c.options("/checkin/turn", headers={"Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": "POST",
                                            "Access-Control-Request-Headers": "content-type"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
