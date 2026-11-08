"""Send a synthetic 3-week check-in history for Walter and Priya to their care team (and Walter's emergency hospital),
so the doctor timeline looks like a real patient's. Synthetic data only; acts as each patient's device over HTTP.

Run from the repo root AFTER the Northgate admin (Dr. Patel) has created the care-team key in the doctor web app
(and, for emergency access, after Dr. Okafor has created Lakeside's key):
  uv run --project packages/contract-py python data/doctor/send_demo_history.py [--days 20] [--base-url URL]

Safe to re-run: envelope IDs are derived from patient and date, and an already-sent day returns 409, which is skipped.
Prints only counts and status codes, never payload contents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, timedelta

from sentinel_contract import SCHEMA_DIR
from sentinel_contract.client import SendRejected, SentinelClient, build_envelope

FIX = json.loads((SCHEMA_DIR / "demo_fixtures.json").read_text())


def S(term: str, severity: str, onset: str, link: bool = False, known: bool = True) -> dict:
    return {"term_code": term, "severity": severity, "onset": onset, "known_side_effect": known, "possible_link_flag": link}


# day offset (days before today) -> (status, trend, reporter, symptoms). Missing offsets = no check-in that day.
WALTER = {
    20: ("completed", "same", "self", []),
    19: ("completed", "same", "self", [S("SE_FATIGUE", "mild", "over_7_days")]),
    17: ("completed", "same", "self", [S("SE_FATIGUE", "mild", "over_7_days")]),
    16: ("completed", "same", "caregiver", []),
    15: ("partial", "unknown", "caregiver", [S("SE_FATIGUE", "mild", "over_7_days")]),
    13: ("completed", "same", "self", [S("SE_DRY_SKIN", "mild", "1_3_days")]),
    12: ("completed", "worse", "self", [S("SE_RASH", "mild", "today", link=True), S("SE_DRY_SKIN", "mild", "4_7_days")]),
    11: ("completed", "worse", "self", [S("SE_RASH", "mild", "1_3_days", link=True)]),
    10: ("completed", "same", "caregiver", [S("SE_RASH", "mild", "1_3_days"), S("SE_DIARRHEA", "mild", "today")]),
    8: ("completed", "worse", "self", [S("SE_RASH", "moderate", "4_7_days", link=True), S("SE_DIARRHEA", "mild", "1_3_days")]),
    7: ("completed", "same", "self", [S("SE_RASH", "moderate", "4_7_days"), S("SE_DIARRHEA", "moderate", "4_7_days")]),
    6: ("completed", "better", "caregiver", [S("SE_RASH", "moderate", "4_7_days"), S("SE_DECREASED_APPETITE", "mild", "1_3_days")]),
    4: ("completed", "same", "self", [S("SE_RASH", "moderate", "over_7_days"), S("SE_PARONYCHIA", "mild", "today")]),
    3: ("completed", "worse", "self", [S("SE_RASH", "moderate", "over_7_days", link=True), S("SE_PARONYCHIA", "mild", "1_3_days")]),
    2: ("partial", "worse", "caregiver", [S("SE_RASH", "moderate", "over_7_days"), S("SE_OTHER_REVIEW", "mild", "1_3_days", known=False)]),
    1: ("completed", "worse", "self", [S("SE_RASH", "moderate", "over_7_days", link=True), S("SE_PARONYCHIA", "moderate", "1_3_days")]),
}
PRIYA = {
    20: ("completed", "same", "self", [S("SE_FATIGUE", "moderate", "over_7_days")]),
    18: ("completed", "same", "self", [S("SE_FATIGUE", "moderate", "over_7_days")]),
    16: ("completed", "better", "self", [S("SE_FATIGUE", "mild", "over_7_days")]),
    14: ("completed", "same", "self", [S("SE_FATIGUE", "mild", "over_7_days"), S("SE_COUGH", "mild", "today")]),
    11: ("completed", "better", "self", [S("SE_COUGH", "mild", "1_3_days")]),
    9: ("completed", "better", "self", []),
    7: ("completed", "same", "self", [S("SE_DRY_SKIN", "mild", "4_7_days")]),
    5: ("completed", "same", "self", []),
    3: ("completed", "better", "self", [S("SE_DRY_SKIN", "mild", "over_7_days")]),
    1: ("completed", "same", "self", []),
}


def age(dob: str, on: date) -> int:
    y, m, d = map(int, dob.split("-"))
    return on.year - y - ((on.month, on.day) < (m, d))


def send(profile: dict, story: dict, days: int, base_url: str) -> None:
    dev = SentinelClient(base_url, profile["patient_ref"])
    keys = {}
    for org in [profile["care_org_id"], *profile.get("emergency_org_ids", [])]:
        try:
            keys[org] = dev.fetch_org_key(org)
        except SendRejected as e:
            print(f"  {profile['display_name']}: no key for {org} ({e.status}); create it in the doctor web app first")
    if profile["care_org_id"] not in keys:
        return
    today = date.today()
    counts: dict[str, int] = {}
    for offset, (status, trend, reporter, symptoms) in sorted(story.items(), reverse=True):
        if offset > days:
            continue
        day = today - timedelta(days=offset)
        payload = {
            "schema_version": "2.0", "patient_ref": profile["patient_ref"], "display_name": profile["display_name"],
            "drug_name": profile["drug_name"], "drug_version": profile["drug_version"],
            "checkin_date": day.isoformat(), "status": status, "trend": trend, "symptoms": symptoms,
            "reporter": reporter, "age_years": age(profile["date_of_birth"], day),
        }
        for org, key in keys.items():
            env_id = "env_" + hashlib.sha256(f"demo-history|{profile['patient_ref']}|{org}|{day}".encode()).hexdigest()[:8]
            try:
                code = dev.send_envelope(build_envelope(env_id, org, payload, key)).status_code
            except SendRejected as e:
                code = e.status
            counts[f"{org} {code}"] = counts.get(f"{org} {code}", 0) + 1
    print(f"  {profile['display_name']}: " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())) + "  (409 = already sent)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--days", type=int, default=20, help="how many days back to send (max 20)")
    args = ap.parse_args()
    profiles = {p["display_name"]: p for p in FIX["device_profiles"]}
    print("Sending synthetic history (envelope status counts per organization):")
    send(profiles["Walter"], WALTER, args.days, args.base_url)
    send(profiles["Priya"], PRIYA, args.days, args.base_url)
    print("Done. Click \"Sync now\" in the doctor web app.")


if __name__ == "__main__":
    main()
