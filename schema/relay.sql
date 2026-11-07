-- Relay store (Sentinel service; care-team, doctor and caregiver roles only). Scoping Doc 26.5; contract 2.0.
-- Holds sealed envelopes, consent links, emergency contacts, alerts and their deliveries.
-- The company role has no path to this file. The service cannot open envelopes or key grants.
-- Server timestamps are UTC with microseconds ('YYYY-MM-DDTHH:MM:SS.ffffffZ') so they sort and page correctly (D-054).
-- Design: docs/design/contract-2.0.md

CREATE TABLE IF NOT EXISTS schema_meta (
  id              INTEGER PRIMARY KEY CHECK (id = 1),
  schema_version  TEXT NOT NULL,
  applied_at      TEXT NOT NULL
);

-- D-064: hospitals and clinics own the record; patients consent to an organization, not to one doctor.
CREATE TABLE IF NOT EXISTS organization (
  org_id          TEXT PRIMARY KEY,             -- org_xxxxxxxx
  display_name    TEXT NOT NULL,
  org_type        TEXT NOT NULL CHECK (org_type IN ('hospital','clinic')),
  public_key      TEXT,                         -- base64 X25519 care-team key; NULL until the org admin registers it
  created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS doctor (
  doctor_id       TEXT PRIMARY KEY,             -- dr_xxxxxxxx
  display_name    TEXT NOT NULL,
  public_key      TEXT                          -- base64 X25519 personal key; used only to receive key grants
);

CREATE TABLE IF NOT EXISTS org_member (
  org_id          TEXT NOT NULL REFERENCES organization(org_id),
  doctor_id       TEXT NOT NULL REFERENCES doctor(doctor_id),
  role            TEXT NOT NULL CHECK (role IN ('attending','on_call','admin')),
  status          TEXT NOT NULL CHECK (status IN ('active','revoked')),
  granted_at      TEXT NOT NULL,
  revoked_at      TEXT,
  PRIMARY KEY (org_id, doctor_id)
);

-- The org private key sealed to a member doctor's personal key. Opaque to the service.
CREATE TABLE IF NOT EXISTS org_key_grant (
  org_id          TEXT NOT NULL REFERENCES organization(org_id),
  doctor_id       TEXT NOT NULL REFERENCES doctor(doctor_id),
  wrapped_key     TEXT NOT NULL,                -- base64 sealed box of the org private key
  granted_by      TEXT NOT NULL REFERENCES doctor(doctor_id),
  granted_at      TEXT NOT NULL,
  PRIMARY KEY (org_id, doctor_id)
);

-- link_type 'care_team': routine access by members. 'emergency': envelopes released only via emergency access (D-065).
CREATE TABLE IF NOT EXISTS care_link (
  org_id          TEXT NOT NULL REFERENCES organization(org_id),
  patient_ref     TEXT NOT NULL,
  link_type       TEXT NOT NULL CHECK (link_type IN ('care_team','emergency')),
  status          TEXT NOT NULL CHECK (status IN ('active','revoked')),
  granted_at      TEXT NOT NULL,
  revoked_at      TEXT,
  PRIMARY KEY (org_id, patient_ref)
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

-- D-067: user-defined at setup, with consent; used only by escalation level 3; never logged; never in company.db.
CREATE TABLE IF NOT EXISTS emergency_contact (
  contact_id      TEXT PRIMARY KEY,             -- ec_xxxxxxxx
  patient_ref     TEXT NOT NULL,
  contact_type    TEXT NOT NULL CHECK (contact_type IN ('emergency_service','hospital','person')),
  phone           TEXT NOT NULL,                -- E.164 or a short emergency number such as 911
  org_id          TEXT REFERENCES organization(org_id),
  priority        INTEGER NOT NULL CHECK (priority BETWEEN 1 AND 3),
  consented_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_contact_patient ON emergency_contact(patient_ref);

CREATE TABLE IF NOT EXISTS care_inbox (
  envelope_id     TEXT PRIMARY KEY,             -- env_xxxxxxxx (one per recipient organization)
  org_id          TEXT NOT NULL REFERENCES organization(org_id),
  patient_ref     TEXT NOT NULL,
  ciphertext      TEXT NOT NULL,                -- base64 sealed box to the org key; the service cannot decrypt it
  payload_sha256  TEXT NOT NULL,                -- hash of the plaintext, computed on the device
  received_at     TEXT NOT NULL,
  fetched_at      TEXT                          -- first fetch by any member
);

CREATE INDEX IF NOT EXISTS ix_inbox_org_received ON care_inbox(org_id, received_at);

CREATE TABLE IF NOT EXISTS alert (
  alert_id         TEXT PRIMARY KEY,            -- alt_xxxxxxxx
  patient_ref      TEXT NOT NULL,
  alert_type       TEXT NOT NULL CHECK (alert_type IN ('missed','severe','emergency_access')),  -- D-065: emergency access notifies too
  escalation_level INTEGER CHECK (escalation_level BETWEEN 1 AND 3),  -- D-068: set for 'missed', NULL for 'severe'
  created_at       TEXT NOT NULL,               -- event time from the device (or scheduler)
  received_at      TEXT NOT NULL,               -- D-054: service time; `since` paging uses this
  acknowledged_at  TEXT,
  CHECK ((alert_type = 'missed') = (escalation_level IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS ix_alert_received ON alert(received_at);

-- D-068: one row per recipient notified, so the hospital keeps a record of who was told, regardless of who is on duty.
CREATE TABLE IF NOT EXISTS alert_delivery (
  alert_id        TEXT NOT NULL REFERENCES alert(alert_id),
  recipient_type  TEXT NOT NULL CHECK (recipient_type IN ('patient','caregiver','care_team','emergency_contact')),
  recipient_id    TEXT NOT NULL,                -- pt_, cg_, org_ or ec_ ID
  channel         TEXT NOT NULL CHECK (channel IN ('in_app')),  -- real calls and texts are v1 (Scoping Doc 11.1)
  delivered_at    TEXT NOT NULL,
  PRIMARY KEY (alert_id, recipient_type, recipient_id)
);

-- D-065: every relay read by a doctor, and every emergency access with its coded reason.
CREATE TABLE IF NOT EXISTS relay_access_log (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_role      TEXT NOT NULL,
  actor_id        TEXT NOT NULL,
  org_id          TEXT,
  action          TEXT NOT NULL,
  patient_ref     TEXT,
  reason          TEXT,
  at              TEXT NOT NULL
);
