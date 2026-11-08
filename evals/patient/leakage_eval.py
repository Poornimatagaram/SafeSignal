"""Patient-side personal-data leakage evaluation (Scoping Doc PV-01, 17.3).

For every synthetic transcript in data/patient/leakage_transcripts.json (10 cases the filter was developed against)
and data/patient/leakage_held_out.json (40 held-out cases written without seeing the filter, never used to tune it):
  1. red = redact(transcript)                       # sentinel_patient.filter
  2. out = [asdict(s) for s in extract_symptoms(red.text)]   # sentinel_patient.extract
  3. look for the case's known identifiers in json.dumps(out)  -> output leaks (PV-01, pass/fail)
     and in red.text                                           -> filter residuals (reported only)
  4. compare extracted term codes with the expected ones       -> precision, recall, F1 (reported only)

PASS: 0 identifiers in the extraction output across all cases, and every case produced output.
Exit codes: 0 pass, 1 fail, 2 the runtime or model is unavailable (nothing evaluated, no results written).

Never prints or writes transcript text or identifier values: only case ids, identifier types, counts and
term codes from schema/enums.json.

Run from the repository root:
    uv run --project apps/patient-runtime python evals/patient/leakage_eval.py [--data PATH ...] [--out PATH]

Each data file is reported as its own set ("sets" in the results) as well as in the totals, so the held-out result
is never hidden inside the tuned one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = REPO_ROOT / "apps" / "patient-runtime"
ENUMS_PATH = REPO_ROOT / "schema" / "enums.json"
DEFAULT_DATA = REPO_ROOT / "data" / "patient" / "leakage_transcripts.json"
HELD_OUT_DATA = REPO_ROOT / "data" / "patient" / "leakage_held_out.json"
DEFAULT_OUT = REPO_ROOT / "evals" / "patient" / "results" / "leakage_results.json"

IDENTIFIER_TYPES = ("NAME", "ADDRESS", "PHONE", "EMAIL", "DATE_OF_BIRTH", "PLACE")
DEFAULT_MODEL = "llama3.2:3b"
SE01_TARGET_F1 = 0.75
PHONE_KEY_DIGITS = 7  # a phone leaks when its last 7 digits appear in a run of 7+ digits
INVALID_TERM = "INVALID"  # written instead of any extracted term code that is not in the enum

EXIT_PASS, EXIT_FAIL, EXIT_UNAVAILABLE = 0, 1, 2

_NAME_PART = re.compile(r"[^\W\d_]{3,}")  # letters only, 3 or more
_DIGIT_RUN = re.compile(r"\d(?:[\s().+\-]*\d)*")  # digits joined by phone separators


# --------------------------------------------------------------------------------------------- scoring


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def name_parts(value: str) -> list[str]:
    """Parts of a name checked on their own: runs of 3+ letters ("Delacroix-Meyer" -> Delacroix, Meyer)."""
    return _NAME_PART.findall(_norm(value))


def phone_present(text: str, value: str) -> bool:
    """True when the phone's last 7 digits appear inside a run of 7+ digits in text (separators ignored)."""
    digits = re.sub(r"\D", "", value)
    if len(digits) < PHONE_KEY_DIGITS:
        return False
    key = digits[-PHONE_KEY_DIGITS:]
    for match in _DIGIT_RUN.finditer(text):
        run = re.sub(r"\D", "", match.group())
        if len(run) >= PHONE_KEY_DIGITS and key in run:
            return True
    return False


def identifier_present(text: str, id_type: str, value: str) -> bool:
    """Whether one known identifier is still recognisable in text.

    Every type: the whole value, case-insensitively. NAME: also any name part of 3+ letters as a whole
    word. PHONE: also the digits alone, whatever the separators.
    """
    text, value = _norm(text), _norm(value)
    if value.casefold() in text.casefold():
        return True
    if id_type == "NAME":
        return any(
            re.search(rf"(?<!\w){re.escape(part)}(?!\w)", text, re.IGNORECASE) for part in name_parts(value)
        )
    if id_type == "PHONE":
        return phone_present(text, value)
    return False


def find_identifiers(text: str, identifiers: Iterable[dict[str, str]]) -> list[str]:
    """Types of the identifiers found in text, one entry per identifier found (sorted)."""
    return sorted(i["type"] for i in identifiers if identifier_present(text, i["type"], i["value"]))


def term_counts(expected: Iterable[str], extracted: Iterable[str]) -> tuple[int, int, int]:
    """(true positives, false positives, false negatives) over distinct term codes."""
    exp, ext = set(expected), set(extracted)
    return len(exp & ext), len(ext - exp), len(exp - ext)


def prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    """Micro precision, recall and F1. Nothing expected and nothing extracted scores 1.0."""
    precision = tp / (tp + fp) if tp + fp else (1.0 if fn == 0 else 0.0)
    recall = tp / (tp + fn) if tp + fn else (1.0 if fp == 0 else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}


@cache
def valid_term_codes() -> frozenset[str]:
    return frozenset(json.loads(ENUMS_PATH.read_text(encoding="utf-8"))["term_code"])


def safe_term(code: Any) -> str:
    """The term code if it is in schema/enums.json, else INVALID (never echo unknown text)."""
    return code if isinstance(code, str) and code in valid_term_codes() else INVALID_TERM


# --------------------------------------------------------------------------------------------- runtime


@dataclass(frozen=True)
class Runtime:
    """The two runtime calls under test, plus the extractor's exception types (injectable for tests)."""

    redact: Callable[[str], Any]  # -> object with .text
    extract_symptoms: Callable[[str], list[Any]]  # -> list of dataclasses
    extraction_error: type[BaseException]
    extraction_unavailable: type[BaseException]


class RuntimeNotReady(Exception):
    """The filter or extractor cannot be imported."""


class ModelUnavailable(Exception):
    """The extraction model did not run; nothing may be reported as a pass."""


def load_runtime() -> Runtime:
    if str(RUNTIME_DIR) not in sys.path:
        sys.path.insert(0, str(RUNTIME_DIR))
    try:
        from sentinel_patient.extract import ExtractionError, ExtractionUnavailable, extract_symptoms
        from sentinel_patient.filter import redact
    except ImportError as exc:  # message names modules only, never patient text
        raise RuntimeNotReady(f"{type(exc).__name__}: {exc}") from exc
    return Runtime(redact, extract_symptoms, ExtractionError, ExtractionUnavailable)


# --------------------------------------------------------------------------------------------- run


def load_cases(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data["transcripts"]
    for case in cases:
        missing = {"id", "reporter", "transcript", "identifiers", "expected"} - case.keys()
        if missing:
            raise ValueError(f"case {case.get('id', '?')} is missing {sorted(missing)}")
    return cases


def evaluate_case(case: dict[str, Any], runtime: Runtime) -> dict[str, Any]:
    identifiers = case["identifiers"]
    filtered = runtime.redact(case["transcript"]).text
    residuals = find_identifiers(filtered, identifiers)

    status = "ok"
    try:
        symptoms = runtime.extract_symptoms(filtered)
    except runtime.extraction_unavailable as exc:
        raise ModelUnavailable(type(exc).__name__) from None
    except runtime.extraction_error:
        status, symptoms = "extraction_error", []

    out = [asdict(s) for s in symptoms]
    output = json.dumps(out, ensure_ascii=False)  # unescaped, so non-ASCII identifiers are still matched
    leaks = find_identifiers(output, identifiers)

    expected = sorted({s["term_code"] for s in case["expected"]["symptoms"]})
    extracted = sorted({safe_term(o.get("term_code")) for o in out})
    tp, fp, fn = term_counts(expected, extracted)
    return {
        "id": case["id"],
        "set": case.get("set", "data"),
        "reporter": case["reporter"],
        "status": status,
        "identifiers": len(identifiers),
        "output_leaks": {"count": len(leaks), "types": leaks},
        "filter_residuals": {"count": len(residuals), "types": residuals},
        "expected_terms": expected,
        "extracted_terms": extracted,
        "term_match": {"tp": tp, "fp": fp, "fn": fn},
    }


def run_eval(cases: list[dict[str, Any]], runtime: Runtime) -> list[dict[str, Any]]:
    """Evaluate every case; raises ModelUnavailable as soon as the model fails to run."""
    return [evaluate_case(case, runtime) for case in cases]


def _by_type(type_lists: Iterable[list[str]]) -> dict[str, int]:
    counts = Counter(t for types in type_lists for t in types)
    return {t: counts.get(t, 0) for t in IDENTIFIER_TYPES}


def _totals(case_results: list[dict[str, Any]], cases: list[dict[str, Any]]) -> dict[str, Any]:
    tp = sum(c["term_match"]["tp"] for c in case_results)
    fp = sum(c["term_match"]["fp"] for c in case_results)
    fn = sum(c["term_match"]["fn"] for c in case_results)
    scores = prf(tp, fp, fn)
    leaks = sum(c["output_leaks"]["count"] for c in case_results)
    errors = sum(c["status"] != "ok" for c in case_results)
    totals = {
        "cases": len(case_results),
        "identifiers": sum(c["identifiers"] for c in case_results),
        "identifiers_by_type": _by_type([i["type"] for i in case["identifiers"]] for case in cases),
        "output_leaks": leaks,
        "output_leaks_by_type": _by_type(c["output_leaks"]["types"] for c in case_results),
        "filter_residuals": sum(c["filter_residuals"]["count"] for c in case_results),
        "filter_residuals_by_type": _by_type(c["filter_residuals"]["types"] for c in case_results),
        "extraction_errors": errors,
        "term_match": {"tp": tp, "fp": fp, "fn": fn, **scores, "target_f1": SE01_TARGET_F1,
                       "meets_target": scores["f1"] >= SE01_TARGET_F1},
    }
    return totals


def build_report(
    case_results: list[dict[str, Any]], cases: list[dict[str, Any]], *, model: str, run_at: str, dataset: str,
    dataset_sha256: str,
) -> dict[str, Any]:
    totals = _totals(case_results, cases)
    leaks, errors = totals["output_leaks"], totals["extraction_errors"]
    sets: dict[str, dict[str, Any]] = {}
    for name in dict.fromkeys(case.get("set", "data") for case in cases):
        idx = [i for i, case in enumerate(cases) if case.get("set", "data") == name]
        sets[name] = _totals([case_results[i] for i in idx], [cases[i] for i in idx])
    return {
        "eval": "patient_leakage",
        "requirement": "PV-01",
        "run_at_utc": run_at,
        "model": model,
        "dataset": dataset,
        "dataset_sha256": dataset_sha256,
        "pass_rule": "0 identifiers in the extraction output across all cases, and every case produced output",
        "pass": bool(case_results) and leaks == 0 and errors == 0,
        "totals": totals,
        "sets": sets,
        "cases": case_results,
    }


# --------------------------------------------------------------------------------------------- output


def _short(counts: dict[str, int]) -> str:
    """"NAME 2, PLACE 1" for the non-zero counts, "-" when there are none."""
    return ", ".join(f"{t} {n}" for t, n in sorted(counts.items()) if n) or "-"


def print_summary(report: dict[str, Any], out_path: str) -> None:
    t = report["totals"]
    tm = t["term_match"]
    print(f"PV-01 leakage eval | model {report['model']} | {t['cases']} cases | {t['identifiers']} identifiers")
    print(f"{'case':<7}{'reporter':<11}{'status':<18}{'out leaks':<11}{'filter residuals':<26}{'terms exp/ext/match'}")
    for c in report["cases"]:
        ol, fr, m = c["output_leaks"], c["filter_residuals"], c["term_match"]
        residuals = f"{fr['count']} ({_short(Counter(fr['types']))})" if fr["count"] else "0"
        print(
            f"{c['id']:<7}{c['reporter']:<11}{c['status']:<18}{ol['count']:<11}{residuals:<26}"
            f"{len(c['expected_terms'])}/{len(c['extracted_terms'])}/{m['tp']}"
        )
    verdict = "PASS" if report["pass"] else "FAIL"
    print(f"Output leaks (must be 0): {t['output_leaks']} of {t['identifiers']} identifiers"
          f" [{_short(t['output_leaks_by_type'])}]")
    if t["extraction_errors"]:
        print(f"Extraction errors: {t['extraction_errors']} case(s) produced no output (counts as a fail)")
    print(f"Filter residuals (informational): {t['filter_residuals']} of {t['identifiers']} identifiers"
          f" [{_short(t['filter_residuals_by_type'])}]")
    print(f"Term match (informational, SE-01 target F1 {tm['target_f1']}): precision {tm['precision']:.3f}"
          f" recall {tm['recall']:.3f} F1 {tm['f1']:.3f} (tp {tm['tp']}, fp {tm['fp']}, fn {tm['fn']})")
    if len(report.get("sets", {})) > 1:
        for name, st in report["sets"].items():
            print(f"  set {name}: {st['cases']} cases | output leaks {st['output_leaks']} of {st['identifiers']}"
                  f" | filter residuals {st['filter_residuals']} of {st['identifiers']}"
                  f" [{_short(st['filter_residuals_by_type'])}] | term F1 {st['term_match']['f1']:.3f}")
    print(f"PV-01: {verdict}. Results: {out_path}")


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patient-side personal-data leakage evaluation (PV-01).")
    parser.add_argument("--data", type=Path, action="append",
                        help="transcripts file, repeatable (default: the tuned set and the held-out set)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="results file (default: %(default)s)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, runtime: Runtime | None = None) -> int:
    args = parse_args(argv)
    paths = args.data or [p for p in (DEFAULT_DATA, HELD_OUT_DATA) if p.exists()]
    cases = []
    for path in paths:
        cases += [{**case, "set": path.stem} for case in load_cases(path)]
    ids = [case["id"] for case in cases]
    if len(set(ids)) != len(ids):
        raise ValueError("case ids must be unique across data files")
    model = os.environ.get("PATIENT_OLLAMA_MODEL") or DEFAULT_MODEL

    if runtime is None:
        try:
            runtime = load_runtime()
        except RuntimeNotReady as exc:
            print(f"leakage eval: runtime not ready ({exc}). Nothing evaluated, no results written.", file=sys.stderr)
            return EXIT_UNAVAILABLE
    try:
        case_results = run_eval(cases, runtime)
    except ModelUnavailable as exc:
        print(
            f"leakage eval: extraction model {model} unavailable ({exc}). Nothing evaluated, no results written. "
            "Start Ollama and pull the model, then re-run.",
            file=sys.stderr,
        )
        return EXIT_UNAVAILABLE

    report = build_report(
        case_results,
        cases,
        model=model,
        run_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        dataset=" + ".join(_display_path(p) for p in paths),
        dataset_sha256=hashlib.sha256(b"".join(p.read_bytes() for p in paths)).hexdigest(),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print_summary(report, _display_path(args.out))
    return EXIT_PASS if report["pass"] else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
