"""Missed check-in scheduler (AL-01; D-068, D-074, D-076). Times are fixed on demo day 2026-11-07 (UTC)."""

import json
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from conftest import TODAY
from sentinel_contract import SCHEMA_DIR
from sentinel_service import demo_ids as ids
from sentinel_service.demo import close_window
from sentinel_service.main import app
from sentinel_service.scheduler import due_days, run_missed_checks, window_bounds
from sentinel_service.seed import seed
from sentinel_service.store import SqliteStore


def at(hhmmss: str) -> datetime:
    return datetime.fromisoformat(f"2026-11-07T{hhmmss}+00:00")


@pytest.fixture()
def live(tmp_path):
    """Demo people with 4 weeks of history (Priya missed the last 2 days) plus 3 synthetic patients per cohort."""
    s = SqliteStore.open(tmp_path)
    seed(s.db, patients_per_cohort=3, weeks=4, today=TODAY)
    yield s
    s.close()


def test_due_days_and_windows():
    assert due_days(date(2026, 11, 1), 1, date(2026, 11, 5), date(2026, 11, 7)) == [
        date(2026, 11, 5), date(2026, 11, 6), date(2026, 11, 7)]
    assert due_days(date(2026, 11, 1), 3, date(2026, 11, 2), date(2026, 11, 10)) == [date(2026, 11, 4),
                                                                                    date(2026, 11, 7),
                                                                                    date(2026, 11, 10)]
    assert due_days(date(2026, 11, 8), 1, date(2026, 11, 1), date(2026, 11, 7)) == []
    start, end = window_bounds(date(2026, 11, 7), "22:00-02:00")  # crosses midnight
    assert (start.isoformat(), end.isoformat()) == ("2026-11-07T22:00:00+00:00", "2026-11-08T02:00:00+00:00")


def test_nothing_while_windows_are_open(live):
    assert run_missed_checks(live, now=at("13:30:00")) == []


def test_third_consecutive_miss_reaches_emergency_contacts(live):
    raised = run_missed_checks(live, now=at("14:00:01"))  # Priya's window 13:00-14:00 just closed
    assert [(r["patient_ref"], r["day"], r["escalation_level"]) for r in raised] == [(ids.PRIYA, "2026-11-07", 3)]
    assert raised[0]["notified"] == ["care_team", "emergency_contact", "patient"]  # no caregiver for Priya
    contacts = live.db.relay.execute(
        "SELECT recipient_id FROM alert_delivery WHERE alert_id = ? AND recipient_type = 'emergency_contact'",
        (raised[0]["alert_id"],)).fetchall()
    assert [r[0] for r in contacts] == ["ec_9e8d7c6b"]
    record = live.db.company.execute("SELECT status, source, received_at, reporter FROM checkin_record "
                                     "WHERE record_id = ?", (raised[0]["record_id"],)).fetchone()
    assert tuple(record) == ("missed", "scheduler", "2026-11-07T14:00:30.000000Z", None)


def test_runs_are_idempotent(live):
    assert len(run_missed_checks(live, now=at("14:00:01"))) == 1
    assert run_missed_checks(live, now=at("14:05:00")) == []


def test_a_check_in_today_prevents_the_alert(live):
    rec = json.loads((SCHEMA_DIR / "examples" / "company_record.valid.json").read_text())
    rec.update(patient_ref=ids.PRIYA, cohort_id="cohort_A", drug_version="v1")
    assert live.put_record(ids.PRIYA, rec)[0] == 201
    with live.db.tx(live.db.company):  # pin the receive time to demo day for this fixed-clock test
        live.db.company.execute("UPDATE checkin_record SET received_at = '2026-11-07T13:20:00.000000Z' "
                                "WHERE record_id = ?", (rec["record_id"],))
    assert run_missed_checks(live, now=at("14:00:01")) == []


def test_synthetic_patients_are_never_marked(live):
    raised = run_missed_checks(live, now=at("23:59:00"))  # every window has closed
    assert {r["patient_ref"] for r in raised} <= {ids.WALTER, ids.PRIYA}


def test_cadence_skips_days_that_are_not_due(live):
    survey = json.loads((SCHEMA_DIR / "examples" / "survey_config.valid.json").read_text())
    survey["schedule"] = {"every_days": 2}
    live.publish_survey(ids.ADMIN, "cohort_A", survey)
    start = live.db.company.execute("SELECT start_date FROM enrollment WHERE patient_ref = ?",
                                    (ids.PRIYA,)).fetchone()[0]
    due_today = (TODAY - date.fromisoformat(start)).days % 2 == 0
    raised = [r for r in run_missed_checks(live, now=at("14:00:01")) if r["patient_ref"] == ids.PRIYA]
    assert bool(raised) == due_today


def test_care_team_sees_the_alert_with_its_level(live):
    run_missed_checks(live, now=at("14:00:01"))
    app.state.store = live
    try:
        with TestClient(app) as c:
            alerts = c.get(f"/v1/orgs/{ids.NORTHGATE}/alerts", headers={"X-Role": "doctor",
                                                                       "X-Actor-Id": ids.DR_SHAH}).json()
    finally:
        app.state.store = None
    latest = alerts[-1]
    assert (latest["patient_ref"], latest["alert_type"], latest["escalation_level"]) == (ids.PRIYA, "missed", 3)
    levels = [a["escalation_level"] for a in alerts if a["patient_ref"] == ids.PRIYA and a["alert_type"] == "missed"]
    assert levels[-3:] == [1, 2, 3]  # yesterday's run continues today


def test_demo_close_window(live):
    now = datetime(2026, 11, 7, 18, 30, 15, tzinfo=timezone.utc)
    window = close_window(live, ids.WALTER, 60, now=now)
    assert window == "17:30-18:32"
    assert run_missed_checks(live, now=now) == [] or all(r["patient_ref"] != ids.WALTER
                                                         for r in run_missed_checks(live, now=now))
    raised = run_missed_checks(live, now=datetime(2026, 11, 7, 18, 32, 1, tzinfo=timezone.utc))
    assert [r["patient_ref"] for r in raised if r["patient_ref"] == ids.WALTER] == [ids.WALTER]
