"""Act as Walter's device: send one real sealed-box envelope (and optionally a severe alert) to the running service.

Lets the doctor web app be built and tested before the patient runtime exists. The doctor web app must have
registered its public key first (PUT /v1/doctors/{id}/public-key), otherwise this exits with 404.

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
        key = client.fetch_doctor_key(walter["doctor_id"])
    except SendRejected as e:
        raise SystemExit(f"cannot fetch doctor key ({e.status}): register it from the doctor web app first. {e.body}")
    env = build_envelope(f"env_{secrets.token_hex(4)}", walter["doctor_id"], plaintext, key)
    res = client.send_envelope(env)
    print(f"envelope {env['envelope_id']} -> {res.status_code}, plaintext sha256 {res.payload_sha256}")

    if args.alert:
        alert = {"schema_version": "1.0", "alert_id": f"alt_{secrets.token_hex(4)}",
                 "patient_ref": walter["patient_ref"], "alert_type": "severe",
                 "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
        res = client.send_alert(alert)
        print(f"alert {alert['alert_id']} -> {res.status_code}, routed {res.body}")


if __name__ == "__main__":
    main()
