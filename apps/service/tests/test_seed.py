"""Seed and persistence: full-scale counts, contract-valid synthetic records, real trial rates, restart safety."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from conftest import TODAY
from sentinel_contract import CONTRACT_VERSION, SCHEMA_DIR, payload_sha256, validation_errors
from sentinel_service import demo_ids as ids
from sentinel_service.main import app
from sentinel_service.seed import arm_rates, is_seeded, seed, trial_map
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
    fixtures = json.loads((SCHEMA_DIR / "demo_fixtures.json").read_text())
    cohort_ids = [k["cohort_id"] for p in fixtures["programs"] for k in p["cohorts"]]
    assert summary["programs"] == 3 and summary["patients"] == 250 * len(cohort_ids) == 3000
    assert summary["weeks"] == ["2026-W42", "2026-W43", "2026-W44", "2026-W45"]
    assert summary["seconds"] < 60
    per_cohort = dict(q(s, "SELECT cohort_id, COUNT(*) FROM enrollment GROUP BY cohort_id"))
    assert per_cohort == {k: 250 for k in cohort_ids}
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
                   "consent": {"care_team": bool(r["consent_care_team"]), "caregiver": bool(r["consent_caregiver"])}}
        if r["source"] == "device":  # device records are full 2.0 company records
            payload.update(reporter=r["reporter"], input_mode=r["input_mode"])
            assert validation_errors("company_record", payload) == []
        else:
            assert r["status"] == "missed" and r["reporter"] is None and r["input_mode"] is None
        assert payload_sha256(payload) == r["payload_sha256"]
        assert r["source"] == ("scheduler" if r["status"] == "missed" else "device")


def test_known_side_effect_follows_the_label(full):
    s, _, _ = full
    known = dict(q(s, "SELECT term_code, MAX(known_side_effect) FROM symptom_record GROUP BY term_code"))
    assert known["SE_RASH"] == 1 and known["SE_DIARRHEA"] == 1
    assert known["SE_DYSPNEA"] == 1 and known["SE_COUGH"] == 1  # on both lung-cancer labels (C2 fix, D-079)
    assert known["SE_NASAL"] == 0  # common in infants on both MELODY arms, but on no label


def test_arm_rates_come_from_the_trial_extract():
    tm = trial_map()
    flaura = arm_rates("flaura", tm["meddra_to_term_code"])
    assert flaura["EG000"]["SE_DIARRHEA"] >= round(167 / 279, 4)  # osimertinib arm, non-serious table
    assert flaura["EG001"]["SE_RASH"] > flaura["EG000"]["SE_RASH"]  # comparator TKIs: more acne-like rash
    mariposa = arm_rates("mariposa", tm["meddra_to_term_code"])
    assert mariposa["EG000"]["SE_INFUSION_REACTION"] > 0.6  # 261/421 on amivantamab
    assert mariposa["EG001"]["SE_INFUSION_REACTION"] == mariposa["EG002"]["SE_INFUSION_REACTION"] == 0


def test_seeded_cohorts_follow_their_trial_arm(full):
    s, _, _ = full
    tm = trial_map()
    for program_id, spec in tm["programs"].items():
        rates = arm_rates(spec["trial"], tm["meddra_to_term_code"])
        for cohort_id, group in spec["cohorts"].items():
            n = q(s, "SELECT COUNT(*) FROM enrollment WHERE cohort_id = ?", cohort_id)[0][0]
            for term, p in rates[group].items():
                k = q(s, "SELECT COUNT(DISTINCT r.patient_ref) FROM checkin_record r JOIN symptom_record x "
                         "USING (record_id) WHERE r.cohort_id = ? AND x.term_code = ?", cohort_id, term)[0][0]
                assert abs(k / n - p) < 0.12, (cohort_id, term, p, k / n)  # share ever reporting ~ trial share
    infusion = dict(q(s, "SELECT r.cohort_id, COUNT(*) FROM checkin_record r JOIN symptom_record x USING (record_id) "
                         "WHERE x.term_code = 'SE_INFUSION_REACTION' GROUP BY r.cohort_id"))
    assert set(infusion) == {"cohort_ryb_A", "cohort_ryb_B"}  # amivantamab arms only


def test_programs_cohorts_and_documents_credit_their_sources(full):
    s, _, _ = full
    out = s.programs()
    assert out["company"]["display_name"] == "Halvaren Therapeutics"
    assert [p["source_trial"] for p in out["programs"]] == ["FLAURA NCT02296125", "MARIPOSA NCT04487080",
                                                            "MELODY NCT03979313"]
    assert all(k["source_arm"] and k["enrolled"] == 250 for p in out["programs"] for k in p["cohorts"])
    docs = s.documents(None)
    assert len(docs) == 9 and {d["kind"] for d in docs} == {"protocol", "sap", "label"}
    for d in docs:
        assert d["source_url"].startswith(("https://cdn.clinicaltrials.gov/large-docs/",
                                           "https://dailymed.nlm.nih.gov/"))


def test_relay_alerts_only_for_linked_patients(full):
    s, summary, _ = full
    linked = {r[0] for r in s.db.relay.execute("SELECT DISTINCT patient_ref FROM alert")}
    assert linked <= {ids.WALTER, ids.PRIYA} and summary["relay_alerts"] > 0
    for table in ("doctor", "organization"):  # keys are generated in browsers, never seeded (D-025)
        assert s.db.relay.execute(f"SELECT COUNT(*) FROM {table} WHERE public_key IS NOT NULL").fetchone()[0] == 0


def test_escalation_levels_follow_consecutive_misses(full):
    s, _, _ = full
    for patient in (ids.WALTER, ids.PRIYA):
        statuses = [r[0] for r in q(s, "SELECT status FROM checkin_record WHERE patient_ref = ? ORDER BY received_at",
                                    patient)]
        expected, run = [], 0
        for st in statuses:
            run = run + 1 if st == "missed" else 0
            if st == "missed":
                expected.append(min(run, 3))
        levels = [r[0] for r in s.db.relay.execute(
            "SELECT escalation_level FROM alert WHERE patient_ref = ? AND alert_type = 'missed' ORDER BY received_at",
            (patient,))]
        assert levels == expected
    deliveries = {tuple(r) for r in s.db.relay.execute(
        "SELECT a.escalation_level, d.recipient_type FROM alert a JOIN alert_delivery d ON d.alert_id = a.alert_id "
        "WHERE a.alert_type = 'missed'")}
    assert all(t != "emergency_contact" for lvl, t in deliveries if lvl < 3)  # contacts only at level 3 (D-068)
    assert {t for _, t in deliveries} >= {"patient", "care_team"}


def test_proxy_reporting_and_input_modes_present(full):
    s, _, _ = full
    reporters = dict(q(s, "SELECT reporter, COUNT(*) FROM checkin_record WHERE source = 'device' GROUP BY reporter"))
    modes = dict(q(s, "SELECT input_mode, COUNT(*) FROM checkin_record WHERE source = 'device' GROUP BY input_mode"))
    assert set(reporters) == {"self", "caregiver", "parent"}
    adults = reporters["self"] + reporters["caregiver"]
    assert 0.05 < reporters["caregiver"] / adults < 0.3
    infant = dict(q(s, "SELECT reporter, COUNT(*) FROM checkin_record WHERE source = 'device' "
                       "AND program_id = 'prog_beyfortus_01' GROUP BY reporter"))
    assert set(infant) == {"parent"}  # a parent answers for a baby (D-058)
    assert set(modes) == {"voice", "text", "mixed"}


def test_company_db_has_no_identifiers(full):
    s, _, _ = full
    cols = {r[1] for t in ("checkin_record", "symptom_record", "enrollment")
            for r in s.db.company.execute(f"PRAGMA table_info({t})")}
    assert not cols & {"display_name", "date_of_birth", "phone", "transcript_text", "patient_words"}
    fixtures = json.loads((SCHEMA_DIR / "demo_fixtures.json").read_text())
    dump = "\n".join(s.db.company.iterdump())
    for p in fixtures["device_profiles"]:
        assert p["display_name"] not in dump and p["phone"] not in dump and p["date_of_birth"] not in dump
    for contact in fixtures["emergency_contacts"]:  # emergency contacts live only in relay.db (D-067)
        # as stored SQL literals: a bare "911" also occurs inside hex hashes
        assert f"'{contact['phone']}'" not in dump and contact["contact_id"] not in dump


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
    assert meta == CONTRACT_VERSION
    s2.close()


def test_healthz_reports_seed_state(tmp_path):
    app.state.store = SqliteStore.open(tmp_path)
    try:
        with TestClient(app) as c:
            assert c.get("/healthz").json() == {"status": "ok", "contract_version": CONTRACT_VERSION, "seeded": False}
    finally:
        app.state.store.close()
        app.state.store = None


def test_existing_database_gains_new_columns(tmp_path):
    import sqlite3

    old = sqlite3.connect(tmp_path / "company.db")  # a 2.1 program table, before label/source columns
    old.execute("CREATE TABLE program (program_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, "
                "drug_name TEXT NOT NULL, created_at TEXT NOT NULL)")
    old.execute("INSERT INTO program VALUES ('prog_demo_01', 'co_demo', 'Tagrisso', '2026-10-01T00:00:00Z')")
    old.commit()
    old.close()
    s = SqliteStore.open(tmp_path)
    cols = {r[1] for r in s.db.company.execute("PRAGMA table_info(program)")}
    assert {"label", "source_trial"} <= cols
    assert s.programs()["programs"][0]["source_trial"] is None  # old rows keep working until a reseed
    s.close()


def test_demo_program_matches_first_listed_program():
    fx = json.loads((SCHEMA_DIR / "demo_fixtures.json").read_text())
    first = fx["programs"][0]
    assert {k: first[k] for k in fx["program"]} == fx["program"] and first["cohorts"] == fx["cohorts"]
    assert all(p["program_id"] in trial_map()["programs"] for p in fx["programs"])
