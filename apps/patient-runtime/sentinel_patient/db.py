"""Local patient database (var/patient/patient.db). Contract 2.0.

Created on first launch by applying schema/patient.sql (CREATE TABLE IF NOT EXISTS, safe to re-run), then seeded
once with this device's synthetic profile, consent, emergency organizations and emergency contacts from
schema/demo_fixtures.json. Never add, rename or drop tables or columns here: the schema is the contract.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from sentinel_contract import SCHEMA_DIR, SCHEMA_VERSION

PATIENT_SQL = SCHEMA_DIR / "patient.sql"
DEMO_FIXTURES = SCHEMA_DIR / "demo_fixtures.json"

PROFILE_COLUMNS = (
    "patient_ref", "display_name", "date_of_birth", "phone", "program_id", "cohort_id", "drug_name",
    "drug_version", "care_org_id", "care_org_public_key", "reporter_default", "caregiver_id", "enrolled_at",
)


class SchemaMismatch(RuntimeError):
    """The database was created for another contract version; CREATE TABLE IF NOT EXISTS cannot upgrade it."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _check_version(conn: sqlite3.Connection, db_path: Path) -> None:
    has_meta = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_meta'").fetchone()
    row = has_meta and conn.execute("SELECT schema_version FROM schema_meta WHERE id = 1").fetchone()
    if row and row["schema_version"] != SCHEMA_VERSION:
        raise SchemaMismatch(f"{db_path} was created for schema {row['schema_version']}; this runtime needs "
                             f"{SCHEMA_VERSION}. Stop the runtime, delete that file (synthetic data only) and restart.")


def _seed(conn: sqlite3.Connection, patient_ref: str) -> None:
    fixtures = json.loads(DEMO_FIXTURES.read_text())
    profile = next((p for p in fixtures["device_profiles"] if p["patient_ref"] == patient_ref), None)
    if profile is None:
        return  # unknown actor ID: nothing to seed; /health reports profile_loaded = false

    conn.execute(f"INSERT INTO patient_profile ({', '.join(PROFILE_COLUMNS)}) "
                 f"VALUES ({', '.join('?' * len(PROFILE_COLUMNS))})",
                 tuple(profile.get(c) for c in PROFILE_COLUMNS))

    c = profile["consent"]
    conn.execute("INSERT INTO consent (share_care_team, emergency_consent, share_caregiver, caregiver_detail, "
                 "updated_at) VALUES (?, ?, ?, ?, ?)",
                 (int(c["share_care_team"]), int(c["emergency_consent"]), int(c["share_caregiver"]),
                  c["caregiver_detail"], utc_now()))

    conn.executemany("INSERT OR IGNORE INTO emergency_org (org_id, public_key) VALUES (?, NULL)",
                     [(org_id,) for org_id in profile.get("emergency_org_ids", [])])

    labels = profile.get("emergency_contact_labels", {})  # local only
    conn.executemany(
        "INSERT OR IGNORE INTO emergency_contact (contact_id, contact_type, phone, org_id, priority, display_label) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [(e["contact_id"], e["contact_type"], e["phone"], e.get("org_id"), e["priority"], labels.get(e["contact_id"]))
         for e in fixtures.get("emergency_contacts", []) if e["patient_ref"] == patient_ref])


def _egress_log_before_2_3(conn: sqlite3.Connection) -> bool:
    """Contract 2.3 (D-088): egress_log gained `kind` and a nullable `outbox_id`. CREATE TABLE IF NOT EXISTS can't
    change an existing table, so a 2.2 table is renamed here, recreated from schema/patient.sql, and its rows copied
    back by `_finish_egress_log_migration` (every old row is a send). Returns True when a migration is under way."""
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'egress_log_2_2'").fetchone():
        return True  # a migration was interrupted (executescript commits): finish it
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(egress_log)")}
    if not columns or "kind" in columns:
        return False
    conn.execute("ALTER TABLE egress_log RENAME TO egress_log_2_2")
    return True


def _finish_egress_log_migration(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO egress_log (log_id, outbox_id, kind, method, url, fields_sent, payload_sha256, "
                 "response_code, sent_at) SELECT log_id, outbox_id, 'send', method, url, fields_sent, payload_sha256, "
                 "response_code, sent_at FROM egress_log_2_2")
    conn.execute("DROP TABLE egress_log_2_2")


def init_db(db_path: Path, patient_ref: str) -> None:
    """Apply the schema, then seed on first launch only, so later changes on the device are never overwritten."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect(db_path)) as conn, conn:
        _check_version(conn, db_path)
        old_log = _egress_log_before_2_3(conn)
        conn.executescript(PATIENT_SQL.read_text())
        if old_log:
            _finish_egress_log_migration(conn)
        conn.execute("INSERT OR IGNORE INTO schema_meta (id, schema_version, applied_at) VALUES (1, ?, ?)",
                     (SCHEMA_VERSION, utc_now()))
        if not conn.execute("SELECT 1 FROM patient_profile WHERE patient_ref = ?", (patient_ref,)).fetchone():
            _seed(conn, patient_ref)
