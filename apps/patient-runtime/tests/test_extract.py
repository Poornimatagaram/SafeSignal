"""Task A3: constrained extraction (PV-02, SE-01). Fake client for the rules; the real local Ollama when running."""

import ast
import json
import socket
from pathlib import Path

import ollama
import pytest

from sentinel_contract import SCHEMA_DIR, enums
from sentinel_patient import extract
from sentinel_patient.extract import (
    ExtractedSymptom,
    ExtractionError,
    ExtractionUnavailable,
    extract_symptoms,
)

PACKAGE = Path(__file__).resolve().parents[1] / "sentinel_patient"
TEXT = "I've had a mild rash on my arms since yesterday."


class FakeClient:
    """Records each chat call; returns `content` (or a dict dumped to JSON) or raises `error`."""

    def __init__(self, content=None, error=None):
        self.content, self.error, self.calls = content, error, []

    def chat(self, *, model, messages, format, options):
        self.calls.append({"model": model, "messages": messages, "format": format, "options": options})
        if self.error is not None:
            raise self.error
        content = self.content if isinstance(self.content, str) else json.dumps(self.content)
        return {"message": {"role": "assistant", "content": content}}


def item(code="SE_RASH", severity="mild", onset="1_3_days"):
    return {"term_code": code, "severity": severity, "onset": onset}


@pytest.fixture(autouse=True)
def default_env(monkeypatch):
    monkeypatch.delenv("PATIENT_OLLAMA_HOST", raising=False)
    monkeypatch.delenv("PATIENT_OLLAMA_MODEL", raising=False)


# --- What is sent to the model -----------------------------------------------------------------------------------
def test_sends_constrained_schema_temperature_zero_and_default_model():
    fake = FakeClient({"symptoms": [item()]})
    assert extract_symptoms(TEXT, client=fake) == [ExtractedSymptom("SE_RASH", "mild", "1_3_days")]
    [call] = fake.calls
    assert call["model"] == "llama3.2:3b"
    assert call["options"] == {"temperature": 0}
    assert call["format"] == {
        "type": "object",
        "properties": {"symptoms": {
            "type": "array",
            "maxItems": 10,
            "items": {
                "type": "object",
                "properties": {
                    "term_code": {"type": "string", "enum": enums()["term_code"]},
                    "severity": {"type": "string", "enum": ["mild", "moderate", "severe", "not_stated"]},
                    "onset": {"type": "string", "enum": enums()["onset"]},
                },
                "required": ["term_code", "severity", "onset"],
                "additionalProperties": False,
            },
        }},
        "required": ["symptoms"],
        "additionalProperties": False,
    }


def test_model_comes_from_env(monkeypatch):
    monkeypatch.setenv("PATIENT_OLLAMA_MODEL", "qwen2.5:3b")
    fake = FakeClient({"symptoms": []})
    extract_symptoms(TEXT, client=fake)
    assert fake.calls[0]["model"] == "qwen2.5:3b"


def test_prompt_lists_the_schema_terms_and_ends_with_the_filtered_text():
    fake = FakeClient({"symptoms": []})
    extract_symptoms("[NAME] says her baby has red skin since today.", client=fake)
    messages = fake.calls[0]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[-1] == {"role": "user", "content": "[NAME] says her baby has red skin since today."}
    system = messages[0]["content"]
    for term in json.loads((SCHEMA_DIR / "terms.json").read_text())["terms"]:
        assert term["term_code"] in system
        if term["term_code"] != "SE_OTHER_REVIEW":
            assert term["label_term"] in system
            assert all(word in system for word in term["everyday_words"])
    for code in enums()["term_code"]:
        assert code in system
    for example in messages[1:-1]:  # few-shot answers are valid against the schema's enums
        if example["role"] == "assistant":
            for s in json.loads(example["content"])["symptoms"]:
                assert s["term_code"] in enums()["term_code"] and s["onset"] in enums()["onset"]


@pytest.mark.parametrize("text", ["", "   ", "\n"])
def test_empty_text_returns_nothing_without_calling_the_model(text):
    fake = FakeClient({"symptoms": [item()]})
    assert extract_symptoms(text, client=fake) == []
    assert fake.calls == []


# --- Post-validation, regardless of the model --------------------------------------------------------------------
def run(symptoms, text=TEXT):
    return extract_symptoms(text, client=FakeClient({"symptoms": symptoms}))


def test_unknown_or_missing_term_code_becomes_other_review():
    got = run([item(code="SE_HEADACHE"), {"severity": "mild", "onset": "today"}])
    assert got == [ExtractedSymptom("SE_OTHER_REVIEW", "mild", "1_3_days")]  # deduped: both map to OTHER


@pytest.mark.parametrize("severity", ["not_stated", "high", "", None, 3, "SEVERE!"])
def test_unstated_or_invalid_severity_becomes_none(severity):
    assert run([item(severity=severity)])[0].severity is None


@pytest.mark.parametrize("onset", ["last_week", "", None, 7, "1-3 days"])
def test_invalid_onset_becomes_unknown(onset):
    assert run([item(onset=onset)])[0].onset == "unknown"


def test_values_are_normalised_for_case_and_whitespace():
    assert run([item(code=" se_cough ", severity=" Moderate", onset="TODAY ")]) == [
        ExtractedSymptom("SE_COUGH", "moderate", "today")]


def test_duplicates_dropped_first_wins_and_non_objects_skipped():
    got = run([item("SE_RASH", "mild", "today"), "SE_COUGH", None, item("SE_RASH", "severe", "4_7_days"),
               item("SE_COUGH", "moderate", "today")])
    assert got == [ExtractedSymptom("SE_RASH", "mild", "today"), ExtractedSymptom("SE_COUGH", "moderate", "today")]


def test_capped_at_ten_items():
    codes = enums()["term_code"]
    assert len(codes) > 10
    got = run([item(code=c) for c in codes])
    assert [s.term_code for s in got] == codes[:10]


def test_severity_without_any_severity_words_is_dropped():
    assert run([item(severity="severe")], text="I've had a rash on my arms since yesterday.")[0].severity is None
    assert run([item(severity="severe")], text="Rash, it's really bad, since yesterday.")[0].severity == "severe"


def test_onset_without_any_time_words_is_unknown():
    assert run([item(onset="4_7_days")], text="I have a mild rash on my arms.")[0].onset == "unknown"
    assert run([item(onset="4_7_days")], text="A mild rash since Monday.")[0].onset == "4_7_days"


# --- Errors ------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("content", ["not json", '{"symptoms": ', "[]", '{"items": []}', '{"symptoms": "rash"}',
                                     "null", ""])
def test_malformed_output_raises_extraction_error_without_content(content):
    secret = "Kowalski rash"
    with pytest.raises(ExtractionError) as err:
        extract_symptoms(secret, client=FakeClient(content.replace("rash", secret)))
    assert not isinstance(err.value, ExtractionUnavailable)
    assert "Kowalski" not in str(err.value) and "not json" not in str(err.value)
    assert err.value.__context__ is None and err.value.__cause__ is None  # no chained error carrying the text


@pytest.mark.parametrize("response", [{}, {"message": {}}, {"message": {"content": None}}, None, "text"])
def test_response_without_content_raises_extraction_error(response):
    class Odd(FakeClient):
        def chat(self, **kwargs):
            return response

    with pytest.raises(ExtractionError, match="no message content"):
        extract_symptoms(TEXT, client=Odd())


class TransportError(Exception):
    """Stands in for httpx.TransportError (tests must not need httpx either)."""


class ConnectTimeout(TransportError):
    pass


@pytest.mark.parametrize("error", [
    ConnectionError("Failed to connect to Ollama"),
    TimeoutError(),
    ConnectTimeout("timed out"),
    ollama.ResponseError("model 'llama3.2:3b' not found", 404),
])
def test_unreachable_or_missing_model_raises_unavailable_naming_host_and_model(error):
    with pytest.raises(ExtractionUnavailable) as err:
        extract_symptoms("My rash, Kowalski", client=FakeClient(error=error))
    message = str(err.value)
    assert "http://127.0.0.1:11434" in message and "llama3.2:3b" in message
    assert "Kowalski" not in message and "rash" not in message
    assert err.value.__context__ is None


@pytest.mark.parametrize("error", [ollama.ResponseError("Kowalski boom", 500), RuntimeError("Kowalski boom")])
def test_other_client_failures_raise_extraction_error_without_their_message(error):
    with pytest.raises(ExtractionError) as err:
        extract_symptoms(TEXT, client=FakeClient(error=error))
    assert not isinstance(err.value, ExtractionUnavailable)
    assert "Kowalski" not in str(err.value)
    assert err.value.__context__ is None


def test_real_client_on_a_closed_loopback_port_is_unavailable(monkeypatch):
    with socket.socket() as s:  # find a free port, then close it so nothing listens there
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    monkeypatch.setenv("PATIENT_OLLAMA_HOST", f"http://127.0.0.1:{port}")
    with pytest.raises(ExtractionUnavailable, match=f"127.0.0.1:{port}"):
        extract_symptoms(TEXT)


# --- Data never leaves the device --------------------------------------------------------------------------------
@pytest.mark.parametrize("host", [
    "http://127.0.0.1:11434", "127.0.0.1:11434", "127.0.0.1", "https://127.0.0.1:11434/", "localhost",
    "http://localhost:11434", "LOCALHOST:11434", "[::1]:11434", "http://[::1]:11434", "::1",
])
def test_accepts_loopback_hosts(monkeypatch, host):
    monkeypatch.setenv("PATIENT_OLLAMA_HOST", host)
    assert extract.ollama_host() == host
    fake = FakeClient({"symptoms": []})
    assert extract_symptoms(TEXT, client=fake) == []


@pytest.mark.parametrize("host", [
    "http://192.168.1.10:11434", "example.com", "http://ollama.example.com:11434", "http://localhost.example.com",
    "http://127.0.0.1@evil.example:11434", "http://evil.example#@127.0.0.1", "http://evil.example\\@127.0.0.1",
    "0.0.0.0:11434", "http://127.0.0.2:11434", "http://[::2]:11434", "ftp://127.0.0.1", ":11434",
    "http://127.0.0.1:port", "http://127.0.0.1%2F@evil.example", "http://local host",
])
def test_rejects_any_non_loopback_host_before_sending(monkeypatch, host):
    monkeypatch.setenv("PATIENT_OLLAMA_HOST", host)
    fake = FakeClient({"symptoms": [item()]})
    with pytest.raises(ValueError, match="loopback"):
        extract_symptoms(TEXT, client=fake)
    assert fake.calls == []


def test_default_client_ignores_proxies_and_redirects():
    client = extract._default_client("http://127.0.0.1:11434")
    http = client._client  # the httpx client inside ollama.Client
    assert http.trust_env is False
    assert http.follow_redirects is False
    assert http.base_url.host == "127.0.0.1"


def _imports(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found |= {f"{node.module}.{a.name}" for a in node.names}
    return found


def test_only_extract_imports_ollama():
    importers = {p.name for p in PACKAGE.rglob("*.py")
                 if any(m == "ollama" or m.startswith("ollama.") for m in _imports(p))}
    assert importers <= {"extract.py"}


@pytest.mark.parametrize("module", ["extract.py", "filter.py"])
def test_filter_and_extract_import_no_network_code(module):
    banned = ("httpx", "requests", "urllib", "urllib3", "http.client", "socket", "aiohttp", "huggingface_hub",
              "sentinel_contract.client")
    bad = {m for m in _imports(PACKAGE / module) for b in banned if m == b or m.startswith(b + ".")}
    assert bad == set()


# --- Real local model (skipped when Ollama or the model is not available) ---------------------------------------
def _real_model_available() -> bool:
    try:
        ollama.Client(host=extract.DEFAULT_HOST, timeout=3, trust_env=False).show(extract.DEFAULT_MODEL)
        return True
    except Exception:  # noqa: BLE001 - any failure means "not available here"
        return False


real_model = pytest.mark.skipif(not _real_model_available(),
                                 reason=f"Ollama with {extract.DEFAULT_MODEL} not running on {extract.DEFAULT_HOST}")


@real_model
@pytest.mark.parametrize("text, expected", [
    ("My baby has red spots on her tummy since yesterday, but no cough.", {"SE_RASH"}),
    ("[NAME] here for my mum. She has loose stools and a sore mouth since Monday, it's quite bad.",
     {"SE_DIARRHEA", "SE_STOMATITIS"}),
    ("I can't catch my breath when I walk up the stairs, it started this morning.", {"SE_DYSPNEA"}),
])
def test_real_model_codes_filtered_answers(text, expected):
    got = extract_symptoms(text)
    assert {s.term_code for s in got} == expected
    for s in got:
        assert s.severity in (None, *enums()["severity"]) and s.onset in enums()["onset"]


@real_model
def test_real_pipeline_redacts_then_extracts():
    from sentinel_patient.filter import redact

    filtered = redact("Hi, this is Walter Brennan from 42 Maple Street, call 555-0142. "
                      "I've been worn out with no energy since two days ago.")
    assert "Walter" not in filtered.text and "555-0142" not in filtered.text
    assert {s.term_code for s in extract_symptoms(filtered.text)} == {"SE_FATIGUE"}
