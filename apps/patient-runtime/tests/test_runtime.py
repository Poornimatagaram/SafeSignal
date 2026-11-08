"""Task A1 skeleton (contract 2.0): database from schema/patient.sql, seeded profile, /health, egress-import rule."""

import ast
import re
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sentinel_contract import SCHEMA_VERSION
from sentinel_patient.config import WALTER, Settings
from sentinel_patient.db import PATIENT_SQL, SchemaMismatch, connect, init_db
from sentinel_patient.main import create_app

PRIYA = "pt_9c1d2e3f"

PACKAGE = Path(__file__).resolve().parents[1] / "sentinel_patient"


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "patient.db"


@pytest.fixture()
def client(db_path):
    with TestClient(create_app(Settings(db_path=db_path, patient_ref=WALTER))) as c:  # runs the lifespan
        yield c


def rows(db_path, sql, *args):
    with closing(connect(db_path)) as conn:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]


def test_health_reports_local_state_without_personal_data(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "schema_version": SCHEMA_VERSION, "patient_ref": WALTER,
                        "profile_loaded": True}
    for local_only in ("Walter", "1934-03-12", "555-0142"):
        assert local_only not in r.text


def test_database_has_every_table_in_patient_sql(client, db_path):
    expected = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", PATIENT_SQL.read_text()))
    actual = {r["name"] for r in rows(db_path, "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert expected and expected <= actual


def test_seeds_walter_profile_consent_and_emergency_setup(client, db_path):
    profile = rows(db_path, "SELECT patient_ref, cohort_id, drug_version, drug_name, care_org_id, reporter_default, "
                            "care_org_public_key FROM patient_profile")
    assert profile == [{"patient_ref": WALTER, "cohort_id": "cohort_B", "drug_version": "v2", "drug_name": "Tagrisso",
                        "care_org_id": "org_5e1a2b3c", "reporter_default": "self",
                        "care_org_public_key": None}]  # key fetched later from the service (D-064)
    consent = rows(db_path, "SELECT share_care_team, emergency_consent, share_caregiver, caregiver_detail FROM consent")
    assert consent == [{"share_care_team": 1, "emergency_consent": 1, "share_caregiver": 1,
                        "caregiver_detail": "alerts_only"}]
    assert rows(db_path, "SELECT * FROM emergency_org") == [{"org_id": "org_8f4d6a2e", "public_key": None}]
    contacts = rows(db_path, "SELECT contact_id, contact_type, org_id, priority, display_label "
                             "FROM emergency_contact ORDER BY priority")
    assert contacts == [
        {"contact_id": "ec_1f2e3d4c", "contact_type": "emergency_service", "org_id": None, "priority": 1,
         "display_label": "Emergency services"},
        {"contact_id": "ec_5a6b7c8d", "contact_type": "hospital", "org_id": "org_8f4d6a2e", "priority": 2,
         "display_label": "Lakeside Emergency Hospital"},
    ]


def test_patient_without_emergency_consent_gets_no_emergency_rows(db_path):
    init_db(db_path, PRIYA)
    assert rows(db_path, "SELECT emergency_consent FROM consent") == [{"emergency_consent": 0}]
    assert rows(db_path, "SELECT * FROM emergency_org") == []
    assert rows(db_path, "SELECT * FROM emergency_contact") == []


TABLES = ("schema_meta", "patient_profile", "consent", "emergency_org", "emergency_contact")


def test_init_is_safe_to_rerun_and_never_reseeds(db_path):
    init_db(db_path, WALTER)
    first = {t: rows(db_path, f"SELECT * FROM {t}") for t in TABLES}
    with closing(connect(db_path)) as conn, conn:  # the patient removes a contact on the device
        conn.execute("DELETE FROM emergency_contact WHERE contact_id = 'ec_5a6b7c8d'")
    init_db(db_path, WALTER)
    after = {t: rows(db_path, f"SELECT * FROM {t}") for t in TABLES}
    assert after["emergency_contact"] == [c for c in first["emergency_contact"] if c["contact_id"] != "ec_5a6b7c8d"]
    assert {t: v for t, v in after.items() if t != "emergency_contact"} == {
        t: v for t, v in first.items() if t != "emergency_contact"}


def test_refuses_a_database_from_another_schema_version(db_path):
    init_db(db_path, WALTER)
    with closing(connect(db_path)) as conn, conn:
        conn.execute("UPDATE schema_meta SET schema_version = '1.0'")
    with pytest.raises(SchemaMismatch, match="needs " + re.escape(SCHEMA_VERSION)):
        init_db(db_path, WALTER)


def test_unknown_actor_gets_no_profile(db_path):
    with TestClient(create_app(Settings(db_path=db_path, patient_ref="pt_00000000"))) as c:
        assert c.get("/health").json()["profile_loaded"] is False
    assert rows(db_path, "SELECT * FROM patient_profile") == []


def test_cors_allows_patient_web_only(client):
    ok = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    other = client.get("/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in other.headers


NETWORK_MODULES = {"sentinel_contract.client", "httpx", "requests", "urllib", "urllib3", "http.client",
                   "aiohttp", "socket", "websockets", "huggingface_hub", "ollama"}
# egress_gate.py is the one path off the device. extract.py may reach only the local model server (Ollama on
# loopback; extract.py refuses any other host), so it may import the ollama client and nothing else on this list.
ALLOWED = {"egress_gate.py": NETWORK_MODULES, "extract.py": {"ollama"}}


def _imports(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found |= {f"{node.module}.{a.name}" for a in node.names}
    return found


def test_only_egress_gate_imports_network_code():
    offenders = {}
    for path in PACKAGE.rglob("*.py"):
        forbidden = NETWORK_MODULES - ALLOWED.get(path.name, set())
        bad = {m for m in _imports(path) for n in forbidden if m == n or m.startswith(n + ".")}
        if bad:
            offenders[path.name] = sorted(bad)
    assert offenders == {}
