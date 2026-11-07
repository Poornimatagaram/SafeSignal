# Schema changelog

Owner: company-side lead. Version rules (Scoping Doc 26.11): 1.x adds optional fields; 2.0 breaks existing payloads. The service accepts the old and new version until the next integration run.

## 1.0 — 2026-11-07 (published for the H1 freeze; pending team sign-off)

Initial contract, from Scoping Doc Section 26 with these changes (see `docs/DECISIONS.md`):

- All payloads carry `schema_version: "1.0"`; `consent_update` adds `doctor_id` and `caregiver_id` (D-014).
- `term_code` is an enum of `terms.json` (D-015); device alerts are `severe` only (D-016).
- New: `survey_config.json` (D-017), `terms.json`, `openapi.json`.
- `company.sql`: `checkin_record.source` (D-003); `v_cohort_weekly` and `v_completion_weekly` redesigned (D-004); `checkin_window` UTC (D-005).
- `relay.sql`: caregiver link timestamps; nullable `doctor.public_key` (D-025).
- `patient.sql`: `patient_profile.drug_name` (D-010), `term_cache.known_for_program` (D-007).
- `doctor_view.sql`: `dr_timeline_entry.envelope_id`/`status`, `dr_key`, `dr_sync_state` (D-011).
