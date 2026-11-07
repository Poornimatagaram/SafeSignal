"""SQLite store for the Sentinel service (replaces the H1 stub; D-020, D-055).

Company methods touch only company.db; relay methods touch only relay.db (Scoping Doc 26.9). Rules are the
same as the stub's: schema validation, enrollment match (D-006), care-link and consent checks, idempotency
(Scoping Doc 26.13), `since` paging on service receive time (D-054).
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from sentinel_contract import payload_sha256

from .common import PAGE_SIZE, normalize_since, now_iso, require_valid
from .db import Databases
from .errors import conflict, forbidden, not_found, unprocessable


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


class SqliteStore:
    def __init__(self, dbs: Databases):
        self.db = dbs

    @classmethod
    def open(cls, data_dir: Path | None = None) -> "SqliteStore":
        return cls(Databases(data_dir))

    def close(self) -> None:
        self.db.close()

    # ---------- patient_device: configuration reads ----------

    def get_survey(self, cohort_id: str) -> dict:
        row = self.db.company.execute(
            "SELECT config_id, cohort_id, version, published_at, questions_json FROM survey_config "
            "WHERE cohort_id = ? ORDER BY version DESC LIMIT 1", (cohort_id,)).fetchone()
        if row is None:
            raise not_found(f"no survey for cohort {cohort_id}")
        out = dict(row)
        out["questions"] = json.loads(out.pop("questions_json"))["questions"]
        return out

    def get_terms(self, program_id: str) -> dict:
        prog = self.db.company.execute("SELECT drug_name FROM program WHERE program_id = ?", (program_id,)).fetchone()
        if prog is None:
            raise not_found(f"unknown program {program_id}")
        drug = prog["drug_name"]
        terms = []
        for t in self.db.company.execute("SELECT * FROM term_code ORDER BY rowid"):
            terms.append({"term_code": t["term_code"], "label_term": t["label_term"],
                          "everyday_words": json.loads(t["everyday_words"]),
                          "severe_trigger": bool(t["severe_trigger"]),
                          "known_for_program": drug in json.loads(t["drug_scope"])})  # D-007
        return {"program_id": program_id, "drug_name": drug, "terms": terms}

    # ---------- patient_device: sends ----------

    def put_record(self, actor_id: str, payload: dict) -> tuple[int, dict]:
        require_valid("company_record", payload)
        if payload["patient_ref"] != actor_id:
            raise forbidden("patient_ref does not match X-Actor-Id")
        c = self.db.company
        enr = c.execute(
            "SELECT e.program_id, e.cohort_id, k.drug_version FROM enrollment e "
            "JOIN cohort k ON k.cohort_id = e.cohort_id WHERE e.patient_ref = ? AND e.active = 1",
            (payload["patient_ref"],)).fetchone()
        if enr is None:
            raise forbidden("patient is not enrolled")
        mismatches = [f for f in ("program_id", "cohort_id", "drug_version") if payload[f] != enr[f]]
        if mismatches:  # D-006
            raise unprocessable("record does not match enrollment",
                                [{"field": f"/{f}", "message": "does not match enrollment"} for f in mismatches])
        digest = payload_sha256(payload)
        result = {"record_id": payload["record_id"], "payload_sha256": digest}
        with self.db.tx(c):
            existing = c.execute("SELECT payload_sha256 FROM checkin_record WHERE record_id = ?",
                                 (payload["record_id"],)).fetchone()
            if existing:
                if existing["payload_sha256"] != digest:
                    raise conflict("record_id already received with a different payload")
                return 200, result
            c.execute(
                "INSERT INTO checkin_record (record_id, schema_version, patient_ref, program_id, cohort_id, "
                "drug_version, iso_week, status, unanswered_questions, consent_doctor, consent_caregiver, "
                "payload_sha256, source, received_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'device', ?)",
                (payload["record_id"], payload["schema_version"], payload["patient_ref"], payload["program_id"],
                 payload["cohort_id"], payload["drug_version"], payload["iso_week"], payload["status"],
                 payload["unanswered_questions"], int(payload["consent"]["doctor"]),
                 int(payload["consent"]["caregiver"]), digest, now_iso()))
            c.executemany(
                "INSERT INTO symptom_record (record_id, term_code, severity, onset, known_side_effect, "
                "possible_link_flag) VALUES (?,?,?,?,?,?)",
                [(payload["record_id"], s["term_code"], s["severity"], s["onset"], int(s["known_side_effect"]),
                  int(s["possible_link_flag"])) for s in payload["symptoms"]])
        return 201, result

    def _active_care_link(self, doctor_id: str, patient_ref: str) -> bool:
        row = self.db.relay.execute("SELECT status FROM care_link WHERE doctor_id = ? AND patient_ref = ?",
                                    (doctor_id, patient_ref)).fetchone()
        return bool(row) and row["status"] == "active"

    def put_envelope(self, actor_id: str, payload: dict) -> tuple[int, dict]:
        require_valid("doctor_envelope", payload)
        if payload["patient_ref"] != actor_id:
            raise forbidden("patient_ref does not match X-Actor-Id")
        if not self._active_care_link(payload["doctor_id"], payload["patient_ref"]):
            raise forbidden("no active care link for this doctor and patient")
        r = self.db.relay
        result = {"envelope_id": payload["envelope_id"], "payload_sha256": payload["payload_sha256"]}
        with self.db.tx(r):
            existing = r.execute("SELECT ciphertext, payload_sha256 FROM doctor_inbox WHERE envelope_id = ?",
                                 (payload["envelope_id"],)).fetchone()
            if existing:  # D-021: same sealed ciphertext and plaintext hash, or it is a different envelope
                if existing["ciphertext"] != payload["ciphertext"] or \
                        existing["payload_sha256"] != payload["payload_sha256"]:
                    raise conflict("envelope_id already received with a different payload")
                return 200, result
            r.execute("INSERT INTO doctor_inbox (envelope_id, doctor_id, patient_ref, ciphertext, payload_sha256, "
                      "received_at) VALUES (?,?,?,?,?,?)",
                      (payload["envelope_id"], payload["doctor_id"], payload["patient_ref"], payload["ciphertext"],
                       payload["payload_sha256"], now_iso()))
        return 201, result

    def _routing(self, patient_ref: str) -> tuple[bool, bool]:
        r = self.db.relay
        doctor = r.execute("SELECT 1 FROM care_link WHERE patient_ref = ? AND status = 'active'",
                           (patient_ref,)).fetchone() is not None
        caregiver = r.execute("SELECT 1 FROM caregiver_link WHERE patient_ref = ? AND status = 'active'",
                              (patient_ref,)).fetchone() is not None
        return doctor, caregiver

    def put_alert(self, actor_id: str, payload: dict) -> tuple[int, dict]:
        require_valid("alert_event", payload)
        if payload["patient_ref"] != actor_id:
            raise forbidden("patient_ref does not match X-Actor-Id")
        r = self.db.relay
        with self.db.tx(r):
            existing = r.execute("SELECT * FROM alert WHERE alert_id = ?", (payload["alert_id"],)).fetchone()
            if existing:
                if (existing["created_at"], existing["patient_ref"], existing["alert_type"]) != \
                        (payload["created_at"], payload["patient_ref"], payload["alert_type"]):
                    raise conflict("alert_id already received with a different payload")
                return 200, {"alert_id": existing["alert_id"], "routed_doctor": bool(existing["routed_doctor"]),
                             "routed_caregiver": bool(existing["routed_caregiver"])}
            doctor, caregiver = self._routing(payload["patient_ref"])
            r.execute("INSERT INTO alert (alert_id, patient_ref, alert_type, created_at, received_at, routed_doctor, "
                      "routed_caregiver) VALUES (?,?,?,?,?,?,?)",
                      (payload["alert_id"], payload["patient_ref"], payload["alert_type"], payload["created_at"],
                       now_iso(), int(doctor), int(caregiver)))
        return 201, {"alert_id": payload["alert_id"], "routed_doctor": doctor, "routed_caregiver": caregiver}

    def put_consent(self, actor_id: str, patient_ref: str, payload: dict) -> dict:
        require_valid("consent_update", payload)
        if not (patient_ref == actor_id == payload["patient_ref"]):
            raise forbidden("patient_ref in path, body and X-Actor-Id must match")
        r = self.db.relay
        t = now_iso()
        with self.db.tx(r):
            if payload["doctor_id"]:
                if r.execute("SELECT 1 FROM doctor WHERE doctor_id = ?", (payload["doctor_id"],)).fetchone() is None:
                    raise unprocessable("unknown doctor", [{"field": "/doctor_id", "message": "unknown doctor"}])
                if payload["share_doctor"]:
                    r.execute("INSERT INTO care_link (doctor_id, patient_ref, status, granted_at) "
                              "VALUES (?, ?, 'active', ?) ON CONFLICT(doctor_id, patient_ref) DO UPDATE SET "
                              "granted_at = CASE WHEN status = 'active' THEN granted_at ELSE excluded.granted_at END, "
                              "status = 'active', revoked_at = NULL", (payload["doctor_id"], patient_ref, t))
                else:
                    r.execute("UPDATE care_link SET status = 'revoked', revoked_at = ? "
                              "WHERE doctor_id = ? AND patient_ref = ? AND status = 'active'",
                              (t, payload["doctor_id"], patient_ref))
            if payload["caregiver_id"]:
                if payload["share_caregiver"]:
                    r.execute("INSERT INTO caregiver_link (caregiver_id, patient_ref, detail_level, status, granted_at) "
                              "VALUES (?, ?, ?, 'active', ?) ON CONFLICT(caregiver_id, patient_ref) DO UPDATE SET "
                              "granted_at = CASE WHEN status = 'active' THEN granted_at ELSE excluded.granted_at END, "
                              "detail_level = excluded.detail_level, status = 'active', revoked_at = NULL",
                              (payload["caregiver_id"], patient_ref, payload["caregiver_detail"], t))
                else:
                    r.execute("UPDATE caregiver_link SET status = 'revoked', revoked_at = ? "
                              "WHERE caregiver_id = ? AND patient_ref = ? AND status = 'active'",
                              (t, payload["caregiver_id"], patient_ref))
        state = {k: payload[k] for k in ("patient_ref", "doctor_id", "caregiver_id", "share_doctor",
                                         "share_caregiver", "caregiver_detail")}
        state["updated_at"] = t
        return state

    # ---------- doctor ----------

    def _require_doctor(self, doctor_id: str):
        row = self.db.relay.execute("SELECT * FROM doctor WHERE doctor_id = ?", (doctor_id,)).fetchone()
        if row is None:
            raise not_found("unknown doctor")
        return row

    def doctor_patients(self, doctor_id: str) -> list[dict]:
        self._require_doctor(doctor_id)
        return _rows(self.db.relay.execute(
            "SELECT patient_ref, granted_at FROM care_link WHERE doctor_id = ? AND status = 'active' "
            "ORDER BY patient_ref", (doctor_id,)))

    def doctor_envelopes(self, doctor_id: str, since: str | None) -> list[dict]:
        self._require_doctor(doctor_id)
        since = normalize_since(since)
        # D-013: only patients with an active care link
        return _rows(self.db.relay.execute(
            "SELECT i.envelope_id, i.patient_ref, i.ciphertext, i.payload_sha256, i.received_at "
            "FROM doctor_inbox i JOIN care_link l ON l.doctor_id = i.doctor_id AND l.patient_ref = i.patient_ref "
            "WHERE i.doctor_id = ? AND l.status = 'active' AND (? IS NULL OR i.received_at > ?) "
            "ORDER BY i.received_at, i.envelope_id LIMIT ?", (doctor_id, since, since, PAGE_SIZE)))

    def ack_envelope(self, doctor_id: str, envelope_id: str) -> dict:
        r = self.db.relay
        with self.db.tx(r):
            row = r.execute("SELECT fetched_at FROM doctor_inbox WHERE envelope_id = ? AND doctor_id = ?",
                            (envelope_id, doctor_id)).fetchone()
            if row is None:
                raise not_found("unknown envelope")
            fetched = row["fetched_at"] or now_iso()
            r.execute("UPDATE doctor_inbox SET fetched_at = ? WHERE envelope_id = ?", (fetched, envelope_id))
        return {"envelope_id": envelope_id, "fetched_at": fetched}

    def doctor_alerts(self, doctor_id: str, since: str | None) -> list[dict]:
        self._require_doctor(doctor_id)
        since = normalize_since(since)
        return _rows(self.db.relay.execute(
            "SELECT a.alert_id, a.patient_ref, a.alert_type, a.created_at, a.received_at FROM alert a "
            "JOIN care_link l ON l.patient_ref = a.patient_ref AND l.doctor_id = ? "
            "WHERE a.routed_doctor = 1 AND l.status = 'active' AND (? IS NULL OR a.received_at > ?) "
            "ORDER BY a.received_at, a.alert_id LIMIT ?", (doctor_id, since, since, PAGE_SIZE)))

    def put_public_key(self, doctor_id: str, public_key: str) -> dict:
        self._require_doctor(doctor_id)
        try:
            raw = base64.b64decode(public_key, validate=True)
        except ValueError:
            raw = b""
        if len(raw) != 32:
            raise unprocessable("public_key must be a base64 X25519 key (32 bytes)",
                                [{"field": "/public_key", "message": "must decode to 32 bytes"}])
        with self.db.tx(self.db.relay):
            self.db.relay.execute("UPDATE doctor SET public_key = ? WHERE doctor_id = ?", (public_key, doctor_id))
        return {"doctor_id": doctor_id, "public_key": public_key}

    def get_public_key(self, actor_patient: str, doctor_id: str) -> dict:
        doc = self._require_doctor(doctor_id)
        if not self._active_care_link(doctor_id, actor_patient):
            raise forbidden("no active care link for this doctor and patient")
        if not doc["public_key"]:
            raise not_found("doctor has not registered a public key yet")  # D-025
        return {"doctor_id": doctor_id, "public_key": doc["public_key"]}

    # ---------- caregiver ----------

    def caregiver_alerts(self, caregiver_id: str) -> list[dict]:
        # D-008 (open): 'summary' detail returns the same minimal fields as 'alerts_only'.
        return _rows(self.db.relay.execute(
            "SELECT a.alert_id, a.patient_ref, a.alert_type, a.created_at, a.received_at FROM alert a "
            "JOIN caregiver_link l ON l.patient_ref = a.patient_ref AND l.caregiver_id = ? "
            "WHERE a.routed_caregiver = 1 AND l.status = 'active' ORDER BY a.received_at, a.alert_id",
            (caregiver_id,)))

    # ---------- company (company.db only) ----------

    def log_access(self, role: str, actor: str, action: str, obj: str) -> None:
        with self.db.tx(self.db.company):
            self.db.company.execute("INSERT INTO access_log (actor_role, actor_id, action, object, at) "
                                    "VALUES (?,?,?,?,?)", (role, actor, action, obj, now_iso()))

    def cohorts_weekly(self, program_id: str) -> list[dict]:
        return _rows(self.db.company.execute(
            "SELECT * FROM v_cohort_weekly WHERE program_id = ? ORDER BY iso_week, cohort_id, term_code",
            (program_id,)))

    def completion(self, program_id: str) -> list[dict]:
        return _rows(self.db.company.execute(
            "SELECT * FROM v_completion_weekly WHERE program_id = ? ORDER BY iso_week, cohort_id", (program_id,)))

    def publish_survey(self, actor_id: str, cohort_id: str, payload: dict) -> dict:
        c = self.db.company
        if c.execute("SELECT 1 FROM cohort WHERE cohort_id = ?", (cohort_id,)).fetchone() is None:
            raise not_found(f"unknown cohort {cohort_id}")
        require_valid("survey_config", payload)
        with self.db.tx(c):
            version = c.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM survey_config WHERE cohort_id = ?",
                                (cohort_id,)).fetchone()[0]
            config_id = f"cfg_{cohort_id.lower()}_v{version}"
            c.execute("INSERT INTO survey_config (config_id, cohort_id, version, questions_json, published_at, "
                      "published_by) VALUES (?,?,?,?,?,?)",
                      (config_id, cohort_id, version, json.dumps(payload), now_iso(), actor_id))
        return {"config_id": config_id, "version": version}

    def export_records(self, program_id: str) -> list[dict]:
        c = self.db.company
        records = _rows(c.execute(  # D-009: received_at is never exported
            "SELECT record_id, patient_ref, program_id, cohort_id, drug_version, iso_week, status, source, "
            "unanswered_questions FROM checkin_record WHERE program_id = ? ORDER BY iso_week, record_id",
            (program_id,)))
        symptoms: dict[str, list] = {}
        for s in c.execute("SELECT s.record_id, s.term_code, s.severity, s.onset, s.known_side_effect, "
                           "s.possible_link_flag FROM symptom_record s JOIN checkin_record r "
                           "ON r.record_id = s.record_id WHERE r.program_id = ? ORDER BY s.id", (program_id,)):
            symptoms.setdefault(s["record_id"], []).append(
                {"term_code": s["term_code"], "severity": s["severity"], "onset": s["onset"],
                 "known_side_effect": bool(s["known_side_effect"]),
                 "possible_link_flag": bool(s["possible_link_flag"])})
        for r in records:
            r["symptoms"] = symptoms.get(r["record_id"], [])
        return records
