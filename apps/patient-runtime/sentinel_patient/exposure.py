"""Possible link (SE-04): a new symptom that started within 7 days after a new exposure is flagged for review.

A deterministic rule, never a model and never a cause (Scoping Doc 17, "Possible link over time"):

- **New exposure:** the patient said they started something new (a cream, soap, food, product or activity) in
  answer to the exposure question, or such an exposure was stored in the last `EXPOSURE_WINDOW_DAYS` days. Its
  description stays on this device (`exposure_event.description` is local only); only the flag ever leaves.
- **New symptom:** its term was not in the patient's previous approved check-in.
- **Link:** the symptom started on or after the exposure started, at most `LINK_DAYS` days later. Onsets are
  buckets ("1 to 3 days ago"), so each is a range of days ago, and the rule asks whether any day in the symptom's
  range is 0 to 7 days after some day in the exposure's range. An unknown symptom onset is never linked.

The flag is `possible_link_flag` in the company record and the doctor payload; screens word it "for review".
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

LINK_DAYS = 7
EXPOSURE_WINDOW_DAYS = 30

# onset bucket -> (fewest, most) days ago it started. "unknown" has no range for a symptom; for an exposure the
# patient called "new" without saying when, it is taken as within the last week.
ONSET_DAYS = {"today": (0, 0), "1_3_days": (1, 3), "4_7_days": (4, 7), "over_7_days": (8, EXPOSURE_WINDOW_DAYS)}
UNKNOWN_EXPOSURE_DAYS = (0, 7)

_NEGATIVE = re.compile(r"^\s*(no\b|nope\b|nothing\b|none\b|not\b|nah\b|i (have not|haven't|did not|didn't)\b|"
                       r"no,|same as (before|usual|always))", re.I)
_POSITIVE = re.compile(r"\b(yes|yeah|yep|new|started|starting|began|begun|switched|changed|tried|trying|using|"
                       r"took up|taking|eating|drinking|bought|cream|lotion|soap|shampoo|polish|detergent|perfume|"
                       r"food|diet|medicine|tablet|pill|vitamin|supplement|tea|garden|gardening|exercise|walking)\b",
                       re.I)


@dataclass(frozen=True)
class Exposure:
    days_ago: tuple[int, int]   # (fewest, most) days ago it started


def is_new_exposure(text: str) -> bool:
    """True when an answer to the exposure question says something new was started ("Yes, a new hand cream")."""
    text = (text or "").strip()
    return bool(text) and not _NEGATIVE.search(text) and bool(_POSITIVE.search(text))


def exposure_from_answer(onset: str | None) -> Exposure:
    return Exposure(ONSET_DAYS.get(onset or "", UNKNOWN_EXPOSURE_DAYS))


def started_on(exposure: Exposure, today: date) -> date:
    """The date stored in exposure_event.started_on: the middle of the range (a whole day)."""
    lo, hi = exposure.days_ago
    return today - timedelta(days=(lo + hi) // 2)


def stored_exposure(started: date, today: date) -> Exposure | None:
    """An exposure stored earlier, as days ago from today; None when outside the window or in the future."""
    days = (today - started).days
    return Exposure((days, days)) if 0 <= days <= EXPOSURE_WINDOW_DAYS else None


def linked(symptom_onset: str, exposure: Exposure) -> bool:
    """Did a symptom with this onset start 0 to LINK_DAYS days after the exposure started (for some day in each
    range)? Days are counted back from today, so "after" means fewer days ago."""
    if symptom_onset not in ONSET_DAYS:
        return False
    s_lo, s_hi = ONSET_DAYS[symptom_onset]
    e_lo, e_hi = exposure.days_ago
    # need s <= e and e - s <= LINK_DAYS for some s in [s_lo, s_hi], e in [e_lo, e_hi]
    return e_hi >= s_lo and e_lo - s_hi <= LINK_DAYS


def possible_links(symptoms: Sequence[dict], exposures: Iterable[Exposure], previous_codes: set[str]) -> set[str]:
    """Term codes to flag: new symptoms (not in the previous check-in) linked to any new exposure."""
    exposures = list(exposures)
    return {s["term_code"] for s in symptoms
            if s["term_code"] not in previous_codes and any(linked(s["onset"], e) for e in exposures)}
