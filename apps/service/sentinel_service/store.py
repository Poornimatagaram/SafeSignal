"""SQLite store for the Sentinel service (D-055), contract 2.0 (docs/design/contract-2.0.md).

Company methods touch only company.db; relay methods touch only relay.db (Scoping Doc 26.9). Rules: schema
validation, enrollment match (D-006), organization membership and care-link checks, emergency access only with a
coded reason (D-065), idempotency (Scoping Doc 26.13), `since` paging on service receive time (D-054).
"""

from __future__ import annotations

import base64
import json
import secrets
from pathlib import Path

from sentinel_contract import payload_sha256

from . import escalation
from .common import PAGE_SIZE, normalize_since, now_iso, require_valid
from .db import Databases
from .errors import conflict, forbidden, not_found, unprocessable

SEALED_KEY_BYTES = 32 + 48  # a 32-byte X25519 private key in a libsodium sealed box


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def _b64_len(value: str) -> int:
    try:
        return len(base64.b64decode(value, validate=True))
    except ValueError:
        return -1


class SqliteStore:
    def __init__(self, dbs: Databases):
        self.db = dbs

    @classmethod
    def open(cls, data_dir: Path | None = None) -> "SqliteStore":
        return cls(Databases(data_dir))

    def close(self) -> None:
        self.db.close()

    # ================= patient_device: configuration reads =================

    def get_survey(self, cohort_id: str) -> dict:
        row = self.db.company.execute(
            "SELECT config_id, cohort_id, version, published_at, questions_json FROM survey_config "
            "WHERE cohort_id = ? ORDER BY version DESC LIMIT 1", (cohort_id,)).fetchone()
        if row is None:
            raise not_found(f"no survey for cohort {cohort_id}")
        out = dict(row)
        body = json.loads(out.pop("questions_json"))
        out["schedule"] = body["schedule"]
        out["questions"] = body["questions"]
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

    def get_org_key(self, actor_patient: str, org_id: str) -> dict:
        org = self._org(org_id)
        if not self._active_link(org_id, actor_patient):
            raise forbidden("no active care or emergency link between this patient and organization")
        if not org["public_key"]:
            raise not_found("organization has not registered a care-team key yet")
        return {"org_id": org_id, "public_key": org["public_key"]}

    # ================= patient_device: sends =================

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
                "drug_version, iso_week, status, unanswered_questions, consent_care_team, consent_caregiver, "
                "payload_sha256, reporter, input_mode, source, received_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'device', ?)",
                (payload["record_id"], payload["schema_version"], payload["patient_ref"], payload["program_id"],
                 payload["cohort_id"], payload["drug_version"], payload["iso_week"], payload["status"],
                 payload["unanswered_questions"], int(payload["consent"]["care_team"]),
                 int(payload["consent"]["caregiver"]), digest, payload["reporter"], payload["input_mode"], now_iso()))
            c.executemany(
                "INSERT INTO symptom_record (record_id, term_code, severity, onset, known_side_effect, "
                "possible_link_flag) VALUES (?,?,?,?,?,?)",
                [(payload["record_id"], s["term_code"], s["severity"], s["onset"], int(s["known_side_effect"]),
                  int(s["possible_link_flag"])) for s in payload["symptoms"]])
        return 201, result

    def put_envelope(self, actor_id: str, payload: dict) -> tuple[int, dict]:
        require_valid("care_envelope", payload)
        if payload["patient_ref"] != actor_id:
            raise forbidden("patient_ref does not match X-Actor-Id")
        self._org(payload["org_id"])
        if not self._active_link(payload["org_id"], payload["patient_ref"]):
            raise forbidden("no active care or emergency link between this patient and organization")
        r = self.db.relay
        result = {"envelope_id": payload["envelope_id"], "payload_sha256": payload["payload_sha256"]}
        with self.db.tx(r):
            existing = r.execute("SELECT org_id, ciphertext, payload_sha256 FROM care_inbox WHERE envelope_id = ?",
                                 (payload["envelope_id"],)).fetchone()
            if existing:  # D-021: same sealed ciphertext, org and plaintext hash, or it is a different envelope
                if (existing["org_id"], existing["ciphertext"], existing["payload_sha256"]) != \
                        (payload["org_id"], payload["ciphertext"], payload["payload_sha256"]):
                    raise conflict("envelope_id already received with a different payload")
                return 200, result
            r.execute("INSERT INTO care_inbox (envelope_id, org_id, patient_ref, ciphertext, payload_sha256, "
                      "received_at) VALUES (?,?,?,?,?,?)",
                      (payload["envelope_id"], payload["org_id"], payload["patient_ref"], payload["ciphertext"],
                       payload["payload_sha256"], now_iso()))
        return 201, result

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
            else:
                at = now_iso()
                r.execute("INSERT INTO alert (alert_id, patient_ref, alert_type, escalation_level, created_at, "
                          "received_at) VALUES (?,?,?,NULL,?,?)",
                          (payload["alert_id"], payload["patient_ref"], payload["alert_type"], payload["created_at"],
                           at))
                escalation.record_deliveries(r, payload["alert_id"],
                                             escalation.recipients(r, payload["patient_ref"], "severe"), at)
            kinds = {row[0] for row in r.execute("SELECT recipient_type FROM alert_delivery WHERE alert_id = ?",
                                                 (payload["alert_id"],))}
        body = {"alert_id": payload["alert_id"], "routed_care_team": "care_team" in kinds,
                "routed_caregiver": "caregiver" in kinds}
        return (200 if existing else 201), body

    def put_consent(self, actor_id: str, patient_ref: str, payload: dict) -> dict:
        require_valid("consent_update", payload)
        if not (patient_ref == actor_id == payload["patient_ref"]):
            raise forbidden("patient_ref in path, body and X-Actor-Id must match")
        care_org = payload["care_org_id"]
        emergency_orgs = payload["emergency_org_ids"]
        if care_org and care_org in emergency_orgs:
            raise unprocessable("an organization cannot be both the care team and an emergency organization",
                                [{"field": "/emergency_org_ids", "message": "contains care_org_id"}])
        for i, org in enumerate(([care_org] if care_org else []) + emergency_orgs):
            if self.db.relay.execute("SELECT 1 FROM organization WHERE org_id = ?", (org,)).fetchone() is None:
                raise unprocessable("unknown organization", [{"field": f"/org[{i}]", "message": "unknown organization"}])
        for i, c in enumerate(payload["emergency_contacts"]):
            if c["org_id"] and self.db.relay.execute("SELECT 1 FROM organization WHERE org_id = ?",
                                                     (c["org_id"],)).fetchone() is None:
                raise unprocessable("unknown organization",
                                    [{"field": f"/emergency_contacts/{i}/org_id", "message": "unknown organization"}])
        r = self.db.relay
        t = now_iso()
        with self.db.tx(r):
            # care team: at most one active care-team organization
            r.execute("UPDATE care_link SET status = 'revoked', revoked_at = ? WHERE patient_ref = ? AND "
                      "link_type = 'care_team' AND status = 'active' AND (? IS NULL OR org_id != ? OR ? = 0)",
                      (t, patient_ref, care_org, care_org, int(payload["share_care_team"])))
            if care_org and payload["share_care_team"]:
                self._activate_link(care_org, patient_ref, "care_team", t)
            # emergency organizations (D-065): exactly the consented list
            keep = emergency_orgs if payload["emergency_consent"] else []
            for (org,) in r.execute("SELECT org_id FROM care_link WHERE patient_ref = ? AND link_type = 'emergency' "
                                    "AND status = 'active'", (patient_ref,)).fetchall():
                if org not in keep:
                    r.execute("UPDATE care_link SET status = 'revoked', revoked_at = ? WHERE org_id = ? AND "
                              "patient_ref = ?", (t, org, patient_ref))
            for org in keep:
                self._activate_link(org, patient_ref, "emergency", t)
            # emergency contacts (D-067): replaced as a set; none without consent
            r.execute("DELETE FROM emergency_contact WHERE patient_ref = ?", (patient_ref,))
            if payload["emergency_consent"]:
                r.executemany("INSERT INTO emergency_contact (contact_id, patient_ref, contact_type, phone, org_id, "
                              "priority, consented_at) VALUES (?,?,?,?,?,?,?)",
                              [(c["contact_id"], patient_ref, c["contact_type"], c["phone"], c["org_id"],
                                c["priority"], t) for c in payload["emergency_contacts"]])
            # caregiver
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
        state = {k: payload[k] for k in ("patient_ref", "care_org_id", "share_care_team", "caregiver_id",
                                         "share_caregiver", "caregiver_detail", "emergency_consent",
                                         "emergency_org_ids")}
        state["emergency_contact_count"] = len(payload["emergency_contacts"]) if payload["emergency_consent"] else 0
        state["updated_at"] = t
        return state

    def _activate_link(self, org_id: str, patient_ref: str, link_type: str, t: str) -> None:
        self.db.relay.execute(
            "INSERT INTO care_link (org_id, patient_ref, link_type, status, granted_at) VALUES (?, ?, ?, 'active', ?) "
            "ON CONFLICT(org_id, patient_ref) DO UPDATE SET "
            "granted_at = CASE WHEN status = 'active' AND link_type = excluded.link_type THEN granted_at "
            "ELSE excluded.granted_at END, link_type = excluded.link_type, status = 'active', revoked_at = NULL",
            (org_id, patient_ref, link_type, t))

    # ================= organizations and doctors =================

    def _org(self, org_id: str):
        row = self.db.relay.execute("SELECT * FROM organization WHERE org_id = ?", (org_id,)).fetchone()
        if row is None:
            raise not_found("unknown organization")
        return row

    def _active_link(self, org_id: str, patient_ref: str, link_type: str | None = None) -> bool:
        row = self.db.relay.execute("SELECT link_type, status FROM care_link WHERE org_id = ? AND patient_ref = ?",
                                    (org_id, patient_ref)).fetchone()
        return bool(row) and row["status"] == "active" and (link_type is None or row["link_type"] == link_type)

    def _member(self, org_id: str, doctor_id: str, *roles: str):
        self._org(org_id)
        row = self.db.relay.execute("SELECT * FROM org_member WHERE org_id = ? AND doctor_id = ? AND status = 'active'",
                                    (org_id, doctor_id)).fetchone()
        if row is None:
            raise forbidden("not an active member of this organization")
        if roles and row["role"] not in roles:
            raise forbidden(f"requires organization role: {', '.join(roles)}")
        return row

    def _log(self, role: str, actor: str, org_id: str | None, action: str, patient_ref: str | None = None,
             reason: str | None = None) -> None:
        self.db.relay.execute("INSERT INTO relay_access_log (actor_role, actor_id, org_id, action, patient_ref, reason, "
                              "at) VALUES (?,?,?,?,?,?,?)", (role, actor, org_id, action, patient_ref, reason, now_iso()))

    def put_doctor_key(self, doctor_id: str, public_key: str) -> dict:
        if self.db.relay.execute("SELECT 1 FROM doctor WHERE doctor_id = ?", (doctor_id,)).fetchone() is None:
            raise not_found("unknown doctor")
        if _b64_len(public_key) != 32:
            raise unprocessable("public_key must be a base64 X25519 key (32 bytes)",
                                [{"field": "/public_key", "message": "must decode to 32 bytes"}])
        with self.db.tx(self.db.relay):
            self.db.relay.execute("UPDATE doctor SET public_key = ? WHERE doctor_id = ?", (public_key, doctor_id))
        return {"doctor_id": doctor_id, "public_key": public_key}

    def doctor_orgs(self, doctor_id: str) -> list[dict]:
        rows = _rows(self.db.relay.execute(
            "SELECT m.org_id, o.display_name, o.org_type, m.role, o.public_key IS NOT NULL AS org_key_registered, "
            "g.doctor_id IS NOT NULL AS has_key_grant FROM org_member m JOIN organization o ON o.org_id = m.org_id "
            "LEFT JOIN org_key_grant g ON g.org_id = m.org_id AND g.doctor_id = m.doctor_id "
            "WHERE m.doctor_id = ? AND m.status = 'active' ORDER BY o.display_name", (doctor_id,)))
        for r in rows:
            r["org_key_registered"], r["has_key_grant"] = bool(r["org_key_registered"]), bool(r["has_key_grant"])
        return rows

    def put_org_key(self, doctor_id: str, org_id: str, public_key: str) -> dict:
        self._member(org_id, doctor_id, "admin")
        if _b64_len(public_key) != 32:
            raise unprocessable("public_key must be a base64 X25519 key (32 bytes)",
                                [{"field": "/public_key", "message": "must decode to 32 bytes"}])
        with self.db.tx(self.db.relay):
            self.db.relay.execute("UPDATE organization SET public_key = ? WHERE org_id = ?", (public_key, org_id))
            self._log("doctor", doctor_id, org_id, "register_org_key")
        return {"org_id": org_id, "public_key": public_key}

    def put_member(self, admin_id: str, org_id: str, doctor_id: str, role: str, status: str) -> dict:
        self._member(org_id, admin_id, "admin")
        if self.db.relay.execute("SELECT 1 FROM doctor WHERE doctor_id = ?", (doctor_id,)).fetchone() is None:
            raise not_found("unknown doctor")
        if doctor_id == admin_id and status != "active":
            raise unprocessable("an admin cannot revoke themselves",
                                [{"field": "/status", "message": "self-revocation not allowed"}])
        t = now_iso()
        r = self.db.relay
        with self.db.tx(r):
            r.execute("INSERT INTO org_member (org_id, doctor_id, role, status, granted_at, revoked_at) "
                      "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(org_id, doctor_id) DO UPDATE SET role = excluded.role, "
                      "status = excluded.status, revoked_at = excluded.revoked_at, granted_at = CASE "
                      "WHEN org_member.status = 'active' THEN org_member.granted_at ELSE excluded.granted_at END",
                      (org_id, doctor_id, role, status, t, t if status == "revoked" else None))
            if status == "revoked":  # D-064: a leaving doctor loses the key grant and all service access
                r.execute("DELETE FROM org_key_grant WHERE org_id = ? AND doctor_id = ?", (org_id, doctor_id))
            self._log("doctor", admin_id, org_id, f"member_{status}", None, doctor_id)
        row = r.execute("SELECT org_id, doctor_id, role, status, granted_at, revoked_at FROM org_member "
                        "WHERE org_id = ? AND doctor_id = ?", (org_id, doctor_id)).fetchone()
        return dict(row)

    def put_key_grant(self, admin_id: str, org_id: str, doctor_id: str, wrapped_key: str) -> dict:
        self._member(org_id, admin_id, "admin")
        target = self._member(org_id, doctor_id)  # only active members receive the key
        del target
        if _b64_len(wrapped_key) != SEALED_KEY_BYTES:
            raise unprocessable("wrapped_key must be a base64 sealed box of a 32-byte key (80 bytes)",
                                [{"field": "/wrapped_key", "message": f"must decode to {SEALED_KEY_BYTES} bytes"}])
        t = now_iso()
        with self.db.tx(self.db.relay):
            self.db.relay.execute(
                "INSERT INTO org_key_grant (org_id, doctor_id, wrapped_key, granted_by, granted_at) VALUES (?,?,?,?,?) "
                "ON CONFLICT(org_id, doctor_id) DO UPDATE SET wrapped_key = excluded.wrapped_key, "
                "granted_by = excluded.granted_by, granted_at = excluded.granted_at",
                (org_id, doctor_id, wrapped_key, admin_id, t))
            self._log("doctor", admin_id, org_id, "key_grant", None, doctor_id)
        return {"org_id": org_id, "doctor_id": doctor_id, "granted_by": admin_id, "granted_at": t}

    def get_key_grant(self, doctor_id: str, org_id: str) -> dict:
        self._member(org_id, doctor_id)
        row = self.db.relay.execute("SELECT org_id, doctor_id, wrapped_key, granted_by, granted_at FROM org_key_grant "
                                    "WHERE org_id = ? AND doctor_id = ?", (org_id, doctor_id)).fetchone()
        if row is None:
            raise not_found("no key grant yet: ask an organization admin")
        return dict(row)

    def org_patients(self, doctor_id: str, org_id: str) -> list[dict]:
        self._member(org_id, doctor_id)
        return _rows(self.db.relay.execute(
            "SELECT patient_ref, granted_at FROM care_link WHERE org_id = ? AND link_type = 'care_team' "
            "AND status = 'active' ORDER BY patient_ref", (org_id,)))

    def org_envelopes(self, doctor_id: str, org_id: str, since: str | None) -> list[dict]:
        self._member(org_id, doctor_id)
        since = normalize_since(since)
        rows = _rows(self.db.relay.execute(  # routine access: care-team links only (D-065)
            "SELECT i.envelope_id, i.patient_ref, i.ciphertext, i.payload_sha256, i.received_at "
            "FROM care_inbox i JOIN care_link l ON l.org_id = i.org_id AND l.patient_ref = i.patient_ref "
            "WHERE i.org_id = ? AND l.link_type = 'care_team' AND l.status = 'active' "
            "AND (? IS NULL OR i.received_at > ?) ORDER BY i.received_at, i.envelope_id LIMIT ?",
            (org_id, since, since, PAGE_SIZE)))
        with self.db.tx(self.db.relay):
            self._log("doctor", doctor_id, org_id, "read_envelopes")
        return rows

    def ack_envelope(self, doctor_id: str, org_id: str, envelope_id: str) -> dict:
        self._member(org_id, doctor_id)
        r = self.db.relay
        with self.db.tx(r):
            row = r.execute("SELECT fetched_at FROM care_inbox WHERE envelope_id = ? AND org_id = ?",
                            (envelope_id, org_id)).fetchone()
            if row is None:
                raise not_found("unknown envelope")
            fetched = row["fetched_at"] or now_iso()
            r.execute("UPDATE care_inbox SET fetched_at = ? WHERE envelope_id = ?", (fetched, envelope_id))
        return {"envelope_id": envelope_id, "fetched_at": fetched}

    def org_alerts(self, doctor_id: str, org_id: str, since: str | None) -> list[dict]:
        self._member(org_id, doctor_id)
        since = normalize_since(since)
        return _rows(self.db.relay.execute(
            "SELECT a.alert_id, a.patient_ref, a.alert_type, a.escalation_level, a.created_at, a.received_at "
            "FROM alert a JOIN alert_delivery d ON d.alert_id = a.alert_id AND d.recipient_type = 'care_team' "
            "AND d.recipient_id = ? WHERE (? IS NULL OR a.received_at > ?) "
            "ORDER BY a.received_at, a.alert_id LIMIT ?", (org_id, since, since, PAGE_SIZE)))

    def emergency_access(self, doctor_id: str, org_id: str, patient_ref: str, reason: str) -> dict:
        self._member(org_id, doctor_id)
        if not self._active_link(org_id, patient_ref, "emergency"):
            raise forbidden("this organization has no active emergency link to the patient")
        r = self.db.relay
        t = now_iso()
        alert_id = f"alt_{secrets.token_hex(4)}"
        with self.db.tx(r):
            envelopes = _rows(r.execute(
                "SELECT envelope_id, patient_ref, ciphertext, payload_sha256, received_at FROM care_inbox "
                "WHERE org_id = ? AND patient_ref = ? ORDER BY received_at, envelope_id", (org_id, patient_ref)))
            self._log("doctor", doctor_id, org_id, "emergency_access", patient_ref, reason)
            r.execute("INSERT INTO alert (alert_id, patient_ref, alert_type, escalation_level, created_at, received_at) "
                      "VALUES (?, ?, 'emergency_access', NULL, ?, ?)", (alert_id, patient_ref, t, t))
            notified = escalation.recipients(r, patient_ref, "emergency_access")
            escalation.record_deliveries(r, alert_id, notified, t)
        return {"org_id": org_id, "patient_ref": patient_ref, "reason": reason, "accessed_at": t,
                "notification_alert_id": alert_id, "notified": [n[0] for n in notified], "envelopes": envelopes}

    # ================= caregiver =================

    def caregiver_alerts(self, caregiver_id: str) -> list[dict]:
        # D-008 (open): 'summary' detail returns the same minimal fields as 'alerts_only'.
        return _rows(self.db.relay.execute(
            "SELECT a.alert_id, a.patient_ref, a.alert_type, a.escalation_level, a.created_at, a.received_at "
            "FROM alert a JOIN alert_delivery d ON d.alert_id = a.alert_id AND d.recipient_type = 'caregiver' "
            "AND d.recipient_id = ? JOIN caregiver_link l ON l.caregiver_id = d.recipient_id "
            "AND l.patient_ref = a.patient_ref AND l.status = 'active' ORDER BY a.received_at, a.alert_id",
            (caregiver_id,)))

    # ================= company (company.db only) =================

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
            "SELECT record_id, patient_ref, program_id, cohort_id, drug_version, iso_week, status, source, reporter, "
            "input_mode, unanswered_questions FROM checkin_record WHERE program_id = ? ORDER BY iso_week, record_id",
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
