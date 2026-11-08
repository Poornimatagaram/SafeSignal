"""Doctor-side checks from Scoping Doc 26.15 on contract 2.0 (Access control, Privacy, End to end), against a live service.

Plays several roles over HTTP only (company user, Northgate admin and members, Lakeside emergency doctor, Walter's
device, Anna). It never reads a database file. It prints and records only check names, status codes, IDs and timings,
never payload contents.

Run from the repo root with the service running (seeded):
  uv run --project packages/contract-py python evals/doctor/access_checks.py [--base-url URL] [--write]

Keys: if Northgate and Lakeside already have care-team keys (registered from the doctor web app), the checks seal to
those keys and skip decryption, so the open apps keep working. Otherwise the script registers throwaway org keys,
which also lets it check decrypt + hash; reseed (`python -m sentinel_service.seed --reset`) before a demo.
The doctor-change check uses Dr. Rivera (not a member in the seed) and leaves her revoked, as she started.
"""

from __future__ import annotations

import argparse
import base64
import json
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from nacl.public import PrivateKey, PublicKey, SealedBox
from sentinel_contract import SCHEMA_DIR, payload_sha256
from sentinel_contract.client import SendRejected, SentinelClient, build_envelope

ROOT = Path(__file__).resolve().parents[2]
FIX = json.loads((SCHEMA_DIR / "demo_fixtures.json").read_text())
DOC = {d["display_name"]: d["doctor_id"] for d in FIX["doctors"]}
SHAH, PATEL, RIVERA, OKAFOR = DOC["Dr. Shah"], DOC["Dr. Patel"], DOC["Dr. Rivera"], DOC["Dr. Okafor"]
ORG = {o["display_name"]: o["org_id"] for o in FIX["organizations"]}
NG, LS = ORG["Northgate Medical Center"], ORG["Lakeside Emergency Hospital"]
CG = FIX["caregivers"][0]["caregiver_id"]
WALTER = next(p for p in FIX["device_profiles"] if p["display_name"] == "Walter")["patient_ref"]
PRIYA = next(p for p in FIX["device_profiles"] if p["display_name"] == "Priya")["patient_ref"]
COMPANY = next(u for u in FIX["company_users"] if u["role"] == "company_safety")["user_id"]
B64 = lambda b: base64.b64encode(bytes(b)).decode()  # noqa: E731

results: list[dict] = []


def check(section: str, name: str, ok: bool, detail: str) -> None:
    results.append({"section": section, "check": name, "pass": bool(ok), "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'}  [{section}] {name}: {detail}")


def skip(section: str, name: str, why: str) -> None:
    print(f"SKIP  [{section}] {name}: {why}")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def h(role: str, actor: str) -> dict:
    return {"X-Role": role, "X-Actor-Id": actor}


def plaintext(trend: str = "worse") -> dict:
    p = json.loads((SCHEMA_DIR / "examples" / "doctor_payload.valid.json").read_text())
    p.update(checkin_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"), trend=trend)
    return p


def consent(share_care_team: bool) -> dict:
    c = json.loads((SCHEMA_DIR / "examples" / "consent_update.valid.json").read_text())
    c["share_care_team"] = share_care_team
    return c


def send_env(dev: SentinelClient, org: str, key: str, patient: dict | None = None) -> tuple[int, dict]:
    env = build_envelope(f"env_{secrets.token_hex(4)}", org, patient or plaintext(), key)
    try:
        return dev.send_envelope(env).status_code, env
    except SendRejected as e:
        return e.status, env


def org_key(http: httpx.Client, org: str, admin: str) -> tuple[str, PrivateKey | None]:
    """Return the org's public key, registering a throwaway one (with its private key) if none exists."""
    r = http.get(f"/v1/orgs/{org}/public-key", headers=h("patient_device", WALTER))
    if r.status_code == 200:
        return r.json()["public_key"], None
    k = PrivateKey.generate()
    http.put(f"/v1/orgs/{org}/public-key", headers=h("doctor", admin), json={"public_key": B64(k.public_key)}).raise_for_status()
    return B64(k.public_key), k


def wait_for(fn, timeout: float = 60) -> tuple[object, float]:
    t0 = time.monotonic()
    while True:
        v = fn()
        if v or time.monotonic() - t0 > timeout:
            return v, time.monotonic() - t0
        time.sleep(1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--write", action="store_true", help="save results to evals/doctor/results/")
    args = ap.parse_args()

    http = httpx.Client(base_url=args.base_url, timeout=10)
    walter = SentinelClient(args.base_url, WALTER)
    priya = SentinelClient(args.base_url, PRIYA)
    shah = h("doctor", SHAH)

    ng_pub, ng_priv = org_key(http, NG, PATEL)
    ls_pub, ls_priv = org_key(http, LS, OKAFOR)
    print("Org keys:", "throwaway (reseed before a demo)" if ng_priv or ls_priv else "registered by the doctor app (decrypt checks skipped)")

    # ---------------- Access control ----------------
    org_calls = [
        ("GET", f"/v1/orgs/{NG}/patients"), ("GET", f"/v1/orgs/{NG}/envelopes"), ("GET", f"/v1/orgs/{NG}/alerts"),
        ("POST", f"/v1/orgs/{NG}/envelopes/env_00000000/ack"), ("PUT", f"/v1/orgs/{NG}/public-key"),
        ("POST", f"/v1/orgs/{NG}/key-grants"), ("GET", f"/v1/orgs/{NG}/key-grants/{SHAH}"),
        ("PUT", f"/v1/orgs/{NG}/members/{RIVERA}"), ("POST", f"/v1/orgs/{LS}/emergency-access"),
        ("GET", f"/v1/caregivers/{CG}/alerts"), ("GET", f"/v1/doctors/{SHAH}/orgs"),
    ]
    # Well-formed bodies, so a 403 comes from the role check and not from body validation.
    body = {"public_key": ng_pub, "doctor_id": RIVERA, "wrapped_key": B64(b"x" * 80), "role": "attending",
            "status": "active", "patient_ref": WALTER, "reason": "emergency_admission"}
    codes = {f"{m} {u}": http.request(m, u, headers=h("company_safety", COMPANY), json=body).status_code for m, u in org_calls}
    bad = [f"{k} -> {v}" for k, v in codes.items() if v != 403]
    check("Access control", "Company role cannot reach any relay endpoint", not bad,
          f"{len(codes)} endpoints all 403" if not bad else "; ".join(bad))

    c1 = http.get(f"/v1/orgs/{NG}/envelopes", headers=h("doctor", RIVERA)).status_code
    c2 = http.get(f"/v1/orgs/{NG}/patients", headers=h("doctor", OKAFOR)).status_code
    check("Access control", "A doctor outside the organization cannot read its envelopes or patients",
          c1 == 403 and c2 == 403, f"Rivera envelopes {c1}, Okafor patients {c2}")

    c3 = http.get(f"/v1/orgs/{NG}/key-grants/{PATEL}", headers=shah).status_code
    check("Access control", "A member cannot fetch another member's key grant", c3 == 403, f"-> {c3}")

    c4 = http.put(f"/v1/orgs/{NG}/public-key", headers=shah, json={"public_key": ng_pub}).status_code
    c5 = http.put(f"/v1/orgs/{NG}/members/{RIVERA}", headers=shah, json={"role": "attending", "status": "active"}).status_code
    check("Access control", "A non-admin member cannot set the org key or add members", c4 == 403 and c5 == 403,
          f"org key {c4}, add member {c5}")

    pr = plaintext()
    pr.update(patient_ref=PRIYA, display_name="Priya", drug_version="v1")
    code, _ = send_env(priya, LS, ls_pub, pr)
    check("Access control", "A patient cannot send an envelope to an organization without a link", code == 403, f"-> {code}")

    missing = http.get(f"/v1/orgs/{NG}/patients").status_code
    check("Access control", "Requests without X-Role / X-Actor-Id are refused", missing == 401, f"-> {missing}")

    try:
        walter.send_consent(consent(False))
        code, _ = send_env(walter, NG, ng_pub)
        listed = [x["patient_ref"] for x in http.get(f"/v1/orgs/{NG}/patients", headers=shah).json()]
        check("Access control", "Revoking consent stops the next envelope", code == 403 and WALTER not in listed,
              f"envelope -> {code}; listed: {WALTER in listed}")
    finally:
        walter.send_consent(consent(True))

    # Doctor change with Rivera: add + grant -> she can read; revoke -> 403 and grant gone.
    rk = PrivateKey.generate()
    http.put(f"/v1/doctors/{RIVERA}/public-key", headers=h("doctor", RIVERA), json={"public_key": B64(rk.public_key)})
    patel = h("doctor", PATEL)
    a = http.put(f"/v1/orgs/{NG}/members/{RIVERA}", headers=patel, json={"role": "attending", "status": "active"}).status_code
    wrapped = B64(SealedBox(rk.public_key).encrypt(bytes(ng_priv) if ng_priv else secrets.token_bytes(32)))
    g = http.post(f"/v1/orgs/{NG}/key-grants", headers=patel, json={"doctor_id": RIVERA, "wrapped_key": wrapped}).status_code
    read = http.get(f"/v1/orgs/{NG}/envelopes", headers=h("doctor", RIVERA)).status_code
    r = http.put(f"/v1/orgs/{NG}/members/{RIVERA}", headers=patel, json={"role": "attending", "status": "revoked"}).status_code
    after = http.get(f"/v1/orgs/{NG}/envelopes", headers=h("doctor", RIVERA)).status_code
    grant = http.get(f"/v1/orgs/{NG}/key-grants/{RIVERA}", headers=h("doctor", RIVERA)).status_code
    check("Access control", "Doctor change: a granted member reads, a revoked member is refused and loses the grant",
          (a, g, read, r) == (200, 201, 200, 200) and after == 403 and grant in (403, 404),
          f"add {a}, grant {g}, read {read}, revoke {r}, read after {after}, grant after {grant}")

    # ---------------- End to end + privacy ----------------
    since = now()
    time.sleep(1.1)  # `since` is strictly after, on 1-second timestamps
    code, env = send_env(walter, NG, ng_pub)

    def arrived():
        rows = http.get(f"/v1/orgs/{NG}/envelopes", headers=shah, params={"since": since}).json()
        return next((x for x in rows if x["envelope_id"] == env["envelope_id"]), None)
    got, dt = wait_for(arrived)
    check("End to end", "Walter's envelope reaches the care team within 1 minute", code == 201 and bool(got),
          f"send {code}, visible after {dt:.1f}s")

    if got:
        raw = base64.b64decode(got["ciphertext"])
        try:
            json.loads(raw)
            is_json = True
        except ValueError:
            is_json = False
        leaked = [k for k in ("symptoms", "term_code", "display_name", "checkin_date") if k.encode() in raw]
        check("Privacy", "Relay returns only ciphertext to the care team", not is_json and not leaked,
              f"{len(raw)} bytes, parses as JSON: {is_json}, plaintext markers: {len(leaked)}")
        if ng_priv:
            opened = json.loads(SealedBox(ng_priv).decrypt(raw))
            ok = payload_sha256(opened) == got["payload_sha256"]
            check("End to end", "Org key decrypts it and the hash matches", ok, "sha256 match" if ok else "mismatch")
        else:
            skip("End to end", "Org key decrypts it and the hash matches", "org key held by the doctor app")
        ack = http.post(f"/v1/orgs/{NG}/envelopes/{got['envelope_id']}/ack", headers=shah).status_code
        check("End to end", "A member can acknowledge the envelope", ack == 200, f"-> {ack}")

    since = now()
    time.sleep(1.1)
    alert = {"schema_version": "2.0", "alert_id": f"alt_{secrets.token_hex(4)}", "patient_ref": WALTER,
             "alert_type": "severe", "created_at": now()}
    walter.send_alert(alert)

    def alert_seen():
        d = any(x["alert_id"] == alert["alert_id"] for x in http.get(f"/v1/orgs/{NG}/alerts", headers=shah, params={"since": since}).json())
        c = any(x["alert_id"] == alert["alert_id"] for x in http.get(f"/v1/caregivers/{CG}/alerts", headers=h("caregiver", CG)).json())
        return d and c
    seen, dt = wait_for(alert_seen)
    check("End to end", "Severe alert reaches the care team and the caregiver", bool(seen), f"after {dt:.1f}s")

    cg_rows = http.get(f"/v1/caregivers/{CG}/alerts", headers=h("caregiver", CG)).json()
    fields = sorted({k for x in cg_rows for k in x})
    check("Privacy", "Caregiver alerts carry no symptom details (AL-03)",
          not any(k in fields for k in ("symptoms", "term_code", "severity", "ciphertext")), f"fields: {', '.join(fields)}")

    # ---------------- Emergency access ----------------
    code_ls, _ = send_env(walter, LS, ls_pub)
    routine = http.get(f"/v1/orgs/{LS}/patients", headers=h("doctor", OKAFOR)).json()
    check("Access control", "The emergency hospital has no routine access", code_ls == 201 and WALTER not in [x["patient_ref"] for x in routine],
          f"sealed copy {code_ls}; routine patients: {len(routine)}")
    bad_reason = http.post(f"/v1/orgs/{LS}/emergency-access", headers=h("doctor", OKAFOR), json={"patient_ref": WALTER, "reason": "curious"}).status_code
    wrong_org = http.post(f"/v1/orgs/{NG}/emergency-access", headers=shah, json={"patient_ref": WALTER, "reason": "emergency_admission"}).status_code
    check("Access control", "Emergency access needs a coded reason and an emergency link", bad_reason == 422 and wrong_org == 403,
          f"bad reason {bad_reason}, care-team org {wrong_org}")
    since = now()
    time.sleep(1.1)
    ea = http.post(f"/v1/orgs/{LS}/emergency-access", headers=h("doctor", OKAFOR), json={"patient_ref": WALTER, "reason": "emergency_admission"})
    body = ea.json() if ea.status_code == 200 else {}
    check("End to end", "Emergency access releases the history and notifies caregiver and care team",
          ea.status_code == 200 and len(body.get("envelopes", [])) >= 1 and {"caregiver", "care_team"} <= set(body.get("notified", [])),
          f"{ea.status_code}, {len(body.get('envelopes', []))} envelope(s), notified {body.get('notified')}")

    def ea_alert():
        d = any(x["alert_type"] == "emergency_access" for x in http.get(f"/v1/orgs/{NG}/alerts", headers=shah, params={"since": since}).json())
        c = any(x["alert_type"] == "emergency_access" and x["created_at"] >= since for x in http.get(f"/v1/caregivers/{CG}/alerts", headers=h("caregiver", CG)).json())
        return d and c
    seen, dt = wait_for(ea_alert, 20)
    check("End to end", "Care team and caregiver see an emergency_access alert", bool(seen), f"after {dt:.1f}s")
    if ls_priv and body.get("envelopes"):
        e = body["envelopes"][-1]
        ok = payload_sha256(json.loads(SealedBox(ls_priv).decrypt(base64.b64decode(e["ciphertext"])))) == e["payload_sha256"]
        check("End to end", "Emergency org key decrypts the released history", ok, "sha256 match" if ok else "mismatch")

    skip("End to end", "Missed check-in alert within 1 minute", "scheduler exists since D-074; this check is not written yet")

    passed = sum(r["pass"] for r in results)
    print(f"\n{passed}/{len(results)} passed")
    if args.write:
        out = ROOT / "evals/doctor/results" / f"access_checks_{datetime.now().strftime('%Y-%m-%d_%H%M')}.json"
        out.write_text(json.dumps({"run_at": now(), "contract": "2.0", "base_url": args.base_url, "passed": passed,
                                   "total": len(results), "results": results}, indent=2) + "\n")
        print(f"wrote {out.relative_to(ROOT)}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
