"""Act as Walter's device: send a real sealed-box envelope to his care team (and to each consented emergency
hospital whose key is registered), and optionally a severe alert. Contract 2.0.

Lets the doctor web app be built and tested before the patient runtime exists. The organization's admin must have
registered its care-team key first (PUT /v1/orgs/{org_id}/public-key), otherwise this exits with 404.

Run from the repo root (service running):
  uv run --project packages/contract-py python scripts/send_demo_envelope.py [--alert] [--trend worse] [--base-url URL]
"""

from __future__ import annotations

import argparse
import json
import secrets
from datetime import datetime, timezone

from sentinel_contract import SCHEMA_DIR
from sentinel_contract.client import SendRejected, SentinelClient, build_envelope


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--alert", action="store_true", help="also send a severe alert")
    ap.add_argument("--trend", default="worse", choices=["better", "same", "worse", "unknown"])
    args = ap.parse_args()

    fixtures = json.loads((SCHEMA_DIR / "demo_fixtures.json").read_text())
    walter = next(p for p in fixtures["device_profiles"] if p["display_name"] == "Walter")
    plaintext = json.loads((SCHEMA_DIR / "examples" / "doctor_payload.valid.json").read_text())
    now = datetime.now(timezone.utc)
    plaintext.update(checkin_date=now.strftime("%Y-%m-%d"), trend=args.trend)

    client = SentinelClient(args.base_url, walter["patient_ref"])
    try:
        key = client.fetch_org_key(walter["care_org_id"])
    except SendRejected as e:
        raise SystemExit(f"cannot fetch the care-team key ({e.status}): the organization admin must register it "
                         f"from the doctor web app first. {e.body}")
    recipients = [(walter["care_org_id"], key)]
    for org in walter["emergency_org_ids"]:
        try:
            recipients.append((org, client.fetch_org_key(org)))
        except SendRejected:
            print(f"skipping emergency organization {org}: no care-team key registered yet")
    for org, org_key in recipients:
        env = build_envelope(f"env_{secrets.token_hex(4)}", org, plaintext, org_key)
        res = client.send_envelope(env)
        print(f"envelope {env['envelope_id']} -> {org}: {res.status_code}, plaintext sha256 {res.payload_sha256}")

    if args.alert:
        alert = {"schema_version": "2.0", "alert_id": f"alt_{secrets.token_hex(4)}",
                 "patient_ref": walter["patient_ref"], "alert_type": "severe",
                 "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
        res = client.send_alert(alert)
        print(f"alert {alert['alert_id']} -> {res.status_code}, routed {res.body}")


if __name__ == "__main__":
    main()
