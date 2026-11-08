"""Seed the service databases with the demo program and synthetic cohort history (Scoping Doc 16, 26.10; D-053).

    python -m sentinel_service.seed              # seed var/service if empty (safe to re-run)
    python -m sentinel_service.seed --reset      # wipe company.db and relay.db first

Content:
- Program, 4 cohorts, term list, survey v1 per cohort, demo doctor, caregiver and links: schema/ files.
- Enrollments: the demo patients from schema/demo_fixtures.json plus synthetic patients up to N per cohort.
- History: daily check-ins from the Monday of the first week through yesterday (today is left for the live demo).
  Side-effect weights come from openFDA report counts for Tagrisso (data/company/openfda); cohort effects are a
  documented synthetic story (STORY below). Missed check-ins are scheduler records (D-003). Relay alerts are
  created only for patients with care or caregiver links.

All data is synthetic. Deterministic for a given --rng-seed and --today.
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from sentinel_contract import SCHEMA_DIR, payload_sha256

from . import escalation
from .common import fmt_ts, iso_week
from .db import REPO_ROOT, Databases, default_data_dir

OPENFDA = REPO_ROOT / "data" / "company" / "openfda" / "tagrisso_reaction_counts.json"

# term_code -> openFDA MedDRA preferred terms whose counts weight it
TERM_PTS = {
    "SE_RASH": ["RASH"],
    "SE_DRY_SKIN": ["DRY SKIN"],
    "SE_PARONYCHIA": ["PARONYCHIA", "NAIL DISORDER"],
    "SE_DIARRHEA": ["DIARRHOEA"],
    "SE_STOMATITIS": ["STOMATITIS"],
    "SE_FATIGUE": ["FATIGUE"],
    "SE_DECREASED_APPETITE": ["DECREASED APPETITE"],
    "SE_DYSPNEA": ["DYSPNOEA"],
    "SE_COUGH": ["COUGH"],
}
TOP_WEEKLY_PREVALENCE = 0.20  # the most-reported term (diarrhoea) -> 20% of patients in a given week
OTHER_REVIEW_PREVALENCE = 0.02

# Synthetic cohort story the dashboard should surface (documented in D-053; not real data):
#   v2 (cohort_B): dermatologic events rise week over week (an emerging signal)
#   v3 (cohort_C): fewer GI events;  v4 (cohort_D): more fatigue
DERM = {"SE_RASH", "SE_PARONYCHIA", "SE_DRY_SKIN"}
STORY = {
    "cohort_B": lambda term, w, n: (1.3 + 0.9 * w / max(n - 1, 1)) if term in DERM else 1.0,
    "cohort_C": lambda term, w, n: 0.6 if term in {"SE_DIARRHEA", "SE_DECREASED_APPETITE"} else 1.0,
    "cohort_D": lambda term, w, n: 1.4 if term == "SE_FATIGUE" else 1.0,
}
SEVERITY = {"default": [("mild", 0.62), ("moderate", 0.30), ("severe", 0.08)],
            "SE_DYSPNEA": [("mild", 0.55), ("moderate", 0.30), ("severe", 0.15)]}
WINDOWS = ["13:00-16:00", "14:00-17:00", "15:00-18:00", "16:00-19:00"]
FIXTURE_ADHERENCE = {"Walter": 0.97, "Priya": 0.82}
PROXY_RATE = 0.15        # share of synthetic patients whose check-ins a caregiver or parent answers (D-058)
INPUT_MODES = [("voice", 0.6), ("text", 0.3), ("mixed", 0.1)]  # D-059
PARTIAL_RATE = 0.04
REPORT_RATE = 0.85      # chance a patient mentions an ongoing symptom on a given check-in
LINK_FLAG_RATE = 0.05   # dermatologic episodes flagged "possible link, for review"


def _load(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text())


def weekly_prevalence() -> dict[str, float]:
    counts = {r["term"]: r["count"] for r in json.loads(OPENFDA.read_text())["results"]}
    weights = {t: sum(counts.get(pt, 0) for pt in pts) for t, pts in TERM_PTS.items()}
    top = max(weights.values())
    prev = {t: TOP_WEEKLY_PREVALENCE * w / top for t, w in weights.items()}
    prev["SE_OTHER_REVIEW"] = OTHER_REVIEW_PREVALENCE
    return prev


def _pick(rng: random.Random, options: list[tuple[str, float]]) -> str:
    x, acc = rng.random(), 0.0
    for value, p in options:
        acc += p
        if x < acc:
            return value
    return options[-1][0]


def _onset(days_since_start: int) -> str:
    if days_since_start == 0:
        return "today"
    if days_since_start <= 3:
        return "1_3_days"
    if days_since_start <= 7:
        return "4_7_days"
    return "over_7_days"


def _uid(rng: random.Random, prefix: str, taken: set[str]) -> str:
    while True:
        v = f"{prefix}{rng.getrandbits(32):08x}"
        if v not in taken:
            taken.add(v)
            return v


def _at(day: date, hhmm: str, plus_seconds: float = 0.0) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return datetime.combine(day, time(h, m), tzinfo=timezone.utc) + timedelta(seconds=plus_seconds)


def is_seeded(dbs: Databases) -> bool:
    return dbs.company.execute("SELECT 1 FROM program LIMIT 1").fetchone() is not None


def seed(dbs: Databases, *, patients_per_cohort: int = 250, weeks: int = 4, rng_seed: int = 1984,
         today: date | None = None) -> dict:
    rng = random.Random(rng_seed)
    today = today or datetime.now(timezone.utc).date()
    fx = _load("demo_fixtures.json")
    terms = _load("terms.json")["terms"]
    survey = _load("examples/survey_config.valid.json")
    program = fx["program"]
    drug = program["drug_name"]
    known = {t["term_code"]: drug in t["drug_scope"] for t in terms}
    prev = weekly_prevalence()
    t0 = fmt_ts(datetime.combine(today - timedelta(days=7 * weeks + 14), time(12), tzinfo=timezone.utc))
    admin = next(u["user_id"] for u in fx["company_users"] if u["role"] == "company_admin")

    # ---- patients ----
    ids: set[str] = {p["patient_ref"] for p in fx["device_profiles"]}
    patients = []  # dicts: patient_ref, cohort_id, window, adherence, consents, reporter, linked, enrolled
    fixture_enroll = {e["patient_ref"]: e for e in fx["enrollments"]}
    for p in fx["device_profiles"]:
        e = fixture_enroll[p["patient_ref"]]
        patients.append({"patient_ref": p["patient_ref"], "cohort_id": e["cohort_id"], "window": e["checkin_window"],
                         "adherence": FIXTURE_ADHERENCE.get(p["display_name"], 0.85),
                         "consent_care_team": p["consent"]["share_care_team"], "reporter": p["reporter_default"],
                         "consent_caregiver": p["consent"]["share_caregiver"], "linked": True,
                         "enrolled": date.fromisoformat(p["enrolled_at"][:10]),
                         "missed_tail": e.get("demo_missed_tail", 0), "synthetic": False})
    cohorts = {c["cohort_id"]: c["drug_version"] for c in fx["cohorts"]}
    for cohort_id in cohorts:
        have = sum(1 for p in patients if p["cohort_id"] == cohort_id)
        for _ in range(max(patients_per_cohort - have, 0)):
            patients.append({"patient_ref": _uid(rng, "pt_", ids), "cohort_id": cohort_id,
                             "window": rng.choice(WINDOWS), "adherence": rng.uniform(0.62, 0.95),
                             "consent_care_team": rng.random() < 0.7, "consent_caregiver": rng.random() < 0.45,
                             "reporter": "caregiver" if rng.random() < PROXY_RATE else "self",
                             "linked": False, "enrolled": None, "missed_tail": 0, "synthetic": True})

    # ---- days and weeks of history ----
    monday = today - timedelta(days=today.weekday()) - timedelta(weeks=weeks - 1)
    days = [monday + timedelta(days=i) for i in range((today - monday).days)]  # up to yesterday
    week_keys = sorted({iso_week(datetime.combine(d, time(12))) for d in days})
    week_index = {w: i for i, w in enumerate(week_keys)}

    record_ids: set[str] = set()
    alert_ids: set[str] = set()
    records, symptoms, alerts = [], [], []
    for p in patients:
        cohort_id, version = p["cohort_id"], cohorts[p["cohort_id"]]
        story = STORY.get(cohort_id, lambda term, w, n: 1.0)
        # episodes: (term, start_day, severity, link_flag) per ISO week
        episodes = []
        for wk in week_keys:
            wdays = [d for d in days if iso_week(datetime.combine(d, time(12))) == wk]
            for term, base in prev.items():
                if rng.random() < min(base * story(term, week_index[wk], len(week_keys)), 0.95):
                    sev = _pick(rng, SEVERITY.get(term, SEVERITY["default"]))
                    flag = term in DERM and rng.random() < LINK_FLAG_RATE
                    episodes.append((term, rng.choice(wdays), wk, sev, flag))
        consecutive_missed = 0
        for d in days:
            if p["enrolled"] and d < p["enrolled"]:
                continue  # no check-ins before the patient enrolled
            wk = iso_week(datetime.combine(d, time(12)))
            x = rng.random()
            status = "missed" if x > p["adherence"] else ("partial" if x > p["adherence"] - PARTIAL_RATE else
                                                         "completed")
            if (today - d).days <= p["missed_tail"]:
                status = "missed"  # demo: a run of misses right before today (demo_fixtures enrollments)
            start, end = p["window"].split("-")
            if status == "missed":
                received = _at(d, end, 30)  # the scheduler marks it after the window closes (D-003)
                syms = []
            else:
                received = _at(d, start, rng.uniform(0, 3 * 3600 - 60))
                syms = []
                for term, sday, ewk, sev, flag in episodes:
                    if ewk == wk and sday <= d and rng.random() < REPORT_RATE and len(syms) < 10:
                        syms.append({"term_code": term, "severity": sev, "onset": _onset((d - sday).days),
                                     "known_side_effect": known[term], "possible_link_flag": flag})
            payload = {
                "schema_version": "2.0", "record_id": _uid(rng, "rec_", record_ids),
                "patient_ref": p["patient_ref"], "program_id": program["program_id"], "cohort_id": cohort_id,
                "drug_version": version, "iso_week": wk, "status": status, "symptoms": syms,
                "unanswered_questions": rng.randint(1, 2) if status == "partial" else 0,
                "consent": {"care_team": p["consent_care_team"], "caregiver": p["consent_caregiver"]},
            }
            if status != "missed":  # scheduler records have no reporter or input mode
                payload["reporter"] = p["reporter"]
                payload["input_mode"] = _pick(rng, INPUT_MODES)
            records.append((payload["record_id"], "2.0", p["patient_ref"], program["program_id"], cohort_id, version,
                            wk, status, payload["unanswered_questions"], int(p["consent_care_team"]),
                            int(p["consent_caregiver"]), payload_sha256(payload), payload.get("reporter"),
                            payload.get("input_mode"), "scheduler" if status == "missed" else "device",
                            fmt_ts(received)))
            symptoms.extend((payload["record_id"], s["term_code"], s["severity"], s["onset"],
                             int(s["known_side_effect"]), int(s["possible_link_flag"])) for s in syms)
            consecutive_missed = consecutive_missed + 1 if status == "missed" else 0
            if p["linked"]:  # D-068: missed alerts carry the escalation level (consecutive misses, capped at 3)
                if status == "missed":
                    alerts.append((_uid(rng, "alt_", alert_ids), p["patient_ref"], "missed",
                                   min(consecutive_missed, 3), fmt_ts(received)))
                if any(s["severity"] == "severe" for s in syms):
                    alerts.append((_uid(rng, "alt_", alert_ids), p["patient_ref"], "severe", None, fmt_ts(received)))

    # ---- write ----
    c, r = dbs.company, dbs.relay
    with dbs.tx(c, r):
        c.execute("INSERT INTO program VALUES (?,?,?,?)", (program["program_id"], program["company_id"], drug, t0))
        c.executemany("INSERT INTO cohort VALUES (?,?,?,?,?)",
                      [(k["cohort_id"], program["program_id"], k["drug_version"], k["label"], patients_per_cohort)
                       for k in fx["cohorts"]])
        c.executemany("INSERT INTO term_code VALUES (?,?,?,?,?)",
                      [(t["term_code"], t["label_term"], json.dumps(t["everyday_words"]), json.dumps(t["drug_scope"]),
                        int(t["severe_trigger"])) for t in terms])
        c.executemany("INSERT INTO survey_config VALUES (?,?,?,?,?,?)",
                      [(f"cfg_{k.lower()}_v1", k, 1, json.dumps(survey), t0, admin) for k in cohorts])
        c.executemany("INSERT INTO enrollment (patient_ref, program_id, cohort_id, checkin_window, start_date, "
                      "synthetic, active) VALUES (?,?,?,?,?,?,1)",
                      [(p["patient_ref"], program["program_id"], p["cohort_id"], p["window"],
                        (p["enrolled"] or monday).isoformat(), int(p["synthetic"])) for p in patients])
        c.executemany("INSERT INTO checkin_record (record_id, schema_version, patient_ref, program_id, cohort_id, "
                      "drug_version, iso_week, status, unanswered_questions, consent_care_team, consent_caregiver, "
                      "payload_sha256, reporter, input_mode, source, received_at) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", records)
        c.executemany("INSERT INTO symptom_record (record_id, term_code, severity, onset, known_side_effect, "
                      "possible_link_flag) VALUES (?,?,?,?,?,?)", symptoms)

        profiles = {p["patient_ref"]: p for p in fx["device_profiles"]}
        granted = {pr: profiles[pr]["enrolled_at"].replace("Z", ".000000Z") for pr in profiles}
        r.executemany("INSERT INTO organization (org_id, display_name, org_type, public_key, created_at) "
                      "VALUES (?,?,?,NULL,?)",
                      [(o["org_id"], o["display_name"], o["org_type"], t0) for o in fx["organizations"]])
        r.executemany("INSERT INTO doctor (doctor_id, display_name, public_key) VALUES (?,?,NULL)",
                      [(d["doctor_id"], d["display_name"]) for d in fx["doctors"]])
        r.executemany("INSERT INTO org_member (org_id, doctor_id, role, status, granted_at) VALUES (?,?,?,?,?)",
                      [(m["org_id"], m["doctor_id"], m["role"], m["status"], t0) for m in fx["org_members"]])
        r.executemany("INSERT INTO care_link (org_id, patient_ref, link_type, status, granted_at) VALUES (?,?,?,?,?)",
                      [(l["org_id"], l["patient_ref"], l["link_type"], l["status"], granted[l["patient_ref"]])
                       for l in fx["care_links"]])
        r.executemany("INSERT INTO caregiver_link (caregiver_id, patient_ref, detail_level, status, granted_at) "
                      "VALUES (?,?,?,?,?)",
                      [(l["caregiver_id"], l["patient_ref"], l["detail_level"], l["status"], granted[l["patient_ref"]])
                       for l in fx["caregiver_links"]])
        r.executemany("INSERT INTO emergency_contact (contact_id, patient_ref, contact_type, phone, org_id, priority, "
                      "consented_at) VALUES (?,?,?,?,?,?,?)",
                      [(e["contact_id"], e["patient_ref"], e["contact_type"], e["phone"], e["org_id"], e["priority"],
                        granted[e["patient_ref"]]) for e in fx["emergency_contacts"]
                       if profiles[e["patient_ref"]]["consent"]["emergency_consent"]])  # D-067
        for alert_id, patient_ref, kind, level, at in alerts:
            r.execute("INSERT INTO alert (alert_id, patient_ref, alert_type, escalation_level, created_at, received_at) "
                      "VALUES (?,?,?,?,?,?)", (alert_id, patient_ref, kind, level, at, at))
            escalation.record_deliveries(r, alert_id, escalation.recipients(r, patient_ref, kind, level), at)

    return {"patients": len(patients), "days": len(days), "weeks": week_keys, "records": len(records),
            "symptoms": len(symptoms), "relay_alerts": len(alerts)}


def reset(data_dir: Path) -> None:
    for name in ("company.db", "relay.db"):
        for suffix in ("", "-wal", "-shm"):
            (data_dir / f"{name}{suffix}").unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--reset", action="store_true", help="delete company.db and relay.db first")
    ap.add_argument("--patients-per-cohort", type=int, default=250)
    ap.add_argument("--weeks", type=int, default=4)
    ap.add_argument("--rng-seed", type=int, default=1984)
    ap.add_argument("--today", type=date.fromisoformat, default=None, help="UTC date to treat as today")
    ap.add_argument("--data-dir", type=Path, default=None)
    args = ap.parse_args()

    data_dir = args.data_dir or default_data_dir()
    if args.reset:
        reset(data_dir)
    dbs = Databases(data_dir)
    try:
        if is_seeded(dbs):
            print(f"{data_dir} is already seeded; nothing to do (use --reset to start over).")
            return
        summary = seed(dbs, patients_per_cohort=args.patients_per_cohort, weeks=args.weeks,
                       rng_seed=args.rng_seed, today=args.today)
    finally:
        dbs.close()
    print(f"seeded {data_dir}: {summary['patients']} patients, {summary['records']} check-ins over "
          f"{summary['days']} days ({', '.join(summary['weeks'])}), {summary['symptoms']} symptom reports, "
          f"{summary['relay_alerts']} relay alerts")


if __name__ == "__main__":
    main()
