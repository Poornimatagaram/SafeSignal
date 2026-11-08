"""Contract tests: schema files, examples, hash vectors and SQL. Run on every build."""

import json
import re
import sqlite3
from pathlib import Path

import pytest

from sentinel_contract import SCHEMA_DIR, PAYLOAD_SCHEMAS, canonical, enums, payload_sha256, validation_errors

EX = SCHEMA_DIR / "examples"


@pytest.mark.parametrize("kind", sorted(PAYLOAD_SCHEMAS))
def test_valid_example_passes(kind):
    payload = json.loads((EX / f"{kind}.valid.json").read_text())
    assert validation_errors(kind, payload) == []


@pytest.mark.parametrize("kind", sorted(PAYLOAD_SCHEMAS))
def test_invalid_example_fails_on_named_field(kind):
    doc = json.loads((EX / f"{kind}.invalid.json").read_text())
    fields = [e["field"] for e in validation_errors(kind, doc["payload"])]
    assert doc["_expect"]["field"] in fields


def test_hash_vectors():
    for v in json.loads((EX / "hash_vectors.json").read_text())["vectors"]:
        assert canonical(v["input"]).decode() == v["canonical"], v["name"]
        assert payload_sha256(v["input"]) == v["sha256"], v["name"]


def test_error_messages_never_echo_values():
    doc = json.loads((EX / "company_record.invalid.json").read_text())
    rendered = json.dumps(validation_errors("company_record", doc["payload"]))
    assert "grandson" not in rendered


def test_no_free_text_in_company_record_schema():
    """Section 14.1 rule 1: every string field is an enum, const or pattern-bound ID."""
    schema = json.loads((SCHEMA_DIR / "company_record.json").read_text())

    def walk(node, path):
        if isinstance(node, dict):
            if node.get("type") == "string":
                assert "pattern" in node or "enum" in node or "const" in node, path
            for k, v in node.items():
                walk(v, f"{path}/{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}/{i}")

    walk(schema, "")


def test_enums_match_schemas():
    e = enums()
    rec = json.loads((SCHEMA_DIR / "company_record.json").read_text())["properties"]
    sym = rec["symptoms"]["items"]["properties"]
    assert rec["cohort_id"]["pattern"] == e["id_patterns"]["cohort_id"]  # 2.2: cohorts unique across programs
    assert all(re.match(e["id_patterns"]["cohort_id"], k) for k in e["cohort_id"])
    assert rec["drug_version"]["enum"] == e["drug_version"]
    assert rec["status"]["enum"] == e["checkin_status"]
    assert sym["term_code"]["enum"] == e["term_code"]
    assert sym["severity"]["enum"] == e["severity"]
    assert sym["onset"]["enum"] == e["onset"]
    terms = [t["term_code"] for t in json.loads((SCHEMA_DIR / "terms.json").read_text())["terms"]]
    assert terms == e["term_code"]


@pytest.mark.parametrize("sql", ["company.sql", "relay.sql", "patient.sql", "doctor_view.sql"])
def test_sql_applies_twice(sql, tmp_path: Path):
    db = sqlite3.connect(tmp_path / "t.db")
    script = (SCHEMA_DIR / sql).read_text()
    db.executescript(script)
    db.executescript(script)  # idempotent (26.11)
    db.close()


def test_cohort_view_suppresses_small_groups(tmp_path: Path):
    db = sqlite3.connect(tmp_path / "c.db")
    db.executescript((SCHEMA_DIR / "company.sql").read_text())
    db.execute("INSERT INTO program (program_id, company_id, drug_name, created_at) "
               "VALUES ('prog_demo_01','co','Tagrisso','t')")
    db.execute("INSERT INTO cohort (cohort_id, program_id, drug_version, label, target_size) "
               "VALUES ('cohort_B','prog_demo_01','v2','B',250)")
    db.execute("INSERT INTO term_code VALUES ('SE_RASH','Rash','[]','[]',0)")
    db.execute("INSERT INTO term_code VALUES ('SE_COUGH','Cough','[]','[]',0)")
    for i in range(6):
        p = f"pt_0000000{i}"
        db.execute("INSERT INTO enrollment (patient_ref, program_id, cohort_id, checkin_window, start_date, active) "
                   "VALUES (?, 'prog_demo_01','cohort_B','14:00-17:00','2026-11-02',1)", (p,))
        r = f"rec_0000000{i}"
        db.execute("INSERT INTO checkin_record (record_id, schema_version, patient_ref, program_id, cohort_id, "
                   "drug_version, iso_week, status, unanswered_questions, consent_care_team, consent_caregiver, "
                   "payload_sha256, reporter, input_mode, source, received_at) VALUES (?, '2.0', ?, 'prog_demo_01', "
                   "'cohort_B','v2','2026-W45','completed',0,1,1,'h','self','voice','device','t')", (r, p))
        db.execute("INSERT INTO symptom_record (record_id, term_code, severity, onset, known_side_effect, "
                   "possible_link_flag) VALUES (?, 'SE_RASH', ?, 'today', 1, 0)", (r, "severe" if i < 2 else "mild"))
        if i < 3:  # only 3 patients with cough -> suppressed
            db.execute("INSERT INTO symptom_record (record_id, term_code, severity, onset, known_side_effect, "
                       "possible_link_flag) VALUES (?, 'SE_COUGH', 'mild', 'today', 0, 0)", (r,))
    rows = db.execute("SELECT term_code, patients, severe_patients, reporting_patients FROM v_cohort_weekly").fetchall()
    assert rows == [("SE_RASH", 6, None, 6)]  # cough dropped; 2 severe shown as NULL (<5)
    comp = db.execute("SELECT records, patients, completion_rate FROM v_completion_weekly").fetchall()
    assert comp == [(6, 6, 1.0)]


def test_demo_fixtures_match_contract():
    import re
    f = json.loads((SCHEMA_DIR / "demo_fixtures.json").read_text())
    pat = enums()["id_patterns"]
    cohorts = {c["cohort_id"]: c["drug_version"] for c in f["cohorts"]}
    every = [c["cohort_id"] for p in f["programs"] for c in p["cohorts"]]
    assert sorted(every) == sorted(enums()["cohort_id"]) and len(set(every)) == len(every)
    assert set(cohorts) <= set(every)
    assert re.match(pat["company_id"], f["company"]["company_id"])
    assert all(p["company_id"] == f["company"]["company_id"] for p in f["programs"])
    assert re.match(pat["program_id"], f["program"]["program_id"])
    for d in f["doctors"]:
        assert re.match(pat["doctor_id"], d["doctor_id"])
    for c in f["caregivers"]:
        assert re.match(pat["caregiver_id"], c["caregiver_id"])
    for u in f["company_users"]:
        assert re.match(pat["company_user_id"], u["user_id"]) and u["role"] in enums()["roles"]
    enrolled = {e["patient_ref"]: e for e in f["enrollments"]}
    for p in f["device_profiles"]:
        assert re.match(pat["patient_ref"], p["patient_ref"])
        e = enrolled[p["patient_ref"]]
        assert (p["program_id"], p["cohort_id"]) == (e["program_id"], e["cohort_id"])
        assert p["drug_version"] == cohorts[p["cohort_id"]]
        assert p["drug_name"] == f["program"]["drug_name"]
        assert re.match(r"^[0-2][0-9]:[0-5][0-9]-[0-2][0-9]:[0-5][0-9]$", e["checkin_window"])  # D-005 UTC window


def test_fixture_organizations_links_and_contacts():
    import re
    f = json.loads((SCHEMA_DIR / "demo_fixtures.json").read_text())
    pat = enums()["id_patterns"]
    orgs = {o["org_id"] for o in f["organizations"]}
    doctors = {d["doctor_id"] for d in f["doctors"]}
    assert all(re.match(pat["org_id"], o) for o in orgs)
    assert all(m["org_id"] in orgs and m["doctor_id"] in doctors and m["role"] in enums()["org_role"]
               for m in f["org_members"])
    assert any(m["role"] == "admin" for m in f["org_members"])  # someone can register org keys and grant access
    assert all(l["org_id"] in orgs and l["link_type"] in enums()["care_link_type"] for l in f["care_links"])
    for c in f["emergency_contacts"]:
        assert re.match(pat["contact_id"], c["contact_id"]) and re.match(pat["phone"], c["phone"])
        assert c["org_id"] is None or c["org_id"] in orgs
    profiles = {p["patient_ref"]: p for p in f["device_profiles"]}
    for p in profiles.values():  # emergency data only with emergency consent (D-067)
        if not p["consent"]["emergency_consent"]:
            assert not p["emergency_org_ids"]
            assert not [c for c in f["emergency_contacts"] if c["patient_ref"] == p["patient_ref"]]


def test_consent_schema_blocks_emergency_data_without_consent():
    doc = json.loads((EX / "consent_update.valid.json").read_text())
    doc["emergency_consent"] = False
    fields = {e["field"] for e in validation_errors("consent_update", doc)}
    assert {"/emergency_org_ids", "/emergency_contacts"} <= fields
    doc["emergency_org_ids"], doc["emergency_contacts"] = [], []
    assert validation_errors("consent_update", doc) == []
