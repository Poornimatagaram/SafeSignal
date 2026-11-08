"""Missed check-in scheduler (Scoping Doc AL-01; D-003, D-068, D-074).

For each live (non-synthetic) active enrollment, a check-in is due on every `every_days`-th day from
`enrollment.start_date` (cohort schedule from the latest survey). When a due day's window has closed and no device
record arrived that day, the scheduler:

1. writes a `missed` scheduler record to company.db (received_at = window end + 30 s, so the day is recorded
   deterministically even when the scheduler catches up late), and
2. raises a relay `missed` alert whose escalation_level is the run of consecutive missed due days (capped at 3),
   delivered to the recipients from `escalation.py` (level 3 adds consented emergency contacts).

Idempotent: a day that already has a scheduler record is never processed again. Reads patient IDs, dates and
consent flags only (Scoping Doc 26.7).
"""

from __future__ import annotations

import json
import secrets
from datetime import date, datetime, time, timedelta, timezone

from sentinel_contract import SCHEMA_VERSION, payload_sha256

from . import escalation
from .common import fmt_ts, iso_week, now_iso

LOOKBACK_DAYS = 31


def window_bounds(day: date, window: str) -> tuple[datetime, datetime]:
    """'HH:MM-HH:MM' in UTC (D-005). A window that ends at or before its start closes the next day."""
    start_s, end_s = window.split("-")
    start = datetime.combine(day, time.fromisoformat(start_s), tzinfo=timezone.utc)
    end = datetime.combine(day, time.fromisoformat(end_s), tzinfo=timezone.utc)
    if end <= start:
        end += timedelta(days=1)
    return start, end


def due_days(start: date, every_days: int, first: date, last: date) -> list[date]:
    """Due days d with first <= d <= last, counting every `every_days` days from `start`."""
    if last < start:
        return []
    offset = max((first - start).days, 0)
    d = start + timedelta(days=-(-offset // every_days) * every_days)
    out = []
    while d <= last:
        out.append(d)
        d += timedelta(days=every_days)
    return out


def _schedules(company) -> dict[str, int]:
    out = {}
    for row in company.execute("SELECT cohort_id, questions_json FROM survey_config s WHERE version = "
                               "(SELECT MAX(version) FROM survey_config t WHERE t.cohort_id = s.cohort_id)"):
        out[row["cohort_id"]] = json.loads(row["questions_json"]).get("schedule", {}).get("every_days", 1)
    return out


def run_missed_checks(store, now: datetime | None = None, lookback_days: int = LOOKBACK_DAYS) -> list[dict]:
    """Process every due day whose window closed by `now`. Returns one dict per missed check-in raised."""
    now = now or datetime.now(timezone.utc)
    c, r = store.db.company, store.db.relay
    first = now.date() - timedelta(days=lookback_days)
    schedules = _schedules(c)
    enrollments = c.execute(
        "SELECT e.patient_ref, e.program_id, e.cohort_id, e.checkin_window, e.start_date, k.drug_version "
        "FROM enrollment e JOIN cohort k ON k.cohort_id = e.cohort_id "
        "WHERE e.active = 1 AND e.synthetic = 0 ORDER BY e.patient_ref").fetchall()
    raised: list[dict] = []
    for e in enrollments:
        rows = c.execute("SELECT substr(received_at, 1, 10) AS day, source, consent_care_team, consent_caregiver "
                         "FROM checkin_record WHERE patient_ref = ? AND received_at >= ? ORDER BY received_at",
                         (e["patient_ref"], first.isoformat())).fetchall()
        device_days = {r_["day"] for r_ in rows if r_["source"] == "device"}
        scheduler_days = {r_["day"] for r_ in rows if r_["source"] == "scheduler"}
        consent = (rows[-1]["consent_care_team"], rows[-1]["consent_caregiver"]) if rows else (0, 0)
        every = schedules.get(e["cohort_id"], 1)
        streak = 0
        for d in due_days(date.fromisoformat(e["start_date"]), every, first, now.date()):
            _, closes = window_bounds(d, e["checkin_window"])
            if closes > now:
                break  # this and later windows are still open
            key = d.isoformat()
            if key in device_days:
                streak = 0
                continue
            streak += 1
            if key in scheduler_days:
                continue  # already recorded
            raised.append(_record_missed(store, e, d, closes, min(streak, 3), consent))
            scheduler_days.add(key)
    return raised


def _stamp(day: date, closes: datetime) -> str:
    """Company receive time for a missed record: 30 s after the window closes, kept on the due day itself so the
    day stays identifiable (and idempotent) even for windows that cross midnight."""
    at = closes + timedelta(seconds=30)
    if at.date() != day:
        at = datetime.combine(day, time(23, 59, 59), tzinfo=timezone.utc)
    return fmt_ts(at)


def _record_missed(store, e, day: date, closes: datetime, level: int, consent: tuple[int, int]) -> dict:
    c, r = store.db.company, store.db.relay
    record_id = f"rec_{secrets.token_hex(4)}"
    alert_id = f"alt_{secrets.token_hex(4)}"
    payload = {"schema_version": SCHEMA_VERSION, "record_id": record_id, "patient_ref": e["patient_ref"],
               "program_id": e["program_id"], "cohort_id": e["cohort_id"], "drug_version": e["drug_version"],
               "iso_week": iso_week(datetime.combine(day, time(12))), "status": "missed", "symptoms": [], "unanswered_questions": 0,
               "consent": {"care_team": bool(consent[0]), "caregiver": bool(consent[1])}}
    at = now_iso()
    with store.db.tx(c, r):
        c.execute("INSERT INTO checkin_record (record_id, schema_version, patient_ref, program_id, cohort_id, "
                  "drug_version, iso_week, status, unanswered_questions, consent_care_team, consent_caregiver, "
                  "payload_sha256, reporter, input_mode, source, received_at) "
                  "VALUES (?,?,?,?,?,?,?, 'missed', 0, ?, ?, ?, NULL, NULL, 'scheduler', ?)",
                  (record_id, SCHEMA_VERSION, e["patient_ref"], e["program_id"], e["cohort_id"], e["drug_version"],
                   payload["iso_week"], consent[0], consent[1], payload_sha256(payload), _stamp(day, closes)))
        r.execute("INSERT INTO alert (alert_id, patient_ref, alert_type, escalation_level, created_at, received_at) "
                  "VALUES (?, ?, 'missed', ?, ?, ?)", (alert_id, e["patient_ref"], level, fmt_ts(closes), at))
        targets = escalation.recipients(r, e["patient_ref"], "missed", level)
        escalation.record_deliveries(r, alert_id, targets, at)
    return {"patient_ref": e["patient_ref"], "day": day.isoformat(), "escalation_level": level,
            "alert_id": alert_id, "record_id": record_id, "notified": sorted({t for t, _ in targets})}
