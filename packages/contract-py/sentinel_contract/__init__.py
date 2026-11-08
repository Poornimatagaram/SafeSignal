"""Shared contract helpers: canonical JSON, payload hashing and JSON Schema validation.

Single implementation used by the Sentinel service and the patient-side client (Scoping Doc 26.13).
The TypeScript side must match `canonical()` byte for byte; see schema/examples/hash_vectors.json.
"""

from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

# Repo layout: <root>/packages/contract-py/sentinel_contract/__init__.py -> <root>/schema
SCHEMA_DIR = Path(os.environ.get("SENTINEL_SCHEMA_DIR") or Path(__file__).resolve().parents[3] / "schema")
SCHEMA_VERSION = "2.0"     # value of `schema_version` inside every payload
CONTRACT_VERSION = "2.2"   # release of schema/ as a whole (tables + API); sent as X-Schema-Version

PAYLOAD_SCHEMAS = {
    "company_record": "company_record.json",
    "doctor_payload": "doctor_payload.json",
    "care_envelope": "care_envelope.json",
    "alert_event": "alert_event.json",
    "consent_update": "consent_update.json",
    "survey_config": "survey_config.json",
}


def canonical(payload: Any) -> bytes:
    """Sorted keys, no whitespace, UTF-8 (non-ASCII kept as-is)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def payload_sha256(payload: Any) -> str:
    """Lowercase hex SHA-256 of the canonical JSON."""
    return hashlib.sha256(canonical(payload)).hexdigest()


@lru_cache(maxsize=None)
def enums() -> dict:
    return json.loads((SCHEMA_DIR / "enums.json").read_text())


@lru_cache(maxsize=None)
def _validator(kind: str) -> Draft202012Validator:
    if kind not in PAYLOAD_SCHEMAS:
        raise KeyError(f"unknown payload kind: {kind}")
    schema = json.loads((SCHEMA_DIR / PAYLOAD_SCHEMAS[kind]).read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


class ContractError(ValueError):
    """A payload failed its JSON Schema. `errors` names each failing field as a JSON Pointer."""

    def __init__(self, kind: str, errors: list[dict]):
        self.kind = kind
        self.errors = errors
        super().__init__(f"{kind} failed validation: {errors}")


def _pointer(path) -> str:
    return "/" + "/".join(str(p) for p in path) if path else "/"


def validation_errors(kind: str, payload: Any) -> list[dict]:
    """Every schema error as {field, message}. Messages never echo payload values (logs must not carry content)."""
    out = []
    for err in sorted(_validator(kind).iter_errors(payload), key=lambda e: list(e.absolute_path)):
        field = _pointer(err.absolute_path)
        if err.validator == "additionalProperties" and isinstance(err.instance, dict):
            allowed = set(err.schema.get("properties", {}))
            extras = sorted(k for k in err.instance if k not in allowed)
            for extra in extras:
                out.append({"field": f"{field.rstrip('/')}/{extra}", "message": "field not allowed by schema"})
            continue
        if err.validator == "required":
            missing = err.message.split("'")[1] if "'" in err.message else "?"
            out.append({"field": f"{field.rstrip('/')}/{missing}", "message": "required field missing"})
            continue
        out.append({"field": field, "message": f"failed '{err.validator}' check"})
    return out


def validate(kind: str, payload: Any) -> None:
    errors = validation_errors(kind, payload)
    if errors:
        raise ContractError(kind, errors)
