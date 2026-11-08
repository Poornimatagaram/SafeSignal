"""Tests for the PV-01 leakage harness (scoring, run logic with fakes, no model) and its dataset.

Run from the repository root:
    uv run --project apps/patient-runtime pytest -q evals/patient
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import leakage_eval as le  # noqa: E402

REPO_ROOT = HERE.parents[1]
DATA_PATH = REPO_ROOT / "data" / "patient" / "leakage_transcripts.json"
ENUMS = json.loads((REPO_ROOT / "schema" / "enums.json").read_text(encoding="utf-8"))
DATA = json.loads(DATA_PATH.read_text(encoding="utf-8"))
CASES = DATA["transcripts"]


# ------------------------------------------------------------------------------------------- fakes


@dataclass(frozen=True)
class FakeRedaction:
    text: str
    entity_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class FakeSymptom:
    term_code: str
    severity: str | None
    onset: str


@dataclass(frozen=True)
class FreeTextSymptom:  # a future extractor that added a free-text field
    term_code: str
    severity: str | None
    onset: str
    note: str


class FakeExtractionError(Exception):
    pass


class FakeExtractionUnavailable(FakeExtractionError):  # subclass: the harness must still treat it as unavailable
    pass


def scrub(case):
    """A perfect filter for one case: every identifier value replaced by a placeholder."""

    def redact(text):
        for ident in case["identifiers"]:
            text = text.replace(ident["value"], f"<{ident['type']}>")
        return FakeRedaction(text, tuple(i["type"] for i in case["identifiers"]))

    return redact


def runtime(redact=lambda t: FakeRedaction(t), extract=lambda t: []):
    return le.Runtime(redact, extract, FakeExtractionError, FakeExtractionUnavailable)


CASE = {
    "id": "t_01",
    "reporter": "self",
    "transcript": "I'm Zora Quill-Abernathy at 7 Elmo Way in Testerton, call 555-0100 or zq@example.com, "
    "born 1/2/1990. My rash started today.",
    "identifiers": [
        {"type": "NAME", "value": "Zora Quill-Abernathy"},
        {"type": "ADDRESS", "value": "7 Elmo Way"},
        {"type": "PLACE", "value": "Testerton"},
        {"type": "PHONE", "value": "555-0100"},
        {"type": "EMAIL", "value": "zq@example.com"},
        {"type": "DATE_OF_BIRTH", "value": "1/2/1990"},
    ],
    "expected": {"symptoms": [{"term_code": "SE_RASH", "severity": None, "onset": "today"}]},
}


def write_data(tmp_path, cases):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"schema_version": "2.0", "source": "test", "transcripts": cases}))
    return path


# ------------------------------------------------------------------------------------------- scoring


def test_value_matches_case_insensitively():
    assert le.identifier_present("contact ZQ@EXAMPLE.COM today", "EMAIL", "zq@example.com")
    assert le.identifier_present("lives at 7 elmo way", "ADDRESS", "7 Elmo Way")
    assert not le.identifier_present("lives at <ADDRESS>", "ADDRESS", "7 Elmo Way")


def test_name_parts_match_as_whole_words_only():
    assert le.name_parts("Zora Quill-Abernathy") == ["Zora", "Quill", "Abernathy"]
    assert le.identifier_present("abernathy called", "NAME", "Zora Quill-Abernathy")
    assert le.identifier_present('{"note": "zora"}', "NAME", "Zora Quill-Abernathy")
    assert not le.identifier_present("Zorastrian quilled", "NAME", "Zora Quill-Abernathy")
    assert not le.identifier_present('"SE_ZORA"', "NAME", "Zora Quill")  # a part: underscore joins words


def test_name_parts_shorter_than_three_letters_are_ignored():
    assert le.name_parts("Jo Li") == []
    assert not le.identifier_present("jo said li was here", "NAME", "Jo Li")
    assert le.identifier_present("jo li was here", "NAME", "Jo Li")  # whole value still counts


def test_name_matching_handles_accents():
    assert le.identifier_present("RENÉE called", "NAME", "Renée Castellanos")
    decomposed = "Renée called"  # same name, NFD form
    assert le.identifier_present(decomposed, "NAME", "Renée Castellanos")


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("call 2185550142", True),
        ("(218) 555 0142", True),
        ("555.0142", True),
        ("+1 218 555-0142 ext", True),
        ("555-014", False),
        ("5550143", False),
        ('{"onset": "1_3_days"}', False),
    ],
)
def test_phone_compares_digits_only(text, found):
    assert le.identifier_present(text, "PHONE", "218-555-0142") is found


def test_find_identifiers_lists_types_per_identifier():
    text = "Zora at Testerton, 5550100"
    assert le.find_identifiers(text, CASE["identifiers"]) == ["NAME", "PHONE", "PLACE"]
    assert le.find_identifiers("[]", CASE["identifiers"]) == []


def test_typical_placeholders_are_not_identifiers():
    text = "<PERSON> <LOCATION> <PHONE_NUMBER> <EMAIL_ADDRESS> <DATE_TIME> [NAME] [ADDRESS] [PLACE] <DATE_OF_BIRTH>"
    for case in CASES + [CASE]:
        assert le.find_identifiers(text, case["identifiers"]) == [], case["id"]


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        ((2, 1, 1), {"precision": 0.667, "recall": 0.667, "f1": 0.667}),
        ((3, 0, 1), {"precision": 1.0, "recall": 0.75, "f1": 0.857}),
        ((0, 0, 0), {"precision": 1.0, "recall": 1.0, "f1": 1.0}),
        ((0, 0, 2), {"precision": 0.0, "recall": 0.0, "f1": 0.0}),
        ((0, 1, 0), {"precision": 0.0, "recall": 0.0, "f1": 0.0}),
    ],
)
def test_prf(counts, expected):
    assert le.prf(*counts) == expected


def test_term_counts_use_distinct_codes():
    assert le.term_counts(["SE_RASH", "SE_COUGH"], ["SE_RASH", "SE_RASH", "SE_FATIGUE"]) == (1, 1, 1)


def test_safe_term_never_echoes_unknown_text():
    assert le.safe_term("SE_RASH") == "SE_RASH"
    assert le.safe_term("Zora has a rash") == le.INVALID_TERM
    assert le.safe_term(None) == le.INVALID_TERM


# ------------------------------------------------------------------------------------------- run logic


def test_clean_run_passes(tmp_path, capsys):
    extract = lambda text: [FakeSymptom("SE_RASH", None, "today")]  # noqa: E731
    out = tmp_path / "results.json"
    code = le.main(["--data", str(write_data(tmp_path, [CASE])), "--out", str(out)], runtime(scrub(CASE), extract))
    report = json.loads(out.read_text())
    assert code == le.EXIT_PASS
    assert report["pass"] is True
    case = report["cases"][0]
    assert case["output_leaks"] == {"count": 0, "types": []}
    assert case["filter_residuals"] == {"count": 0, "types": []}
    assert case["expected_terms"] == case["extracted_terms"] == ["SE_RASH"]
    assert report["totals"]["term_match"]["f1"] == 1.0
    assert "PV-01: PASS" in capsys.readouterr().out


def test_filter_residuals_are_reported_but_do_not_fail(tmp_path):
    out = tmp_path / "results.json"
    code = le.main(["--data", str(write_data(tmp_path, [CASE])), "--out", str(out)], runtime())  # no filtering
    report = json.loads(out.read_text())
    assert code == le.EXIT_PASS
    assert report["totals"]["filter_residuals"] == len(CASE["identifiers"])
    assert report["totals"]["filter_residuals_by_type"] == {t: 1 for t in le.IDENTIFIER_TYPES}
    assert report["totals"]["output_leaks"] == 0


@pytest.mark.parametrize(
    ("note", "leaked"),
    [("Quill says hi", ["NAME"]), ("ring 555 0100", ["PHONE"]), ("from TESTERTON", ["PLACE"])],
)
def test_identifier_in_output_fails(tmp_path, note, leaked):
    extract = lambda text: [FreeTextSymptom("SE_RASH", "mild", "today", note)]  # noqa: E731
    out = tmp_path / "results.json"
    code = le.main(["--data", str(write_data(tmp_path, [CASE])), "--out", str(out)], runtime(scrub(CASE), extract))
    report = json.loads(out.read_text())
    assert code == le.EXIT_FAIL
    assert report["pass"] is False
    assert report["cases"][0]["output_leaks"] == {"count": len(leaked), "types": leaked}
    assert sum(report["totals"]["output_leaks_by_type"].values()) == len(leaked)


def test_model_unavailable_exits_2_and_writes_nothing(tmp_path, capsys):
    def extract(text):
        raise FakeExtractionUnavailable("connection refused")

    out = tmp_path / "results.json"
    code = le.main(["--data", str(write_data(tmp_path, [CASE])), "--out", str(out)], runtime(extract=extract))
    assert code == le.EXIT_UNAVAILABLE
    assert not out.exists()
    assert "PASS" not in capsys.readouterr().out


def test_runtime_not_importable_exits_2(tmp_path, monkeypatch):
    def not_ready():
        raise le.RuntimeNotReady("ImportError: cannot import name 'redact'")

    monkeypatch.setattr(le, "load_runtime", not_ready)
    out = tmp_path / "results.json"
    assert le.main(["--data", str(write_data(tmp_path, [CASE])), "--out", str(out)]) == le.EXIT_UNAVAILABLE
    assert not out.exists()


def test_extraction_error_is_not_a_pass(tmp_path):
    def extract(text):
        raise FakeExtractionError("bad JSON from model")

    out = tmp_path / "results.json"
    code = le.main(["--data", str(write_data(tmp_path, [CASE])), "--out", str(out)], runtime(scrub(CASE), extract))
    report = json.loads(out.read_text())
    assert code == le.EXIT_FAIL
    assert report["cases"][0]["status"] == "extraction_error"
    assert report["totals"]["extraction_errors"] == 1
    assert report["totals"]["output_leaks"] == 0
    assert report["totals"]["term_match"]["fn"] == 1


def test_invalid_term_code_is_never_written(tmp_path):
    extract = lambda text: [FakeSymptom("Zora Quill rash", None, "today")]  # noqa: E731
    out = tmp_path / "results.json"
    code = le.main(["--data", str(write_data(tmp_path, [CASE])), "--out", str(out)], runtime(scrub(CASE), extract))
    written = out.read_text()
    assert code == le.EXIT_FAIL  # the name went into the output
    assert json.loads(written)["cases"][0]["extracted_terms"] == [le.INVALID_TERM]
    assert "Zora" not in written and "Quill" not in written


def test_results_and_stdout_never_contain_patient_words(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("PATIENT_OLLAMA_MODEL", "fake-model:1b")
    extract = lambda text: [FakeSymptom("SE_FATIGUE", "mild", "today")]  # noqa: E731
    out = tmp_path / "results.json"
    code = le.main(["--data", str(DATA_PATH), "--out", str(out)], runtime(extract=extract))  # identity filter
    written, printed = out.read_text(), capsys.readouterr().out
    report = json.loads(written)
    assert code == le.EXIT_PASS
    assert report["model"] == "fake-model:1b"
    assert report["dataset"] == "data/patient/leakage_transcripts.json"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", report["run_at_utc"])
    assert report["totals"]["filter_residuals"] == report["totals"]["identifiers"]
    for case in CASES:
        for ident in case["identifiers"]:
            assert ident["value"].casefold() not in written.casefold(), (case["id"], ident["type"])
            assert ident["value"].casefold() not in printed.casefold(), (case["id"], ident["type"])
            for part in le.name_parts(ident["value"]) if ident["type"] == "NAME" else []:
                assert not re.search(rf"\b{part}\b", written + printed, re.IGNORECASE), (case["id"], "NAME part")
        for sentence in re.split(r"(?<=[.?!])\s+", case["transcript"]):
            assert sentence not in written and sentence not in printed, case["id"]


# ------------------------------------------------------------------------------------------- dataset


def test_dataset_shape():
    assert DATA["schema_version"] == "2.0"
    assert "no real people" in DATA["source"]
    assert len(CASES) == 10
    ids = [c["id"] for c in CASES]
    assert len(set(ids)) == len(ids)
    for case in CASES:
        assert re.fullmatch(r"lk_\d{2}", case["id"])
        assert set(case) == {"id", "reporter", "transcript", "identifiers", "expected"}
        assert set(case["expected"]) == {"symptoms"}


def test_identifiers_are_heavy_verbatim_and_cover_every_type():
    seen = set()
    for case in CASES:
        assert len(case["identifiers"]) >= 4, case["id"]
        for ident in case["identifiers"]:
            assert set(ident) == {"type", "value"}
            assert ident["type"] in le.IDENTIFIER_TYPES, case["id"]
            assert ident["value"] and ident["value"] in case["transcript"], (case["id"], ident["type"])
            seen.add(ident["type"])
    assert seen == set(le.IDENTIFIER_TYPES)


def test_harness_detects_every_identifier_in_its_raw_transcript():
    for case in CASES:
        found = le.find_identifiers(case["transcript"], case["identifiers"])
        assert len(found) == len(case["identifiers"]), case["id"]


def test_enum_only_output_never_matches_dataset_identifiers():
    every_value = [
        {"term_code": t, "severity": s, "onset": o}
        for t in ENUMS["term_code"]
        for s in [*ENUMS["severity"], None]
        for o in ENUMS["onset"]
    ]
    output = json.dumps(every_value)
    for case in CASES:
        assert le.find_identifiers(output, case["identifiers"]) == [], case["id"]


def test_contact_details_are_fictional():
    for case in CASES:
        for ident in case["identifiers"]:
            if ident["type"] == "PHONE":
                digits = re.sub(r"\D", "", ident["value"])
                assert len(digits) >= 7 and re.fullmatch(r"55501\d\d", digits[-7:]), case["id"]
            if ident["type"] == "EMAIL":
                assert re.fullmatch(r"[^@\s]+@example\.(com|org)", ident["value"]), case["id"]


def test_labels_are_valid_contract_enums():
    for case in CASES:
        assert case["reporter"] in ENUMS["reporter"], case["id"]
        codes = [s["term_code"] for s in case["expected"]["symptoms"]]
        assert len(codes) == len(set(codes)), case["id"]
        for symptom in case["expected"]["symptoms"]:
            assert set(symptom) == {"term_code", "severity", "onset"}
            assert symptom["term_code"] in ENUMS["term_code"], case["id"]
            assert symptom["onset"] in ENUMS["onset"], case["id"]
            assert symptom["severity"] is None or symptom["severity"] in ENUMS["severity"], case["id"]


def test_case_mix():
    reporters = {c["reporter"] for c in CASES}
    assert {"self", "parent", "caregiver"} <= reporters
    expected = {c["id"]: {s["term_code"] for s in c["expected"]["symptoms"]} for c in CASES}
    assert any(not codes for codes in expected.values()), "a case with no symptoms"
    assert any("SE_OTHER_REVIEW" in codes for codes in expected.values()), "a symptom off the term list"
    assert any("no rash" in c["transcript"].lower() and "SE_RASH" not in expected[c["id"]] for c in CASES)
    onsets = {s["onset"] for c in CASES for s in c["expected"]["symptoms"]}
    assert len(onsets) >= 4
    assert any(s["severity"] is None for c in CASES for s in c["expected"]["symptoms"])
