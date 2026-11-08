"""The doctor payload: plaintext of a care envelope, built on the device (contract 2.0, D-066; task A7).

Pure: no network and no client import (only egress_gate.py may reach the service). The payload is sealed by
egress_gate before it leaves, so `display_name` is the one local field that may appear in it (never in the clear).

- `age_years` whole years from the date of birth.
- `compute_trend` the SE-05 trend over the last 7 approved check-ins.
- `build_doctor_payload` exactly the schema's fields from coded values only; validated.
- `doctor_payload_for_session` the payload of an approved session, rebuilt deterministically from the database.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from statistics import fmean

from sentinel_contract import SCHEMA_VERSION, validate

__all__ = ["SEVERITY_SCORE", "TREND_WINDOW", "age_years", "checkin_score", "compute_trend", "build_doctor_payload",
           "doctor_payload_for_session"]

SEVERITY_SCORE = {"mild": 1, "moderate": 2, "severe": 3}
TREND_WINDOW = 6       # earlier approved check-ins compared with today's (7 in all)
TREND_MARGIN = 0.5


def age_years(date_of_birth: str, on: date) -> int:
    """Whole years from `date_of_birth` ("YYYY-MM-DD") to `on`."""
    born = date.fromisoformat(date_of_birth)
    return on.year - born.year - ((on.month, on.day) < (born.month, born.day))


def checkin_score(symptoms: Sequence[Mapping]) -> int:
    """Sum of severity scores (mild 1, moderate 2, severe 3); a check-in with no symptoms scores 0."""
    return sum(SEVERITY_SCORE[s["severity"]] for s in symptoms)


def compute_trend(current: Sequence[Mapping], previous: Sequence[Sequence[Mapping]]) -> str:
    """SE-05 trend of today's check-in against the earlier ones.

    Rule: each check-in scores the sum of its symptoms' severities (mild 1, moderate 2, severe 3; none = 0).
    `previous` holds the symptoms of up to the 6 earlier approved check-ins, oldest first (7 with today); only the
    newest 6 count. With no earlier check-in the trend is "unknown". Otherwise, with m = mean of the earlier scores:
    today > m + 0.5 -> "worse"; today < m - 0.5 -> "better"; else "same".
    """
    window = list(previous)[-TREND_WINDOW:]
    if not window:
        return "unknown"
    mean = fmean(checkin_score(p) for p in window)
    today = checkin_score(current)
    if today > mean + TREND_MARGIN:
        return "worse"
    if today < mean - TREND_MARGIN:
        return "better"
    return "same"


def _flag(value):
    """0/1 from SQLite -> bool; anything else is left as is so the schema refuses it instead of guessing."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    return value


def build_doctor_payload(*, profile: Mapping, symptoms: Sequence[Mapping], status: str, trend: str,
                         checkin_date: str, reporter: str) -> dict:
    """The 2.0 doctor payload with exactly the schema's fields; raises ContractError if it is not valid.

    Copies only the coded fields: nothing else in `profile` (date of birth, phone, ...) or the symptom mappings
    (patient words, transcripts) can reach it. `age_years` is the age on `checkin_date`. A profile without a date of
    birth raises ValueError: the payload cannot be built (never guessed).
    """
    dob = profile["date_of_birth"] if "date_of_birth" in profile.keys() else None
    if not dob:
        raise ValueError("the profile has no date of birth; the doctor payload needs age_years")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "patient_ref": profile["patient_ref"],
        "display_name": profile["display_name"],
        "drug_name": profile["drug_name"],
        "drug_version": profile["drug_version"],
        "checkin_date": checkin_date,
        "status": status,
        "trend": trend,
        "symptoms": [{"term_code": s["term_code"], "severity": s["severity"], "onset": s["onset"],
                      "known_side_effect": _flag(s["known_side_effect"]),
                      "possible_link_flag": _flag(s["possible_link_flag"])} for s in symptoms],
        "reporter": reporter,
        "age_years": age_years(dob, date.fromisoformat(checkin_date)),
    }
    validate("doctor_payload", payload)  # ContractError names fields only, never values
    return payload


def _local_date(timestamp: str) -> str:
    """Local calendar date of a stored timestamp (UTC "...Z" or any ISO 8601 with offset)."""
    if timestamp.endswith("Z"):
        timestamp = timestamp[:-1] + "+00:00"
    return datetime.fromisoformat(timestamp).astimezone().date().isoformat()


_SYMPTOMS = ("SELECT term_code, severity, onset, known_side_effect, possible_link_flag FROM symptom_event "
             "WHERE session_id = ? ORDER BY rowid")


def doctor_payload_for_session(conn: sqlite3.Connection, session_id: str, patient_ref: str) -> dict:
    """The doctor payload of an approved session (ended_at set), from the database only.

    Symptoms are the session's symptom_event rows (in the order they were approved); status and reporter come from
    the session; checkin_date is the local date the session started; the trend compares it with up to 6 earlier
    approved sessions (ended before this one; same-second ties by insertion order). Rebuilding the same session gives the same payload.
    Raises LookupError for an unknown profile or session, ValueError for a session not yet approved or a profile
    without a date of birth, ContractError if the result is not schema-valid.
    """
    profile = conn.execute("SELECT * FROM patient_profile WHERE patient_ref = ?", (patient_ref,)).fetchone()
    if profile is None:
        raise LookupError("no profile for this patient_ref")
    session = conn.execute("SELECT rowid, started_at, ended_at, status, reporter FROM checkin_session "
                           "WHERE session_id = ?", (session_id,)).fetchone()
    if session is None:
        raise LookupError(f"no session {session_id}")
    if session["ended_at"] is None:
        raise ValueError(f"session {session_id} is not approved")
    symptoms = [dict(r) for r in conn.execute(_SYMPTOMS, (session_id,))]
    # ended_at has 1-second resolution: two approvals in the same second are ordered by insertion (rowid)
    earlier = conn.execute("SELECT session_id FROM checkin_session WHERE ended_at IS NOT NULL "
                           "AND (ended_at < ? OR (ended_at = ? AND rowid < ?)) "
                           "ORDER BY ended_at DESC, rowid DESC LIMIT ?",
                           (session["ended_at"], session["ended_at"], session["rowid"], TREND_WINDOW)).fetchall()
    previous = [[dict(r) for r in conn.execute(_SYMPTOMS, (row["session_id"],))] for row in reversed(earlier)]
    return build_doctor_payload(profile=dict(profile), symptoms=symptoms, status=session["status"],
                                trend=compute_trend(symptoms, previous), checkin_date=_local_date(session["started_at"]),
                                reporter=session["reporter"])
