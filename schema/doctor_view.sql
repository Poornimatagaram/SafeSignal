-- Doctor DB: IndexedDB stores in the doctor's browser (decrypted data; never sent back). Scoping Doc 26.5.
-- Written as SQL for reference; the doctor web app creates one IndexedDB object store per table,
-- keyed by the PRIMARY KEY column, with the same field names.

CREATE TABLE IF NOT EXISTS dr_patient (
  patient_ref     TEXT PRIMARY KEY,
  display_name    TEXT NOT NULL,
  drug_name       TEXT NOT NULL,
  drug_version    TEXT NOT NULL,
  last_checkin    TEXT
);

CREATE TABLE IF NOT EXISTS dr_timeline_entry (
  entry_id           TEXT PRIMARY KEY,          -- '<envelope_id>:<term_code>'
  patient_ref        TEXT NOT NULL REFERENCES dr_patient(patient_ref),
  envelope_id        TEXT NOT NULL,             -- D-011: traceability back to the envelope
  checkin_date       TEXT NOT NULL,             -- exact date, doctor only
  status             TEXT NOT NULL CHECK (status IN ('completed','partial','missed')),
  term_code          TEXT NOT NULL,
  severity           TEXT NOT NULL,
  onset              TEXT NOT NULL,
  known_side_effect  INTEGER NOT NULL,
  possible_link_flag INTEGER NOT NULL,
  trend              TEXT NOT NULL CHECK (trend IN ('better','same','worse','unknown'))
);

CREATE TABLE IF NOT EXISTS dr_alert (
  alert_id        TEXT PRIMARY KEY,
  patient_ref     TEXT NOT NULL,
  alert_type      TEXT NOT NULL,
  created_at      TEXT NOT NULL,
  seen_at         TEXT
);

-- D-011: the doctor's key pair and sync cursors also live in the browser only.
CREATE TABLE IF NOT EXISTS dr_key (
  doctor_id       TEXT PRIMARY KEY,
  public_key      TEXT NOT NULL,                -- base64; registered with the service
  private_key     TEXT NOT NULL,                -- base64; NEVER exported, logged or transmitted
  created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dr_sync_state (
  stream          TEXT PRIMARY KEY CHECK (stream IN ('envelopes','alerts')),
  since           TEXT NOT NULL                 -- newest received_at / created_at seen (Scoping Doc 26.13)
);
