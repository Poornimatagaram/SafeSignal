"""The single egress path off this device (PV-04, PV-05, PV-06, PV-08; task A4).

This is the ONLY module allowed to import sentinel_contract.client or any HTTP library (tests enforce it).

- `build_company_record` builds the 2.0 company record from the profile, consent and coded symptoms only, and
  validates it: no names, dates of birth, phones, words or free text can reach it (PV-08).
- `queue_payload` writes the schema-valid payload to `outbox` (canonical JSON plus its hash) before anything is sent.
- `send_queued` sends the stored payload unchanged through `SentinelClient`, logs every request that reached the
  service in `egress_log` (PV-06) and returns the receipt (PV-05). `SendRetryable` keeps the payload queued for a
  retry with the same `rec_` id; `SendRejected` marks it failed and it is never retried. A sent payload is never sent
  twice: the stored receipt comes back instead.
- `build_alert` builds the 2.0 severe alert (AL-02, SE-03): ids and a timestamp only, never symptom details (AL-03).
  It is queued and sent like a record (destination "alert", `send_alert`), with the same receipt and egress_log.
- `RetryWorker` retries every queued row automatically until the service accepts it (PV-07), with the backoff of
  `BACKOFF_SECONDS` (2, 4, 8, 16, 32, 60, 60 ... seconds), in the order consent, alert, company record, care
  envelope; it also seals and queues the envelopes of pending sessions once a key exists. Refused rows are never
  retried.
- Care envelopes (NF-05; task A7): `queue_care_envelope` seals the doctor payload of an approved session
  (`care_payload.doctor_payload_for_session`) to the care-team organization's key (`fetch_org_key`, always fetched
  fresh) and queues it, only while the patient shares with the care team and only for sessions approved while
  sharing. The stored envelope is resent unchanged on retry (re-sealing gives a new ciphertext and a 409, D-021).
  For envelopes the outbox, egress_log and receipt hash is the PLAINTEXT hash the envelope carries (26.13).
  No key yet (404 until the org admin registers one) raises `KeyUnavailable`: nothing is queued and the session
  stays in `pending_care_sessions`, which the retry worker keeps trying.
- Consent updates (CN-01): `queue_consent_update` queues the full current consent state for
  `PUT /v1/consent/{patient_ref}` and supersedes (marks failed, never sent) every older queued update.
- `refresh_config` fetches the survey and term list (configuration only; no patient data in the request) into
  `survey_cache` and `term_cache`; offline keeps the cache.

Logs carry method, path, status code and outbox_id only: never payloads, response bodies or patient data.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import re
import secrets
import sqlite3
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sentinel_contract import SCHEMA_VERSION, canonical, payload_sha256, validate
from sentinel_contract.client import (BACKOFF_SECONDS, ContractError, SendRejected, SendRetryable, SentinelClient,
                                      build_envelope, field_names)

from . import care_payload
from .db import connect, utc_now

log = logging.getLogger(__name__)

__all__ = ["Receipt", "ConfigRefresh", "make_client", "field_names", "new_record_id", "records_url",
           "build_company_record", "queue_payload", "send_queued", "receipt_for", "refresh_config",
           "new_alert_id", "alerts_url", "build_alert", "RetryWorker", "BACKOFF_SECONDS",
           "new_envelope_id", "envelopes_url", "new_consent_id", "consent_url", "KeyUnavailable", "fetch_org_key",
           "queue_care_envelope", "pending_care_sessions", "build_consent_update", "queue_consent_update",
           "latest_consent_receipt"]

# outbox.destination -> payload kind in schema/ (schema/enums.json -> outbox_destination)
PAYLOAD_KINDS = {"company_record": "company_record", "care_envelope": "care_envelope", "alert": "alert_event",
                 "consent": "consent_update"}
# outbox_id must equal the payload's own ID, so a retry reuses it (brief "Always")
ID_FIELDS = {"company_record": "record_id", "care_envelope": "envelope_id", "alert": "alert_id"}
# destinations this gate sends today -> SentinelClient method
SENDERS = {"company_record": "send_record", "alert": "send_alert", "care_envelope": "send_envelope",
           "consent": "send_consent"}

# SentinelClient raises SendRetryable(f"{status} from {path}") for a 5xx reply (the request reached the service)
# and chains the httpx.TransportError for no network (it reached nothing).
_SERVER_ERROR = re.compile(r"(5\d\d) from /\S*")


@dataclass(frozen=True)
class Receipt:
    status: str               # "sent" | "queued" (no network: kept in outbox) | "failed" (service refused)
    outbox_id: str            # == record_id for company records
    destination: str          # outbox destination, e.g. "company_record"
    method: str               # "POST"
    url: str                  # full URL, e.g. "http://127.0.0.1:8000/v1/records"
    fields_sent: list[str]    # field names only, e.g. "symptoms[].term_code"; never values
    payload_sha256: str       # hash of the canonical payload (for an envelope: of its plaintext); = the service's
    sent_at: str | None       # UTC "YYYY-MM-DDTHH:MM:SSZ" when sent, else None
    response_code: int | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ConfigRefresh:
    survey: str               # "updated" | "offline" | "rejected" | "no_profile"
    terms: str                # same values


def make_client(settings) -> SentinelClient:
    return SentinelClient(base_url=settings.sentinel_base_url, patient_ref=settings.patient_ref)


def new_record_id() -> str:
    return "rec_" + secrets.token_hex(4)


def records_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/v1/records"


def new_alert_id() -> str:
    return "alt_" + secrets.token_hex(4)


def alerts_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/v1/alerts"


def new_envelope_id() -> str:
    return "env_" + secrets.token_hex(4)


def envelopes_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/v1/care-envelopes"


def new_consent_id() -> str:
    """Outbox id of a consent update (the consent payload itself has no id field)."""
    return "con_" + secrets.token_hex(4)


def consent_url(base_url: str, patient_ref: str) -> str:
    return f"{base_url.rstrip('/')}/v1/consent/{patient_ref}"


# ---------- build ----------

def _iso_week(now: datetime | None) -> str:
    """Current ISO week in UTC, e.g. "2026-W45". A naive datetime is taken as UTC."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    iso = now.astimezone(timezone.utc).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _flag(value: Any) -> Any:
    """0/1 from SQLite -> bool. Anything else is left as is, so the schema refuses it instead of guessing."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    return value


def build_company_record(*, record_id: str, profile: Mapping, consent: Mapping, symptoms: Sequence[Mapping],
                         unanswered_questions: int, reporter: str, input_mode: str,
                         now: datetime | None = None) -> dict:
    """The 2.0 company record with exactly the schema's fields; raises ContractError if it is not valid.

    Enrollment fields come from the profile (D-006). Only coded values are copied: nothing else in `profile`,
    `consent` or the symptom mappings (names, dates of birth, phones, patient words) can reach the record.
    """
    record = {
        "schema_version": SCHEMA_VERSION,
        "record_id": record_id,
        "patient_ref": profile["patient_ref"],
        "program_id": profile["program_id"],
        "cohort_id": profile["cohort_id"],
        "drug_version": profile["drug_version"],
        "iso_week": _iso_week(now),
        "status": "completed" if unanswered_questions == 0 else "partial",
        "symptoms": [{"term_code": s["term_code"], "severity": s["severity"], "onset": s["onset"],
                      "known_side_effect": _flag(s["known_side_effect"]),
                      "possible_link_flag": _flag(s["possible_link_flag"])} for s in symptoms],
        "unanswered_questions": unanswered_questions,
        "consent": {"care_team": _flag(consent["share_care_team"]), "caregiver": _flag(consent["share_caregiver"])},
        "reporter": reporter,
        "input_mode": input_mode,
    }
    validate("company_record", record)  # ContractError names fields only, never values
    return record


def build_alert(*, alert_id: str, patient_ref: str, now: datetime | None = None) -> dict:
    """The 2.0 severe alert with exactly the schema's fields; raises ContractError if it is not valid.

    Devices send only "severe" (D-016). It carries no symptom, term, severity or words (AL-03): the care team and
    caregiver learn only that a severe alert was raised. A naive `now` is taken as UTC.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    alert = {
        "schema_version": SCHEMA_VERSION,
        "alert_id": alert_id,
        "patient_ref": patient_ref,
        "alert_type": "severe",
        "created_at": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    validate("alert_event", alert)  # ContractError names fields only, never values
    return alert


# ---------- outbox ----------

def queue_payload(conn: sqlite3.Connection, *, outbox_id: str, session_id: str | None, destination: str,
                  payload: dict) -> None:
    """Write a schema-valid payload to the outbox as "queued". Does not commit: the caller owns the transaction.

    Same id and same payload again is a no-op; same id with a different payload raises ValueError.
    The stored hash is the payload's hash, except for a care envelope: there it is the plaintext hash the envelope
    carries (`payload_sha256`, 26.13), which is what the service stores and the receipt shows.
    """
    kind = PAYLOAD_KINDS.get(destination)
    if kind is None:
        raise ValueError(f"unknown outbox destination {destination!r}")
    validate(kind, payload)
    id_field = ID_FIELDS.get(destination)
    if id_field and payload.get(id_field) != outbox_id:
        raise ValueError(f"outbox_id must equal the payload's {id_field}")
    digest = _row_hash(destination, payload)
    text = canonical(payload).decode("utf-8")
    row = conn.execute("SELECT destination, payload, payload_sha256 FROM outbox WHERE outbox_id = ?",
                       (outbox_id,)).fetchone()
    if row is not None:
        if (row[0], row[1], row[2]) == (destination, text, digest):
            return
        raise ValueError(f"outbox {outbox_id} already holds a different payload")
    conn.execute("INSERT INTO outbox (outbox_id, session_id, destination, payload, payload_sha256, status, created_at) "
                 "VALUES (?, ?, ?, ?, ?, 'queued', ?)", (outbox_id, session_id, destination, text, digest, utc_now()))


def _row_hash(destination: str, payload: Mapping) -> str | None:
    """outbox/egress_log/receipt hash: the plaintext hash an envelope carries, else the payload's own hash."""
    if destination == "care_envelope":
        return payload.get("payload_sha256")
    return payload_sha256(payload)


def _route(destination: str, payload: Mapping) -> tuple[str, str]:
    """(method, path) for a destination; brief "How to talk to the service"."""
    if destination == "consent":
        return "PUT", f"/v1/consent/{payload['patient_ref']}"
    return "POST", {"company_record": "/v1/records", "care_envelope": "/v1/care-envelopes",
                    "alert": "/v1/alerts"}[destination]


def _log_request(conn: sqlite3.Connection, outbox_id: str, method: str, url: str, fields: list[str], digest: str,
                 response_code: int, at: str) -> None:
    conn.execute("INSERT INTO egress_log (outbox_id, method, url, fields_sent, payload_sha256, response_code, sent_at) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?)", (outbox_id, method, url, json.dumps(fields), digest, response_code, at))


def _server_status(error: SendRetryable) -> int | None:
    """The 5xx status if the request reached the service; None for a transport error (it reached nothing)."""
    if error.__cause__ is not None:
        return None
    match = _SERVER_ERROR.fullmatch(str(error))
    return int(match.group(1)) if match else None


_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(outbox_id: str) -> threading.Lock:
    """One send at a time per outbox row, so two callers can never send it twice."""
    with _locks_guard:
        return _locks.setdefault(outbox_id, threading.Lock())


def send_queued(db_path: Path, outbox_id: str, *, client) -> Receipt:
    """Send the stored payload unchanged and return the receipt. Sent or failed rows are never sent again."""
    base_url = getattr(client, "base_url", "")  # SentinelClient has it; only completes a not-yet-sent receipt's URL
    with _lock_for(outbox_id):
        with closing(connect(db_path)) as conn:
            row = conn.execute("SELECT destination, payload, payload_sha256, status FROM outbox WHERE outbox_id = ?",
                               (outbox_id,)).fetchone()
        if row is None:
            raise KeyError(outbox_id)
        if row["status"] != "queued":
            return receipt_for(db_path, outbox_id, base_url=base_url)
        destination = row["destination"]
        if destination not in SENDERS:
            raise NotImplementedError(f"sending {destination} payloads is not built yet")

        payload = json.loads(row["payload"])
        digest = row["payload_sha256"]
        # An envelope cannot be re-hashed (its hash is of the plaintext inside): its stored text must be the
        # canonical JSON it was queued as, and the hash it carries must be the stored one.
        intact = (canonical(payload).decode("utf-8") == row["payload"] and _row_hash(destination, payload) == digest
                  if destination == "care_envelope" else payload_sha256(payload) == digest)
        if not intact:
            raise RuntimeError(f"outbox {outbox_id} payload does not match its stored hash; not sent")
        method, path = _route(destination, payload)
        url, fields = f"{base_url.rstrip('/')}{path}", field_names(payload)
        queued = Receipt("queued", outbox_id, destination, method, url, fields, digest, None, None)

        try:
            result = getattr(client, SENDERS[destination])(payload)
        except SendRetryable as e:
            code = _server_status(e)
            if code is not None:  # reached the service: log it (PV-06), keep it queued
                with closing(connect(db_path)) as conn, conn:
                    _log_request(conn, outbox_id, method, url, fields, digest, code, utc_now())
            log.warning("egress %s %s -> %s, kept in outbox (%s)", method, path, code or "no network", outbox_id)
            return queued
        except SendRejected as e:
            with closing(connect(db_path)) as conn, conn:
                conn.execute("UPDATE outbox SET status = 'failed' WHERE outbox_id = ? AND status = 'queued'",
                             (outbox_id,))
                _log_request(conn, outbox_id, method, url, fields, digest, e.status, utc_now())
            log.warning("egress %s %s -> %s, refused; not retried (%s)", method, path, e.status, outbox_id)
            return Receipt("failed", outbox_id, destination, method, url, fields, digest, None, e.status)
        except ContractError as e:  # the stored payload no longer matches the schema: nothing was sent
            with closing(connect(db_path)) as conn, conn:
                conn.execute("UPDATE outbox SET status = 'failed' WHERE outbox_id = ? AND status = 'queued'",
                             (outbox_id,))
            log.error("egress %s %s not sent, payload fails the schema at %s (%s)", method, path,
                      [err["field"] for err in e.errors], outbox_id)
            return Receipt("failed", outbox_id, destination, method, url, fields, digest, None, None)

        sent_at = utc_now()
        with closing(connect(db_path)) as conn, conn:
            conn.execute("UPDATE outbox SET status = 'sent', sent_at = ? WHERE outbox_id = ? AND status = 'queued'",
                         (sent_at, outbox_id))
            _log_request(conn, outbox_id, result.method, result.url, list(result.fields_sent), result.payload_sha256,
                         result.status_code, sent_at)
        log.info("egress %s %s -> %s (%s)", result.method, path, result.status_code, outbox_id)
        return Receipt("sent", outbox_id, destination, result.method, result.url, list(result.fields_sent),
                       result.payload_sha256, sent_at, result.status_code)


# ---------- care envelopes (NF-05; task A7) ----------

class KeyUnavailable(Exception):
    """The organization's public key could not be fetched; nothing was sealed or queued.

    `reason`: "no_key" (404: its admin has not registered one yet, the normal case at first), "refused" (403 or
    another 4xx, or a reply that is not base64 of a 32-byte key) or "offline" (no network or 5xx).
    """

    def __init__(self, reason: str, org_id: str):
        self.reason, self.org_id = reason, org_id
        super().__init__(f"public key of {org_id} unavailable: {reason}")


def _is_key(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return len(base64.b64decode(value, validate=True)) == 32
    except (binascii.Error, ValueError):
        return False


def fetch_org_key(db_path: Path, org_id: str, *, client) -> str:
    """The organization's current X25519 public key (base64), fetched fresh every time: an org may re-register its
    key, so a cached one is never used to seal. The care-team org's key is stored in
    `patient_profile.care_org_public_key` (for display only). Raises KeyUnavailable."""
    path = f"/v1/orgs/{org_id}/public-key"
    try:
        key = client.fetch_org_key(org_id)
    except SendRetryable:
        log.warning("egress GET %s -> no network or server error", path)
        raise KeyUnavailable("offline", org_id) from None
    except SendRejected as e:
        log.warning("egress GET %s -> %s", path, e.status)
        raise KeyUnavailable("no_key" if e.status == 404 else "refused", org_id) from None
    except (KeyError, TypeError, ValueError):  # a reply without a usable public_key
        log.warning("egress GET %s -> reply does not match the contract", path)
        raise KeyUnavailable("refused", org_id) from None
    if not _is_key(key):
        log.warning("egress GET %s -> 200, not a 32-byte key", path)
        raise KeyUnavailable("refused", org_id)
    log.info("egress GET %s -> 200", path)
    with closing(connect(db_path)) as conn, conn:
        conn.execute("UPDATE patient_profile SET care_org_public_key = ? WHERE care_org_id = ?", (key, org_id))
    return key


def _sharing_care_team(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT share_care_team FROM consent ORDER BY consent_id DESC LIMIT 1").fetchone()
    return bool(row and row["share_care_team"])


def _approved_while_sharing(conn: sqlite3.Connection, session_id: str) -> bool:
    """The session was approved (ended_at set) and its company record (queued or sent) says consent.care_team."""
    for row in conn.execute("SELECT o.payload FROM outbox o JOIN checkin_session s ON s.session_id = o.session_id "
                            "WHERE o.session_id = ? AND o.destination = 'company_record' "
                            "AND o.status IN ('queued', 'sent') AND s.ended_at IS NOT NULL", (session_id,)):
        try:
            if json.loads(row["payload"])["consent"]["care_team"] is True:
                return True
        except (KeyError, TypeError, ValueError):
            continue
    return False


def _envelope_row(conn: sqlite3.Connection, session_id: str) -> str | None:
    row = conn.execute("SELECT outbox_id FROM outbox WHERE session_id = ? AND destination = 'care_envelope' "
                       "ORDER BY created_at, outbox_id LIMIT 1", (session_id,)).fetchone()
    return row["outbox_id"] if row else None


def _care_org(conn: sqlite3.Connection, patient_ref: str) -> str | None:
    row = conn.execute("SELECT care_org_id FROM patient_profile WHERE patient_ref = ?", (patient_ref,)).fetchone()
    return row["care_org_id"] if row else None


def queue_care_envelope(db_path: Path, session_id: str, patient_ref: str, *, client) -> str | None:
    """Seal the doctor payload of an approved session to the care-team organization and queue it (NF-05).

    Returns the envelope_id (== outbox_id) of the session's care envelope: the existing one if it was queued
    before, else a new one. Returns None when there is nothing to send: the patient does not share with the care
    team now, there is no care organization, or the session was not approved while sharing (its company record is
    missing, refused or says consent.care_team false). Does not send: `send_queued` or the retry worker does.
    Raises KeyUnavailable (nothing queued; try again later), ValueError (no date of birth) or ContractError.
    Only the care-team organization for now: envelopes for consented emergency organizations (D-065) are a later
    task.
    """
    with _lock_for(f"care:{session_id}"):  # the approve route and the retry worker never seal one session twice
        with closing(connect(db_path)) as conn:
            if (existing := _envelope_row(conn, session_id)) is not None:
                return existing
            org_id = _care_org(conn, patient_ref)
            if not (org_id and _sharing_care_team(conn) and _approved_while_sharing(conn, session_id)):
                return None
            payload = care_payload.doctor_payload_for_session(conn, session_id, patient_ref)
        key = fetch_org_key(db_path, org_id, client=client)
        envelope_id = new_envelope_id()
        envelope = build_envelope(envelope_id, org_id, payload, key)
        with closing(connect(db_path)) as conn, conn:
            if not (_sharing_care_team(conn) and _care_org(conn, patient_ref) == org_id):
                return None  # consent was withdrawn or changed while the key was fetched
            queue_payload(conn, outbox_id=envelope_id, session_id=session_id, destination="care_envelope",
                          payload=envelope)
        log.info("care envelope %s queued for %s", envelope_id, org_id)
        return envelope_id


def pending_care_sessions(db_path: Path) -> list[str]:
    """Approved sessions whose care envelope is still to be sealed (oldest first): the patient shares with the care
    team now, a care organization is set, the session was approved while sharing, and it has no care_envelope row.
    Empty while consent is off: turning it off stops future sharing (CN-03)."""
    with closing(connect(db_path)) as conn:
        if not _sharing_care_team(conn):
            return []
        if not conn.execute("SELECT 1 FROM patient_profile WHERE care_org_id IS NOT NULL").fetchone():
            return []
        candidates = [r["session_id"] for r in conn.execute(
            "SELECT s.session_id FROM checkin_session s WHERE s.ended_at IS NOT NULL AND NOT EXISTS "
            "(SELECT 1 FROM outbox o WHERE o.session_id = s.session_id AND o.destination = 'care_envelope') "
            "ORDER BY s.ended_at, s.session_id")]
        return [sid for sid in candidates if _approved_while_sharing(conn, sid)]


# ---------- consent updates (CN-01) ----------

def build_consent_update(conn: sqlite3.Connection, patient_ref: str) -> dict:
    """The 2.0 consent update for the CURRENT local state; raises LookupError without a profile or consent row and
    ContractError if it is not valid. Emergency organizations and contacts are included only with emergency
    consent; contact labels (display_label) never leave the device."""
    profile = conn.execute("SELECT care_org_id, caregiver_id FROM patient_profile WHERE patient_ref = ?",
                           (patient_ref,)).fetchone()
    consent = conn.execute("SELECT share_care_team, share_caregiver, caregiver_detail, emergency_consent FROM consent "
                           "ORDER BY consent_id DESC LIMIT 1").fetchone()
    if profile is None or consent is None:
        raise LookupError("no profile or consent on this device")
    emergency = bool(consent["emergency_consent"])
    orgs = [r["org_id"] for r in conn.execute("SELECT org_id FROM emergency_org ORDER BY org_id")] if emergency else []
    contacts = [{"contact_id": r["contact_id"], "contact_type": r["contact_type"], "phone": r["phone"],
                 "org_id": r["org_id"], "priority": r["priority"]}
                for r in conn.execute("SELECT contact_id, contact_type, phone, org_id, priority FROM emergency_contact "
                                      "ORDER BY priority, contact_id")] if emergency else []
    update = {
        "schema_version": SCHEMA_VERSION,
        "patient_ref": patient_ref,
        "care_org_id": profile["care_org_id"],
        "share_care_team": _flag(consent["share_care_team"]),
        "caregiver_id": profile["caregiver_id"],
        "share_caregiver": _flag(consent["share_caregiver"]),
        "caregiver_detail": consent["caregiver_detail"],
        "emergency_consent": emergency,
        "emergency_org_ids": orgs,
        "emergency_contacts": contacts,
    }
    validate("consent_update", update)
    return update


def queue_consent_update(conn: sqlite3.Connection, patient_ref: str) -> str:
    """Queue the full current consent state (destination "consent", session_id NULL) and return its outbox_id.

    Does not commit: the caller owns the transaction and writes the new consent row first. Every older update still
    queued is marked failed with no egress_log row (superseded, never sent): each update is the whole state, so an
    older one landing after this one would undo it. (One already in flight may still land; this newer one is
    queued behind it and is sent after it, so the service ends on the newest state.)
    """
    update = build_consent_update(conn, patient_ref)
    outbox_id = new_consent_id()
    conn.execute("UPDATE outbox SET status = 'failed' WHERE destination = 'consent' AND status = 'queued'")
    queue_payload(conn, outbox_id=outbox_id, session_id=None, destination="consent", payload=update)
    return outbox_id


def latest_consent_receipt(db_path: Path, *, base_url: str = "") -> Receipt | None:
    """Receipt of the newest consent update (sent, queued or failed); None if none was ever queued."""
    with closing(connect(db_path)) as conn:
        row = conn.execute("SELECT outbox_id FROM outbox WHERE destination = 'consent' "
                           "ORDER BY created_at DESC, rowid DESC LIMIT 1").fetchone()
    return receipt_for(db_path, row["outbox_id"], base_url=base_url) if row else None


# ---------- automatic retry (PV-07) ----------

class RetryWorker:
    """Retries every queued row until the service accepts it (201 or 200), and seals pending care envelopes.

    After the n-th failed attempt of a row (no network or 5xx) the next one is due `backoff[min(n-1, len-1)]`
    seconds later: 2, 4, 8, 16, 32, 60, 60 ... A newly queued row is due at once. Refused ("failed") and "sent" rows
    are never touched. Attempt counts live in memory only, so a restart begins again at 2 s. Order: consent first
    (a withdrawal reaches the service before later sends), then alerts, records and care envelopes. Sending goes
    through `send_queued`, so receipts, egress_log and never-twice are the same as for a send from the approve
    route; a row being sent by one caller is skipped by the others.

    Each pass first calls `queue_care_envelope` for every due session of `pending_care_sessions` (backoff key
    "care:<session_id>", same delays): no key yet (KeyUnavailable) backs off; once queued, the envelope is sent in
    the same pass. `patient_ref` defaults to the device's single patient_profile row.
    """

    PRIORITY = ("consent", "alert", "company_record", "care_envelope")
    CARE = "care:"

    def __init__(self, db_path: Path, client_factory: Callable[[], Any], *, backoff: Sequence[int] = BACKOFF_SECONDS,
                 clock: Callable[[], float] = time.monotonic, patient_ref: str | None = None):
        if not backoff:
            raise ValueError("backoff needs at least one delay")
        self.db_path, self.client_factory = Path(db_path), client_factory
        self.backoff, self.clock = tuple(backoff), clock
        self.patient_ref = patient_ref
        self._state: dict[str, tuple[int, float]] = {}   # outbox_id or "care:<session_id>" -> (failures, due at)
        self._in_flight: set[str] = set()
        self._guard = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _patient_ref(self) -> str | None:
        if self.patient_ref:
            return self.patient_ref
        with closing(connect(self.db_path)) as conn:
            refs = [r[0] for r in conn.execute("SELECT patient_ref FROM patient_profile LIMIT 2")]
        return refs[0] if len(refs) == 1 else None

    def _queued(self) -> list[tuple[str, str]]:
        order = " ".join(f"WHEN '{d}' THEN {i}" for i, d in enumerate(self.PRIORITY))
        marks = ",".join("?" * len(self.PRIORITY))
        with closing(connect(self.db_path)) as conn:
            return [(r[0], r[1]) for r in conn.execute(
                f"SELECT outbox_id, destination FROM outbox WHERE status = 'queued' AND destination IN ({marks}) "
                f"ORDER BY CASE destination {order} END, created_at, outbox_id", self.PRIORITY).fetchall()]

    def _claim(self, keys: list[str], *, care: bool) -> list[str]:
        """Claim the due keys of one kind and forget the state of that kind's keys that are no longer pending."""
        now = self.clock()
        with self._guard:
            live = set(keys)
            for gone in [k for k in self._state if k.startswith(self.CARE) == care
                         and k not in live and k not in self._in_flight]:
                del self._state[gone]  # sent, refused or sealed elsewhere (e.g. the approve route)
            due = [k for k in keys if k not in self._in_flight and self._state.get(k, (0, now))[1] <= now]
            self._in_flight.update(due)
        return due

    def _claim_due(self) -> list[str]:
        return self._claim([oid for oid, _ in self._queued()], care=False)

    def _claim_care_due(self) -> list[str]:
        return self._claim([self.CARE + sid for sid in pending_care_sessions(self.db_path)], care=True)

    def _finish(self, key: str, still_queued: bool) -> None:
        with self._guard:
            self._in_flight.discard(key)
            if not still_queued:
                self._state.pop(key, None)
                return
            attempts = self._state.get(key, (0, 0.0))[0] + 1
            delay = self.backoff[min(attempts - 1, len(self.backoff) - 1)]
            self._state[key] = (attempts, self.clock() + delay)

    def run_once(self) -> list[Receipt]:
        """Seal due pending care envelopes, then send every queued row whose next attempt is due; returns the
        receipts of the rows it tried to send (sent, queued or failed)."""
        care_due = self._claim_care_due()
        pending = list(care_due)
        receipts: list[Receipt] = []
        client = None
        try:
            if care_due:
                client = self.client_factory()
                patient_ref = self._patient_ref()
                for key in care_due:
                    session_id = key[len(self.CARE):]
                    retry = True
                    try:
                        if patient_ref is not None:
                            queue_care_envelope(self.db_path, session_id, patient_ref, client=client)
                            retry = False
                    except KeyUnavailable as e:
                        log.info("care envelope for %s waits: key %s", session_id, e.reason)
                    except Exception as e:  # never the message: it could quote a value
                        log.error("care envelope for %s failed with %s; backing off", session_id, type(e).__name__)
                    finally:
                        pending.remove(key)
                        self._finish(key, retry)

            due = self._claim_due()
            pending.extend(due)
            if not due:
                return receipts
            client = client or self.client_factory()
            for outbox_id in due:
                still_queued = True
                try:
                    receipt = send_queued(self.db_path, outbox_id, client=client)
                    receipts.append(receipt)
                    still_queued = receipt.status == "queued"
                except KeyError:  # the row is gone
                    still_queued = False
                except Exception as e:  # never the message: it could quote a value
                    log.error("egress retry of %s failed with %s; backing off", outbox_id, type(e).__name__)
                finally:
                    pending.remove(outbox_id)
                    self._finish(outbox_id, still_queued)
        finally:
            for key in pending:  # the client could not be built (or a pass was cut short): back these off
                self._finish(key, True)
            close = getattr(client, "close", None)
            if callable(close):
                close()
        return receipts

    def status(self, outbox_id: str) -> dict | None:
        """{"attempts": n, "next_attempt_in": seconds} for a queued row this worker would send; else None."""
        with closing(connect(self.db_path)) as conn:
            row = conn.execute("SELECT status, destination FROM outbox WHERE outbox_id = ?", (outbox_id,)).fetchone()
        if row is None or row["status"] != "queued" or row["destination"] not in self.PRIORITY:
            return None
        now = self.clock()
        with self._guard:
            attempts, due_at = self._state.get(outbox_id, (0, now))
        return {"attempts": attempts, "next_attempt_in": max(0.0, due_at - now)}

    def start(self, interval: float = 1.0) -> None:
        """Run `run_once` every `interval` seconds on a daemon thread until `stop`."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()

        def loop() -> None:
            while not self._stop.is_set():
                try:
                    self.run_once()
                except Exception as e:  # e.g. the database is busy; try again next tick
                    log.error("egress retry pass failed with %s", type(e).__name__)
                self._stop.wait(interval)

        self._thread = threading.Thread(target=loop, name="egress-retry", daemon=True)
        self._thread.start()

    def stop(self, timeout: float | None = 5.0) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)


def receipt_for(db_path: Path, outbox_id: str, *, base_url: str = "") -> Receipt | None:
    """The receipt for an outbox row, from the row and its latest egress_log entry; None if there is no such row.

    `base_url` only completes the URL of a payload that has never reached the service (no egress_log row yet).
    """
    with closing(connect(db_path)) as conn:
        row = conn.execute("SELECT destination, payload, payload_sha256, status, sent_at FROM outbox "
                           "WHERE outbox_id = ?", (outbox_id,)).fetchone()
        if row is None:
            return None
        entry = conn.execute("SELECT method, url, fields_sent, response_code FROM egress_log WHERE outbox_id = ? "
                             "ORDER BY log_id DESC LIMIT 1", (outbox_id,)).fetchone()
    if entry is not None:
        method, url, fields = entry["method"], entry["url"], json.loads(entry["fields_sent"])
    else:
        payload = json.loads(row["payload"])
        method, path = _route(row["destination"], payload)
        url, fields = f"{base_url.rstrip('/')}{path}", field_names(payload)
    response_code = entry["response_code"] if entry is not None and row["status"] != "queued" else None
    return Receipt(row["status"], outbox_id, row["destination"], method, url, fields, row["payload_sha256"],
                   row["sent_at"], response_code)


# ---------- configuration (GET only; no patient data in the request) ----------

def _store_survey(conn: sqlite3.Connection, body: Mapping, cohort_id: str) -> None:
    config = {"schedule": body["schedule"], "questions": body["questions"]}
    validate("survey_config", config)
    if body["cohort_id"] != cohort_id:
        raise ValueError("survey is for another cohort")
    if not isinstance(body["config_id"], str) or type(body["version"]) is not int:
        raise TypeError("survey config_id or version has the wrong type")
    conn.execute(
        "INSERT INTO survey_cache (config_id, cohort_id, version, questions_json, fetched_at) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(config_id) DO UPDATE SET cohort_id = excluded.cohort_id, version = excluded.version, "
        "questions_json = excluded.questions_json, fetched_at = excluded.fetched_at",
        (body["config_id"], body["cohort_id"], body["version"], json.dumps(config, ensure_ascii=False), utc_now()))


def _store_terms(conn: sqlite3.Connection, body: Mapping, program_id: str) -> None:
    if body["program_id"] != program_id:
        raise ValueError("term list is for another program")
    rows = []
    for t in body["terms"]:
        words = t["everyday_words"]
        if not (isinstance(t["term_code"], str) and isinstance(t["label_term"], str) and isinstance(words, list)
                and all(isinstance(w, str) for w in words) and isinstance(t["severe_trigger"], bool)
                and isinstance(t["known_for_program"], bool)):
            raise TypeError("term has the wrong shape")
        rows.append((t["term_code"], t["label_term"], json.dumps(words, ensure_ascii=False), int(t["severe_trigger"]),
                     int(t["known_for_program"])))
    conn.executemany(  # upsert, never DELETE or REPLACE: symptom_event rows reference term_cache
        "INSERT INTO term_cache (term_code, label_term, everyday_words, severe_trigger, known_for_program) "
        "VALUES (?, ?, ?, ?, ?) ON CONFLICT(term_code) DO UPDATE SET label_term = excluded.label_term, "
        "everyday_words = excluded.everyday_words, severe_trigger = excluded.severe_trigger, "
        "known_for_program = excluded.known_for_program", rows)


def _refresh(db_path: Path, path: str, fetch: Callable[[], dict],
             store: Callable[[sqlite3.Connection, Mapping], None]) -> str:
    try:
        body = fetch()
        with closing(connect(db_path)) as conn, conn:  # all or nothing
            store(conn, body)
    except SendRetryable:
        log.warning("egress GET %s -> no network or server error, cache kept", path)
        return "offline"
    except SendRejected as e:
        log.warning("egress GET %s -> %s, cache kept", path, e.status)
        return "rejected"
    except (KeyError, TypeError, ValueError):  # includes ContractError
        log.warning("egress GET %s -> reply does not match the contract, cache kept", path)
        return "rejected"
    log.info("egress GET %s -> 200, cache updated", path)
    return "updated"


def refresh_config(db_path: Path, patient_ref: str, *, client) -> ConfigRefresh:
    """Fetch the cohort's survey and the program's term list into the local caches."""
    with closing(connect(db_path)) as conn:
        profile = conn.execute("SELECT cohort_id, program_id FROM patient_profile WHERE patient_ref = ?",
                               (patient_ref,)).fetchone()
    if profile is None:
        return ConfigRefresh(survey="no_profile", terms="no_profile")
    cohort_id, program_id = profile["cohort_id"], profile["program_id"]
    survey = _refresh(db_path, "/v1/survey", lambda: client.fetch_survey(cohort_id),
                      lambda conn, body: _store_survey(conn, body, cohort_id))
    terms = _refresh(db_path, "/v1/terms", lambda: client.fetch_terms(program_id),
                     lambda conn, body: _store_terms(conn, body, program_id))
    return ConfigRefresh(survey=survey, terms=terms)
