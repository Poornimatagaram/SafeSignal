"""Task A3: constrained extraction (PV-02, SE-01). Fake client for the rules; the real local Ollama when running."""

import ast
import datetime
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
    onset_in_text,
    severity_in_text,
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


def item(code="SE_RASH", severity="mild", onset="1_3_days", match="clear"):
    return {"term_code": code, "match": match, "severity": severity, "onset": onset}


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
                    "match": {"type": "string", "enum": ["clear", "unsure"]},
                    "severity": {"type": "string", "enum": ["mild", "moderate", "severe", "not_stated"]},
                    "onset": {"type": "string", "enum": enums()["onset"]},
                },
                "required": ["term_code", "match", "severity", "onset"],
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
                assert s["match"] in ("clear", "unsure")


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
    assert run([item(code=" se_cough ", severity=" Moderate", onset="TODAY ", match=" Clear")],
               text="A moderate cough since this morning.") == [ExtractedSymptom("SE_COUGH", "moderate", "today")]


def test_duplicates_dropped_first_wins_and_non_objects_skipped():
    got = run([item("SE_RASH", "mild", "today"), "SE_COUGH", None, item("SE_RASH", "severe", "4_7_days"),
               item("SE_COUGH", "moderate", "today")], text="A mild rash and a moderate cough since this morning.")
    assert got == [ExtractedSymptom("SE_RASH", "mild", "today"), ExtractedSymptom("SE_COUGH", "moderate", "today")]


def test_capped_at_ten_items():
    codes = enums()["term_code"]
    assert len(codes) > 10
    text = ("A mild rash, dry skin, sore nails, diarrhea, mouth ulcers, tired, off my food, a reaction at the "
            "infusion, out of breath, coughing and swollen ankles, all since yesterday.")
    got = run([item(code=c) for c in codes], text=text)
    assert [s.term_code for s in got] == codes[:10]


def test_severity_without_any_severity_words_is_dropped():
    assert run([item(severity="severe")], text="I've had a rash on my arms since yesterday.")[0].severity is None
    assert run([item(severity="severe")], text="Rash, it's really bad, since yesterday.")[0].severity == "severe"


def test_onset_without_any_time_words_is_unknown():
    assert run([item(onset="4_7_days")], text="I have a mild rash on my arms.")[0].onset == "unknown"
    assert run([item(onset="4_7_days")], text="A mild rash for about a week.")[0].onset == "4_7_days"
    # time words but no phrase the rules can date: the model's onset is kept
    assert run([item(onset="4_7_days")], text="A mild rash, it started recently.")[0].onset == "4_7_days"


# --- Unsure and grounding: no guessed term codes (rules override the model, Scoping Doc 17.1) -------------------
def codes(symptoms):
    return [s.term_code for s in symptoms]


def test_unsure_match_becomes_other_review_unless_the_terms_own_words_are_used():
    weak = "My skin itches a bit since yesterday."  # "itch" is a curated cue for SE_RASH, not one of its schema words
    assert run([item("SE_RASH", match="unsure")], text=weak) == [
        ExtractedSymptom("SE_OTHER_REVIEW", "mild", "1_3_days")]
    assert codes(run([item("SE_RASH", match="clear")], text=weak)) == ["SE_RASH"]
    # label_term or everyday_words from schema/terms.json: a dictionary match, not a guess
    assert codes(run([item("SE_RASH", match="unsure")], text=TEXT)) == ["SE_RASH"]
    assert codes(run([item("SE_DRY_SKIN", match="unsure")], text="Cracked skin on my heels.")) == ["SE_DRY_SKIN"]
    # a negated schema word does not count
    assert codes(run([item("SE_RASH", match="unsure")], text="No rash, but my skin itches a bit.")) == [
        "SE_OTHER_REVIEW"]


@pytest.mark.parametrize("match", [None, "", "maybe", 1])
def test_missing_or_odd_match_leaves_the_decision_to_grounding(match):
    symptom = item("SE_RASH")
    symptom["match"] = match
    assert codes(run([symptom])) == ["SE_RASH"]
    symptom["term_code"] = "SE_COUGH"  # no cough cue in TEXT
    assert codes(run([symptom])) == ["SE_OTHER_REVIEW"]


def test_chest_feels_tight_is_never_coded_as_cough():
    got = run([item("SE_COUGH", "not_stated", "1_3_days")], text="My chest feels tight since yesterday.")
    assert got == [ExtractedSymptom("SE_OTHER_REVIEW", None, "1_3_days")]


def test_ungrounded_codes_become_one_other_review_and_grounded_ones_stay():
    got = run([item("SE_DRY_SKIN", "not_stated", "unknown"), item("SE_PARONYCHIA", "not_stated", "unknown")],
              text="I have cracked skin on my heels.")
    assert codes(got) == ["SE_DRY_SKIN", "SE_OTHER_REVIEW"]
    got = run([item("SE_COUGH"), item("SE_DYSPNEA"), item("SE_OTHER_REVIEW")],
              text="Tight chest, a bit, since yesterday.")
    assert codes(got) == ["SE_OTHER_REVIEW"]  # three ungrounded or other items, deduplicated


@pytest.mark.parametrize("text, code", [
    ("My chest feels tight.", "SE_COUGH"),
    ("My chest feels tight.", "SE_DYSPNEA"),
    ("There's a pressure in my chest.", "SE_DYSPNEA"),
    ("My mouth is dry.", "SE_DRY_SKIN"),
    ("Dry eyes and a dry cough.", "SE_DRY_SKIN"),
    ("My stomach hurts.", "SE_STOMATITIS"),
    ("My throat is sore.", "SE_STOMATITIS"),
    ("He has a runny nose and a temperature.", "SE_DIARRHEA"),
    ("I have a headache and feel sick.", "SE_DIARRHEA"),
    ("Cracked skin on my fingers.", "SE_PARONYCHIA"),
    ("I keep seeing spots in my vision.", "SE_RASH"),
    ("I'm sick and tired of the tablets.", "SE_FATIGUE"),
    ("Swollen glands in my neck.", "SE_EDEMA"),
    ("My back hurts.", "SE_INFUSION_REACTION"),
])
def test_code_without_a_cue_in_the_text_becomes_other_review(text, code):
    assert codes(run([item(code)], text=text)) == ["SE_OTHER_REVIEW"]


@pytest.mark.parametrize("text, code", [
    ("I feel chesty.", "SE_COUGH"),
    ("He can't stop coughing.", "SE_COUGH"),
    ("My skin is itchy with red bumps.", "SE_RASH"),
    ("The baby has spots on his cheeks.", "SE_RASH"),
    ("My skin is peeling and flaky.", "SE_DRY_SKIN"),
    ("The skin around her fingernails is red.", "SE_PARONYCHIA"),
    ("I've had the runs since Monday.", "SE_DIARRHEA"),
    ("Her tummy has been running all day.", "SE_DIARRHEA"),
    ("Her mouth is full of little ulcers.", "SE_STOMATITIS"),
    ("I'm exhausted all the time.", "SE_FATIGUE"),
    ("I've never been so tired.", "SE_FATIGUE"),
    ("I don't have much energy.", "SE_FATIGUE"),
    ("I'm not really hungry.", "SE_DECREASED_APPETITE"),
    ("He won't eat anything.", "SE_DECREASED_APPETITE"),
    ("I got shivery during the infusion.", "SE_INFUSION_REACTION"),
    ("I can't catch my breath.", "SE_DYSPNEA"),
    ("I get breathless on the stairs.", "SE_DYSPNEA"),
    ("His legs get puffy in the evening.", "SE_EDEMA"),
    ("The rash has gone red.", "SE_RASH"),
    ("I'm not coughing as much.", "SE_COUGH"),
])
def test_code_with_a_cue_in_the_text_is_kept(text, code):
    assert codes(run([item(code)], text=text)) == [code]


def test_every_schema_word_grounds_its_own_term():
    for term in json.loads((SCHEMA_DIR / "terms.json").read_text())["terms"]:
        if term["term_code"] == "SE_OTHER_REVIEW":
            continue
        for phrase in [term["label_term"], *term["everyday_words"]]:
            got = run([item(term["term_code"])], text=f"Since yesterday: {phrase}.")
            assert codes(got) == [term["term_code"]], phrase


@pytest.mark.parametrize("text, code", [
    ("The diarrhea has stopped now.", "SE_DIARRHEA"),
    ("No rash today.", "SE_RASH"),
    ("No rash, no cough, I feel fine.", "SE_COUGH"),
    ("I haven't had any diarrhea.", "SE_DIARRHEA"),
    ("I'm not tired anymore.", "SE_FATIGUE"),
    ("The rash went away.", "SE_RASH"),
    ("I had a rash but it's gone now.", "SE_RASH"),
    ("The cough has cleared up.", "SE_COUGH"),
    ("Her mouth ulcers have healed.", "SE_STOMATITIS"),
])
def test_symptom_that_is_denied_or_has_stopped_is_dropped(text, code):
    assert run([item(code)], text=text) == []


def test_stopped_symptom_dropped_while_the_others_stay():
    got = run([item("SE_DIARRHEA"), item("SE_FATIGUE")], text="The diarrhea has stopped now, but I'm still tired.")
    assert codes(got) == ["SE_FATIGUE"]
    got = run([item("SE_RASH"), item("SE_STOMATITIS")], text="The rash went away but my mouth is sore.")
    assert codes(got) == ["SE_STOMATITIS"]


def test_other_review_is_never_dropped_by_the_guard():
    assert codes(run([item("SE_OTHER_REVIEW")], text="No headache now.")) == ["SE_OTHER_REVIEW"]


# --- Severity and onset agree with the plain words in the text --------------------------------------------------
SATURDAY = datetime.date(2026, 11, 7)  # demo day


@pytest.mark.parametrize("text, expected", [
    ("Mild.", "mild"), ("It's just a little.", "mild"), ("Not too bad.", "mild"), ("Slight.", "mild"),
    ("It isn't too bad.", "mild"), ("Not bad at all.", "mild"), ("Very mild.", "mild"), ("Slightly sore.", "mild"),
    ("A little bit.", "mild"), ("3 out of 10.", "mild"),
    ("Moderate.", "moderate"), ("Medium, I'd say.", "moderate"), ("Quite bad.", "moderate"),
    ("Fairly bad.", "moderate"), ("Pretty bad.", "moderate"), ("It's not mild, it's quite bad.", "moderate"),
    ("Severe.", "severe"), ("Really bad.", "severe"), ("Very bad.", "severe"), ("Terrible.", "severe"),
    ("It's awful.", "severe"), ("I can't do anything.", "severe"), ("8/10.", "severe"),
    ("Not mild, really bad.", "severe"),
    ("Not severe.", None), ("It's not severe.", None), ("I wouldn't say it's terrible.", None),
    ("Not that severe.", None), ("Severe? No.", None),
    ("Bad.", None), ("Mild or moderate.", None), ("Somewhere between mild and moderate.", None),
    ("A bit better.", None), ("Quite a bit.", None), ("Really itchy.", None), ("I don't know.", None),
    ("Yes.", None), ("", None), ("   ", None),
])
def test_severity_in_text(text, expected):
    assert severity_in_text(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("Today.", "today"), ("This morning.", "today"), ("Earlier today.", "today"), ("A few hours ago.", "today"),
    ("Yesterday.", "1_3_days"), ("Two days ago.", "1_3_days"), ("A couple of days.", "1_3_days"),
    ("In the last few days.", "1_3_days"), ("Last night.", "1_3_days"), ("A day or two.", "1_3_days"),
    ("Since Thursday.", "1_3_days"),
    ("Since Monday.", "4_7_days"), ("Last week.", "4_7_days"), ("About a week.", "4_7_days"),
    ("Five days.", "4_7_days"), ("More than 3 days.", "4_7_days"),
    ("Two weeks.", "over_7_days"), ("A month.", "over_7_days"), ("For weeks.", "over_7_days"),
    ("Much earlier.", "over_7_days"), ("Ages ago.", "over_7_days"), ("More than a week.", "over_7_days"),
    ("10 days.", "over_7_days"),
    ("Earlier.", None), ("Recently.", None), ("This week.", None), ("Several days.", None), ("Not long ago.", None),
    ("Three or four days.", None), ("Yesterday or maybe last week.", None), ("I don't know.", None), ("", None),
    ("It didn't start today, it was yesterday.", "1_3_days"),
    ("My 2 year old has had it since yesterday.", "1_3_days"),
])
def test_onset_in_text(text, expected):
    assert onset_in_text(text, today=SATURDAY) == expected


@pytest.mark.parametrize("today, expected", [
    (datetime.date(2026, 11, 2), "today"),        # Monday
    (datetime.date(2026, 11, 4), "1_3_days"),     # Wednesday
    (datetime.date(2026, 11, 7), "4_7_days"),     # Saturday
])
def test_onset_from_a_weekday_counts_back_from_today(today, expected):
    assert onset_in_text("Since Monday.", today=today) == expected
    assert onset_in_text("Since last Monday.", today=datetime.date(2026, 11, 2)) == "4_7_days"


def test_onset_in_text_defaults_to_the_local_date():
    assert onset_in_text("since yesterday") == "1_3_days"


@pytest.mark.parametrize("text, expected", [
    ("A rash, quite bad.", "moderate"), ("A rash, it's not too bad.", "mild"), ("A rash, really bad.", "severe")])
def test_extraction_severity_agrees_with_severity_in_text(text, expected):
    assert severity_in_text(text) == expected
    for model_says in ("mild", "moderate", "severe"):
        assert run([item(severity=model_says)], text=text)[0].severity == expected
    assert run([item(severity="not_stated")], text=text)[0].severity is None  # never filled in by the rules


def test_extraction_severity_negated_or_ambiguous_is_not_kept():
    assert run([item(severity="severe")], text="A rash, not severe.")[0].severity is None
    assert run([item(severity="mild")], text="A rash, it's bad.")[0].severity is None
    assert run([item(severity="severe")], text="A rash, it's bad.")[0].severity == "severe"  # bad: moderate or severe
    got = run([item("SE_RASH", "mild"), item("SE_COUGH", "severe")], text="A mild rash and a really bad cough.")
    assert [s.severity for s in got] == ["mild", "severe"]


@pytest.mark.parametrize("text, expected", [
    ("A rash for about a week.", "4_7_days"), ("A rash since two weeks ago.", "over_7_days"),
    ("A rash since this morning.", "today")])
def test_extraction_onset_agrees_with_onset_in_text(text, expected):
    assert onset_in_text(text) == expected
    for model_says in ("today", "1_3_days", "4_7_days", "over_7_days"):
        assert run([item(onset=model_says)], text=text)[0].onset == expected
    assert run([item(onset="unknown")], text=text)[0].onset == "unknown"  # never filled in by the rules


def test_helpers_never_call_a_model(monkeypatch):
    monkeypatch.setattr(extract, "_default_client", lambda host: pytest.fail("model called"))
    severity_in_text("really bad")
    onset_in_text("since yesterday")


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
@pytest.mark.parametrize("text", ["My chest feels tight since yesterday.", "my chest feels tight since yesterday"])
def test_real_model_codes_chest_tightness_as_other_review_never_cough(text):
    got = extract_symptoms(text)
    assert [s.term_code for s in got] == ["SE_OTHER_REVIEW"]
    assert got[0].onset == "1_3_days"


@real_model
@pytest.mark.parametrize("text, expected", [
    ("I have cracked skin on my heels.", {"SE_DRY_SKIN"}),
    ("The diarrhea has stopped now, but I'm still tired.", {"SE_FATIGUE"}),
])
def test_real_model_does_not_guess_or_keep_stopped_symptoms(text, expected):
    assert {s.term_code for s in extract_symptoms(text)} == expected


@real_model
def test_real_pipeline_redacts_then_extracts():
    from sentinel_patient.filter import redact

    filtered = redact("Hi, this is Walter Brennan from 42 Maple Street, call 555-0142. "
                      "I've been worn out with no energy since two days ago.")
    assert "Walter" not in filtered.text and "555-0142" not in filtered.text
    assert {s.term_code for s in extract_symptoms(filtered.text)} == {"SE_FATIGUE"}
