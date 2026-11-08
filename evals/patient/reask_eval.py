"""Patient-side answer-rating evaluation (Scoping Doc VC-04 to VC-06, 17.3 "Answer rating", 20 re-ask cases).

For every synthetic case in data/patient/reask_cases.json:
  1. question = the case's question from the example survey (schema/examples/survey_config.valid.json)
  2. filtered = redact(answer).text                              # sentinel_patient.filter, as the runtime does
  3. r = rate_answer(question, ask, filtered)                    # sentinel_patient.rating
  4. r.rating vs expected_rating                                 -> VC-04 (pass/fail: >= 16 of 20 correct)
  5. rambling cases: every expected_relevant phrase in r.relevant_text and no expected_not_relevant phrase
                                                                 -> VC-06 extraction (reported only)
  6. r.source counted                                            -> source mix (reported only)

Exit codes: 0 pass, 1 fail, 2 the runtime cannot be imported (nothing evaluated, no results written).

Never prints or writes answer text or relevant_text: only case ids, question ids, asks, rating enums, pass flags
and counts. A rating outside schema/enums.json `answer_rating` is written as INVALID; a source that is not a
short lower-case token is written as OTHER.

Run from the repository root:
    uv run --project apps/patient-runtime python evals/patient/reask_eval.py [--data PATH] [--out PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = REPO_ROOT / "apps" / "patient-runtime"
ENUMS_PATH = REPO_ROOT / "schema" / "enums.json"
SURVEY_PATH = REPO_ROOT / "schema" / "examples" / "survey_config.valid.json"
DEFAULT_DATA = REPO_ROOT / "data" / "patient" / "reask_cases.json"
DEFAULT_OUT = REPO_ROOT / "evals" / "patient" / "results" / "reask_results.json"

VC04_TARGET = 16  # correct ratings needed out of 20 (Scoping Doc 12.1, 17.3)
VC04_CASES = 20
RAMBLING = "rambling"
INVALID = "INVALID"  # written instead of a rating that is not in the enum
OTHER_SOURCE = "OTHER"  # written instead of a source that is not a short token
ERROR = "ERROR"  # the rater raised on this case

EXIT_PASS, EXIT_FAIL, EXIT_UNAVAILABLE = 0, 1, 2

_SOURCE_TOKEN = re.compile(r"[a-z][a-z0-9_]{0,31}")
_SPACE = re.compile(r"\s+")


# --------------------------------------------------------------------------------------------- scoring


@cache
def ratings() -> tuple[str, ...]:
    return tuple(json.loads(ENUMS_PATH.read_text(encoding="utf-8"))["answer_rating"])


def safe_rating(value: Any) -> str:
    """The rating if it is in schema/enums.json, else INVALID (never echo unknown text)."""
    return value if isinstance(value, str) and value in ratings() else INVALID


def safe_source(value: Any) -> str:
    """The source if it is a short lower-case token ("model", "rule", ...), else OTHER."""
    return value if isinstance(value, str) and _SOURCE_TOKEN.fullmatch(value) else OTHER_SOURCE


def _norm(text: str) -> str:
    """NFC, casefolded, whitespace collapsed, curly apostrophes made straight."""
    text = unicodedata.normalize("NFC", text).replace("’", "'")
    return _SPACE.sub(" ", text).strip().casefold()


def phrase_in(text: str | None, phrase: str) -> bool:
    return bool(text) and _norm(phrase) in _norm(text)


def extraction_check(relevant_text: str | None, keep: Iterable[str], drop: Iterable[str]) -> dict[str, Any]:
    """Counts only: how many must-keep phrases were kept and how many off-topic phrases leaked into relevant_text."""
    keep, drop = list(keep), list(drop)
    kept = sum(phrase_in(relevant_text, p) for p in keep)
    leaked = sum(phrase_in(relevant_text, p) for p in drop)
    return {
        "relevant_kept": kept,
        "relevant_expected": len(keep),
        "off_topic_kept": leaked,
        "off_topic_listed": len(drop),
        "pass": kept == len(keep) and leaked == 0,
    }


def confusion(case_results: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """expected rating -> got rating -> count; columns are the enum plus INVALID and ERROR."""
    cols = [*ratings(), INVALID, ERROR]
    table = {exp: dict.fromkeys(cols, 0) for exp in ratings()}
    for c in case_results:
        table[c["expected"]][c["got"]] += 1
    return table


# --------------------------------------------------------------------------------------------- runtime


@dataclass(frozen=True)
class Runtime:
    """The two runtime calls under test (injectable for tests)."""

    redact: Callable[[str], Any]  # -> object with .text
    rate_answer: Callable[[Mapping[str, Any], int, str], Any]  # -> object with .rating, .relevant_text, .source


class RuntimeNotReady(Exception):
    """The filter or rater cannot be imported."""


def load_runtime() -> Runtime:
    if str(RUNTIME_DIR) not in sys.path:
        sys.path.insert(0, str(RUNTIME_DIR))
    try:
        from sentinel_patient.filter import redact
        from sentinel_patient.rating import rate_answer
    except ImportError as exc:  # message names modules only, never patient text
        raise RuntimeNotReady(f"{type(exc).__name__}: {exc}") from exc
    return Runtime(redact, rate_answer)


# --------------------------------------------------------------------------------------------- run


def load_questions(path: Path = SURVEY_PATH) -> dict[str, dict[str, Any]]:
    survey = json.loads(path.read_text(encoding="utf-8"))
    return {q["question_id"]: q for q in survey["questions"]}


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
    for case in cases:
        missing = {"id", "question_id", "ask", "answer", "expected_rating", "expected_relevant"} - case.keys()
        if missing:
            raise ValueError(f"case {case.get('id', '?')} is missing {sorted(missing)}")
    return cases


def evaluate_case(case: dict[str, Any], question: Mapping[str, Any], runtime: Runtime) -> dict[str, Any]:
    filtered = runtime.redact(case["answer"]).text
    expected = case["expected_rating"]
    try:
        result = runtime.rate_answer(question, case["ask"], filtered)
    except Exception as exc:  # noqa: BLE001 - one broken case must not hide the others; type name only
        got, source, relevant, status = ERROR, OTHER_SOURCE, None, f"error:{type(exc).__name__}"
    else:
        got = safe_rating(getattr(result, "rating", None))
        source = safe_source(getattr(result, "source", None))
        relevant = getattr(result, "relevant_text", None)
        relevant = relevant if isinstance(relevant, str) else None
        status = "ok"
    out = {
        "id": case["id"],
        "question_id": case["question_id"],
        "purpose": question.get("purpose"),
        "ask": case["ask"],
        "status": status,
        "expected": expected,
        "got": got,
        "source": source,
        "rating_pass": got == expected,
    }
    if expected == RAMBLING:
        out["extraction"] = extraction_check(
            relevant, case["expected_relevant"], case.get("expected_not_relevant", []))
    return out


def run_eval(cases: list[dict[str, Any]], questions: dict[str, dict[str, Any]], runtime: Runtime) -> list[dict]:
    return [evaluate_case(case, questions[case["question_id"]], runtime) for case in cases]


def build_report(case_results: list[dict[str, Any]], *, run_at: str, dataset: str, dataset_sha256: str) -> dict:
    correct = sum(c["rating_pass"] for c in case_results)
    rambling = [c for c in case_results if "extraction" in c]
    target = VC04_TARGET * len(case_results) / VC04_CASES if case_results else VC04_TARGET
    totals = {
        "cases": len(case_results),
        "ratings_correct": correct,
        "rating_accuracy": round(correct / len(case_results), 3) if case_results else 0.0,
        "target_correct": target,
        "errors": sum(c["status"] != "ok" for c in case_results),
        "per_rating": {
            r: {"cases": sum(c["expected"] == r for c in case_results),
                "correct": sum(c["expected"] == r and c["rating_pass"] for c in case_results)}
            for r in ratings()
        },
        "confusion": confusion(case_results),
        "rambling_extraction": {"cases": len(rambling), "pass": sum(c["extraction"]["pass"] for c in rambling)},
        "source_mix": dict(sorted(Counter(c["source"] for c in case_results).items())),
    }
    return {
        "eval": "patient_reask_rating",
        "requirement": "VC-04 (pass/fail); VC-06 extraction reported",
        "run_at_utc": run_at,
        "dataset": dataset,
        "dataset_sha256": dataset_sha256,
        "pass_rule": f"at least {VC04_TARGET} of {VC04_CASES} ratings correct",
        "pass": bool(case_results) and correct >= target,
        "totals": totals,
        "cases": case_results,
    }


# --------------------------------------------------------------------------------------------- output


def print_summary(report: dict[str, Any], out_path: str) -> None:
    t = report["totals"]
    print(f"VC-04 answer-rating eval | {t['cases']} cases")
    print(f"{'case':<7}{'q':<4}{'purpose':<16}{'ask':<5}{'expected':<11}{'got':<11}{'source':<10}{'ok':<4}extract")
    for c in report["cases"]:
        ex = c.get("extraction")
        extract = "-" if ex is None else (
            f"{'pass' if ex['pass'] else 'FAIL'} (kept {ex['relevant_kept']}/{ex['relevant_expected']}, "
            f"off-topic {ex['off_topic_kept']}/{ex['off_topic_listed']})")
        print(f"{c['id']:<7}{c['question_id']:<4}{c['purpose'] or '-':<16}{c['ask']:<5}{c['expected']:<11}"
              f"{c['got']:<11}{c['source']:<10}{'y' if c['rating_pass'] else 'n':<4}{extract}")
    cols = [*ratings(), INVALID, ERROR]
    print("Confusion (rows expected, columns got):")
    print(f"  {'':<11}" + "".join(f"{col[:9]:>10}" for col in cols))
    for exp, row in t["confusion"].items():
        print(f"  {exp:<11}" + "".join(f"{row[col]:>10}" for col in cols))
    if t["errors"]:
        print(f"Rater errors: {t['errors']} case(s) raised (counted as wrong)")
    re_ = t["rambling_extraction"]
    print(f"Rambling extraction (VC-06, informational): {re_['pass']} of {re_['cases']} cases")
    print("Source mix: " + (", ".join(f"{k} {v}" for k, v in t["source_mix"].items()) or "-"))
    verdict = "PASS" if report["pass"] else "FAIL"
    print(f"Ratings correct: {t['ratings_correct']} of {t['cases']} ({t['rating_accuracy']:.0%}), "
          f"target {t['target_correct']:g}")
    print(f"VC-04: {verdict}. Results: {out_path}")


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patient-side answer-rating evaluation (VC-04 to VC-06).")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="cases file (default: %(default)s)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="results file (default: %(default)s)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, runtime: Runtime | None = None) -> int:
    args = parse_args(argv)
    cases = load_cases(args.data)
    questions = load_questions()

    if runtime is None:
        try:
            runtime = load_runtime()
        except RuntimeNotReady as exc:
            print(f"reask eval: runtime not ready ({exc}). Nothing evaluated, no results written.", file=sys.stderr)
            return EXIT_UNAVAILABLE

    case_results = run_eval(cases, questions, runtime)
    report = build_report(
        case_results,
        run_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        dataset=_display_path(args.data),
        dataset_sha256=hashlib.sha256(args.data.read_bytes()).hexdigest(),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print_summary(report, _display_path(args.out))
    return EXIT_PASS if report["pass"] else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
