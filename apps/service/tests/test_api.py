"""API behaviour, contract 2.0 (Scoping Doc 26.13 error codes; docs/design/contract-2.0.md)."""

import base64
import json

import pytest
from fastapi.testclient import TestClient
from nacl.public import PrivateKey, SealedBox

from sentinel_contract import (CONTRACT_VERSION, SCHEMA_DIR, ContractError, canonical, payload_sha256,
                               validation_errors)
from sentinel_contract.client import SendRejected, SentinelClient, build_envelope
from sentinel_service import demo_ids as ids
from sentinel_service.main import app

EX = SCHEMA_DIR / "examples"
PT = {"X-Role": "patient_device", "X-Actor-Id": ids.WALTER}
COMPANY_READER = {"X-Role": "company_reader", "X-Actor-Id": ids.MARCO}


def dr(doctor_id):
    return {"X-Role": "doctor", "X-Actor-Id": doctor_id}


def example(kind):
    return json.loads((EX / f"{kind}.valid.json").read_text())


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


class Hospital:
    """Browser-side key handling for one organization, as the doctor web app will do it."""

    def __init__(self, c, org_id, admin_id):
        self.c, self.org_id, self.admin = c, org_id, admin_id
        self.org_sk = PrivateKey.generate()
        self.doctor_sks = {}
        r = c.put(f"/v1/orgs/{org_id}/public-key", json={"public_key": b64(bytes(self.org_sk.public_key))},
                  headers=dr(admin_id))
        assert r.status_code == 200, r.json()
        self.onboard(admin_id)

    def register_doctor(self, doctor_id):
        sk = PrivateKey.generate()
        self.doctor_sks[doctor_id] = sk
        assert self.c.put(f"/v1/doctors/{doctor_id}/public-key", json={"public_key": b64(bytes(sk.public_key))},
                          headers=dr(doctor_id)).status_code == 200
        return sk

    def onboard(self, doctor_id):
        sk = self.doctor_sks.get(doctor_id) or self.register_doctor(doctor_id)
        wrapped = SealedBox(sk.public_key).encrypt(bytes(self.org_sk))
        r = self.c.post(f"/v1/orgs/{self.org_id}/key-grants", json={"doctor_id": doctor_id, "wrapped_key": b64(wrapped)},
                        headers=dr(self.admin))
        assert r.status_code == 201, r.json()

    def unwrap_org_key(self, doctor_id) -> PrivateKey:
        grant = self.c.get(f"/v1/orgs/{self.org_id}/key-grants/{doctor_id}", headers=dr(doctor_id))
        assert grant.status_code == 200, grant.json()
        raw = SealedBox(self.doctor_sks[doctor_id]).decrypt(base64.b64decode(grant.json()["wrapped_key"]))
        return PrivateKey(raw)


def decrypt(org_sk: PrivateKey, envelope: dict) -> dict:
    plaintext = SealedBox(org_sk).decrypt(base64.b64decode(envelope["ciphertext"]))
    payload = json.loads(plaintext)
    assert plaintext == canonical(payload) and payload_sha256(payload) == envelope["payload_sha256"]
    return payload


def walter_client():
    return SentinelClient("http://testserver", ids.WALTER, http=TestClient(app))


# ---------------- basics ----------------

def test_missing_headers_401(c):
    assert c.get("/v1/survey", params={"cohort_id": "cohort_B"}).status_code == 401


def test_contract_version_header_and_terms(c):
    r = c.get("/v1/terms", params={"program_id": ids.PROGRAM_ID}, headers=PT)
    assert r.headers["X-Schema-Version"] == CONTRACT_VERSION
    terms = {t["term_code"]: t for t in r.json()["terms"]}
    assert terms["SE_RASH"]["known_for_program"] is True and terms["SE_COUGH"]["known_for_program"] is True
    assert terms["SE_INFUSION_REACTION"]["known_for_program"] is False  # Rybrevant only


def test_survey_includes_schedule(c):
    body = c.get("/v1/survey", params={"cohort_id": "cohort_B"}, headers=PT).json()
    assert body["schedule"] == {"every_days": 1} and len(body["questions"]) == 6


def test_record_created_then_idempotent_then_conflict(c):
    rec = example("company_record")
    r1 = c.post("/v1/records", json=rec, headers=PT)
    assert r1.status_code == 201 and r1.json()["payload_sha256"] == payload_sha256(rec)
    assert c.post("/v1/records", json=rec, headers=PT).status_code == 200
    changed = dict(rec, unanswered_questions=1)
    assert c.post("/v1/records", json=changed, headers=PT).status_code == 409


@pytest.mark.parametrize("kind,method,path", [
    ("company_record", "post", "/v1/records"), ("care_envelope", "post", "/v1/care-envelopes"),
    ("alert_event", "post", "/v1/alerts"), ("consent_update", "put", f"/v1/consent/{ids.WALTER}")])
def test_invalid_examples_rejected_422_naming_field(c, kind, method, path):
    doc = json.loads((EX / f"{kind}.invalid.json").read_text())
    r = getattr(c, method)(path, json=doc["payload"], headers=PT)
    assert r.status_code == 422
    assert doc["_expect"]["field"] in [e["field"] for e in r.json()["errors"]]


def test_record_must_match_enrollment_and_actor(c):
    rec = dict(example("company_record"), cohort_id="cohort_A", drug_version="v1")
    r = c.post("/v1/records", json=rec, headers=PT)
    assert r.status_code == 422 and {e["field"] for e in r.json()["errors"]} == {"/cohort_id", "/drug_version"}
    other = {"X-Role": "patient_device", "X-Actor-Id": ids.PRIYA}
    assert c.post("/v1/records", json=example("company_record"), headers=other).status_code == 403


def test_client_refuses_free_text_before_sending(c):
    bad = json.loads((EX / "company_record.invalid.json").read_text())["payload"]
    with pytest.raises(ContractError):
        walter_client().send_record(bad)
    assert app.state.store.db.company.execute("SELECT COUNT(*) FROM checkin_record").fetchone()[0] == 0


# ---------------- company ----------------

def test_company_cannot_reach_relay(c):
    co = {"X-Role": "company_safety", "X-Actor-Id": ids.DR_LEE}
    for path in (f"/v1/orgs/{ids.NORTHGATE}/envelopes", f"/v1/orgs/{ids.NORTHGATE}/alerts",
                 f"/v1/orgs/{ids.NORTHGATE}/patients", f"/v1/caregivers/{ids.ANNA}/alerts"):
        assert c.get(path, headers=co).status_code == 403, path
    assert c.post("/v1/records", json=example("company_record"), headers=co).status_code == 403


def test_company_roles_and_access_log(c):
    assert c.get("/v1/company/cohorts/weekly", params={"program_id": ids.PROGRAM_ID},
                 headers=COMPANY_READER).status_code == 200
    assert c.get("/v1/company/records/export", params={"program_id": ids.PROGRAM_ID},
                 headers=COMPANY_READER).status_code == 403
    admin = {"X-Role": "company_admin", "X-Actor-Id": ids.ADMIN}
    new = dict(example("survey_config"), schedule={"every_days": 2})
    r = c.put("/v1/company/cohorts/cohort_B/survey", json=new, headers=admin)
    assert r.status_code == 201 and r.json()["version"] == 2
    assert c.get("/v1/survey", params={"cohort_id": "cohort_B"}, headers=PT).json()["schedule"] == {"every_days": 2}
    log = app.state.store.db.company.execute("SELECT actor_role, action FROM access_log ORDER BY id").fetchall()
    assert [tuple(r) for r in log] == [("company_reader", "read"), ("company_admin", "publish_survey")]


def test_cohort_rows_never_below_5(seeded):
    store, _ = seeded
    app.state.store = store
    try:
        with TestClient(app) as c:
            rows = c.get("/v1/company/cohorts/weekly", params={"program_id": ids.PROGRAM_ID},
                         headers=COMPANY_READER).json()
            comp = c.get("/v1/company/completion", params={"program_id": ids.PROGRAM_ID},
                         headers=COMPANY_READER).json()
    finally:
        app.state.store = None
    assert rows and all(r["patients"] >= 5 and r["reporting_patients"] >= 5 for r in rows)
    assert all(r["severe_patients"] is None or r["severe_patients"] == 0 or r["severe_patients"] >= 5 for r in rows)
    assert len(comp) == 4 * 2 and all(0 < r["completion_rate"] < 1 and r["missed_rate"] > 0 for r in comp)
    for r in comp:  # input modes count answered records only
        answered = r["voice_records"] + r["text_records"] + r["mixed_records"]
        assert abs(answered - r["records"] * (1 - r["missed_rate"])) <= 1


def test_company_programs_documents_terms_and_survey(c):
    body = c.get("/v1/company/programs", headers=COMPANY_READER).json()
    assert body["company"]["company_id"] == "co_halvaren"
    progs = {p["program_id"]: p for p in body["programs"]}
    assert set(progs) == {ids.PROGRAM_ID, "prog_rybrevant_01", "prog_beyfortus_01"}
    assert progs["prog_beyfortus_01"]["population"] == "infants"
    walter_cohort = next(k for k in progs[ids.PROGRAM_ID]["cohorts"] if k["cohort_id"] == "cohort_B")
    assert "Osimertinib" in walter_cohort["source_arm"]
    docs = c.get("/v1/company/documents", params={"program_id": "prog_rybrevant_01"}, headers=COMPANY_READER).json()
    assert {d["kind"] for d in docs} == {"protocol", "sap", "label"}
    terms = c.get("/v1/company/terms", params={"program_id": "prog_beyfortus_01"}, headers=COMPANY_READER).json()
    known = {t["term_code"] for t in terms["terms"] if t["known_for_program"]}
    assert known == {"SE_RASH", "SE_INJECTION_SITE"}
    survey = c.get("/v1/company/cohorts/cohort_inf_A/survey", headers=COMPANY_READER).json()
    assert "baby" in survey["questions"][0]["asks"][0]
    assert c.get("/v1/company/programs", headers=PT).status_code == 403


def test_record_for_a_second_program_cohort_is_valid():
    rec = dict(example("company_record"), program_id="prog_rybrevant_01", cohort_id="cohort_ryb_A")
    rec["symptoms"] = [dict(rec["symptoms"][0], term_code="SE_INFUSION_REACTION")]
    assert validation_errors("company_record", rec) == []
    assert validation_errors("company_record", dict(rec, cohort_id="cohort A")) != []


def test_export_has_no_receipt_time_and_includes_reporter(c):
    c.post("/v1/records", json=example("company_record"), headers=PT)
    safety = {"X-Role": "company_safety", "X-Actor-Id": ids.DR_LEE}
    rows = c.get("/v1/company/records/export", params={"program_id": ids.PROGRAM_ID}, headers=safety).json()
    assert len(rows) == 1 and "received_at" not in rows[0]
    assert (rows[0]["reporter"], rows[0]["input_mode"]) == ("self", "voice")
    csv = c.get("/v1/company/records/export", params={"program_id": ids.PROGRAM_ID, "format": "csv"}, headers=safety)
    assert csv.status_code == 200 and "received_at" not in csv.text and csv.text.count("\n") == 3


# ---------------- care teams (D-064) ----------------

def test_doctor_sees_only_own_organizations(c):
    orgs = c.get(f"/v1/doctors/{ids.DR_SHAH}/orgs", headers=dr(ids.DR_SHAH)).json()
    assert [(o["org_id"], o["role"]) for o in orgs] == [(ids.NORTHGATE, "attending")]
    assert c.get(f"/v1/doctors/{ids.DR_SHAH}/orgs", headers=dr(ids.DR_RIVERA)).status_code == 403
    assert c.get(f"/v1/orgs/{ids.NORTHGATE}/patients", headers=dr(ids.DR_RIVERA)).status_code == 403  # not a member
    patients = c.get(f"/v1/orgs/{ids.NORTHGATE}/patients", headers=dr(ids.DR_SHAH)).json()
    assert {p["patient_ref"] for p in patients} == {ids.WALTER, ids.PRIYA}


def test_only_admins_manage_keys_and_members(c):
    key = b64(bytes(PrivateKey.generate().public_key))
    assert c.put(f"/v1/orgs/{ids.NORTHGATE}/public-key", json={"public_key": key},
                 headers=dr(ids.DR_SHAH)).status_code == 403
    assert c.put(f"/v1/orgs/{ids.NORTHGATE}/members/{ids.DR_RIVERA}", json={"role": "attending", "status": "active"},
                 headers=dr(ids.DR_SHAH)).status_code == 403
    assert c.get(f"/v1/orgs/{ids.NORTHGATE}/public-key", headers=PT).status_code == 404  # not registered yet


def test_care_team_reads_history_and_survives_a_doctor_change(c):
    north = Hospital(c, ids.NORTHGATE, ids.DR_PATEL)
    north.onboard(ids.DR_SHAH)

    client = walter_client()
    key = client.fetch_org_key(ids.NORTHGATE)
    for i in range(2):
        env = build_envelope(f"env_0000000{i}", ids.NORTHGATE, example("doctor_payload"), key)
        assert client.send_envelope(env).status_code == 201

    shah_key = north.unwrap_org_key(ids.DR_SHAH)
    got = c.get(f"/v1/orgs/{ids.NORTHGATE}/envelopes", headers=dr(ids.DR_SHAH)).json()
    assert [decrypt(shah_key, e)["display_name"] for e in got] == ["Walter", "Walter"]
    assert c.post(f"/v1/orgs/{ids.NORTHGATE}/envelopes/env_00000000/ack", headers=dr(ids.DR_SHAH)).status_code == 200

    # Dr. Shah leaves; Dr. Rivera joins and reads the full history at once
    assert c.put(f"/v1/orgs/{ids.NORTHGATE}/members/{ids.DR_SHAH}", json={"role": "attending", "status": "revoked"},
                 headers=dr(ids.DR_PATEL)).status_code == 200
    assert c.get(f"/v1/orgs/{ids.NORTHGATE}/envelopes", headers=dr(ids.DR_SHAH)).status_code == 403
    assert c.get(f"/v1/orgs/{ids.NORTHGATE}/key-grants/{ids.DR_SHAH}", headers=dr(ids.DR_SHAH)).status_code == 403
    assert c.put(f"/v1/orgs/{ids.NORTHGATE}/members/{ids.DR_RIVERA}", json={"role": "attending", "status": "active"},
                 headers=dr(ids.DR_PATEL)).status_code == 200
    north.onboard(ids.DR_RIVERA)
    rivera_key = north.unwrap_org_key(ids.DR_RIVERA)
    history = c.get(f"/v1/orgs/{ids.NORTHGATE}/envelopes", headers=dr(ids.DR_RIVERA)).json()
    assert len(history) == 2 and all(decrypt(rivera_key, e)["patient_ref"] == ids.WALTER for e in history)


def test_key_grant_must_be_a_sealed_32_byte_key(c):
    Hospital(c, ids.NORTHGATE, ids.DR_PATEL)
    r = c.post(f"/v1/orgs/{ids.NORTHGATE}/key-grants", json={"doctor_id": ids.DR_SHAH, "wrapped_key": b64(b"x" * 10)},
               headers=dr(ids.DR_PATEL))
    assert r.status_code == 422
    r = c.post(f"/v1/orgs/{ids.NORTHGATE}/key-grants", json={"doctor_id": ids.DR_RIVERA,
                                                             "wrapped_key": b64(b"x" * 80)}, headers=dr(ids.DR_PATEL))
    assert r.status_code == 403  # not a member: cannot receive the key


# ---------------- emergency access (D-065) ----------------

def test_emergency_hospital_reads_only_through_audited_emergency_access(c):
    lake = Hospital(c, ids.LAKESIDE, ids.DR_OKAFOR)
    client = walter_client()
    env = build_envelope("env_0000aaaa", ids.LAKESIDE, example("doctor_payload"), client.fetch_org_key(ids.LAKESIDE))
    assert client.send_envelope(env).status_code == 201

    assert c.get(f"/v1/orgs/{ids.LAKESIDE}/envelopes", headers=dr(ids.DR_OKAFOR)).json() == []  # no routine access
    assert c.get(f"/v1/orgs/{ids.LAKESIDE}/patients", headers=dr(ids.DR_OKAFOR)).json() == []
    r = c.post(f"/v1/orgs/{ids.LAKESIDE}/emergency-access",
               json={"patient_ref": ids.WALTER, "reason": "emergency_admission"}, headers=dr(ids.DR_OKAFOR))
    assert r.status_code == 200, r.json()
    body = r.json()
    assert decrypt(lake.unwrap_org_key(ids.DR_OKAFOR), body["envelopes"][0])["display_name"] == "Walter"
    assert sorted(body["notified"]) == ["care_team", "caregiver"]

    log = app.state.store.db.relay.execute(
        "SELECT action, patient_ref, reason FROM relay_access_log WHERE action = 'emergency_access'").fetchall()
    assert [tuple(x) for x in log] == [("emergency_access", ids.WALTER, "emergency_admission")]
    anna = c.get(f"/v1/caregivers/{ids.ANNA}/alerts", headers={"X-Role": "caregiver", "X-Actor-Id": ids.ANNA}).json()
    assert [a["alert_type"] for a in anna] == ["emergency_access"]
    Hospital(c, ids.NORTHGATE, ids.DR_PATEL)
    north_alerts = c.get(f"/v1/orgs/{ids.NORTHGATE}/alerts", headers=dr(ids.DR_PATEL)).json()
    assert [a["alert_type"] for a in north_alerts] == ["emergency_access"]


def test_emergency_access_needs_an_emergency_link_and_a_coded_reason(c):
    Hospital(c, ids.LAKESIDE, ids.DR_OKAFOR)
    r = c.post(f"/v1/orgs/{ids.LAKESIDE}/emergency-access", json={"patient_ref": ids.PRIYA,
                                                                  "reason": "unresponsive_patient"},
               headers=dr(ids.DR_OKAFOR))
    assert r.status_code == 403  # Priya did not consent to emergency access
    r = c.post(f"/v1/orgs/{ids.LAKESIDE}/emergency-access", json={"patient_ref": ids.WALTER, "reason": "curious"},
               headers=dr(ids.DR_OKAFOR))
    assert r.status_code == 422
    r = c.post(f"/v1/orgs/{ids.NORTHGATE}/emergency-access", json={"patient_ref": ids.WALTER,
                                                                   "reason": "unresponsive_patient"},
               headers=dr(ids.DR_SHAH))
    assert r.status_code == 403  # Northgate is the care team, not an emergency organization


# ---------------- consent (D-064, D-067) ----------------

def test_consent_sets_links_and_contacts_and_revocation_blocks_envelopes(c):
    north = Hospital(c, ids.NORTHGATE, ids.DR_PATEL)
    client = walter_client()
    key = client.fetch_org_key(ids.NORTHGATE)
    consent = example("consent_update")
    sent = client.send_consent(consent)  # the client raises SendRejected if the server hash differs from its own
    assert sent.body["emergency_contact_count"] == 2 and sent.body["payload_sha256"] == payload_sha256(consent)

    no_emergency = dict(consent, emergency_consent=False, emergency_org_ids=[], emergency_contacts=[])
    client.send_consent(no_emergency)
    relay = app.state.store.db.relay
    assert relay.execute("SELECT COUNT(*) FROM emergency_contact WHERE patient_ref = ?", (ids.WALTER,)).fetchone()[0] == 0
    assert relay.execute("SELECT status FROM care_link WHERE org_id = ? AND patient_ref = ?",
                         (ids.LAKESIDE, ids.WALTER)).fetchone()[0] == "revoked"

    client.send_consent(dict(no_emergency, share_care_team=False))
    with pytest.raises(SendRejected) as e:
        client.send_envelope(build_envelope("env_0000bbbb", ids.NORTHGATE, example("doctor_payload"), key))
    assert e.value.status == 403
    assert c.get(f"/v1/orgs/{ids.NORTHGATE}/patients", headers=dr(ids.DR_PATEL)).json() == [
        {"patient_ref": ids.PRIYA, "granted_at": "2026-10-17T15:00:00.000000Z"}]
    del north


def test_consent_rejects_care_team_listed_as_emergency(c):
    bad = dict(example("consent_update"), emergency_org_ids=[ids.NORTHGATE])
    r = c.put(f"/v1/consent/{ids.WALTER}", json=bad, headers=PT)
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "/emergency_org_ids"


def test_config_fetches_reach_on_fetch_with_request_hash_not_body(c):
    seen = []
    client = SentinelClient("http://testserver", ids.WALTER, http=TestClient(app), on_fetch=seen.append)
    client.fetch_survey("cohort_B")
    with pytest.raises(SendRejected):
        client.fetch_survey("cohort_nope")
    ok, bad = seen
    assert (ok.method, ok.status_code, ok.fields_sent) == ("GET", 200, ["cohort_id"])
    assert ok.payload_sha256 == payload_sha256({"cohort_id": "cohort_B"}) and ok.url.endswith("cohort_id=cohort_B")
    assert bad.status_code == 404


# ---------------- alerts ----------------

def test_severe_alert_routed_to_care_team_and_caregiver(c):
    Hospital(c, ids.NORTHGATE, ids.DR_PATEL)
    r = c.post("/v1/alerts", json=example("alert_event"), headers=PT)
    assert r.status_code == 201 and r.json()["routed_care_team"] and r.json()["routed_caregiver"]
    assert c.post("/v1/alerts", json=example("alert_event"), headers=PT).status_code == 200
    assert r.json()["payload_sha256"] == payload_sha256(example("alert_event"))  # 2.3: the receipt hash
    north = c.get(f"/v1/orgs/{ids.NORTHGATE}/alerts", headers=dr(ids.DR_SHAH)).json()
    assert [(a["alert_type"], a["escalation_level"]) for a in north] == [("severe", None)]
    anna = c.get(f"/v1/caregivers/{ids.ANNA}/alerts", headers={"X-Role": "caregiver", "X-Actor-Id": ids.ANNA}).json()
    assert set(anna[0]) == {"alert_id", "patient_ref", "alert_type", "escalation_level", "created_at", "received_at"}


def test_since_pages_on_receive_time_not_device_time(c):
    late = dict(example("alert_event"), alert_id="alt_0000000a", created_at="2026-11-01T09:00:00Z")  # queued offline
    assert c.post("/v1/alerts", json=example("alert_event"), headers=PT).status_code == 201
    cursor = c.get(f"/v1/orgs/{ids.NORTHGATE}/alerts", headers=dr(ids.DR_SHAH)).json()[-1]["received_at"]
    assert c.post("/v1/alerts", json=late, headers=PT).status_code == 201
    nxt = c.get(f"/v1/orgs/{ids.NORTHGATE}/alerts", params={"since": cursor}, headers=dr(ids.DR_SHAH)).json()
    assert [a["alert_id"] for a in nxt] == ["alt_0000000a"]
    assert c.get(f"/v1/orgs/{ids.NORTHGATE}/alerts", params={"since": "yesterday"},
                 headers=dr(ids.DR_SHAH)).status_code == 422
