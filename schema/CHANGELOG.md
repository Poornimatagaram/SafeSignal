# Schema changelog

Owner: company-side lead. Version rules (Scoping Doc 26.11): 1.x adds optional fields; 2.0 breaks existing payloads. The service accepts the old and new version until the next integration run.

## 2.1 — 2026-11-07

Additive; payloads unchanged (`schema_version` stays `"2.0"`). Responses carry `X-Schema-Version: 2.1`.

- `company.sql`: `enrollment.synthetic` marks seeded patients, which the missed check-in scheduler skips (D-075).
- `demo_fixtures.json`: Priya consents to an emergency contact (911) and has `demo_missed_tail: 2`, so today's missed window raises a level 3 alert in the demo (D-076).

## 2.0 — 2026-11-07 (breaking)

Design: `docs/design/contract-2.0.md`. No teammate code depended on 1.x, so the service accepts only 2.0 (D-070).

- **Organizations replace doctors as recipients** (D-064): `relay.sql` adds `organization`, `org_member`, `org_key_grant`; `care_link` is per organization with `link_type` `care_team` or `emergency`; `doctor_inbox` becomes `care_inbox`; `doctor.clinic` removed. `doctor_envelope.json` → `care_envelope.json` (`org_id` replaces `doctor_id`).
- **Emergency access** (D-065): `relay_access_log`; alert type `emergency_access`.
- **Emergency contacts with consent** (D-067): `relay.sql` `emergency_contact`; `consent_update.json` 2.0 with `care_org_id`, `share_care_team`, `emergency_consent`, `emergency_org_ids`, `emergency_contacts` (no free text; empty without consent).
- **Escalation** (D-068): `alert.escalation_level` (1–3 for missed), `alert_delivery` records every notification.
- **Payloads** (D-066): company record adds `reporter`, `input_mode` and renames `consent.doctor` → `consent.care_team`; doctor payload adds `reporter`, `age_years`. All payloads `schema_version: "2.0"`.
- **Schedule** (D-069): `survey_config.json` requires `schedule.every_days`; `enrollment.start_date`.
- `patient.sql`: `care_org_id`, `care_org_public_key`, `reporter_default`, `emergency_org`, `emergency_contact`, consent `share_care_team`/`emergency_consent`, session `reporter`/`input_mode`, outbox `care_envelope`.
- `doctor_view.sql`: `dr_org_key`; `org_id`, `age_years`, `shared`, `reporter`, `escalation_level`; per-organization sync keys.
- `company.sql`: `checkin_record.consent_care_team`, `reporter`, `input_mode`.
- `demo_fixtures.json`: organizations, doctors, members, care and emergency links, emergency contacts (all fictional).

## 1.1 — 2026-11-07

Additive; payloads unchanged (their `schema_version` stays `"1.0"`). Responses now carry `X-Schema-Version: 1.1`.

- `relay.sql`: `alert.received_at` (service time). Doctor and caregiver alert responses include `received_at`, and `?since=` pages on it instead of the device's `created_at`, so alerts queued offline are never skipped (D-054).
- Server timestamps use microseconds (`YYYY-MM-DDTHH:MM:SS.ffffffZ`); `?since=` accepts any ISO 8601 UTC time and is normalized (D-054).
- New constant `CONTRACT_VERSION = "1.1"` in `sentinel_contract` and `@sentinel/contract`.

## 1.0 — 2026-11-07 (published for the H1 freeze; pending team sign-off)

Initial contract, from Scoping Doc Section 26 with these changes (see `docs/DECISIONS.md`):

- All payloads carry `schema_version: "1.0"`; `consent_update` adds `doctor_id` and `caregiver_id` (D-014).
- `term_code` is an enum of `terms.json` (D-015); device alerts are `severe` only (D-016).
- New: `survey_config.json` (D-017), `terms.json`, `openapi.json`.
- `company.sql`: `checkin_record.source` (D-003); `v_cohort_weekly` and `v_completion_weekly` redesigned (D-004); `checkin_window` UTC (D-005).
- `relay.sql`: caregiver link timestamps; nullable `doctor.public_key` (D-025).
- `patient.sql`: `patient_profile.drug_name` (D-010), `term_cache.known_for_program` (D-007).
- `doctor_view.sql`: `dr_timeline_entry.envelope_id`/`status`, `dr_key`, `dr_sync_state` (D-011).
- Added before sign-off (data only, no payload change): `demo_fixtures.json` (D-033).
