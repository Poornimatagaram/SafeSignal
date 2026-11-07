# Changelog

All changes to the project, newest first. Schema-only history is also kept in `schema/CHANGELOG.md`. Decision IDs refer to `docs/DECISIONS.md`.

## 2026-11-07 — Session 001: H1 handover package

### Added
- Repository setup: `git init` (branch `main`), `.gitignore` per 26.12 (databases, `.env`, keys, audio), `pyproject.toml` (Python 3.12, FastAPI, jsonschema, httpx, PyNaCl; pytest), `.python-version`, `uv.lock`.
- `CLAUDE.md`, `docs/DECISIONS.md` (D-001 to D-025), `docs/SESSION_LOG.md`, `CHANGELOG.md`.
- `schema/` contract v1.0:
  - SQL: `company.sql`, `relay.sql`, `patient.sql`, `doctor_view.sql` (all `IF NOT EXISTS`, with `schema_meta`).
  - JSON Schemas: `company_record.json`, `doctor_payload.json`, `doctor_envelope.json`, `alert_event.json`, `consent_update.json`, `survey_config.json`.
  - `enums.json`, `terms.json` (draft term list from 25.3, pending openFDA check), `openapi.json`.
  - `examples/`: one valid and one invalid example per payload, `hash_vectors.json` (8 vectors), `check_hash_vectors.mjs` (JS reference implementation).
  - `CHANGELOG.md`.
- `contract/`: shared canonical JSON, SHA-256 hashing and schema validation (D-019).
- `sentinel_service/`: FastAPI stub with every 26.7 endpoint, header auth, role and actor checks, body-free logging, `X-Schema-Version` header, CORS from `SENTINEL_ALLOWED_ORIGINS`, in-memory store enforcing validation, enrollment, consent and idempotency (D-020).
- `clients/sentinel_client.py` (patient side: fetch survey/terms/doctor key; send record/envelope/alert/consent; `build_envelope` sealed box; receipt field names) and `clients/sentinel_api.d.ts` (generated TypeScript types).
- `scripts/build_examples.py`, `scripts/export_openapi.py`.
- Tests: `tests/test_contract.py`, `tests/test_stub_service.py` (38 passing).

### Changed (relative to Scoping Doc Section 26)
- Company DB: `checkin_record.source` (D-003); views redesigned with denominators, severe counts and `missed_rate` (D-004); `checkin_window` in UTC (D-005); indexes added.
- Relay store: `caregiver_link.granted_at`/`revoked_at`; `doctor.public_key` nullable (D-025).
- Patient DB: `patient_profile.drug_name` (D-010); `term_cache.known_for_program` (D-007).
- Doctor view: `dr_timeline_entry.envelope_id`/`status`, `dr_key`, `dr_sync_state` (D-011).
- Payloads: unified `schema_version` and `consent_update` gains `doctor_id`/`caregiver_id` (D-014); `term_code` enum (D-015); device alerts `severe` only (D-016).

### Fixed
- Stub no longer seeds a placeholder doctor public key; `GET /v1/doctors/{id}/public-key` returns 404 until the doctor registers one (D-025). Test added.
