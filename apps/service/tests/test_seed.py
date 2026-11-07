"""Seed and persistence: full-scale counts, contract-valid synthetic records, the v2 signal, restart safety."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from conftest import TODAY
from sentinel_contract import SCHEMA_DIR, payload_sha256, validation_errors
from sentinel_service import demo_ids as ids
from sentinel_service.main import app
from sentinel_service.seed import is_seeded, seed
from sentinel_service.store import SqliteStore


@pytest.fixture(scope="module")
def full(tmp_path_factory):
    path = tmp_path_factory.mktemp("full")
    s = SqliteStore.open(path)
    t0 = time.perf_counter()
    summary = seed(s.db, today=TODAY)  # defaults: 250 per cohort, 4 weeks
    summary["seconds"] = time.perf_counter() - t0
    yield s, summary, path
    s.close()


def q(store, sql, *args):
    return store.db.company.execute(sql, args).fetchall()


def test_full_scale_counts(full):
    s, summary, _ = full
    assert summary["patients"] == 1000
    assert summary["weeks"] == ["2026-W42", "2026-W43", "2026-W44", "2026-W45"]
    assert summary["seconds"] < 30
    per_cohort = dict(q(s, "SELECT cohort_id, COUNT(*) FROM enrollment GROUP BY cohort_id"))
    assert per_cohort == {"cohort_A": 250, "cohort_B": 250, "cohort_C": 250, "cohort_D": 250}
    assert q(s, "SELECT cohort_id FROM enrollment WHERE patient_ref = ?", ids.WALTER)[0][0] == "cohort_B"


def test_today_is_left_for_the_live_demo(full):
    s, _, _ = full
    latest = q(s, "SELECT MAX(received_at) FROM checkin_record WHERE status != 'missed'")[0][0]
    assert latest < TODAY.isoformat()
    first_walter = q(s, "SELECT MIN(received_at) FROM checkin_record WHERE patient_ref = ?", ids.WALTER)[0][0]
    assert first_walter >= "2026-10-17"  # no check-ins before he enrolled


def test_synthetic_records_are_contract_valid_and_hashed(full):
    s, _, _ = full
    rows = q(s, "SELECT * FROM checkin_record ORDER BY record_id LIMIT 300")
    for r in rows:
        syms = [{"term_code": x["term_code"], "severity": x["severity"], "onset": x["onset"],
                 "known_side_effect": bool(x["known_side_effect"]), "possible_link_flag": bool(x["possible_link_flag"])}
                for x in q(s, "SELECT * FROM symptom_record WHERE record_id = ? ORDER BY id", r["record_id"])]
        payload = {"schema_version": r["schema_version"], "record_id": r["record_id"], "patient_ref": r["patient_ref"],
                   "program_id": r["program_id"], "cohort_id": r["cohort_id"], "drug_version": r["drug_version"],
                   "iso_week": r["iso_week"], "status": r["status"], "symptoms": syms,
                   "unanswered_questions": r["unanswered_questions"],
                   "consent": {"doctor": bool(r["consent_doctor"]), "caregiver": bool(r["consent_caregiver"])}}
        assert validation_errors("company_record", payload) == []
        assert payload_sha256(payload) == r["payload_sha256"]
        assert r["source"] == ("scheduler" if r["status"] == "missed" else "device")


def test_known_side_effect_follows_the_label(full):
    s, _, _ = full
    known = dict(q(s, "SELECT term_code, MAX(known_side_effect) FROM symptom_record GROUP BY term_code"))
    assert known["SE_RASH"] == 1 and known["SE_DIARRHEA"] == 1
    assert known["SE_DYSPNEA"] == 0 and known["SE_COUGH"] == 0  # reported for Tagrisso, not on its label in terms.json


def test_v2_dermatologic_signal_rises(full):
    s, _, _ = full
    rows = {(r["cohort_id"], r["iso_week"]): r["patients"] / r["reporting_patients"]
            for r in s.cohorts_weekly(ids.PROGRAM_ID) if r["term_code"] == "SE_RASH"}
    assert rows[("cohort_B", "2026-W45")] > rows[("cohort_B", "2026-W42")]
    for other in ("cohort_A", "cohort_C", "cohort_D"):
        assert rows[("cohort_B", "2026-W45")] > rows[(other, "2026-W45")]


def test_relay_alerts_only_for_linked_patients(full):
    s, summary, _ = full
    linked = {r[0] for r in s.db.relay.execute("SELECT DISTINCT patient_ref FROM alert")}
    assert linked <= {ids.WALTER, ids.PRIYA} and summary["relay_alerts"] > 0
    assert s.db.relay.execute("SELECT COUNT(*) FROM doctor WHERE public_key IS NOT NULL").fetchone()[0] == 0  # D-025


def test_company_db_has_no_identifiers(full):
    s, _, _ = full
    cols = {r[1] for t in ("checkin_record", "symptom_record", "enrollment")
            for r in s.db.company.execute(f"PRAGMA table_info({t})")}
    assert not cols & {"display_name", "date_of_birth", "phone", "transcript_text", "patient_words"}
    fixtures = json.loads((SCHEMA_DIR / "demo_fixtures.json").read_text())
    dump = "\n".join(s.db.company.iterdump())
    for p in fixtures["device_profiles"]:
        assert p["display_name"] not in dump and p["phone"] not in dump and p["date_of_birth"] not in dump


def test_seed_is_idempotent_and_data_survives_restart(tmp_path):
    s = SqliteStore.open(tmp_path)
    seed(s.db, patients_per_cohort=0, weeks=0, today=TODAY)
    assert is_seeded(s.db)
    rec = json.loads((SCHEMA_DIR / "examples" / "company_record.valid.json").read_text())
    assert s.put_record(ids.WALTER, rec)[0] == 201
    s.close()

    s2 = SqliteStore.open(tmp_path)  # "restart"
    assert is_seeded(s2.db)
    assert s2.put_record(ids.WALTER, rec)[0] == 200  # still there, idempotent
    meta = s2.db.company.execute("SELECT schema_version FROM schema_meta").fetchone()[0]
    assert meta == "1.1"
    s2.close()


def test_healthz_reports_seed_state(tmp_path):
    app.state.store = SqliteStore.open(tmp_path)
    try:
        with TestClient(app) as c:
            assert c.get("/healthz").json() == {"status": "ok", "contract_version": "1.1", "seeded": False}
    finally:
        app.state.store.close()
        app.state.store = None
