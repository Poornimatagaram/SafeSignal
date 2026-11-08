"""SE-04 possible-link rule: deterministic, for review, never a cause."""

from datetime import date

import pytest

from sentinel_patient import exposure as ex

TODAY = date(2026, 11, 8)


@pytest.mark.parametrize("text, new", [
    ("Yes, a new hand cream", True), ("I switched to a different soap", True), ("yes", True),
    ("I've been eating more fish", True), ("No", False), ("Nothing new", False), ("no, same as before", False),
    ("I haven't started anything", False), ("", False), ("the weather is nice", False),
])
def test_new_exposure_from_the_answer(text, new):
    assert ex.is_new_exposure(text) is new


@pytest.mark.parametrize("symptom_onset, exposure_onset, linked", [
    ("1_3_days", "4_7_days", True),      # rash 1-3 days ago, cream 4-7 days ago
    ("today", "today", True),
    ("today", "4_7_days", True),         # up to 7 days after
    ("4_7_days", "1_3_days", False),     # the symptom was there before the exposure
    ("4_7_days", "today", False),        # the symptom came first
    ("today", "over_7_days", False),     # "over a week" ago is more than 7 days before today
    ("4_7_days", "over_7_days", True),   # 8 days ago, then a symptom 4 to 7 days ago
    ("unknown", "1_3_days", False),      # unknown onset is never linked
])
def test_link_needs_the_symptom_on_or_after_the_exposure_within_7_days(symptom_onset, exposure_onset, linked):
    assert ex.linked(symptom_onset, ex.exposure_from_answer(exposure_onset)) is linked


def test_exposure_without_a_time_counts_as_within_the_last_week():
    assert ex.exposure_from_answer(None).days_ago == (0, 7)
    assert ex.linked("1_3_days", ex.exposure_from_answer(None))


def test_stored_exposures_count_for_30_days_only():
    assert ex.stored_exposure(date(2026, 11, 3), TODAY).days_ago == (5, 5)
    assert ex.stored_exposure(date(2026, 9, 1), TODAY) is None
    assert ex.stored_exposure(date(2026, 11, 9), TODAY) is None
    assert ex.linked("today", ex.stored_exposure(date(2026, 11, 3), TODAY))
    assert not ex.linked("today", ex.stored_exposure(date(2026, 10, 25), TODAY))  # 14 days before


def test_started_on_is_the_middle_of_the_range():
    assert ex.started_on(ex.exposure_from_answer("1_3_days"), TODAY) == date(2026, 11, 6)
    assert ex.started_on(ex.exposure_from_answer("today"), TODAY) == TODAY


def test_only_new_symptoms_are_flagged():
    symptoms = [{"term_code": "SE_RASH", "onset": "1_3_days"}, {"term_code": "SE_FATIGUE", "onset": "today"}]
    cream = ex.exposure_from_answer("4_7_days")
    assert ex.possible_links(symptoms, [cream], previous_codes=set()) == {"SE_RASH", "SE_FATIGUE"}
    assert ex.possible_links(symptoms, [cream], previous_codes={"SE_FATIGUE"}) == {"SE_RASH"}
    assert ex.possible_links(symptoms, [], previous_codes=set()) == set()
