-- Patient DB (on the patient's device). Scoping Doc 26.3.
-- Applied by the device runtime on first launch. Columns marked "local only" can never appear in the outbox. Contract 2.0.

CREATE TABLE IF NOT EXISTS schema_meta (
  id              INTEGER PRIMARY KEY CHECK (id = 1),
  schema_version  TEXT NOT NULL,
  applied_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patient_profile (
  patient_ref       TEXT PRIMARY KEY,           -- pt_xxxxxxxx, the only ID shared off-device
  display_name      TEXT NOT NULL,              -- local only (also inside encrypted doctor payloads)
  date_of_birth     TEXT,                       -- local only
  phone             TEXT,                       -- local only
  program_id        TEXT NOT NULL,
  cohort_id         TEXT NOT NULL,
  drug_name         TEXT NOT NULL,              -- D-010: needed for the doctor payload
  drug_version      TEXT NOT NULL,
  care_org_id       TEXT,                       -- org_xxxxxxxx: the hospital or clinic that holds the record (D-064)
  care_org_public_key TEXT,                     -- envelopes are sealed to this key
  reporter_default  TEXT NOT NULL DEFAULT 'self' CHECK (reporter_default IN ('self','parent','caregiver','other')),  -- D-058
  caregiver_id      TEXT,                       -- cg_xxxxxxxx
  enrolled_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS consent (
  consent_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  share_care_team   INTEGER NOT NULL CHECK (share_care_team IN (0,1)),
  emergency_consent INTEGER NOT NULL CHECK (emergency_consent IN (0,1)),  -- D-067
  share_caregiver   INTEGER NOT NULL CHECK (share_caregiver IN (0,1)),
  caregiver_detail  TEXT NOT NULL CHECK (caregiver_detail IN ('alerts_only','summary')),
  updated_at        TEXT NOT NULL
);

-- D-065: hospitals the patient chose for emergencies; envelopes are also sealed to these, released only via emergency access.
CREATE TABLE IF NOT EXISTS emergency_org (
  org_id            TEXT PRIMARY KEY,
  public_key        TEXT
);

-- D-067: user-defined emergency contacts. display_label stays on the device; the rest is shared only with consent.
CREATE TABLE IF NOT EXISTS emergency_contact (
  contact_id        TEXT PRIMARY KEY,           -- ec_xxxxxxxx
  contact_type      TEXT NOT NULL CHECK (contact_type IN ('emergency_service','hospital','person')),
  phone             TEXT NOT NULL,
  org_id            TEXT,
  priority          INTEGER NOT NULL CHECK (priority BETWEEN 1 AND 3),
  display_label     TEXT                        -- local only, e.g. "Anna (daughter)"
);

CREATE TABLE IF NOT EXISTS survey_cache (
  config_id         TEXT PRIMARY KEY,
  cohort_id         TEXT NOT NULL,
  version           INTEGER NOT NULL,
  questions_json    TEXT NOT NULL,              -- schedule, questions and re-ask wordings (schema/survey_config.json)
  fetched_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS term_cache (
  term_code         TEXT PRIMARY KEY,           -- SE_RASH, ...
  label_term        TEXT NOT NULL,
  everyday_words    TEXT NOT NULL,              -- JSON array
  severe_trigger    INTEGER NOT NULL CHECK (severe_trigger IN (0,1)),
  known_for_program INTEGER NOT NULL CHECK (known_for_program IN (0,1))  -- D-007: sets known_side_effect
);

CREATE TABLE IF NOT EXISTS checkin_session (
  session_id        TEXT PRIMARY KEY,
  config_id         TEXT NOT NULL REFERENCES survey_cache(config_id),
  started_at        TEXT NOT NULL,
  ended_at          TEXT,
  status            TEXT NOT NULL CHECK (status IN ('completed','partial','missed')),
  reporter          TEXT NOT NULL DEFAULT 'self' CHECK (reporter IN ('self','parent','caregiver','other')),  -- D-066
  input_mode        TEXT NOT NULL DEFAULT 'voice' CHECK (input_mode IN ('voice','text','mixed'))             -- D-066
);

CREATE TABLE IF NOT EXISTS answer_turn (
  turn_id           INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id        TEXT NOT NULL REFERENCES checkin_session(session_id),
  question_id       TEXT NOT NULL,
  attempt           INTEGER NOT NULL CHECK (attempt BETWEEN 0 AND 2),  -- 0 = first ask, 1-2 = re-asks
  prompt_text       TEXT NOT NULL,
  transcript_text   TEXT,                       -- local only
  rating            TEXT CHECK (rating IN ('complete','partial','off_topic','rambling','no_answer')),
  created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS symptom_event (
  event_id           TEXT PRIMARY KEY,
  session_id         TEXT NOT NULL REFERENCES checkin_session(session_id),
  term_code          TEXT NOT NULL REFERENCES term_cache(term_code),
  severity           TEXT NOT NULL CHECK (severity IN ('mild','moderate','severe')),
  onset              TEXT NOT NULL CHECK (onset IN ('today','1_3_days','4_7_days','over_7_days','unknown')),
  known_side_effect  INTEGER NOT NULL CHECK (known_side_effect IN (0,1)),
  possible_link_flag INTEGER NOT NULL CHECK (possible_link_flag IN (0,1)),
  patient_words      TEXT,                      -- local only
  created_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exposure_event (
  exposure_id       TEXT PRIMARY KEY,
  description       TEXT NOT NULL,              -- local only, e.g. new nail product
  started_on        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outbox (
  outbox_id         TEXT PRIMARY KEY,
  session_id        TEXT REFERENCES checkin_session(session_id),
  destination       TEXT NOT NULL CHECK (destination IN ('company_record','care_envelope','alert','consent')),
  payload           TEXT NOT NULL,              -- schema-valid JSON or encrypted envelope
  payload_sha256    TEXT NOT NULL,
  status            TEXT NOT NULL CHECK (status IN ('queued','sent','failed')),
  created_at        TEXT NOT NULL,
  sent_at           TEXT
);

CREATE TABLE IF NOT EXISTS egress_log (
  log_id            INTEGER PRIMARY KEY AUTOINCREMENT,
  outbox_id         TEXT REFERENCES outbox(outbox_id),   -- NULL for a configuration fetch (2.3)
  kind              TEXT NOT NULL DEFAULT 'send' CHECK (kind IN ('send','config_fetch')),
  method            TEXT NOT NULL,
  url               TEXT NOT NULL,
  fields_sent       TEXT NOT NULL,              -- JSON list of field names, shown on the receipt
  payload_sha256    TEXT NOT NULL,
  response_code     INTEGER,
  sent_at           TEXT NOT NULL
);
