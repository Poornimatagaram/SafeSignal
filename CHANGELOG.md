# Changelog

All changes to the project, newest first. Schema-only history is also kept in `schema/CHANGELOG.md`. Decision IDs refer to `docs/DECISIONS.md`.

## 2026-11-07 — Session 004: shared GitHub repo (branch `company/shared-remote`)

### Added
- Remote `origin` = `https://github.com/Poornimatagaram/SafeSignal.git`; its initial commit merged (unrelated histories, no force push) (D-041).
- `LICENSE` (MIT, from the repo owner's initial commit).
- `.gitattributes`: LF line endings everywhere; generated files marked (D-042).
- `scripts/check_ownership.sh`: fails if a branch changes files outside its area's folders (D-044).
- README "Git workflow" section; `evals/<area>/` and `data/<area>/` split (D-044).
- Decisions D-040 to D-047 (D-045, D-046 open).

### Changed
- `README.md`: SafeSignal title and description from the shared repo above our content (D-040).
- `.gitignore`: merged with the shared repo's Python template; packaging folders anchored to the root so `src/lib/` and similar app code is never ignored (D-041).
- `AGENTS.md` (root and 3 teammate apps): plain pointer files instead of symlinks (D-043).
- `CODEOWNERS`: company entries → `@nkousik18`; added `evals/<area>`, `data/<area>`, `.gitignore`, `.gitattributes`, `LICENSE` (D-046).
- Root `CLAUDE.md`, `docs/company/CLAUDE.md` and every teammate brief: git workflow rule and "`scripts/check_ownership.sh` passes" in Done when.
- Teammate briefs moved `apps/<app>/CLAUDE.md` → `docs/briefs/<app>.md` (company-owned); each `apps/<app>/CLAUDE.md` is now the owner's file importing the brief with `@../../docs/briefs/<app>.md`; `AGENTS.md` points to both (D-047).

## 2026-11-07 — Session 003: teammate onboarding (branch `company/teammate-onboarding`)

### Added
- `schema/demo_fixtures.json`: demo IDs, enrollments, links, company users, on-device profiles (D-033); contract test for it.
- `docs/INTEGRATION_STATUS.md`: what the service does today, endpoint status, switch-over plan, how to run it for browser apps (D-036).
- `docs/company/CLAUDE.md`: company-owner instructions (moved out of the root file) (D-034).
- `apps/patient-runtime/CLAUDE.md`, `apps/patient-web/CLAUDE.md`, `apps/doctor-web/CLAUDE.md`: full agent briefs with corrected paths and "Changed from the scoping doc" lists; `AGENTS.md` links in each and at the root (D-034).
- `apps/<teammate app>/CHANGELOG.md` for each teammate app (D-035).
- `scripts/send_demo_envelope.py`: fake Walter device for doctor-web testing (D-037).
- Decisions D-033 to D-039 (D-039 open).

### Changed
- Root `CLAUDE.md`: now team-wide only (routing table, sources, shared rules) (D-034).
- `apps/service/sentinel_service/demo_ids.py` and `stub_store.py`: load demo IDs, enrollments and links from `schema/demo_fixtures.json` (D-033).
- `README.md`: "New here?" pointer, log rule, demo-envelope script; teammate app READMEs point to their `CLAUDE.md`, the status page and fixtures.
- `CODEOWNERS`: `docs/`, root `CLAUDE.md`, `AGENTS.md`, `CHANGELOG.md`, `README.md` owned by the company side (D-035).
- `schema/CHANGELOG.md`: notes `demo_fixtures.json` under 1.0.

## 2026-11-07 — Session 002: centralized repo structure (branch `company/repo-structure`)

### Added
- `README.md` (layout, ownership, ports, naming, run and check commands) and `CODEOWNERS` (placeholder handles) (D-026, D-027).
- `packages/contract-py/pyproject.toml` (`sentinel-contract`, hatchling) and `apps/service/pyproject.toml` with the contract as an editable path dependency; one lockfile per project (D-028).
- `packages/contract-ts/`: `package.json` (`@sentinel/contract`), `src/index.js` + `index.d.ts` (`canonical`, async `payloadSha256` on Web Crypto), `test/hash_vectors.test.mjs` (D-029).
- Ownership READMEs in `apps/company-web`, `apps/patient-runtime`, `apps/patient-web`, `apps/doctor-web`, `apps/service`, plus `evals/` and `data/` (D-030).
- `.gitignore`: `var/` for all runtime databases (D-031).
- Decisions D-026 to D-032.

### Changed
- Moved (history kept with `git mv`): scoping document → `docs/scoping-document.md`; `contract/` → `packages/contract-py/sentinel_contract/`; `clients/sentinel_client.py` → `sentinel_contract/client.py`; `clients/sentinel_api.d.ts` → `packages/contract-ts/src/api.d.ts`; `schema/examples/check_hash_vectors.mjs` → `packages/contract-ts/test/hash_vectors.test.mjs`; `sentinel_service/` → `apps/service/sentinel_service/`; tests split into `packages/contract-py/tests/` and `apps/service/tests/`; root `pyproject.toml`, `uv.lock`, `.python-version` → `apps/service/`.
- Imports now `from sentinel_contract import ...` and `from sentinel_contract.client import ...`; `SCHEMA_DIR` resolves from the repo root or `SENTINEL_SCHEMA_DIR`.
- `scripts/build_examples.py` and `scripts/export_openapi.py` run with `uv run --project ...` and no longer patch `sys.path` for the contract.
- `CLAUDE.md`: new paths, test commands and branch rule.
- D-012 superseded by D-027 (doctor UI belongs to the doctor teammate); D-019 paths superseded by D-029.

### Removed
- Root `contract/`, `clients/`, `tests/`, root `pyproject.toml`/`uv.lock`/`.python-version`.

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
