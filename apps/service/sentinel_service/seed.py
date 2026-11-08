"""Seed the service databases with the company's programs and synthetic cohort history (Scoping Doc 16; D-053, D-081).

    python -m sentinel_service.seed              # seed var/service if empty (safe to re-run)
    python -m sentinel_service.seed --reset      # wipe company.db and relay.db first

Content:
- Company (fictional, D-078), its programs and cohorts, the term list, surveys, demo doctors, caregiver and links:
  schema/demo_fixtures.json and schema/terms.json.
- Real public grounding (data/company/, D-081): each cohort samples its records from one real trial arm's
  adverse-event rates (ClinicalTrials.gov extracts; mapping in trial_map.json). Programs list the trial's protocol,
  statistical analysis plan and FDA label in the `document` table (D-080).
- Enrollments: the demo patients from demo_fixtures plus synthetic patients up to N per cohort, in every program.
- History: daily check-ins from the Monday of the first week through yesterday (today is left for the live demo).
  Missed check-ins are scheduler records (D-003). Relay alerts are created only for patients with care or caregiver
  links.

Every patient and record is synthetic; only the rates and documents are real. Deterministic for a given --rng-seed
and --today.
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

DATA = REPO_ROOT / "data" / "company"
TRIAL_MAP = DATA / "trial_map.json"

WEEKLY_ACTIVE = 0.6      # an affected patient has an episode of that side effect in a given week
OTHER_REVIEW_PREVALENCE = 0.02  # weekly chance of something the term list does not cover
DERM = {"SE_RASH", "SE_PARONYCHIA", "SE_DRY_SKIN"}
SEVERITY = {"default": [("mild", 0.62), ("moderate", 0.30), ("severe", 0.08)],
            "SE_DYSPNEA": [("mild", 0.55), ("moderate", 0.30), ("severe", 0.15)]}
WINDOWS = ["13:00-16:00", "14:00-17:00", "15:00-18:00", "16:00-19:00"]
FIXTURE_ADHERENCE = {"Walter": 0.97, "Priya": 0.82}
INPUT_MODES = [("voice", 0.6), ("text", 0.3), ("mixed", 0.1)]  # D-059
PARTIAL_RATE = 0.04
REPORT_RATE = 0.85      # chance a patient mentions an ongoing symptom on a given check-in
LINK_FLAG_RATE = 0.05   # dermatologic episodes flagged "possible link, for review"


def _load(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text())


def trial_map() -> dict:
    return json.loads(TRIAL_MAP.read_text())


def trial_study(trial: str) -> dict:
    return json.loads((DATA / "ctgov" / f"{trial}.json").read_text())["study"]


def arm_rates(trial: str, meddra_to_term: dict[str, list[str]]) -> dict[str, dict[str, float]]:
    """Per arm (event group ID): term_code -> share of patients affected during the trial.

    A term code's MedDRA terms (serious and non-serious tables) combine as 1 - prod(1 - p_i).
    """
    lookup = {t.lower(): code for code, terms in meddra_to_term.items() for t in terms}
    ae = trial_study(trial)["resultsSection"]["adverseEventsModule"]
    survive = {g["id"]: {code: 1.0 for code in meddra_to_term} for g in ae["eventGroups"]}
    for event in ae.get("otherEvents", []) + ae.get("seriousEvents", []):
        code = lookup.get(event["term"].lower())
        if code is None:
            continue
        for st in event["stats"]:
            if st.get("numAtRisk"):
                survive[st["groupId"]][code] *= 1 - st.get("numAffected", 0) / st["numAtRisk"]
    return {g: {code: round(1 - s, 4) for code, s in codes.items()} for g, codes in survive.items()}


def arm_titles(trial: str) -> dict[str, str]:
    groups = trial_study(trial)["resultsSection"]["adverseEventsModule"]["eventGroups"]
    return {g["id"]: g["title"] for g in groups}


def documents(program_id: str, spec: dict) -> list[dict]:
    """Protocol and SAP from the trial's ClinicalTrials.gov record, plus the FDA label (D-080)."""
    study = trial_study(spec["trial"])
    nct = spec["nct"]
    out = []
    for d in study.get("documentSection", {}).get("largeDocumentModule", {}).get("largeDocs", []):
        kind = {"Prot": "protocol", "SAP": "sap"}.get(d["typeAbbrev"])
        if kind is None:
            continue
        title = {"protocol": "Study Protocol", "sap": "Statistical Analysis Plan"}[kind]
        out.append({"doc_id": f"doc_{spec['trial']}_{kind}", "program_id": program_id, "kind": kind,
                    "title": f"{spec['acronym']} ({nct}) {title}", "version": d.get("date") or "unknown",
                    "source_url": f"https://cdn.clinicaltrials.gov/large-docs/{nct[-2:]}/{nct}/{d['filename']}"})
    label = json.loads((DATA / "labels" / f"{spec['label']}.json").read_text())
    eff = label["effective_time"]
    out.append({"doc_id": f"doc_{spec['label']}_label", "program_id": program_id, "kind": "label",
                "title": f"FDA prescribing information ({spec['label'].capitalize()})",
                "version": f"{eff[:4]}-{eff[4:6]}-{eff[6:]}", "source_url": label["dailymed_url"]})
    return out


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
    tmap = trial_map()
    t0 = fmt_ts(datetime.combine(today - timedelta(days=7 * weeks + 14), time(12), tzinfo=timezone.utc))
    admin = next(u["user_id"] for u in fx["company_users"] if u["role"] == "company_admin")
    safety = next(u["user_id"] for u in fx["company_users"] if u["role"] == "company_safety")

    monday = today - timedelta(days=today.weekday()) - timedelta(weeks=weeks - 1)
    days = [monday + timedelta(days=i) for i in range((today - monday).days)]  # up to yesterday
    week_keys = sorted({iso_week(datetime.combine(d, time(12))) for d in days})

    ids: set[str] = {p["patient_ref"] for p in fx["device_profiles"]}
    record_ids: set[str] = set()
    alert_ids: set[str] = set()
    programs, cohort_rows, surveys, docs = [], [], [], []
    patients, records, symptoms, alerts = [], [], [], []
    fixture_enroll = {e["patient_ref"]: e for e in fx["enrollments"]}

    for prog in fx["programs"]:
        spec = tmap["programs"][prog["program_id"]]
        drug = prog["drug_name"]
        known = {t["term_code"]: drug in t["drug_scope"] for t in terms}
        rates = arm_rates(spec["trial"], tmap["meddra_to_term_code"])
        titles = arm_titles(spec["trial"])
        survey = json.loads((REPO_ROOT / spec["survey"]).read_text())
        reporters = list(spec["reporter"].items())
        programs.append((prog["program_id"], prog["company_id"], drug, t0, prog["label"], prog["population"],
                         f"{spec['acronym']} {spec['nct']}", f"https://clinicaltrials.gov/study/{spec['nct']}?tab=results"))
        docs.extend(documents(prog["program_id"], spec))
        cohorts = {c["cohort_id"]: c["drug_version"] for c in prog["cohorts"]}
        for c in prog["cohorts"]:
            group = spec["cohorts"][c["cohort_id"]]
            cohort_rows.append((c["cohort_id"], prog["program_id"], c["drug_version"], c["label"], patients_per_cohort,
                                f"{spec['acronym']} arm {group}: {titles[group]}"))
            surveys.append((f"cfg_{c['cohort_id'].lower()}_v1", c["cohort_id"], 1, json.dumps(survey), t0, admin))

        # ---- patients ----
        members = []
        for p in fx["device_profiles"]:
            if p["program_id"] != prog["program_id"]:
                continue
            e = fixture_enroll[p["patient_ref"]]
            members.append({"patient_ref": p["patient_ref"], "cohort_id": e["cohort_id"], "window": e["checkin_window"],
                            "adherence": FIXTURE_ADHERENCE.get(p["display_name"], 0.85),
                            "consent_care_team": p["consent"]["share_care_team"], "reporter": p["reporter_default"],
                            "consent_caregiver": p["consent"]["share_caregiver"], "linked": True,
                            "enrolled": date.fromisoformat(p["enrolled_at"][:10]),
                            "missed_tail": e.get("demo_missed_tail", 0), "synthetic": False})
        for cohort_id in cohorts:
            have = sum(1 for p in members if p["cohort_id"] == cohort_id)
            for _ in range(max(patients_per_cohort - have, 0)):
                members.append({"patient_ref": _uid(rng, "pt_", ids), "cohort_id": cohort_id,
                                "window": rng.choice(WINDOWS), "adherence": rng.uniform(0.62, 0.95),
                                "consent_care_team": rng.random() < 0.7, "consent_caregiver": rng.random() < 0.45,
                                "reporter": _pick(rng, reporters), "linked": False, "enrolled": None,
                                "missed_tail": 0, "synthetic": True})

        # ---- days and weeks of history, sampled from the cohort's real trial arm ----
        for p in members:
            p["program_id"] = prog["program_id"]
            cohort_id, version = p["cohort_id"], cohorts[p["cohort_id"]]
            arm = rates[spec["cohorts"][cohort_id]]
            # Which side effects this patient has during the window (trial rate), and how bad they are for them.
            affected = {term: _pick(rng, SEVERITY.get(term, SEVERITY["default"]))
                        for term, p_arm in arm.items() if rng.random() < p_arm}
            episodes = []  # (term, start_day, iso_week, severity, link_flag)
            for wk in week_keys:
                wdays = [d for d in days if iso_week(datetime.combine(d, time(12))) == wk]
                weekly = [(t, sev) for t, sev in affected.items() if rng.random() < WEEKLY_ACTIVE]
                if rng.random() < OTHER_REVIEW_PREVALENCE:
                    weekly.append(("SE_OTHER_REVIEW", _pick(rng, SEVERITY["default"])))
                for term, sev in weekly:
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
                    "patient_ref": p["patient_ref"], "program_id": prog["program_id"], "cohort_id": cohort_id,
                    "drug_version": version, "iso_week": wk, "status": status, "symptoms": syms,
                    "unanswered_questions": rng.randint(1, 2) if status == "partial" else 0,
                    "consent": {"care_team": p["consent_care_team"], "caregiver": p["consent_caregiver"]},
                }
                if status != "missed":  # scheduler records have no reporter or input mode
                    payload["reporter"] = p["reporter"]
                    payload["input_mode"] = _pick(rng, INPUT_MODES)
                records.append((payload["record_id"], "2.0", p["patient_ref"], prog["program_id"], cohort_id,
                                version, wk, status, payload["unanswered_questions"], int(p["consent_care_team"]),
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
                        alerts.append((_uid(rng, "alt_", alert_ids), p["patient_ref"], "severe", None,
                                       fmt_ts(received)))
        patients.extend(members)

    # ---- write ----
    c, r = dbs.company, dbs.relay
    co = fx["company"]
    with dbs.tx(c, r):
        c.execute("INSERT INTO company (company_id, display_name, note) VALUES (?,?,?)",
                  (co["company_id"], co["display_name"], co["note"]))
        c.executemany("INSERT INTO program (program_id, company_id, drug_name, created_at, label, population, "
                      "source_trial, source_url) VALUES (?,?,?,?,?,?,?,?)", programs)
        c.executemany("INSERT INTO cohort (cohort_id, program_id, drug_version, label, target_size, source_arm) "
                      "VALUES (?,?,?,?,?,?)", cohort_rows)
        c.executemany("INSERT INTO term_code VALUES (?,?,?,?,?)",
                      [(t["term_code"], t["label_term"], json.dumps(t["everyday_words"]), json.dumps(t["drug_scope"]),
                        int(t["severe_trigger"])) for t in terms])
        c.executemany("INSERT INTO survey_config VALUES (?,?,?,?,?,?)", surveys)
        c.executemany("INSERT INTO document (doc_id, title, source_url, version, approved_by, approved_at, program_id, "
                      "kind) VALUES (?,?,?,?,?,?,?,?)",
                      [(d["doc_id"], d["title"], d["source_url"], d["version"], safety, t0, d["program_id"],
                        d["kind"]) for d in docs])
        c.executemany("INSERT INTO enrollment (patient_ref, program_id, cohort_id, checkin_window, start_date, "
                      "synthetic, active) VALUES (?,?,?,?,?,?,1)",
                      [(p["patient_ref"], p["program_id"], p["cohort_id"], p["window"],
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

    return {"programs": len(programs), "patients": len(patients), "days": len(days), "weeks": week_keys,
            "records": len(records), "symptoms": len(symptoms), "documents": len(docs), "relay_alerts": len(alerts)}


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
    print(f"seeded {data_dir}: {summary['programs']} programs, {summary['patients']} patients, {summary['records']} check-ins over "
          f"{summary['days']} days ({', '.join(summary['weeks'])}), {summary['symptoms']} symptom reports, "
          f"{summary['documents']} documents, {summary['relay_alerts']} relay alerts")


if __name__ == "__main__":
    main()
