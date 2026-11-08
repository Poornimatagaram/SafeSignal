"""End-to-end check: one check-in reaches every persona through the service, each seeing only its own slice.

Starts a throwaway service (temp data dir, free port, scheduler off), seeds it, then plays every persona over real
HTTP against it. The demo databases under var/ are never touched.

  patient device  SentinelClient, exactly as the egress gate should: consent, record, one envelope per org, alert
  doctors         Dr. Patel (Northgate admin) and Dr. Okafor (Lakeside admin) create keys like the browser does,
                  fetch and decrypt envelopes, check the hash; Dr. Rivera (not a member) is refused
  caregiver       Anna sees the severe and emergency-access alerts
  company         sees the record in the export and aggregates, never relay data or small groups

Covers the automatable items of Scoping Doc 26.15 (contract, access control, privacy). Exits 1 if any check fails.
Run from the repo root:
  uv run --project apps/service python scripts/e2e_check.py [--keep]
"""

from __future__ import annotations

import argparse
import base64
import copy
import json
import os
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from nacl.public import PrivateKey, SealedBox

from sentinel_contract import SCHEMA_DIR, ContractError, canonical, payload_sha256
from sentinel_contract.client import SendRejected, SentinelClient, build_envelope

REPO = Path(__file__).resolve().parents[1]
SERVICE_DIR = REPO / "apps" / "service"
FIX = json.loads((SCHEMA_DIR / "demo_fixtures.json").read_text())
EX = SCHEMA_DIR / "examples"

PROGRAM = FIX["program"]["program_id"]
NORTHGATE, LAKESIDE = "org_5e1a2b3c", "org_8f4d6a2e"
PATEL, SHAH, RIVERA, OKAFOR = "dr_b29c4e71", "dr_3a7f10b2", "dr_c71e0f9a", "dr_d4a8e2b6"
WALTER = next(p for p in FIX["device_profiles"] if p["display_name"] == "Walter")
ANNA = WALTER["caregiver_id"]


def example(name: str) -> dict:
    return json.loads((EX / f"{name}.valid.json").read_text())


def b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


class Report:
    def __init__(self) -> None:
        self.failed: list[str] = []
        self.passed = 0

    def head(self, title: str) -> None:
        print(f"\n{title}")

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        if ok:
            self.passed += 1
            print(f"  PASS  {name}")
        else:
            self.failed.append(name)
            print(f"  FAIL  {name}" + (f": {detail}" if detail else ""))
        return ok


# ---------------------------------------------------------------- isolated service

def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_service(data_dir: Path, port: int, log_path: Path) -> subprocess.Popen:
    env = {**os.environ, "SERVICE_DATA_DIR": str(data_dir), "SERVICE_SCHEDULER": "off"}
    env.pop("SENTINEL_ALLOWED_ORIGINS", None)
    subprocess.run([sys.executable, "-m", "sentinel_service.seed", "--data-dir", str(data_dir),
                    "--patients-per-cohort", "40", "--weeks", "2"],
                   cwd=SERVICE_DIR, env=env, check=True, stdout=subprocess.DEVNULL)
    log = log_path.open("w")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "sentinel_service.main:app", "--host", "127.0.0.1",
                             "--port", str(port)], cwd=SERVICE_DIR, env=env, stdout=log, stderr=subprocess.STDOUT)
    deadline = time.time() + 20
    while time.time() < deadline:
        if proc.poll() is not None:
            raise SystemExit(f"service exited early; see {log_path}")
        try:
            if httpx.get(f"http://127.0.0.1:{port}/healthz", timeout=1).status_code == 200:
                return proc
        except httpx.TransportError:
            time.sleep(0.2)
    proc.terminate()
    raise SystemExit("service did not become healthy in 20 s")


# ---------------------------------------------------------------- personas

def as_role(base: str, role: str, actor: str) -> httpx.Client:
    return httpx.Client(base_url=base, timeout=10, headers={"X-Role": role, "X-Actor-Id": actor})


class Doctor:
    """What doctor-web does in the browser: personal key pair, org key for admins, key grants, decrypt."""

    def __init__(self, base: str, doctor_id: str):
        self.id = doctor_id
        self.http = as_role(base, "doctor", doctor_id)
        self.personal = PrivateKey.generate()
        self.org_keys: dict[str, PrivateKey] = {}

    def register(self) -> int:
        return self.http.put(f"/v1/doctors/{self.id}/public-key",
                             json={"public_key": b64(bytes(self.personal.public_key))}).status_code

    def create_org_key(self, org_id: str) -> tuple[int, int]:
        org = PrivateKey.generate()
        r1 = self.http.put(f"/v1/orgs/{org_id}/public-key", json={"public_key": b64(bytes(org.public_key))})
        wrapped = SealedBox(self.personal.public_key).encrypt(bytes(org))
        r2 = self.http.post(f"/v1/orgs/{org_id}/key-grants", json={"doctor_id": self.id, "wrapped_key": b64(wrapped)})
        return r1.status_code, r2.status_code

    def load_grant(self, org_id: str) -> bool:
        r = self.http.get(f"/v1/orgs/{org_id}/key-grants/{self.id}")
        if r.status_code != 200:
            return False
        raw = SealedBox(self.personal).decrypt(base64.b64decode(r.json()["wrapped_key"]))
        self.org_keys[org_id] = PrivateKey(raw)
        return True

    def open(self, org_id: str, env: dict) -> dict:
        plain = SealedBox(self.org_keys[org_id]).decrypt(base64.b64decode(env["ciphertext"]))
        return json.loads(plain)


# ---------------------------------------------------------------- the run

def run(base: str, data_dir: Path, log_path: Path, rep: Report) -> None:
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    iso = now.isocalendar()
    iso_week = f"{iso.year}-W{iso.week:02d}"
    tag = secrets.token_hex(4)

    patient = SentinelClient(base, WALTER["patient_ref"])
    patel, shah, rivera, okafor = (Doctor(base, d) for d in (PATEL, SHAH, RIVERA, OKAFOR))
    anna = as_role(base, "caregiver", ANNA)
    company = as_role(base, "company_reader", "co_reader_e2e")
    safety = as_role(base, "company_safety", "co_safety_e2e")

    rep.head("Setup")
    h = httpx.get(f"{base}/healthz").json()
    rep.check("service healthy and seeded", h.get("status") == "ok" and h.get("seeded") is True, str(h))
    try:
        patient.fetch_org_key(NORTHGATE)
        rep.check("org key is 404 before the admin registers it", False, "got a key")
    except SendRejected as e:
        rep.check("org key is 404 before the admin registers it", e.status == 404, str(e.status))

    rep.head("Doctor side: keys, as doctor-web does in the browser")
    rep.check("Dr. Patel registers a personal key", patel.register() == 200)
    rep.check("Dr. Okafor registers a personal key", okafor.register() == 200)
    rep.check("Dr. Shah registers a personal key", shah.register() == 200)
    rep.check("Northgate admin registers the care-team key and a self grant",
              patel.create_org_key(NORTHGATE) == (200, 201))
    rep.check("Lakeside admin registers its key and a self grant", okafor.create_org_key(LAKESIDE) == (200, 201))
    stray = b64(bytes(PrivateKey.generate().public_key))
    r = shah.http.put(f"/v1/orgs/{NORTHGATE}/public-key", json={"public_key": stray})
    rep.check("a non-admin member cannot replace the org key (403)", r.status_code == 403, str(r.status_code))
    rep.check("admin can read back his own key grant", patel.load_grant(NORTHGATE))
    rep.check("Lakeside admin can read back her key grant", okafor.load_grant(LAKESIDE))

    rep.head("Patient device: SentinelClient, as the egress gate should call it")
    survey = patient.fetch_survey(WALTER["cohort_id"])
    rep.check("fetch_survey returns the cohort survey with a schedule", "schedule" in survey, ",".join(survey))
    terms = patient.fetch_terms(PROGRAM)
    rep.check("fetch_terms returns the term list", bool(terms), "")

    consent = example("consent_update")
    res = patient.send_consent(consent)
    rep.check("send_consent accepted", res.status_code == 200, str(res.status_code))
    rep.check("consent response never echoes contact details",
              "emergency_contacts" not in res.body and "911" not in json.dumps(res.body), json.dumps(res.body))

    record = example("company_record")
    record.update(record_id=f"rec_{tag}", iso_week=iso_week)
    res = patient.send_record(record)
    rep.check("send_record → 201 created", res.status_code == 201, str(res.status_code))
    rep.check("receipt hash equals the service's stored hash", res.body.get("payload_sha256") == payload_sha256(record))
    rep.check("resend of the same record → 200", patient.send_record(record).status_code == 200)
    changed = copy.deepcopy(record)
    changed["unanswered_questions"] = 1
    try:
        patient.send_record(changed)
        rep.check("same record_id with a changed payload → 409", False, "accepted")
    except SendRejected as e:
        rep.check("same record_id with a changed payload → 409", e.status == 409, str(e.status))

    bad = json.loads((EX / "company_record.invalid.json").read_text())
    try:
        patient.send_record(bad)
        rep.check("client refuses an invalid record before sending", False, "sent")
    except ContractError:
        rep.check("client refuses an invalid record before sending", True)
    r = patient._http.post("/v1/records", content=canonical(bad), headers={"Content-Type": "application/json"})
    errs = r.json().get("errors", []) if r.status_code == 422 else []
    rep.check("service rejects the invalid record with 422 naming the field",
              r.status_code == 422 and all(e.get("field") for e in errs) and bool(errs), f"{r.status_code} {errs}")

    plaintext = example("doctor_payload")
    plaintext.update(checkin_date=today, trend="worse")
    envelopes = {}
    for org in (NORTHGATE, LAKESIDE):
        env = build_envelope(f"env_{secrets.token_hex(4)}", org, plaintext, patient.fetch_org_key(org))
        res = patient.send_envelope(env)
        envelopes[org] = env
        rep.check(f"envelope sealed to {org} → 201", res.status_code == 201, str(res.status_code))

    alert = {"schema_version": "2.0", "alert_id": f"alt_{tag}", "patient_ref": WALTER["patient_ref"],
             "alert_type": "severe", "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
    res = patient.send_alert(alert)
    rep.check("severe alert → 201, routed to care team and caregiver",
              res.status_code == 201 and res.body.get("routed_care_team") and res.body.get("routed_caregiver"),
              json.dumps(res.body))

    rep.head("Doctor view: the care team reads the same check-in")
    orgs = patel.http.get(f"/v1/doctors/{PATEL}/orgs").json()
    rep.check("Dr. Patel's memberships include Northgate", any(o["org_id"] == NORTHGATE for o in orgs))
    pts = patel.http.get(f"/v1/orgs/{NORTHGATE}/patients").json()
    rep.check("Northgate's patient list includes Walter", any(p["patient_ref"] == WALTER["patient_ref"] for p in pts))
    inbox = patel.http.get(f"/v1/orgs/{NORTHGATE}/envelopes").json()
    mine = next((e for e in inbox if e["envelope_id"] == envelopes[NORTHGATE]["envelope_id"]), None)
    rep.check("the envelope is in Northgate's inbox", mine is not None)
    if mine:
        opened = patel.open(NORTHGATE, mine)
        rep.check("Dr. Patel decrypts it with the org key", opened.get("patient_ref") == WALTER["patient_ref"])
        rep.check("decrypted payload hash equals payload_sha256 (26.13)",
                  payload_sha256(opened) == mine["payload_sha256"])
        rep.check("decrypted symptoms equal what the patient sent", opened["symptoms"] == plaintext["symptoms"])
        ack = patel.http.post(f"/v1/orgs/{NORTHGATE}/envelopes/{mine['envelope_id']}/ack")
        rep.check("ack → 200 with fetched_at", ack.status_code == 200 and ack.json().get("fetched_at"))
    rep.check("routine inbox holds no emergency envelope",
              all(e["envelope_id"] != envelopes[LAKESIDE]["envelope_id"] for e in inbox))
    alerts = patel.http.get(f"/v1/orgs/{NORTHGATE}/alerts").json()
    rep.check("Northgate sees the severe alert", any(a["alert_id"] == alert["alert_id"] for a in alerts))

    r = shah.http.get(f"/v1/orgs/{NORTHGATE}/key-grants/{SHAH}")
    rep.check("a member without a grant gets no key (404)", r.status_code == 404, str(r.status_code))
    r = rivera.http.get(f"/v1/orgs/{NORTHGATE}/envelopes")
    rep.check("a non-member doctor is refused the inbox (403)", r.status_code == 403, str(r.status_code))
    r = okafor.http.get(f"/v1/orgs/{NORTHGATE}/envelopes")
    rep.check("another hospital's doctor is refused Northgate's inbox (403)", r.status_code == 403, str(r.status_code))

    rep.head("Emergency hospital: audited access only")
    routine = okafor.http.get(f"/v1/orgs/{LAKESIDE}/envelopes").json()
    rep.check("Lakeside's routine inbox does not show Walter",
              all(e["patient_ref"] != WALTER["patient_ref"] for e in routine))
    r = okafor.http.post(f"/v1/orgs/{LAKESIDE}/emergency-access",
                         json={"patient_ref": WALTER["patient_ref"], "reason": "emergency_admission"})
    body = r.json() if r.status_code == 200 else {}
    em = next((e for e in body.get("envelopes", []) if e["envelope_id"] == envelopes[LAKESIDE]["envelope_id"]), None)
    rep.check("emergency access returns Walter's envelope", r.status_code == 200 and em is not None, str(r.status_code))
    if em:
        rep.check("Dr. Okafor decrypts it with Lakeside's key",
                  payload_sha256(okafor.open(LAKESIDE, em)) == em["payload_sha256"])

    rep.head("Caregiver")
    ca = anna.get(f"/v1/caregivers/{ANNA}/alerts").json()
    types = {a["alert_type"] for a in ca if a["patient_ref"] == WALTER["patient_ref"]}
    rep.check("Anna sees the severe alert", any(a["alert_id"] == alert["alert_id"] for a in ca))
    rep.check("Anna is told about the emergency access", "emergency_access" in types, ",".join(sorted(types)))
    rep.check("Anna's alerts carry no symptom content",
              all(set(a) <= {"alert_id", "patient_ref", "alert_type", "escalation_level", "created_at", "received_at"}
                  for a in ca))
    r = as_role(base, "caregiver", "cg_00000000").get(f"/v1/caregivers/{ANNA}/alerts")
    rep.check("another caregiver cannot read Anna's alerts (403)", r.status_code == 403, str(r.status_code))

    rep.head("Company: aggregates and the export, never relay data")
    export = safety.get("/v1/company/records/export", params={"program_id": PROGRAM}).json()
    row = next((x for x in export if x["record_id"] == record["record_id"]), None)
    rep.check("the record is in the company export", row is not None)
    if row:
        rep.check("export carries reporter and input_mode from the device",
                  row["reporter"] == record["reporter"] and row["input_mode"] == record["input_mode"])
        rep.check("export symptoms equal the record's coded symptoms",
                  [s["term_code"] for s in row["symptoms"]] == [s["term_code"] for s in record["symptoms"]])
    rep.check("the export never contains the patient's name", WALTER["display_name"] not in json.dumps(export))
    weekly = company.get("/v1/company/cohorts/weekly", params={"program_id": PROGRAM}).json()
    rep.check("cohort views return rows", len(weekly) > 0)
    rep.check("no cohort group smaller than 5 patients", all(w["patients"] >= 5 for w in weekly))
    comp = company.get("/v1/company/completion", params={"program_id": PROGRAM}).json()
    rep.check("completion includes this week for Walter's cohort",
              any(c["iso_week"] == iso_week and c["cohort_id"] == WALTER["cohort_id"] for c in comp))
    for path in (f"/v1/orgs/{NORTHGATE}/envelopes", f"/v1/orgs/{NORTHGATE}/alerts", f"/v1/caregivers/{ANNA}/alerts"):
        r = company.get(path)
        rep.check(f"company role refused {path} (403)", r.status_code == 403, str(r.status_code))
    r = company.get("/v1/company/records/export", params={"program_id": PROGRAM})
    rep.check("company_reader cannot export records (403)", r.status_code == 403, str(r.status_code))

    rep.head("Consent revocation")
    revoked = {**consent, "share_care_team": False}
    patient.send_consent(revoked)
    northgate_key = b64(bytes(patel.org_keys[NORTHGATE].public_key))
    env = build_envelope(f"env_{secrets.token_hex(4)}", NORTHGATE, plaintext, northgate_key)
    try:
        patient.send_envelope(env)
        rep.check("after revoking care-team consent the next envelope is refused (403)", False, "accepted")
    except SendRejected as e:
        rep.check("after revoking care-team consent the next envelope is refused (403)", e.status == 403, str(e.status))
    patient.send_consent(consent)

    rep.head("Privacy at rest and in logs")
    relay = sqlite3.connect(data_dir / "relay.db")
    stored = relay.execute("SELECT ciphertext FROM care_inbox WHERE envelope_id = ?",
                           (envelopes[NORTHGATE]["envelope_id"],)).fetchone()
    rep.check("relay holds only ciphertext for the envelope",
              stored is not None and WALTER["display_name"].encode() not in base64.b64decode(stored[0])
              and stored[0] == envelopes[NORTHGATE]["ciphertext"])
    for name in ("company.db", "relay.db"):
        blob = (data_dir / name).read_bytes() + ((data_dir / f"{name}-wal").read_bytes()
                                                  if (data_dir / f"{name}-wal").exists() else b"")
        rep.check(f"{name} never contains the patient's name", WALTER["display_name"].encode() not in blob)
    log = log_path.read_text()
    leaks = [w for w in (WALTER["display_name"], "SE_RASH", envelopes[NORTHGATE]["ciphertext"][:24], '"symptoms"')
             if w in log]
    rep.check("service log has no names, symptoms, ciphertext or bodies", not leaks, ", ".join(leaks))


def main() -> None:
    ap = argparse.ArgumentParser(description="End-to-end check across patient, doctor, caregiver and company")
    ap.add_argument("--keep", action="store_true", help="keep the temp data dir and service log for inspection")
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="sentinel-e2e-"))
    data_dir, log_path = tmp / "data", tmp / "service.log"
    data_dir.mkdir()
    port = free_port()
    print(f"Throwaway service on 127.0.0.1:{port}, data in {tmp}")
    proc = start_service(data_dir, port, log_path)
    rep = Report()
    try:
        run(f"http://127.0.0.1:{port}", data_dir, log_path, rep)
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        if not args.keep:
            for p in sorted(tmp.rglob("*"), reverse=True):
                p.unlink() if p.is_file() else p.rmdir()
            tmp.rmdir()
    print(f"\n{rep.passed} passed, {len(rep.failed)} failed")
    if rep.failed:
        print("Failed: " + "; ".join(rep.failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
