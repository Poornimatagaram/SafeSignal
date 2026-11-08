"""Task A5: answer rating and relevant-part extraction (VC-04, VC-06). Fake client for the rules and validation;
the real local Ollama when running. Probe texts are written here; never the held-out re-ask cases."""

import ast
import json
from pathlib import Path

import ollama
import pytest
from sentinel_contract import enums

from sentinel_patient import extract, rating
from sentinel_patient.rating import RATINGS, Rating, rate_answer, split_sentences

PACKAGE = Path(__file__).resolve().parents[1] / "sentinel_patient"

QUESTIONS = {
    "wellbeing": {"question_id": "q1", "purpose": "wellbeing",
                  "asks": ["How have you been feeling since yesterday?",
                           "Have you felt any different in your body since yesterday?",
                           "Did you feel unwell yesterday, yes or no?"]},
    "symptom_screen": {"question_id": "q2", "purpose": "symptom_screen",
                       "asks": ["Have you noticed anything new on your skin or nails?",
                                "Any new rash, spots or nail changes?",
                                "Is it a rash, a nail problem, or nothing new?"]},
    "severity": {"question_id": "q3", "purpose": "severity",
                 "asks": ["How bad is it?", "Is it mild, moderate or severe?",
                          "Is it bad enough to stop you doing things, yes or no?"]},
    "onset": {"question_id": "q4", "purpose": "onset",
              "asks": ["When did it start?", "Did it start today, in the last few days, or earlier?",
                       "Did it start this week, yes or no?"]},
    "adherence": {"question_id": "q5", "purpose": "adherence",
                  "asks": ["Did you take your medicine today?", "Have you had your tablets or treatment today?",
                           "Yes or no?"]},
    "exposure": {"question_id": "q6", "purpose": "exposure",
                 "asks": ["Anything new you started using, eating or doing?",
                          "Any new soap, cream, food or activity?", "Yes or no?"]},
}

RAMBLE_SCREEN = ("Well, my brother came over on Sunday and we fixed the fence at the back. It took the whole "
                 "afternoon because the posts were rotten. Then we had fish and chips and watched a film. "
                 "My fingernails have gone all split at the edges. He's coming back next week to paint it.")
RAMBLE_SCREEN_ANSWER = "My fingernails have gone all split at the edges."


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


class NoCallClient:
    def chat(self, **_):
        raise AssertionError("the model must not be called when the rules decide")


def model_says(rating_value, indices=()):
    return FakeClient({"rating": rating_value, "relevant_sentences": list(indices)})


# --- Interface ------------------------------------------------------------------------------------------------
def test_ratings_match_schema_enum():
    assert RATINGS == tuple(enums()["answer_rating"])


def test_rating_is_frozen():
    r = Rating("complete", "x", "rules")
    with pytest.raises(AttributeError):
        r.rating = "partial"


def test_split_sentences_returns_exact_substrings():
    text = "First one. Second one?  Third!\nFourth line"
    got = split_sentences(text)
    assert got == ["First one.", "Second one?", "Third!", "Fourth line"]
    assert all(s in text for s in got)


def test_split_sentences_splits_long_unpunctuated_runs_at_commas():
    text = ", ".join(["we went to the shops and bought some bread and milk"] * 4)
    got = split_sentences(text)
    assert len(got) == 4 and all(s in text for s in got)


# --- Rules: no answer --------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text", ["", "   ", "...", "?", "Um.", "Hmm, uh...", "I don't know.", "Dunno",
                                  "Pardon?", "What?", "Sorry, what?", "Can you repeat that please?",
                                  "Didn't catch that.", "I'm not sure.", "No idea, sorry."])
def test_no_answer_rules(text):
    assert rate_answer(QUESTIONS["severity"], 0, text, client=NoCallClient()) == Rating("no_answer", "", "rules")


# --- Rules: per purpose (table) ------------------------------------------------------------------------------
@pytest.mark.parametrize("purpose, ask, text, expected", [
    ("severity", 0, "Pretty bad, honestly.", "complete"),
    ("severity", 0, "Just a little.", "complete"),
    ("severity", 1, "Severe.", "complete"),
    ("severity", 0, "About seven out of ten.", "complete"),
    ("severity", 2, "Yes, I had to stay in bed.", "complete"),
    ("severity", 2, "No.", "complete"),
    ("severity", 1, "Sort of.", "partial"),
    ("onset", 0, "Since Tuesday.", "complete"),
    ("onset", 0, "Two weeks ago.", "complete"),
    ("onset", 1, "Earlier.", "complete"),
    ("onset", 2, "Yeah.", "complete"),
    ("onset", 2, "Maybe.", "partial"),
    ("adherence", 0, "Yes I did.", "complete"),
    ("adherence", 0, "Nope.", "complete"),
    ("adherence", 0, "I forgot to take them.", "complete"),
    ("adherence", 1, "I think so.", "partial"),
    ("adherence", 2, "Yep.", "complete"),
    ("symptom_screen", 0, "No.", "complete"),
    ("symptom_screen", 0, "Nothing new.", "complete"),
    ("symptom_screen", 0, "Yes.", "partial"),
    ("symptom_screen", 1, "My skin is peeling on my hands.", "complete"),
    ("symptom_screen", 2, "A nail problem.", "complete"),
    ("symptom_screen", 2, "A rash.", "complete"),
    ("exposure", 0, "No, nothing new.", "complete"),
    ("exposure", 0, "Yes.", "partial"),
    ("exposure", 2, "Yes.", "complete"),
    ("wellbeing", 0, "Not too bad, thanks.", "complete"),
    ("wellbeing", 0, "Pretty tired.", "complete"),
    ("wellbeing", 2, "No.", "complete"),
])
def test_rules_decide_by_purpose_without_the_model(purpose, ask, text, expected):
    got = rate_answer(QUESTIONS[purpose], ask, text, client=NoCallClient())
    assert (got.rating, got.source) == (expected, "rules")
    assert got.relevant_text and got.relevant_text in text


@pytest.mark.parametrize("model_rating", ["off_topic", "partial", "no_answer", "rambling"])
def test_rules_override_the_model(model_rating):
    client = model_says(model_rating, [0])
    got = rate_answer(QUESTIONS["severity"], 0, "Quite bad really.", client=client)
    assert got == Rating("complete", "Quite bad really.", "rules")
    assert client.calls == []


def test_rambling_rule_keeps_only_the_answer_sentence():
    got = rate_answer(QUESTIONS["symptom_screen"], 0, RAMBLE_SCREEN, client=NoCallClient())
    assert got == Rating("rambling", RAMBLE_SCREEN_ANSWER, "rules")


@pytest.mark.parametrize("purpose, text, answer", [
    ("severity", ("The bus was late so I missed my appointment and had to rebook it for next month. The lady at "
                 "the desk was very kind about it though. The pain in my mouth is really bad. I also need new "
                 "glasses at some point this year."), "The pain in my mouth is really bad."),
    ("onset", ("We have been redecorating the spare room and choosing paint took forever. My wife wanted green "
              "and I wanted blue. It started on Saturday morning. We ended up with grey in the end, of all "
              "things."), "It started on Saturday morning."),
    ("adherence", ("The chemist only had half my prescription so I need to go back on Friday, and the queue was "
                  "out the door. Yes, I took it with my breakfast. The car park there is a nightmare as "
                  "well, I had to park two streets away."), "Yes, I took it with my breakfast."),
])
def test_rambling_rule_by_purpose(purpose, text, answer):
    got = rate_answer(QUESTIONS[purpose], 0, text, client=NoCallClient())
    assert got == Rating("rambling", answer, "rules")


def test_long_answer_that_stays_on_topic_is_complete():
    text = ("I have a rash on both arms. The rash is red and itchy. There are spots on my chest too. "
            "My nails are cracking at the tips. The skin on my hands is dry and peeling as well.")
    got = rate_answer(QUESTIONS["symptom_screen"], 0, text, client=NoCallClient())
    assert got == Rating("complete", text, "rules")


# --- Model: each rating, validated -------------------------------------------------------------------------------
def test_model_call_is_constrained_and_deterministic():
    client = model_says("off_topic")
    rate_answer(QUESTIONS["onset"], 0, "My cat is called Biscuit. She is ginger.", client=client)
    (call,) = client.calls
    assert call["options"] == {"temperature": 0}
    assert call["format"] == rating.output_schema()
    assert call["format"]["properties"]["rating"]["enum"] == list(RATINGS)
    assert call["model"] == extract.ollama_model()
    last = call["messages"][-1]["content"]
    assert "When did it start?" in last and "0: My cat is called Biscuit." in last and "1: She is ginger." in last


@pytest.mark.parametrize("model_rating, indices, expected, relevant", [
    ("complete", [0], "complete", "I bought a new body wash."),
    ("partial", [0], "partial", "I bought a new body wash."),
    ("off_topic", [0], "off_topic", ""),
    ("no_answer", [], "off_topic", ""),  # real words are never "no answer"; the rules own no_answer
    ("rambling", [0], "complete", "I bought a new body wash."),  # a short answer cannot ramble
    ("rambling", [], "off_topic", ""),  # rambling with no answer in it
])
def test_model_ratings_short_answer(model_rating, indices, expected, relevant):
    text = "I bought a new body wash. It smells of lemons."
    got = rate_answer(QUESTIONS["exposure"], 1, text, client=model_says(model_rating, indices))
    assert got == Rating(expected, relevant, "model")


LONG_UNRULED = ("My nephew is getting married in June and the whole family is going. The venue is an old barn "
                "out in the countryside with a big lawn. I have started using a different hand soap since last "
                "week. We still need to buy a present and find somewhere to stay nearby. My sister is doing the "
                "flowers.")


def test_model_rambling_long_answer_quotes_only_input_sentences():
    got = rate_answer(QUESTIONS["wellbeing"], 0, LONG_UNRULED, client=model_says("rambling", [2]))
    assert got == Rating("rambling", "I have started using a different hand soap since last week.", "model")


def test_model_complete_on_long_answer_with_a_subset_is_rambling():
    got = rate_answer(QUESTIONS["wellbeing"], 0, LONG_UNRULED, client=model_says("complete", [2]))
    assert got.rating == "rambling" and got.source == "model"


def test_model_complete_without_indices_keeps_the_whole_short_answer():
    got = rate_answer(QUESTIONS["exposure"], 0, "Some new hair dye.", client=model_says("complete", []))
    assert got == Rating("complete", "Some new hair dye.", "model")


def test_bad_indices_are_dropped_and_model_text_never_used():
    sentences = ["I got a new pillow.", "It is very soft.", "Blue too."]
    text = " ".join(sentences)
    client = FakeClient({"rating": "partial", "relevant_sentences": [1, -1, 3, 99, "0", 1.0, True, None, 1],
                         "relevant_text": "INVENTED BY MODEL"})
    got = rate_answer(QUESTIONS["exposure"], 1, text, client=client)
    assert got == Rating("partial", "It is very soft.", "model")
    assert "INVENTED" not in got.relevant_text


def test_relevant_text_is_always_made_of_input_sentences():
    for indices in ([0, 1], [1, 0], [0, 0, 0], [2]):
        got = rate_answer(QUESTIONS["wellbeing"], 0, LONG_UNRULED, client=model_says("rambling", indices))
        parts = split_sentences(got.relevant_text)
        assert parts and all(p in split_sentences(LONG_UNRULED) for p in parts)


# --- Model problems: rules fall back, never raise ------------------------------------------------------------
@pytest.mark.parametrize("client", [
    FakeClient(error=ConnectionError("down")),
    FakeClient(error=ollama.ResponseError("model not found", 404)),
    FakeClient(error=RuntimeError("boom")),
    FakeClient("not json"),
    FakeClient({"rating": "excellent", "relevant_sentences": []}),
    FakeClient({"relevant_sentences": [0]}),
    FakeClient([1, 2]),
])
def test_model_problems_fall_back_to_rules(client):
    got = rate_answer(QUESTIONS["exposure"], 0, "I bought a new body wash.", client=client)
    assert got.source == "rules_fallback"
    assert got.rating == "partial" and got.relevant_text == "I bought a new body wash."


def test_fallback_long_off_topic_is_off_topic():
    text = ("My nephew is getting married in June and the whole family is going. The venue is an old barn out in "
            "the countryside with a big lawn. We still need to buy a present and find somewhere to stay nearby. "
            "My sister is doing the flowers.")
    got = rate_answer(QUESTIONS["onset"], 0, text, client=FakeClient(error=ConnectionError()))
    assert got == Rating("off_topic", "", "rules_fallback")


def test_fallback_keeps_symptom_sentences_as_partial():
    got = rate_answer(QUESTIONS["severity"], 0, "The rash is on my elbows.", client=FakeClient(error=OSError()))
    assert got == Rating("partial", "The rash is on my elbows.", "rules_fallback")


def test_non_loopback_host_falls_back_without_calling(monkeypatch):
    monkeypatch.setenv("PATIENT_OLLAMA_HOST", "http://example.com:11434")
    client = model_says("complete", [0])
    got = rate_answer(QUESTIONS["exposure"], 0, "I bought a new body wash.", client=client)
    assert got.source == "rules_fallback" and client.calls == []


@pytest.mark.parametrize("question, ask", [({}, 0), ({"purpose": "severity"}, 5), ({"asks": "x"}, -1),
                                           (QUESTIONS["onset"], 7)])
def test_odd_question_or_ask_never_raises(question, ask):
    got = rate_answer(question, ask, "Something happened.", client=FakeClient(error=ConnectionError()))
    assert got.rating in RATINGS


# --- Privacy guards ----------------------------------------------------------------------------------------------
def _tree():
    return ast.parse((PACKAGE / "rating.py").read_text())


def test_rating_never_prints_or_logs():
    names = set()
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Call):
            func = node.func
            names.add(func.id if isinstance(func, ast.Name) else getattr(func, "attr", ""))
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            assert not any(m.split(".")[0] in ("logging", "warnings") for m in mods)
    assert not names & {"print", "debug", "info", "warning", "error", "exception", "log"}


def test_rating_imports_no_network_code():
    banned = ("httpx", "requests", "urllib", "urllib3", "http", "socket", "aiohttp", "huggingface_hub",
              "sentinel_contract.client", "ollama")
    mods = set()
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add(node.module or "")
    assert not {m for m in mods for b in banned if m == b or m.startswith(b + ".")}


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
def test_real_model_rambling_keeps_the_answer():
    text = ("Honestly it has been such a busy week. My granddaughter had her school play on Tuesday and she was "
            "a tree, bless her. We went for pizza after and it was far too loud in there. I've been coughing a "
            "lot since the weekend. Then on Thursday the boiler broke and the engineer couldn't come till Monday.")
    got = rate_answer(QUESTIONS["wellbeing"], 0, text)
    assert got.rating == "rambling"
    assert "coughing" in got.relevant_text and "boiler" not in got.relevant_text


@real_model
def test_real_model_off_topic():
    got = rate_answer(QUESTIONS["onset"], 0, "I'm planning to repaint the kitchen yellow.")
    assert got == Rating("off_topic", "", "model")


@real_model
def test_real_model_complete():
    got = rate_answer(QUESTIONS["exposure"], 0, "We had sushi for the first time on Friday.")
    assert got.rating == "complete" and got.source == "model"
    assert got.relevant_text == "We had sushi for the first time on Friday."
