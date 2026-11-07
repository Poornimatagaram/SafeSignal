"""In-memory stub store (H1 handover). Same rules as the real service: schema validation, enrollment
cross-check, consent/care-link gating, idempotency. Data resets on restart. Step 2 replaces this with SQLite
behind the same method names.
"""

from __future__ import annotations

import base64
import hashlib
import json
import random
from datetime import datetime, timezone

from contract import SCHEMA_DIR, payload_sha256, validation_errors

from . import demo_ids as ids
from .errors import conflict, forbidden, not_found, unprocessable

PAGE_SIZE = 100


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate(kind: str, payload) -> None:
    errors = validation_errors(kind, payload)
    if errors:
        raise unprocessable(f"{kind} failed schema validation", errors)


def _page_since(items: list[dict], key: str, since: str | None) -> list[dict]:
    rows = [i for i in items if since is None or i[key] > since]
    rows.sort(key=lambda i: i[key])
    return rows[:PAGE_SIZE]


class StubStore:
    def __init__(self) -> None:
        terms = json.loads((SCHEMA_DIR / "terms.json").read_text())["terms"]
        survey = json.loads((SCHEMA_DIR / "examples" / "survey_config.valid.json").read_text())
        t0 = "2026-11-01T00:00:00Z"

        self.terms = terms
        self.enrollment = {
            ids.WALTER: {"program_id": ids.PROGRAM_ID, "cohort_id": "cohort_B", "checkin_window": "14:00-17:00"},
            ids.PRIYA: {"program_id": ids.PROGRAM_ID, "cohort_id": "cohort_A", "checkin_window": "13:00-14:00"},
        }
        self.surveys = {  # cohort_id -> list of versions (latest last)
            c: [{"config_id": f"cfg_{c.lower()}_v1", "cohort_id": c, "version": 1,
                 "published_at": t0, "questions": survey["questions"]}]
            for c in ids.COHORTS
        }
        # D-025: no placeholder key; the doctor's browser registers the real one on first launch.
        self.doctors = {ids.DR_SHAH: {"display_name": "Dr. Shah", "clinic": "Demo Clinic", "public_key": None}}
        self.care_links = {(ids.DR_SHAH, p): {"status": "active", "granted_at": t0} for p in (ids.WALTER, ids.PRIYA)}
        self.caregiver_links = {(ids.ANNA, ids.WALTER): {"status": "active", "detail_level": "alerts_only",
                                                        "granted_at": t0}}
        self.consent = {}
        self.records: dict[str, dict] = {}
        self.envelopes: dict[str, dict] = {}
        self.alerts: dict[str, dict] = {
            "alt_00000001": {"alert_id": "alt_00000001", "patient_ref": ids.PRIYA, "alert_type": "missed",
                             "created_at": "2026-11-06T14:00:30Z", "routed_doctor": True, "routed_caregiver": False},
        }
        self.access_log: list[dict] = []
        self._fake_rows = self._build_fake_company_rows()

    # ---------- patient_device ----------

    def get_survey(self, cohort_id: str) -> dict:
        if cohort_id not in self.surveys:
            raise not_found(f"no survey for cohort {cohort_id}")
        return self.surveys[cohort_id][-1]

    def get_terms(self, program_id: str) -> dict:
        if program_id != ids.PROGRAM_ID:
            raise not_found(f"unknown program {program_id}")
        return {
            "program_id": program_id,
            "drug_name": ids.DRUG_NAME,
            "terms": [{"term_code": t["term_code"], "label_term": t["label_term"],
                       "everyday_words": t["everyday_words"], "severe_trigger": t["severe_trigger"],
                       "known_for_program": ids.DRUG_NAME in t["drug_scope"]} for t in self.terms],
        }

    def put_record(self, actor_id: str, payload: dict) -> tuple[int, dict]:
        _validate("company_record", payload)
        if payload["patient_ref"] != actor_id:
            raise forbidden("patient_ref does not match X-Actor-Id")
        enr = self.enrollment.get(payload["patient_ref"])
        if enr is None:
            raise forbidden("patient is not enrolled")
        mismatches = [f for f, v in (("program_id", enr["program_id"]), ("cohort_id", enr["cohort_id"]),
                                     ("drug_version", ids.COHORTS[enr["cohort_id"]])) if payload[f] != v]
        if mismatches:  # D-006
            raise unprocessable("record does not match enrollment",
                                [{"field": f"/{f}", "message": "does not match enrollment"} for f in mismatches])
        digest = payload_sha256(payload)
        existing = self.records.get(payload["record_id"])
        if existing:
            if existing["payload_sha256"] != digest:
                raise conflict("record_id already received with a different payload")
            return 200, {"record_id": payload["record_id"], "payload_sha256": digest}
        self.records[payload["record_id"]] = {**payload, "payload_sha256": digest, "source": "device",
                                              "received_at": now_iso()}
        return 201, {"record_id": payload["record_id"], "payload_sha256": digest}

    def put_envelope(self, actor_id: str, payload: dict) -> tuple[int, dict]:
        _validate("doctor_envelope", payload)
        if payload["patient_ref"] != actor_id:
            raise forbidden("patient_ref does not match X-Actor-Id")
        link = self.care_links.get((payload["doctor_id"], payload["patient_ref"]))
        if not link or link["status"] != "active":
            raise forbidden("no active care link for this doctor and patient")
        existing = self.envelopes.get(payload["envelope_id"])
        # Idempotency key is the hash of the ciphertext: sealed boxes are randomized, so a client retry must
        # resend the same stored ciphertext, never re-encrypt.
        digest = hashlib.sha256(payload["ciphertext"].encode()).hexdigest()
        if existing:
            if existing["_ct_sha256"] != digest or existing["payload_sha256"] != payload["payload_sha256"]:
                raise conflict("envelope_id already received with a different payload")
            return 200, {"envelope_id": payload["envelope_id"], "payload_sha256": payload["payload_sha256"]}
        self.envelopes[payload["envelope_id"]] = {
            "envelope_id": payload["envelope_id"], "doctor_id": payload["doctor_id"],
            "patient_ref": payload["patient_ref"], "ciphertext": payload["ciphertext"],
            "payload_sha256": payload["payload_sha256"], "_ct_sha256": digest,
            "received_at": now_iso(), "fetched_at": None,
        }
        return 201, {"envelope_id": payload["envelope_id"], "payload_sha256": payload["payload_sha256"]}

    def put_alert(self, actor_id: str, payload: dict) -> tuple[int, dict]:
        _validate("alert_event", payload)
        if payload["patient_ref"] != actor_id:
            raise forbidden("patient_ref does not match X-Actor-Id")
        routed_doctor = any(p == actor_id and l["status"] == "active" for (_, p), l in self.care_links.items())
        routed_caregiver = any(p == actor_id and l["status"] == "active"
                               for (_, p), l in self.caregiver_links.items())
        existing = self.alerts.get(payload["alert_id"])
        if existing:
            if existing["created_at"] != payload["created_at"] or existing["patient_ref"] != payload["patient_ref"]:
                raise conflict("alert_id already received with a different payload")
            return 200, {k: existing[k] for k in ("alert_id", "routed_doctor", "routed_caregiver")}
        self.alerts[payload["alert_id"]] = {**{k: payload[k] for k in ("alert_id", "patient_ref", "alert_type",
                                                                       "created_at")},
                                            "routed_doctor": routed_doctor, "routed_caregiver": routed_caregiver}
        return 201, {"alert_id": payload["alert_id"], "routed_doctor": routed_doctor,
                     "routed_caregiver": routed_caregiver}

    def put_consent(self, actor_id: str, patient_ref: str, payload: dict) -> dict:
        _validate("consent_update", payload)
        if not (patient_ref == actor_id == payload["patient_ref"]):
            raise forbidden("patient_ref in path, body and X-Actor-Id must match")
        t = now_iso()
        if payload["doctor_id"]:
            if payload["doctor_id"] not in self.doctors:
                raise unprocessable("unknown doctor", [{"field": "/doctor_id", "message": "unknown doctor"}])
            key = (payload["doctor_id"], patient_ref)
            prev = self.care_links.get(key)
            if payload["share_doctor"]:
                granted = prev["granted_at"] if prev and prev["status"] == "active" else t
                self.care_links[key] = {"status": "active", "granted_at": granted}
            elif prev:
                self.care_links[key] = {**prev, "status": "revoked", "revoked_at": t}
        if payload["caregiver_id"]:
            key = (payload["caregiver_id"], patient_ref)
            prev = self.caregiver_links.get(key)
            if payload["share_caregiver"]:
                granted = prev["granted_at"] if prev and prev["status"] == "active" else t
                self.caregiver_links[key] = {"status": "active", "detail_level": payload["caregiver_detail"],
                                             "granted_at": granted}
            elif prev:
                self.caregiver_links[key] = {**prev, "status": "revoked", "revoked_at": t}
        state = {k: payload[k] for k in ("patient_ref", "doctor_id", "caregiver_id", "share_doctor",
                                         "share_caregiver", "caregiver_detail")}
        state["updated_at"] = t
        self.consent[patient_ref] = state
        return state

    # ---------- doctor ----------

    def _active_patients(self, doctor_id: str) -> dict[str, str]:
        return {p: l["granted_at"] for (d, p), l in self.care_links.items() if d == doctor_id and l["status"] == "active"}

    def _require_doctor(self, doctor_id: str) -> dict:
        if doctor_id not in self.doctors:
            raise not_found("unknown doctor")
        return self.doctors[doctor_id]

    def doctor_patients(self, doctor_id: str) -> list[dict]:
        self._require_doctor(doctor_id)
        return [{"patient_ref": p, "granted_at": g} for p, g in sorted(self._active_patients(doctor_id).items())]

    def doctor_envelopes(self, doctor_id: str, since: str | None) -> list[dict]:
        self._require_doctor(doctor_id)
        active = self._active_patients(doctor_id)  # D-013: revoked links hide envelopes
        rows = [e for e in self.envelopes.values() if e["doctor_id"] == doctor_id and e["patient_ref"] in active]
        return [{k: e[k] for k in ("envelope_id", "patient_ref", "ciphertext", "payload_sha256", "received_at")}
                for e in _page_since(rows, "received_at", since)]

    def ack_envelope(self, doctor_id: str, envelope_id: str) -> dict:
        env = self.envelopes.get(envelope_id)
        if not env or env["doctor_id"] != doctor_id:
            raise not_found("unknown envelope")
        env["fetched_at"] = env["fetched_at"] or now_iso()
        return {"envelope_id": envelope_id, "fetched_at": env["fetched_at"]}

    def doctor_alerts(self, doctor_id: str, since: str | None) -> list[dict]:
        self._require_doctor(doctor_id)
        active = self._active_patients(doctor_id)
        rows = [a for a in self.alerts.values() if a["routed_doctor"] and a["patient_ref"] in active]
        return [{k: a[k] for k in ("alert_id", "patient_ref", "alert_type", "created_at")}
                for a in _page_since(rows, "created_at", since)]

    def put_public_key(self, doctor_id: str, public_key: str) -> dict:
        doc = self._require_doctor(doctor_id)
        try:
            raw = base64.b64decode(public_key, validate=True)
        except ValueError:
            raw = b""
        if len(raw) != 32:
            raise unprocessable("public_key must be a base64 X25519 key (32 bytes)",
                                [{"field": "/public_key", "message": "must decode to 32 bytes"}])
        doc["public_key"] = public_key
        return {"doctor_id": doctor_id, "public_key": public_key}

    def get_public_key(self, actor_patient: str, doctor_id: str) -> dict:
        doc = self._require_doctor(doctor_id)
        link = self.care_links.get((doctor_id, actor_patient))
        if not link or link["status"] != "active":
            raise forbidden("no active care link for this doctor and patient")
        if not doc["public_key"]:
            raise not_found("doctor has not registered a public key yet")
        return {"doctor_id": doctor_id, "public_key": doc["public_key"]}

    # ---------- caregiver ----------

    def caregiver_alerts(self, caregiver_id: str) -> list[dict]:
        linked = {p for (c, p), l in self.caregiver_links.items() if c == caregiver_id and l["status"] == "active"}
        rows = [a for a in self.alerts.values() if a["routed_caregiver"] and a["patient_ref"] in linked]
        # D-008 (open): 'summary' detail currently returns the same minimal fields as 'alerts_only'.
        return [{k: a[k] for k in ("alert_id", "patient_ref", "alert_type", "created_at")}
                for a in sorted(rows, key=lambda a: a["created_at"])]

    # ---------- company ----------

    def log_access(self, role: str, actor: str, action: str, obj: str) -> None:
        self.access_log.append({"actor_role": role, "actor_id": actor, "action": action, "object": obj,
                                "at": now_iso()})

    def _build_fake_company_rows(self) -> dict:
        rng = random.Random(1984)
        weeks = ["2026-W42", "2026-W43", "2026-W44", "2026-W45"]
        # Stub story: v2 (cohort_B) runs higher on rash and nail changes.
        base = {"SE_RASH": 0.18, "SE_PARONYCHIA": 0.10, "SE_DIARRHEA": 0.14, "SE_FATIGUE": 0.20,
                "SE_DRY_SKIN": 0.08, "SE_STOMATITIS": 0.04}
        lift = {"cohort_B": {"SE_RASH": 1.8, "SE_PARONYCHIA": 1.6}}
        weekly, completion = [], []
        for c, v in ids.COHORTS.items():
            for w in weeks:
                records = 250 * 7
                missed = int(records * rng.uniform(0.18, 0.30))
                partial = int(records * rng.uniform(0.03, 0.06))
                reporting = int(250 * rng.uniform(0.86, 0.95))
                completion.append({"program_id": ids.PROGRAM_ID, "cohort_id": c, "drug_version": v, "iso_week": w,
                                   "records": records, "patients": 250,
                                   "completion_rate": round((records - missed - partial) / records, 3),
                                   "missed_rate": round(missed / records, 3)})
                for term, rate in base.items():
                    n = int(reporting * rate * lift.get(c, {}).get(term, 1.0) * rng.uniform(0.85, 1.15))
                    if n < 5:
                        continue
                    sev = int(n * rng.uniform(0.0, 0.12))
                    weekly.append({"program_id": ids.PROGRAM_ID, "cohort_id": c, "drug_version": v, "iso_week": w,
                                   "term_code": term, "patients": n,
                                   "severe_patients": None if 1 <= sev <= 4 else sev,
                                   "reporting_patients": reporting})
        return {"weekly": weekly, "completion": completion}

    def cohorts_weekly(self, program_id: str) -> list[dict]:
        return [r for r in self._fake_rows["weekly"] if r["program_id"] == program_id]

    def completion(self, program_id: str) -> list[dict]:
        return [r for r in self._fake_rows["completion"] if r["program_id"] == program_id]

    def publish_survey(self, actor_id: str, cohort_id: str, payload: dict) -> dict:
        if cohort_id not in self.surveys:
            raise not_found(f"unknown cohort {cohort_id}")
        _validate("survey_config", payload)
        version = self.surveys[cohort_id][-1]["version"] + 1
        cfg = {"config_id": f"cfg_{cohort_id.lower()}_v{version}", "cohort_id": cohort_id, "version": version,
               "published_at": now_iso(), "questions": payload["questions"], "published_by": actor_id}
        self.surveys[cohort_id].append(cfg)
        return {"config_id": cfg["config_id"], "version": version}

    def export_records(self, program_id: str) -> list[dict]:
        rows = []
        for r in sorted(self.records.values(), key=lambda r: r["record_id"]):
            if r["program_id"] != program_id:
                continue
            rows.append({k: r[k] for k in ("record_id", "patient_ref", "program_id", "cohort_id", "drug_version",
                                           "iso_week", "status", "source", "unanswered_questions", "symptoms")})
        return rows
