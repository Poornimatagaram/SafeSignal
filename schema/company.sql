-- Company DB (Sentinel service, company tenant). Scoping Doc 26.4.
-- Holds pseudonymized records only. Company endpoints read the v_* views and exports, never base tables directly.
-- Changes from the scoping doc are tagged with their decision ID (docs/DECISIONS.md).

CREATE TABLE IF NOT EXISTS schema_meta (
  id              INTEGER PRIMARY KEY CHECK (id = 1),
  schema_version  TEXT NOT NULL,
  applied_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS program (
  program_id      TEXT PRIMARY KEY,
  company_id      TEXT NOT NULL,
  drug_name       TEXT NOT NULL,
  created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cohort (
  cohort_id       TEXT PRIMARY KEY,
  program_id      TEXT NOT NULL REFERENCES program(program_id),
  drug_version    TEXT NOT NULL,
  label           TEXT NOT NULL,
  target_size     INTEGER
);

CREATE TABLE IF NOT EXISTS survey_config (
  config_id       TEXT PRIMARY KEY,
  cohort_id       TEXT NOT NULL REFERENCES cohort(cohort_id),
  version         INTEGER NOT NULL,
  questions_json  TEXT NOT NULL,                -- validates against schema/survey_config.json
  published_at    TEXT NOT NULL,
  published_by    TEXT NOT NULL,
  UNIQUE (cohort_id, version)
);

CREATE TABLE IF NOT EXISTS term_code (
  term_code       TEXT PRIMARY KEY,
  label_term      TEXT NOT NULL,
  everyday_words  TEXT NOT NULL,                -- JSON array
  drug_scope      TEXT NOT NULL,                -- JSON array of drug names (D-007: drives known_for_program)
  severe_trigger  INTEGER NOT NULL CHECK (severe_trigger IN (0,1))
);

CREATE TABLE IF NOT EXISTS enrollment (
  patient_ref     TEXT PRIMARY KEY,             -- pt_xxxxxxxx, no name or contact
  program_id      TEXT NOT NULL REFERENCES program(program_id),
  cohort_id       TEXT NOT NULL REFERENCES cohort(cohort_id),
  checkin_window  TEXT NOT NULL,                -- D-005: 'HH:MM-HH:MM' in UTC, e.g. '14:00-17:00'
  active          INTEGER NOT NULL CHECK (active IN (0,1))
);

CREATE TABLE IF NOT EXISTS checkin_record (
  record_id            TEXT PRIMARY KEY,        -- rec_xxxxxxxx
  schema_version       TEXT NOT NULL,
  patient_ref          TEXT NOT NULL REFERENCES enrollment(patient_ref),
  program_id           TEXT NOT NULL,
  cohort_id            TEXT NOT NULL,
  drug_version         TEXT NOT NULL,
  iso_week             TEXT NOT NULL,           -- 2026-W45
  status               TEXT NOT NULL CHECK (status IN ('completed','partial','missed')),
  unanswered_questions INTEGER NOT NULL,
  consent_doctor       INTEGER NOT NULL,
  consent_caregiver    INTEGER NOT NULL,
  payload_sha256       TEXT NOT NULL,           -- matches the patient's egress receipt
  source               TEXT NOT NULL DEFAULT 'device' CHECK (source IN ('device','scheduler')),  -- D-003
  received_at          TEXT NOT NULL            -- D-009: ops/scheduler only; never returned by a company endpoint
);

CREATE INDEX IF NOT EXISTS ix_record_patient_received ON checkin_record(patient_ref, received_at);
CREATE INDEX IF NOT EXISTS ix_record_program_week ON checkin_record(program_id, iso_week);

CREATE TABLE IF NOT EXISTS symptom_record (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  record_id          TEXT NOT NULL REFERENCES checkin_record(record_id),
  term_code          TEXT NOT NULL REFERENCES term_code(term_code),
  severity           TEXT NOT NULL CHECK (severity IN ('mild','moderate','severe')),
  onset              TEXT NOT NULL CHECK (onset IN ('today','1_3_days','4_7_days','over_7_days','unknown')),
  known_side_effect  INTEGER NOT NULL CHECK (known_side_effect IN (0,1)),
  possible_link_flag INTEGER NOT NULL CHECK (possible_link_flag IN (0,1))
);

CREATE INDEX IF NOT EXISTS ix_symptom_record ON symptom_record(record_id);

CREATE TABLE IF NOT EXISTS document (           -- document assistant (Could)
  doc_id          TEXT PRIMARY KEY,
  title           TEXT NOT NULL,
  source_url      TEXT NOT NULL,
  version         TEXT NOT NULL,
  approved_by     TEXT NOT NULL,
  approved_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS access_log (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_role      TEXT NOT NULL,
  actor_id        TEXT NOT NULL,
  action          TEXT NOT NULL,
  object          TEXT NOT NULL,
  at              TEXT NOT NULL
);

-- D-004: one row per cohort-week-term, with the denominator (patients who sent any record that cohort-week)
-- and a severe count. Rows where fewer than 5 patients reported the term are dropped; severe counts of 1-4
-- are returned as NULL (shown as "<5") so a small severe group cannot be singled out (NF-03).
DROP VIEW IF EXISTS v_cohort_weekly;
CREATE VIEW v_cohort_weekly AS
WITH reporting AS (
  SELECT program_id, cohort_id, drug_version, iso_week,
         COUNT(DISTINCT patient_ref) AS reporting_patients
  FROM checkin_record
  WHERE status IN ('completed','partial')
  GROUP BY program_id, cohort_id, drug_version, iso_week
),
term_counts AS (
  SELECT c.program_id, c.cohort_id, c.drug_version, c.iso_week, s.term_code,
         COUNT(DISTINCT c.patient_ref) AS patients,
         COUNT(DISTINCT CASE WHEN s.severity = 'severe' THEN c.patient_ref END) AS severe_patients
  FROM checkin_record c
  JOIN symptom_record s ON s.record_id = c.record_id
  GROUP BY c.program_id, c.cohort_id, c.drug_version, c.iso_week, s.term_code
)
SELECT t.program_id, t.cohort_id, t.drug_version, t.iso_week, t.term_code,
       t.patients,
       CASE WHEN t.severe_patients BETWEEN 1 AND 4 THEN NULL ELSE t.severe_patients END AS severe_patients,
       r.reporting_patients
FROM term_counts t
JOIN reporting r USING (program_id, cohort_id, drug_version, iso_week)
WHERE t.patients >= 5 AND r.reporting_patients >= 5;

-- Completion counts records (one per patient per day) and needs D-003 scheduler 'missed' records to be meaningful.
DROP VIEW IF EXISTS v_completion_weekly;
CREATE VIEW v_completion_weekly AS
SELECT program_id, cohort_id, drug_version, iso_week,
       COUNT(*) AS records,
       COUNT(DISTINCT patient_ref) AS patients,
       ROUND(1.0 * SUM(status = 'completed') / COUNT(*), 3) AS completion_rate,
       ROUND(1.0 * SUM(status = 'missed') / COUNT(*), 3) AS missed_rate
FROM checkin_record
GROUP BY program_id, cohort_id, drug_version, iso_week
HAVING COUNT(DISTINCT patient_ref) >= 5;
