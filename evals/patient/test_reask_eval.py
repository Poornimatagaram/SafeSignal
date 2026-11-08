"""Tests for the VC-04 answer-rating harness (scoring and run logic with a fake rater, no model) and its dataset.

Run from the repository root:
    uv run --project apps/patient-runtime pytest -q evals/patient
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import reask_eval as rv  # noqa: E402

REPO_ROOT = HERE.parents[1]
DATA_PATH = REPO_ROOT / "data" / "patient" / "reask_cases.json"
ENUMS = json.loads((REPO_ROOT / "schema" / "enums.json").read_text(encoding="utf-8"))
SURVEY = json.loads((REPO_ROOT / "schema" / "examples" / "survey_config.valid.json").read_text(encoding="utf-8"))
QUESTIONS = {q["question_id"]: q for q in SURVEY["questions"]}
DATA = json.loads(DATA_PATH.read_text(encoding="utf-8"))
CASES = DATA["cases"]


# ------------------------------------------------------------------------------------------- fakes


@dataclass(frozen=True)
class FakeRedaction:
    text: str
    entity_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class FakeRating:
    rating: str
    relevant_text: str | None
    source: str


def identity(text):
    return FakeRedaction(text)


def oracle(cases, wrong=(), relevant=None):
    """A rater that returns each case's expected rating (except ids in `wrong`) and its relevant phrases."""
    by_answer = {c["answer"]: c for c in cases}

    def rate(question, ask, text):
        case = by_answer[text]
        assert question["question_id"] == case["question_id"] and ask == case["ask"]
        rating = case["expected_rating"]
        if case["id"] in wrong:
            rating = "complete" if rating != "complete" else "partial"
        rel = relevant(case) if relevant else " ... ".join(case["expected_relevant"])
        return FakeRating(rating, rel, "rule" if len(text) < 40 else "model")

    return rate


def write_data(tmp_path, cases):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"schema_version": "2.0", "source": "test", "cases": cases}))
    return path


def run(tmp_path, cases, rate, redact=identity):
    out = tmp_path / "results.json"
    code = rv.main(["--data", str(write_data(tmp_path, cases)), "--out", str(out)], rv.Runtime(redact, rate))
    return code, (json.loads(out.read_text()) if out.exists() else None)


# ------------------------------------------------------------------------------------------- scoring


def test_ratings_come_from_the_enum():
    assert rv.ratings() == tuple(ENUMS["answer_rating"])
    assert rv.safe_rating("rambling") == "rambling"
    assert rv.safe_rating("he talked about his grandson") == rv.INVALID
    assert rv.safe_rating(None) == rv.INVALID


def test_safe_source_only_passes_short_tokens():
    assert rv.safe_source("model") == "model"
    assert rv.safe_source("rule_short") == "rule_short"
    assert rv.safe_source("I took my medicine") == rv.OTHER_SOURCE
    assert rv.safe_source(None) == rv.OTHER_SOURCE


def test_phrase_matching_ignores_case_spacing_and_apostrophes():
    assert rv.phrase_in("Yes, I  TOOK my\nmedicine", "i took my medicine")
    assert rv.phrase_in("I couldn’t do up my buttons", "couldn't do up my buttons")
    assert not rv.phrase_in(None, "x")
    assert not rv.phrase_in("", "x")


def test_extraction_check():
    ok = rv.extraction_check("a rash on my arms and my nails are cracked", ["a rash on my arms", "nails"], ["football"])
    assert ok == {"relevant_kept": 2, "relevant_expected": 2, "off_topic_kept": 0, "off_topic_listed": 1,
                  "pass": True}
    assert not rv.extraction_check("a rash on my arms", ["a rash on my arms", "nails"], [])["pass"]
    assert not rv.extraction_check("a rash, and the football", ["a rash"], ["football"])["pass"]
    assert not rv.extraction_check(None, ["a rash"], [])["pass"]


# ------------------------------------------------------------------------------------------- run logic


def test_perfect_rater_passes(tmp_path, capsys):
    code, report = run(tmp_path, CASES, oracle(CASES))
    assert code == rv.EXIT_PASS
    t = report["totals"]
    assert report["pass"] is True
    assert t["ratings_correct"] == 20 and t["rating_accuracy"] == 1.0
    assert t["rambling_extraction"] == {"cases": 5, "pass": 5}
    assert sum(t["source_mix"].values()) == 20 and set(t["source_mix"]) == {"rule", "model"}
    for exp, row in t["confusion"].items():
        assert row[exp] == t["per_rating"][exp]["cases"] and sum(row.values()) == row[exp]
    assert "VC-04: PASS" in capsys.readouterr().out


@pytest.mark.parametrize(("n_wrong", "code"), [(4, rv.EXIT_PASS), (5, rv.EXIT_FAIL)])
def test_threshold_is_16_of_20(tmp_path, n_wrong, code):
    wrong = {c["id"] for c in CASES[:n_wrong]}
    got, report = run(tmp_path, CASES, oracle(CASES, wrong=wrong))
    assert got == code
    assert report["totals"]["ratings_correct"] == 20 - n_wrong
    assert sum(not c["rating_pass"] for c in report["cases"]) == n_wrong


def test_extraction_failure_is_reported_but_does_not_fail(tmp_path):
    code, report = run(tmp_path, CASES, oracle(CASES, relevant=lambda c: c["answer"]))  # keeps everything
    assert code == rv.EXIT_PASS
    assert report["totals"]["rambling_extraction"] == {"cases": 5, "pass": 0}
    for c in report["cases"]:
        if c["expected"] == "rambling":
            assert c["extraction"]["relevant_kept"] == c["extraction"]["relevant_expected"]
            assert c["extraction"]["off_topic_kept"] == c["extraction"]["off_topic_listed"] > 0
        else:
            assert "extraction" not in c


def test_answer_is_redacted_before_rating(tmp_path):
    seen = []

    def rate(question, ask, text):
        seen.append(text)
        return FakeRating("complete", text, "rule")

    run(tmp_path, CASES[:3], rate, redact=lambda t: FakeRedaction("[FILTERED]"))
    assert seen == ["[FILTERED]"] * 3


def test_invalid_rating_and_errors_count_as_wrong(tmp_path):
    def rate(question, ask, text):
        if ask == 0:
            raise RuntimeError(text)  # the message holds patient words: must never be written
        return FakeRating(text, text, text)  # free text in every field

    code, report = run(tmp_path, CASES, rate)
    assert code == rv.EXIT_FAIL
    got = Counter(c["got"] for c in report["cases"])
    assert set(got) <= {rv.INVALID, rv.ERROR}
    assert got[rv.ERROR] == report["totals"]["errors"] == sum(c["ask"] == 0 for c in CASES)
    assert {c["status"] for c in report["cases"] if c["got"] == rv.ERROR} == {"error:RuntimeError"}
    assert set(report["totals"]["source_mix"]) == {rv.OTHER_SOURCE}


def test_runtime_not_importable_exits_2(tmp_path, monkeypatch):
    def not_ready():
        raise rv.RuntimeNotReady("ImportError: cannot import name 'rate_answer'")

    monkeypatch.setattr(rv, "load_runtime", not_ready)
    out = tmp_path / "results.json"
    assert rv.main(["--data", str(write_data(tmp_path, CASES)), "--out", str(out)]) == rv.EXIT_UNAVAILABLE
    assert not out.exists()


def test_results_and_stdout_never_contain_answer_text(tmp_path, capsys):
    def rate(question, ask, text):  # echoes the answer everywhere it can
        return FakeRating("rambling", text, "model")

    out = tmp_path / "results.json"
    rv.main(["--data", str(DATA_PATH), "--out", str(out)], rv.Runtime(identity, rate))
    written, printed = out.read_text(), capsys.readouterr().out
    report = json.loads(written)
    assert report["dataset"] == "data/patient/reask_cases.json"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", report["run_at_utc"])
    for case in CASES:
        phrases = [*case["expected_relevant"], *case.get("expected_not_relevant", [])]
        phrases += [s for s in re.split(r"(?<=[.?!])\s+|\.\.\.\s*", case["answer"]) if len(s) > 8]
        for phrase in phrases:
            if len(phrase) > 3:  # skip "Yes"
                assert phrase.casefold() not in written.casefold(), case["id"]
                assert phrase.casefold() not in printed.casefold(), case["id"]
        for name in re.findall(r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)+\b", case["answer"]):
            assert name not in written and name not in printed, case["id"]


# ------------------------------------------------------------------------------------------- dataset


def test_dataset_shape():
    assert DATA["schema_version"] == "2.0"
    assert "no real people" in DATA["source"]
    assert len(CASES) == rv.VC04_CASES == 20
    ids = [c["id"] for c in CASES]
    assert len(set(ids)) == len(ids)
    allowed = {"id", "question_id", "ask", "style", "answer", "expected_rating", "expected_relevant",
               "expected_not_relevant"}
    for case in CASES:
        assert re.fullmatch(r"rq_\d{2}", case["id"])
        assert allowed - {"expected_not_relevant"} <= set(case) <= allowed, case["id"]
        assert isinstance(case["answer"], str)


def test_labels_are_valid():
    for case in CASES:
        assert case["question_id"] in QUESTIONS, case["id"]
        assert case["ask"] in (0, 1, 2) and case["ask"] < len(QUESTIONS[case["question_id"]]["asks"]), case["id"]
        assert case["expected_rating"] in ENUMS["answer_rating"], case["id"]
        assert case["style"] in ("plain", "slow"), case["id"]


def test_phrases_appear_in_the_answer():
    for case in CASES:
        for phrase in [*case["expected_relevant"], *case.get("expected_not_relevant", [])]:
            assert phrase and rv.phrase_in(case["answer"], phrase), (case["id"], phrase)
        for keep in case["expected_relevant"]:
            for drop in case.get("expected_not_relevant", []):
                assert not rv.phrase_in(keep, drop) and not rv.phrase_in(drop, keep), case["id"]


def test_coverage():
    ratings = Counter(c["expected_rating"] for c in CASES)
    assert set(ratings) == set(ENUMS["answer_rating"])
    assert min(ratings.values()) >= 3, ratings
    assert {QUESTIONS[c["question_id"]]["purpose"] for c in CASES} == set(ENUMS["question_purpose"])
    assert {c["ask"] for c in CASES} == {0, 1, 2}
    assert sum(c["style"] == "slow" for c in CASES) >= 4  # Walter-style slow, halting speech
    rambling = [c for c in CASES if c["expected_rating"] == "rambling"]
    assert len(rambling) >= 4
    for case in rambling:
        assert case["expected_relevant"] and case["expected_not_relevant"], case["id"]
        assert len(case["answer"]) > 150, case["id"]


def test_relevant_labels_match_rating():
    for case in CASES:
        if case["expected_rating"] in ("off_topic", "no_answer"):
            assert case["expected_relevant"] == [], case["id"]
        else:
            assert case["expected_relevant"], case["id"]
        if case["expected_rating"] != "rambling":
            assert "expected_not_relevant" not in case, case["id"]
    assert any(c["answer"] == "" for c in CASES), "a silent answer"
