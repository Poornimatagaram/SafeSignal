"""Patient-side client for the Sentinel service (Scoping Doc 26.11 item 4).

Used ONLY by the patient runtime's egress gate (apps/patient-runtime).
Import: from sentinel_contract.client import SentinelClient The gate owns the outbox, egress_log and the receipt; this client
validates, hashes and sends. Every send validates against the published JSON Schema first and refuses to send
an invalid payload (the refusal shown in the demo).

Config: SENTINEL_BASE_URL, SENTINEL_ACTOR_ID (the patient's pt_ ID). Role is always patient_device.

Error handling (26.13):
  SendRejected  -> 401/403/409/422: do not retry; fix code or surface to the user
  SendRetryable -> 5xx or no network: keep in the outbox, retry with backoff (2, 4, 8 ... 60 s)
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from . import ContractError, canonical, payload_sha256, validate

BACKOFF_SECONDS = [2, 4, 8, 16, 32, 60]


class SendRejected(Exception):
    def __init__(self, status: int, body: Any):
        self.status, self.body = status, body
        super().__init__(f"rejected with {status}: {body}")


class SendRetryable(Exception):
    pass


@dataclass
class SendResult:
    method: str
    url: str
    status_code: int          # 201 created or 200 already received
    payload_sha256: str       # what the egress receipt shows; equals the service's stored hash
    fields_sent: list[str]    # field names for the receipt and egress_log.fields_sent
    body: dict = field(default_factory=dict)


def field_names(payload: Any, prefix: str = "") -> list[str]:
    """Flatten to receipt field names: 'symptoms[].term_code'. Never includes values."""
    out: list[str] = []
    if isinstance(payload, dict):
        for k in sorted(payload):
            name = f"{prefix}.{k}" if prefix else k
            v = payload[k]
            if isinstance(v, (dict, list)) and v:
                out.extend(field_names(v, name))
            else:
                out.append(name)
    elif isinstance(payload, list):
        seen: list[str] = []
        for item in payload:
            for n in field_names(item, f"{prefix}[]"):
                if n not in seen:
                    seen.append(n)
        out.extend(seen or [f"{prefix}[]"])
    return out


class SentinelClient:
    def __init__(self, base_url: Optional[str] = None, patient_ref: Optional[str] = None,
                 http: Optional[httpx.Client] = None, timeout: float = 10.0):
        """`http` lets tests pass a pre-built client (e.g. FastAPI's TestClient)."""
        self.base_url = (base_url or os.environ["SENTINEL_BASE_URL"]).rstrip("/")
        self.patient_ref = patient_ref or os.environ["SENTINEL_ACTOR_ID"]
        self._http = http or httpx.Client(base_url=self.base_url, timeout=timeout)
        self._http.headers.update({"X-Role": "patient_device", "X-Actor-Id": self.patient_ref})

    def close(self) -> None:
        self._http.close()

    # ---------- reads (configuration only; no patient data in the request) ----------

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        try:
            r = self._http.get(path, params=params)
        except httpx.TransportError as e:
            raise SendRetryable(str(e)) from e
        if r.status_code >= 500:
            raise SendRetryable(f"{r.status_code} from {path}")
        if r.status_code != 200:
            raise SendRejected(r.status_code, r.json())
        return r.json()

    def fetch_survey(self, cohort_id: str) -> dict:
        return self._get("/v1/survey", {"cohort_id": cohort_id})

    def fetch_terms(self, program_id: str) -> dict:
        return self._get("/v1/terms", {"program_id": program_id})

    def fetch_org_key(self, org_id: str) -> str:
        """Care-team (or consented emergency) organization's public key; 404 until its admin registers one."""
        return self._get(f"/v1/orgs/{org_id}/public-key")["public_key"]

    # ---------- sends (the only outbound patient data) ----------

    def _send(self, method: str, path: str, kind: str, payload: dict, receipt_hash: str) -> SendResult:
        validate(kind, payload)  # raises ContractError; nothing leaves
        try:
            r = self._http.request(method, path, content=canonical(payload),
                                   headers={"Content-Type": "application/json"})
        except httpx.TransportError as e:
            raise SendRetryable(str(e)) from e
        if r.status_code >= 500:
            raise SendRetryable(f"{r.status_code} from {path}")
        if r.status_code not in (200, 201):
            raise SendRejected(r.status_code, r.json())
        body = r.json()
        server_hash = body.get("payload_sha256")
        if server_hash is not None and server_hash != receipt_hash:
            raise SendRejected(r.status_code, {"error": "hash_mismatch", "client": receipt_hash, "server": server_hash})
        return SendResult(method, f"{self.base_url}{path}", r.status_code, receipt_hash, field_names(payload), body)

    def send_record(self, record: dict) -> SendResult:
        return self._send("POST", "/v1/records", "company_record", record, payload_sha256(record))

    def send_envelope(self, envelope: dict) -> SendResult:
        # Receipt hash for an envelope is the plaintext hash it carries (26.13).
        return self._send("POST", "/v1/care-envelopes", "care_envelope", envelope, envelope["payload_sha256"])

    def send_alert(self, alert: dict) -> SendResult:
        return self._send("POST", "/v1/alerts", "alert_event", alert, payload_sha256(alert))

    def send_consent(self, consent: dict) -> SendResult:
        return self._send("PUT", f"/v1/consent/{consent['patient_ref']}", "consent_update", consent,
                          payload_sha256(consent))


def build_envelope(envelope_id: str, org_id: str, plaintext: dict, org_public_key_b64: str) -> dict:
    """Validate the doctor payload, hash it, and seal it to an organization's care-team X25519 key (sealed box).

    Build one envelope per recipient organization: the care team, plus each consented emergency organization
    (contract 2.0, docs/design/contract-2.0.md). Each gets its own envelope_id.

    Store the returned envelope in the outbox and resend it unchanged on retry: sealing is randomized,
    so re-sealing would produce a different ciphertext and a 409.
    """
    from nacl.public import PublicKey, SealedBox

    validate("doctor_payload", plaintext)
    key = PublicKey(base64.b64decode(org_public_key_b64))
    ciphertext = SealedBox(key).encrypt(canonical(plaintext))
    return {
        "schema_version": "2.0",
        "envelope_id": envelope_id,
        "org_id": org_id,
        "patient_ref": plaintext["patient_ref"],
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        "payload_sha256": payload_sha256(plaintext),
    }


__all__ = ["SentinelClient", "SendResult", "SendRejected", "SendRetryable", "ContractError", "build_envelope",
           "field_names", "BACKOFF_SECONDS"]
