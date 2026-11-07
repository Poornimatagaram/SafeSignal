-- Relay store (Sentinel service; doctor and caregiver roles only). Scoping Doc 26.5.
-- Holds encrypted envelopes, consent links and alerts. The company role has no path to this file.
-- Server timestamps are UTC with microseconds ('YYYY-MM-DDTHH:MM:SS.ffffffZ') so they sort and page correctly (D-054).

CREATE TABLE IF NOT EXISTS schema_meta (
  id              INTEGER PRIMARY KEY CHECK (id = 1),
  schema_version  TEXT NOT NULL,
  applied_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS doctor (
  doctor_id       TEXT PRIMARY KEY,             -- dr_xxxxxxxx
  display_name    TEXT NOT NULL,
  clinic          TEXT,
  public_key      TEXT                          -- base64 X25519; NULL until the doctor's browser registers it
);

CREATE TABLE IF NOT EXISTS care_link (
  doctor_id       TEXT NOT NULL REFERENCES doctor(doctor_id),
  patient_ref     TEXT NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('active','revoked')),
  granted_at      TEXT NOT NULL,
  revoked_at      TEXT,
  PRIMARY KEY (doctor_id, patient_ref)
);

CREATE TABLE IF NOT EXISTS caregiver_link (
  caregiver_id    TEXT NOT NULL,                -- cg_xxxxxxxx
  patient_ref     TEXT NOT NULL,
  detail_level    TEXT NOT NULL CHECK (detail_level IN ('alerts_only','summary')),
  status          TEXT NOT NULL CHECK (status IN ('active','revoked')),
  granted_at      TEXT NOT NULL,
  revoked_at      TEXT,
  PRIMARY KEY (caregiver_id, patient_ref)
);

CREATE TABLE IF NOT EXISTS doctor_inbox (
  envelope_id     TEXT PRIMARY KEY,             -- env_xxxxxxxx
  doctor_id       TEXT NOT NULL REFERENCES doctor(doctor_id),
  patient_ref     TEXT NOT NULL,
  ciphertext      TEXT NOT NULL,                -- base64 sealed box; the service cannot decrypt it
  payload_sha256  TEXT NOT NULL,                -- hash of the plaintext, computed on the device
  received_at     TEXT NOT NULL,
  fetched_at      TEXT
);

CREATE INDEX IF NOT EXISTS ix_inbox_doctor_received ON doctor_inbox(doctor_id, received_at);

CREATE TABLE IF NOT EXISTS alert (
  alert_id         TEXT PRIMARY KEY,            -- alt_xxxxxxxx
  patient_ref      TEXT NOT NULL,
  alert_type       TEXT NOT NULL CHECK (alert_type IN ('missed','severe')),
  created_at       TEXT NOT NULL,                -- event time from the device (or scheduler)
  received_at      TEXT NOT NULL,                -- D-054: service time; `since` paging uses this, never created_at
  routed_doctor    INTEGER NOT NULL,
  routed_caregiver INTEGER NOT NULL,
  acknowledged_at  TEXT
);

CREATE INDEX IF NOT EXISTS ix_alert_received ON alert(received_at);
