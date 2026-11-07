"""API behaviour tests against the stub (Scoping Doc 26.13 error codes, 26.15 checklist items the stub covers)."""

import base64
import copy
import json

import pytest
from fastapi.testclient import TestClient
from nacl.public import PrivateKey, SealedBox

from sentinel_contract.client import SendRejected, SentinelClient, build_envelope
from sentinel_contract import SCHEMA_DIR, canonical, payload_sha256
from sentinel_service import demo_ids as ids
from sentinel_service.main import app
from sentinel_service.stub_store import StubStore

EX = SCHEMA_DIR / "examples"
PT = {"X-Role": "patient_device", "X-Actor-Id": ids.WALTER}
DR = {"X-Role": "doctor", "X-Actor-Id": ids.DR_SHAH}


def example(kind):
    return json.loads((EX / f"{kind}.valid.json").read_text())


@pytest.fixture()
def c():
    app.state.store = StubStore()  # fresh state per test
    return TestClient(app)


def test_missing_headers_401(c):
    assert c.get("/v1/survey", params={"cohort_id": "cohort_B"}).status_code == 401


def test_schema_version_header(c):
    r = c.get("/v1/terms", params={"program_id": ids.PROGRAM_ID}, headers=PT)
    assert r.headers["X-Schema-Version"] == "1.0"
    terms = {t["term_code"]: t for t in r.json()["terms"]}
    assert terms["SE_RASH"]["known_for_program"] is True
    assert terms["SE_COUGH"]["known_for_program"] is False  # Rybrevant-only


def test_record_created_then_idempotent_then_conflict(c):
    rec = example("company_record")
    r1 = c.post("/v1/records", json=rec, headers=PT)
    assert r1.status_code == 201 and r1.json()["payload_sha256"] == payload_sha256(rec)
    assert c.post("/v1/records", json=rec, headers=PT).status_code == 200
    changed = copy.deepcopy(rec)
    changed["unanswered_questions"] = 1
    assert c.post("/v1/records", json=changed, headers=PT).status_code == 409


@pytest.mark.parametrize("kind,path", [("company_record", "/v1/records"), ("doctor_envelope", "/v1/doctor-envelopes"),
                                       ("alert_event", "/v1/alerts")])
def test_invalid_examples_rejected_422_naming_field(c, kind, path):
    doc = json.loads((EX / f"{kind}.invalid.json").read_text())
    r = c.post(path, json=doc["payload"], headers=PT)
    assert r.status_code == 422
    assert doc["_expect"]["field"] in [e["field"] for e in r.json()["errors"]]


def test_record_must_match_enrollment_and_actor(c):
    rec = example("company_record")
    rec["cohort_id"], rec["drug_version"] = "cohort_A", "v1"
    r = c.post("/v1/records", json=rec, headers=PT)
    assert r.status_code == 422 and {e["field"] for e in r.json()["errors"]} == {"/cohort_id", "/drug_version"}
    other = {"X-Role": "patient_device", "X-Actor-Id": ids.PRIYA}
    assert c.post("/v1/records", json=example("company_record"), headers=other).status_code == 403


def test_company_cannot_reach_relay_or_patient_endpoints(c):
    co = {"X-Role": "company_safety", "X-Actor-Id": ids.DR_LEE}
    assert c.get(f"/v1/doctors/{ids.DR_SHAH}/envelopes", headers=co).status_code == 403
    assert c.get(f"/v1/doctors/{ids.DR_SHAH}/alerts", headers=co).status_code == 403
    assert c.get(f"/v1/caregivers/{ids.ANNA}/alerts", headers=co).status_code == 403
    assert c.post("/v1/records", json=example("company_record"), headers=co).status_code == 403


def test_company_roles(c):
    reader = {"X-Role": "company_reader", "X-Actor-Id": ids.MARCO}
    assert c.get("/v1/company/cohorts/weekly", params={"program_id": ids.PROGRAM_ID}, headers=reader).status_code == 200
    assert c.get("/v1/company/records/export", params={"program_id": ids.PROGRAM_ID}, headers=reader).status_code == 403
    assert c.put("/v1/company/cohorts/cohort_B/survey", json=example("survey_config"), headers=reader).status_code == 403
    admin = {"X-Role": "company_admin", "X-Actor-Id": ids.ADMIN}
    r = c.put("/v1/company/cohorts/cohort_B/survey", json=example("survey_config"), headers=admin)
    assert r.status_code == 201 and r.json()["version"] == 2
    assert c.get("/v1/survey", params={"cohort_id": "cohort_B"}, headers=PT).json()["version"] == 2
    assert len(app.state.store.access_log) == 2


def test_cohort_rows_never_below_5(c):
    reader = {"X-Role": "company_reader", "X-Actor-Id": ids.MARCO}
    rows = c.get("/v1/company/cohorts/weekly", params={"program_id": ids.PROGRAM_ID}, headers=reader).json()
    assert rows and all(r["patients"] >= 5 and r["reporting_patients"] >= 5 for r in rows)
    assert all(r["severe_patients"] is None or r["severe_patients"] == 0 or r["severe_patients"] >= 5 for r in rows)


def test_export_has_no_receipt_time(c):
    c.post("/v1/records", json=example("company_record"), headers=PT)
    safety = {"X-Role": "company_safety", "X-Actor-Id": ids.DR_LEE}
    rows = c.get("/v1/company/records/export", params={"program_id": ids.PROGRAM_ID}, headers=safety).json()
    assert len(rows) == 1 and "received_at" not in rows[0]
    csv = c.get("/v1/company/records/export", params={"program_id": ids.PROGRAM_ID, "format": "csv"}, headers=safety)
    assert csv.status_code == 200 and "received_at" not in csv.text and csv.text.count("\n") == 3  # header + 2 symptoms


def test_doctor_actor_must_match_path(c):
    other = {"X-Role": "doctor", "X-Actor-Id": "dr_00000000"}
    assert c.get(f"/v1/doctors/{ids.DR_SHAH}/envelopes", headers=other).status_code == 403


def test_envelope_round_trip_with_real_encryption_and_revocation(c):
    sk = PrivateKey.generate()
    pk_b64 = base64.b64encode(bytes(sk.public_key)).decode()
    assert c.put(f"/v1/doctors/{ids.DR_SHAH}/public-key", json={"public_key": pk_b64}, headers=DR).status_code == 200

    client = SentinelClient("http://testserver", ids.WALTER, http=TestClient(app))
    key = client.fetch_doctor_key(ids.DR_SHAH)
    env = build_envelope("env_91c2a7d4", ids.DR_SHAH, example("doctor_payload"), key)
    res = client.send_envelope(env)
    assert res.status_code == 201 and "ciphertext" in res.fields_sent

    got = c.get(f"/v1/doctors/{ids.DR_SHAH}/envelopes", headers=DR).json()
    assert len(got) == 1
    plaintext = SealedBox(sk).decrypt(base64.b64decode(got[0]["ciphertext"]))
    assert plaintext == canonical(example("doctor_payload"))
    assert payload_sha256(json.loads(plaintext)) == got[0]["payload_sha256"]
    assert c.post(f"/v1/doctors/{ids.DR_SHAH}/envelopes/env_91c2a7d4/ack", headers=DR).status_code == 200

    consent = example("consent_update")
    consent["share_doctor"] = False
    client.send_consent(consent)
    env2 = build_envelope("env_91c2a7d5", ids.DR_SHAH, example("doctor_payload"), key)
    with pytest.raises(SendRejected) as e:
        client.send_envelope(env2)
    assert e.value.status == 403
    assert c.get(f"/v1/doctors/{ids.DR_SHAH}/patients", headers=DR).json() == [
        {"patient_ref": ids.PRIYA, "granted_at": "2026-11-01T00:00:00Z"}]


def test_severe_alert_routed_to_doctor_and_caregiver(c):
    r = c.post("/v1/alerts", json=example("alert_event"), headers=PT)
    assert r.status_code == 201 and r.json()["routed_doctor"] and r.json()["routed_caregiver"]
    dr = c.get(f"/v1/doctors/{ids.DR_SHAH}/alerts", headers=DR).json()
    assert {a["alert_type"] for a in dr} == {"missed", "severe"}
    cg = c.get(f"/v1/caregivers/{ids.ANNA}/alerts", headers={"X-Role": "caregiver", "X-Actor-Id": ids.ANNA}).json()
    assert [a["alert_type"] for a in cg] == ["severe"] and set(cg[0]) == {"alert_id", "patient_ref", "alert_type",
                                                                         "created_at"}


def test_since_paging_is_strictly_after(c):
    dr = c.get(f"/v1/doctors/{ids.DR_SHAH}/alerts", headers=DR).json()
    assert len(dr) == 1
    assert c.get(f"/v1/doctors/{ids.DR_SHAH}/alerts", params={"since": dr[0]["created_at"]}, headers=DR).json() == []


def test_client_refuses_free_text_before_sending(c):
    from sentinel_contract import ContractError
    client = SentinelClient("http://testserver", ids.WALTER, http=TestClient(app))
    bad = json.loads((EX / "company_record.invalid.json").read_text())["payload"]
    with pytest.raises(ContractError):
        client.send_record(bad)
    assert app.state.store.records == {}


def test_public_key_404_until_registered(c):
    assert c.get(f"/v1/doctors/{ids.DR_SHAH}/public-key", headers=PT).status_code == 404
    bad = c.put(f"/v1/doctors/{ids.DR_SHAH}/public-key", json={"public_key": "c2hvcnQ="}, headers=DR)
    assert bad.status_code == 422
