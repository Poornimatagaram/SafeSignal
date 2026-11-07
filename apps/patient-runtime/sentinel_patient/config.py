"""Runtime settings from the environment.

Shared: SENTINEL_BASE_URL, SENTINEL_ACTOR_ID. Patient-only settings use the PATIENT_ prefix.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# <root>/apps/patient-runtime/sentinel_patient/config.py -> <root>
REPO_ROOT = Path(__file__).resolve().parents[3]

PORT = 8001
WALTER = "pt_4b82d0c6"  # demo patient for this device (schema/demo_fixtures.json -> device_profiles)


def _split(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    db_path: Path = REPO_ROOT / "var" / "patient" / "patient.db"
    patient_ref: str = WALTER
    sentinel_base_url: str = "http://127.0.0.1:8000"
    allowed_origins: list[str] = field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])

    @classmethod
    def from_env(cls) -> Settings:
        d = cls()
        return cls(
            db_path=Path(os.environ.get("PATIENT_DB_PATH") or d.db_path),
            patient_ref=os.environ.get("SENTINEL_ACTOR_ID") or d.patient_ref,
            sentinel_base_url=os.environ.get("SENTINEL_BASE_URL") or d.sentinel_base_url,
            allowed_origins=_split(os.environ.get("PATIENT_ALLOWED_ORIGINS", "")) or d.allowed_origins,
        )
