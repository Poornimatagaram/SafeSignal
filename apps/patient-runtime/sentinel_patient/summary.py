"""Spoken summary at the end of a check-in, and one spoken correction (VC-08). Rule-based only: no model call.

`spoken_summary(items, unanswered)` reads back what will be shared, from a fixed template. It never uses model text
and never says why a symptom happened (no causal words). Items are the check-in summary items
({term_code, label, severity | None, onset, known_side_effect}).

`parse_correction(filtered_text, items)` turns one spoken correction ("the rash is quite bad", "it started
yesterday", "I don't have a rash") into a `Correction`, using the same rules as extraction (`extract.py`): which item
the sentence is about comes from the grounding cues (label, everyday words, curated cues), severity and onset from
`severity_in_text` / `onset_in_text`, and a denial ("no rash", "the rash has gone", "I don't have that") means remove.
One change only: anything ambiguous or not understood returns None (never guess).

Privacy: nothing here logs, prints or stores text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import extract

OTHER_REVIEW = extract.OTHER_REVIEW
# Same meaning as checkin.ONSET_WORDS (kept here so checkin can import this module without a cycle).
ONSET_SPOKEN = {"today": "started today", "1_3_days": "started 1 to 3 days ago",
                "4_7_days": "started 4 to 7 days ago", "over_7_days": "started more than a week ago",
                "unknown": "start not known"}
OTHER_REVIEW_SPOKEN = "something else, for your care team to review"
NO_SEVERITY_SPOKEN = "how bad is not said yet"
_COUNT_WORDS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
                "twelve")
OPENING = "Here is what I heard."
NOTHING = "You did not report any new problems."
CLOSING = "If something is wrong, you can change one answer. Otherwise, tap Share this."


def spoken_summary(items: list[dict], unanswered: int) -> str:
    """Template text for text-to-speech, e.g. "Here is what I heard. Rash, moderate, started 1 to 3 days ago. One
    question was not answered. If something is wrong, you can change one answer. Otherwise, tap Share this."."""
    sentences = [OPENING]
    if items:
        sentences += [_item_sentence(i) for i in items]
    else:
        sentences.append(NOTHING)
    if unanswered > 0:
        count = _COUNT_WORDS[unanswered] if unanswered < len(_COUNT_WORDS) else str(unanswered)
        sentences.append(f"{count.capitalize()} question{'s were' if unanswered > 1 else ' was'} not answered.")
    sentences.append(CLOSING)
    return " ".join(sentences)


def _item_sentence(item: dict) -> str:
    if item["term_code"] == OTHER_REVIEW:
        name = OTHER_REVIEW_SPOKEN
    else:
        name = (item.get("label") or item["term_code"]).strip()
        name = name[:1].lower() + name[1:]  # "Rash" -> "rash"; capitalised again below
    severity = item.get("severity") or NO_SEVERITY_SPOKEN
    onset = ONSET_SPOKEN.get(item.get("onset") or "unknown", ONSET_SPOKEN["unknown"])
    sentence = f"{name}, {severity}, {onset}."
    return sentence[:1].upper() + sentence[1:]


@dataclass(frozen=True)
class Correction:
    term_code: str
    severity: str | None = None     # new severity
    onset: str | None = None        # new onset (enums onset)
    remove: bool = False            # "I don't have that" / "that's wrong, no rash"


# "something else" is how the summary names SE_OTHER_REVIEW.
_OTHER_RE = re.compile(r"(?<![\w'])(?:something\s+else|the\s+other\s+(?:one|thing|problem)|other\s+thing)(?![\w'])",
                       re.IGNORECASE)
# A denial that names no symptom ("I don't have that", "take it off"); not "I don't have it that bad".
_LEVEL_AFTER = r"(?!\s+(?:(?:that|so|too|very|really)\s+)?(?:bad\w*|severe\w*|serious\w*|terribl\w*|awful\w*|much))"
_DENIAL_RE = re.compile(
    r"(?<![\w'])(?:"
    r"(?:don't|do\s+not|doesn't|does\s+not|didn't|did\s+not|never)\s+(?:even\s+)?(?:have|had|get|got)\s+"
    rf"(?:that|it|this|one|any)(?:\s+(?:one|at\s+all))?{_LEVEL_AFTER}"
    r"|(?:take|cross|leave)\s+(?:that|it|this)(?:\s+one)?\s+(?:off|out)"
    r"|(?:remove|delete|drop)\s+(?:that|it|this)"
    r"|(?:it's|it\s+is|that's|that\s+is)\s+(?:gone|not\s+there)"
    r")(?![\w'])",
    re.IGNORECASE)
_ONSET_UNKNOWN_RE = re.compile(
    r"(?<![\w'])(?:(?:don't|do\s+not|not|can't|cannot)\s+(?:really\s+)?(?:know|remember|sure|say|tell)\s+when|"
    r"no\s+idea\s+when)(?![\w'])", re.IGNORECASE)


def parse_correction(filtered_text: str, items: list[dict]) -> Correction | None:
    """The one change the patient asked for, or None when it is unclear which item or what change."""
    text = extract._normalise(filtered_text).strip()
    if not text or not items:
        return None
    codes = [i["term_code"] for i in items]
    mentioned = _mentioned(text, codes)
    if len(mentioned) > 1:
        return None
    if mentioned:
        code, denied = next(iter(mentioned.items()))
        if code not in codes:
            return None  # a symptom that is not in the summary: adding one is not a correction
    elif len(items) == 1:
        code, denied = codes[0], False
    else:
        return None

    remove = denied or _DENIAL_RE.search(text) is not None
    severity = extract.severity_in_text(text)
    onset = extract.onset_in_text(text)
    if _ONSET_UNKNOWN_RE.search(text):
        onset = None if onset else "unknown"  # "I don't know when, maybe yesterday": unclear
        if onset is None:
            return None
    changes = sum((remove, severity is not None, onset is not None))
    if changes != 1:
        return None
    return Correction(term_code=code, severity=severity, onset=onset, remove=remove)


def _mentioned(text: str, codes: list[str]) -> dict[str, bool]:
    """Every term the text is about -> whether it is denied ("no rash", "the rash has gone")."""
    out: dict[str, bool] = {}
    for code in extract.term_codes():
        if code == OTHER_REVIEW:
            continue
        grounding = extract._grounding(code, text)
        if grounding != extract._UNGROUNDED:
            out[code] = grounding == extract._DENIED
    if OTHER_REVIEW in codes and _OTHER_RE.search(text):
        out[OTHER_REVIEW] = False
    return out
