"""Contract tests: schema files, examples, hash vectors and SQL. Run on every build."""

import json
import sqlite3
from pathlib import Path

import pytest

from contract import SCHEMA_DIR, PAYLOAD_SCHEMAS, canonical, enums, payload_sha256, validation_errors

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
    assert rec["cohort_id"]["enum"] == e["cohort_id"]
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
    db.execute("INSERT INTO program VALUES ('prog_demo_01','co','Tagrisso','t')")
    db.execute("INSERT INTO cohort VALUES ('cohort_B','prog_demo_01','v2','B',250)")
    db.execute("INSERT INTO term_code VALUES ('SE_RASH','Rash','[]','[]',0)")
    db.execute("INSERT INTO term_code VALUES ('SE_COUGH','Cough','[]','[]',0)")
    for i in range(6):
        p = f"pt_0000000{i}"
        db.execute("INSERT INTO enrollment VALUES (?, 'prog_demo_01','cohort_B','14:00-17:00',1)", (p,))
        r = f"rec_0000000{i}"
        db.execute("INSERT INTO checkin_record VALUES (?, '1.0', ?, 'prog_demo_01','cohort_B','v2','2026-W45',"
                   "'completed',0,1,1,'h','device','t')", (r, p))
        db.execute("INSERT INTO symptom_record (record_id, term_code, severity, onset, known_side_effect, "
                   "possible_link_flag) VALUES (?, 'SE_RASH', ?, 'today', 1, 0)", (r, "severe" if i < 2 else "mild"))
        if i < 3:  # only 3 patients with cough -> suppressed
            db.execute("INSERT INTO symptom_record (record_id, term_code, severity, onset, known_side_effect, "
                       "possible_link_flag) VALUES (?, 'SE_COUGH', 'mild', 'today', 0, 0)", (r,))
    rows = db.execute("SELECT term_code, patients, severe_patients, reporting_patients FROM v_cohort_weekly").fetchall()
    assert rows == [("SE_RASH", 6, None, 6)]  # cough dropped; 2 severe shown as NULL (<5)
    comp = db.execute("SELECT records, patients, completion_rate FROM v_completion_weekly").fetchall()
    assert comp == [(6, 6, 1.0)]
