-- Doctor DB: IndexedDB stores in the doctor's browser (decrypted data; never sent back). Scoping Doc 26.5; contract 2.0.
-- Written as SQL for reference; the doctor web app creates one IndexedDB object store per table in a database
-- named 'sentinel_doctor_view', keyed by the PRIMARY KEY column, with the same field names.
-- A doctor may belong to several organizations; every record carries the org_id it came from (D-064).

CREATE TABLE IF NOT EXISTS dr_patient (
  patient_ref     TEXT PRIMARY KEY,
  org_id          TEXT NOT NULL,                -- the care-team organization (or emergency org) it was read through
  display_name    TEXT NOT NULL,
  age_years       INTEGER NOT NULL,             -- D-066
  drug_name       TEXT NOT NULL,
  drug_version    TEXT NOT NULL,
  last_checkin    TEXT,
  shared          INTEGER NOT NULL DEFAULT 1    -- 0 after the patient revokes the care link (D-038)
);

CREATE TABLE IF NOT EXISTS dr_timeline_entry (
  entry_id           TEXT PRIMARY KEY,          -- '<envelope_id>:<term_code>'
  patient_ref        TEXT NOT NULL REFERENCES dr_patient(patient_ref),
  envelope_id        TEXT NOT NULL,             -- D-011: traceability back to the envelope
  checkin_date       TEXT NOT NULL,             -- exact date, care team only
  status             TEXT NOT NULL CHECK (status IN ('completed','partial','missed')),
  reporter           TEXT NOT NULL,             -- D-066: self, parent, caregiver or other
  term_code          TEXT NOT NULL,
  severity           TEXT NOT NULL,
  onset              TEXT NOT NULL,
  known_side_effect  INTEGER NOT NULL,
  possible_link_flag INTEGER NOT NULL,
  trend              TEXT NOT NULL CHECK (trend IN ('better','same','worse','unknown'))
);

CREATE TABLE IF NOT EXISTS dr_alert (
  alert_id         TEXT PRIMARY KEY,
  org_id           TEXT NOT NULL,
  patient_ref      TEXT NOT NULL,
  alert_type       TEXT NOT NULL,
  escalation_level INTEGER,                     -- D-068: 1, 2 or 3 for missed check-ins
  created_at       TEXT NOT NULL,
  received_at      TEXT NOT NULL,
  seen_at          TEXT
);

-- The doctor's personal key pair (receives key grants). NEVER exported, logged or transmitted.
CREATE TABLE IF NOT EXISTS dr_key (
  doctor_id       TEXT PRIMARY KEY,
  public_key      TEXT NOT NULL,
  private_key     TEXT NOT NULL,
  created_at      TEXT NOT NULL
);

-- D-064: organization care-team keys, unwrapped from key grants in this browser only. NEVER exported or transmitted.
CREATE TABLE IF NOT EXISTS dr_org_key (
  org_id          TEXT PRIMARY KEY,
  public_key      TEXT NOT NULL,
  private_key     TEXT NOT NULL,
  obtained_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dr_sync_state (
  sync_key        TEXT PRIMARY KEY,             -- '<org_id>:envelopes' or '<org_id>:alerts'
  since           TEXT NOT NULL                 -- newest received_at seen (D-054)
);
