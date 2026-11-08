"""Task A7 doctor payload (D-066, SE-05): age, trend, the coded-only payload and the session builder."""

import json
from contextlib import closing
from datetime import date, datetime

import pytest

from sentinel_contract import SCHEMA_DIR, ContractError, validate
from sentinel_patient import care_payload as cp
from sentinel_patient.config import WALTER
from sentinel_patient.db import connect, init_db

DOCTOR_FIELDS = set(json.loads((SCHEMA_DIR / "doctor_payload.json").read_text())["properties"])
LOCAL_ONLY = ("1934-03-12", "555-0142")  # Walter's date_of_birth and phone (local only, never in the payload)
RASH = {"term_code": "SE_RASH", "severity": "moderate", "onset": "1_3_days", "known_side_effect": 1,
        "possible_link_flag": 0}


def sym(severity, code="SE_RASH"):
    return {"term_code": code, "severity": severity, "onset": "today", "known_side_effect": 1,
            "possible_link_flag": 0}


# ---------- age ----------

@pytest.mark.parametrize("dob, on, age", [
    ("1934-03-12", date(2026, 11, 7), 92),
    ("1934-03-12", date(2026, 3, 11), 91),   # the day before the birthday
    ("1934-03-12", date(2026, 3, 12), 92),   # on the birthday
    ("2026-01-01", date(2026, 11, 7), 0),    # an infant
    ("2000-02-29", date(2026, 2, 28), 25),   # leap-day birthday
    ("2000-02-29", date(2026, 3, 1), 26),
])
def test_age_years_is_whole_years(dob, on, age):
    assert cp.age_years(dob, on) == age


# ---------- trend (SE-05) ----------

def test_trend_is_unknown_without_earlier_checkins():
    assert cp.compute_trend([sym("severe")], []) == "unknown"
    assert cp.compute_trend([], []) == "unknown"


def test_checkin_score_sums_severities():
    assert cp.checkin_score([]) == 0
    assert cp.checkin_score([sym("mild"), sym("moderate", "SE_FATIGUE"), sym("severe", "SE_COUGH")]) == 6


@pytest.mark.parametrize("current, previous, trend", [
    ([sym("moderate")], [[sym("moderate")]], "same"),                      # 2 vs 2
    ([sym("severe")], [[sym("moderate")]], "worse"),                       # 3 > 2.5
    ([sym("mild")], [[sym("moderate")]], "better"),                        # 1 < 1.5
    ([], [[sym("mild")]], "better"),                                       # 0 < 0.5
    ([sym("mild")], [[], [sym("mild")]], "same"),                          # mean 0.5: 1 is not > 1.0
    ([sym("moderate")], [[], [sym("mild")]], "worse"),                     # 2 > 1.0
    ([sym("mild")], [[sym("mild")], [sym("moderate")]], "same"),           # mean 1.5: 1 is not < 1.0
    ([], [[sym("mild")], [sym("moderate")]], "better"),
])
def test_trend_rule(current, previous, trend):
    assert cp.compute_trend(current, previous) == trend


def test_trend_uses_only_the_newest_six_earlier_checkins():
    # 7 check-ins with today: a severe one 7 check-ins ago falls out of the window
    old = [[sym("severe"), sym("severe", "SE_COUGH")]]
    recent = [[sym("mild")]] * 6
    assert cp.compute_trend([sym("mild")], old + recent) == "same"
    assert cp.compute_trend([sym("mild")], [[sym("severe"), sym("severe", "SE_COUGH")]] + recent[:5]) == "better"


# ---------- build ----------

PROFILE = {"patient_ref": WALTER, "display_name": "Walter", "date_of_birth": "1934-03-12", "phone": "555-0142",
           "program_id": "prog_demo_01", "cohort_id": "cohort_B", "drug_name": "Tagrisso", "drug_version": "v2",
           "care_org_id": "org_5e1a2b3c"}


def test_build_matches_the_schema_example_and_copies_only_coded_fields():
    symptom = {**RASH, "possible_link_flag": 1, "patient_words": "itchy all over", "transcript_text": "call me"}
    payload = cp.build_doctor_payload(profile=PROFILE, symptoms=[symptom], status="completed", trend="worse",
                                      checkin_date="2026-11-07", reporter="self")
    example = json.loads((SCHEMA_DIR / "examples" / "doctor_payload.valid.json").read_text())
    assert payload == example
    assert set(payload) == DOCTOR_FIELDS
    text = json.dumps(payload)
    for value in LOCAL_ONLY + ("itchy", "call me", "phone", "date_of_birth", "patient_words", "prog_demo_01"):
        assert value not in text
    validate("doctor_payload", payload)


def test_build_maps_flags_to_booleans_and_age_on_the_checkin_date():
    payload = cp.build_doctor_payload(profile={**PROFILE, "date_of_birth": "1934-11-08"}, symptoms=[RASH],
                                      status="partial", trend="unknown", checkin_date="2026-11-07", reporter="parent")
    assert payload["symptoms"][0]["known_side_effect"] is True
    assert payload["symptoms"][0]["possible_link_flag"] is False
    assert (payload["age_years"], payload["status"], payload["reporter"]) == (91, "partial", "parent")


def test_build_without_a_date_of_birth_cannot_be_built():
    with pytest.raises(ValueError, match="date of birth"):
        cp.build_doctor_payload(profile={**PROFILE, "date_of_birth": None}, symptoms=[], status="completed",
                                trend="same", checkin_date="2026-11-07", reporter="self")


@pytest.mark.parametrize("change", [{"severity": "terrible"}, {"term_code": "rash"}, {"known_side_effect": "yes"}])
def test_build_refuses_invalid_values(change):
    with pytest.raises(ContractError) as exc:
        cp.build_doctor_payload(profile=PROFILE, symptoms=[{**RASH, **change}], status="completed", trend="same",
                                checkin_date="2026-11-07", reporter="self")
    assert str(next(iter(change.values()))) not in str(exc.value)


# ---------- from the database ----------

@pytest.fixture()
def db_path(tmp_path):
    path = tmp_path / "patient.db"
    init_db(path, WALTER)
    with closing(connect(path)) as conn, conn:
        conn.execute("INSERT INTO survey_cache VALUES ('cfg_cohort_b_v1', 'cohort_B', 1, '{}', '2026-10-17T15:00:00Z')")
        conn.executemany("INSERT INTO term_cache VALUES (?, ?, '[]', 0, 1)",
                         [("SE_RASH", "Rash"), ("SE_FATIGUE", "Fatigue"), ("SE_COUGH", "Cough")])
    return path


def add_session(path, session_id, day, symptoms=(), *, approved=True, status="completed", reporter="self"):
    started = f"2026-11-{day:02d}T15:00:00Z"
    with closing(connect(path)) as conn, conn:
        conn.execute("INSERT INTO checkin_session (session_id, config_id, started_at, ended_at, status, reporter) "
                     "VALUES (?, 'cfg_cohort_b_v1', ?, ?, ?, ?)",
                     (session_id, started, f"2026-11-{day:02d}T15:10:00Z" if approved else None, status, reporter))
        for i, s in enumerate(symptoms):
            conn.execute("INSERT INTO symptom_event (event_id, session_id, term_code, severity, onset, "
                         "known_side_effect, possible_link_flag, patient_words, created_at) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?, 'my own words', ?)",
                         (f"sym_{session_id}_{i}", session_id, s["term_code"], s["severity"], s["onset"],
                          s["known_side_effect"], s["possible_link_flag"], started))


def local_day(day):
    return datetime.fromisoformat(f"2026-11-{day:02d}T15:00:00+00:00").astimezone().date().isoformat()


def build(path, session_id):
    with closing(connect(path)) as conn:
        return cp.doctor_payload_for_session(conn, session_id, WALTER)


def test_session_payload_from_the_database(db_path):
    add_session(db_path, "ses_old", 5, [sym("mild")])
    add_session(db_path, "ses_today", 7, [RASH, sym("mild", "SE_FATIGUE")], status="partial", reporter="caregiver")
    payload = build(db_path, "ses_today")
    assert payload == {
        "schema_version": "2.0", "patient_ref": WALTER, "display_name": "Walter", "drug_name": "Tagrisso",
        "drug_version": "v2", "checkin_date": local_day(7), "status": "partial", "trend": "worse",  # 3 > 1.5
        "symptoms": [{"term_code": "SE_RASH", "severity": "moderate", "onset": "1_3_days", "known_side_effect": True,
                      "possible_link_flag": False},
                     {"term_code": "SE_FATIGUE", "severity": "mild", "onset": "today", "known_side_effect": True,
                      "possible_link_flag": False}],
        "reporter": "caregiver", "age_years": 92}
    assert "my own words" not in json.dumps(payload)
    assert build(db_path, "ses_today") == payload  # deterministic
    assert build(db_path, "ses_old")["trend"] == "unknown"  # nothing approved before it


def test_session_trend_uses_only_earlier_approved_sessions_up_to_six(db_path):
    add_session(db_path, "ses_a", 1, [sym("severe"), sym("severe", "SE_COUGH")])  # 7th back: outside the window
    for day in range(2, 8):
        add_session(db_path, f"ses_{day}", day, [sym("mild")] if day % 2 else [])     # scores 0/1, mean 0.5
    add_session(db_path, "ses_unapproved", 8, [sym("severe")], approved=False)        # not approved: ignored
    add_session(db_path, "ses_today", 9, [])
    add_session(db_path, "ses_later", 10, [sym("severe")])                            # after it: ignored
    assert build(db_path, "ses_today")["trend"] == "same"  # 0 is not < 0.5 - 0.5 (with ses_a: 9/7, "better")
    with closing(connect(db_path)) as conn, conn:
        conn.execute("DELETE FROM symptom_event WHERE session_id = 'ses_7'")
        conn.execute("DELETE FROM checkin_session WHERE session_id = 'ses_7'")  # ses_a slides into the window
    assert build(db_path, "ses_today")["trend"] == "better"  # mean (6+2)/6; without ses_a it would be "same"


def test_same_second_approvals_are_ordered_by_insertion(db_path):
    add_session(db_path, "ses_z", 7, [sym("severe")])
    add_session(db_path, "ses_a", 7, [])  # same ended_at, approved after ses_z
    assert build(db_path, "ses_z")["trend"] == "unknown"
    assert build(db_path, "ses_a")["trend"] == "better"


def test_session_with_no_symptoms_and_errors(db_path):
    add_session(db_path, "ses_1", 6, [sym("moderate")])
    add_session(db_path, "ses_2", 7, [])
    assert build(db_path, "ses_2")["symptoms"] == [] and build(db_path, "ses_2")["trend"] == "better"
    add_session(db_path, "ses_open", 8, [], approved=False)
    with pytest.raises(ValueError, match="not approved"):
        build(db_path, "ses_open")
    with pytest.raises(LookupError):
        build(db_path, "ses_missing")
    with closing(connect(db_path)) as conn:
        with pytest.raises(LookupError):
            cp.doctor_payload_for_session(conn, "ses_2", "pt_00000000")
    with closing(connect(db_path)) as conn, conn:
        conn.execute("UPDATE patient_profile SET date_of_birth = NULL")
    with pytest.raises(ValueError, match="date of birth"):
        build(db_path, "ses_2")


def test_local_date_handles_z_and_offsets():
    assert cp._local_date("2026-11-07T15:00:00Z") == local_day(7)
    assert cp._local_date("2026-11-07T15:00:00+00:00") == local_day(7)
