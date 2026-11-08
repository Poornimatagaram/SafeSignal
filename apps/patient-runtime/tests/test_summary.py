"""VC-08: spoken summary (template only) and one spoken correction (rule-based)."""

import ast
import re
from pathlib import Path

import pytest

from sentinel_patient import summary
from sentinel_patient.summary import Correction, parse_correction, spoken_summary

PACKAGE = Path(__file__).resolve().parents[1] / "sentinel_patient"
END = "If something is wrong, you can change one answer. Otherwise, tap Share this."


def item(code, label, severity=None, onset="unknown", known=True):
    return {"term_code": code, "label": label, "severity": severity, "onset": onset, "known_side_effect": known}


RASH = item("SE_RASH", "Rash", "moderate", "1_3_days")
FATIGUE = item("SE_FATIGUE", "Fatigue", "mild", "unknown")
DIARRHEA = item("SE_DIARRHEA", "Diarrhea", None, "today", known=False)
OTHER = item("SE_OTHER_REVIEW", "Other, needs review", "mild", "4_7_days", known=False)


# --- Template ----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("items, unanswered, expected", [
    ([], 0, f"Here is what I heard. You did not report any new problems. {END}"),
    ([], 2, f"Here is what I heard. You did not report any new problems. Two questions were not answered. {END}"),
    ([RASH], 0, f"Here is what I heard. Rash, moderate, started 1 to 3 days ago. {END}"),
    ([RASH, FATIGUE], 1, "Here is what I heard. Rash, moderate, started 1 to 3 days ago. Fatigue, mild, start not "
                         f"known. One question was not answered. {END}"),
    ([DIARRHEA], 0, f"Here is what I heard. Diarrhea, how bad is not said yet, started today. {END}"),
    ([OTHER], 0, "Here is what I heard. Something else, for your care team to review, mild, started 4 to 7 days "
                 f"ago. {END}"),
    ([item("SE_DRY_SKIN", "Dry skin", "severe", "over_7_days")], 13,
     f"Here is what I heard. Dry skin, severe, started more than a week ago. 13 questions were not answered. {END}"),
])
def test_template(items, unanswered, expected):
    assert spoken_summary(items, unanswered) == expected


@pytest.mark.parametrize("unanswered, phrase", [(0, None), (1, "One question was not answered."),
                                                (2, "Two questions were not answered.")])
def test_unanswered(unanswered, phrase):
    text = spoken_summary([RASH], unanswered)
    if phrase is None:
        assert "not answered" not in text
    else:
        assert phrase in text


def test_no_causal_words_and_short_sentences():
    text = spoken_summary([RASH, FATIGUE, DIARRHEA, OTHER], 2)
    assert not re.search(r"caus|because|due to|side effect|reaction to|from the|drug|medicine|linked", text, re.I)
    assert all(len(s.split()) <= 16 for s in text.split(". "))


def test_no_model_or_network_in_modules():
    for name in ("summary.py", "commands.py"):
        tree = ast.parse((PACKAGE / name).read_text())
        imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        imported |= {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert not imported & {"ollama", "httpx", "requests", "urllib", "socket", "logging", "sentinel_contract"}
        assert "print(" not in (PACKAGE / name).read_text()
        assert "extract_symptoms" not in (PACKAGE / name).read_text()


# --- Corrections -------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text, items, expected", [
    # severity
    ("The rash is quite bad actually.", [RASH, FATIGUE], Correction("SE_RASH", severity="moderate")),
    ("No, the tiredness is really bad.", [RASH, FATIGUE], Correction("SE_FATIGUE", severity="severe")),
    ("It's only a little bit.", [RASH], Correction("SE_RASH", severity="mild")),
    ("the diarrhoea is about 8 out of 10", [RASH, DIARRHEA], Correction("SE_DIARRHEA", severity="severe")),
    # onset
    ("The rash started yesterday.", [RASH, FATIGUE], Correction("SE_RASH", onset="1_3_days")),
    ("I've been tired for two weeks.", [RASH, FATIGUE], Correction("SE_FATIGUE", onset="over_7_days")),
    ("It began this morning.", [FATIGUE], Correction("SE_FATIGUE", onset="today")),
    ("I don't know when the rash started.", [RASH, FATIGUE], Correction("SE_RASH", onset="unknown")),
    # remove
    ("That's wrong, no rash.", [RASH, FATIGUE], Correction("SE_RASH", remove=True)),
    ("I don't have a rash.", [RASH, FATIGUE], Correction("SE_RASH", remove=True)),
    ("The rash has gone.", [RASH, FATIGUE], Correction("SE_RASH", remove=True)),
    ("I don't have that.", [FATIGUE], Correction("SE_FATIGUE", remove=True)),
    ("Take it off please.", [RASH], Correction("SE_RASH", remove=True)),
    # SE_OTHER_REVIEW by how the summary names it
    ("Something else was really bad.", [RASH, OTHER], Correction("SE_OTHER_REVIEW", severity="severe")),
])
def test_correction(text, items, expected):
    assert parse_correction(text, items) == expected


@pytest.mark.parametrize("text, items", [
    ("It's quite bad.", [RASH, FATIGUE]),                          # which one?
    ("The rash and the tiredness are mild.", [RASH, FATIGUE]),     # two items
    ("The rash is mild and started yesterday.", [RASH, FATIGUE]),  # two changes
    ("No rash, it's mild.", [RASH]),                               # remove and a severity
    ("The rash is bad.", [RASH]),                                  # moderate or severe: never guess
    ("That's wrong.", [RASH]),                                     # wrong how?
    ("I have a cough as well.", [RASH]),                           # a new symptom is not a correction
    ("The cough is mild.", [RASH]),
    ("The rash is not severe.", [RASH]),                           # negated level: unclear
    ("I don't have it that bad.", [RASH]),                         # not a denial, no clear level
    ("I'm not sure when, maybe yesterday.", [RASH]),               # unsure onset
    ("Everything is fine.", [RASH]),                               # nothing understood
    ("", [RASH]),
    ("The rash is mild.", []),
])
def test_correction_unclear(text, items):
    assert parse_correction(text, items) is None


def test_correction_single_item_shortcut_needs_no_name():
    assert parse_correction("It's severe.", [DIARRHEA]) == Correction("SE_DIARRHEA", severity="severe")
    assert parse_correction("It's severe.", [DIARRHEA, RASH]) is None


def test_onset_words_match_checkin():
    from sentinel_patient.checkin import ONSET_WORDS
    assert summary.ONSET_SPOKEN == ONSET_WORDS
