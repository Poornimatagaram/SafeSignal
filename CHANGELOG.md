# Changelog

All changes to the project, newest first. Schema-only history is also kept in `schema/CHANGELOG.md`. Decision IDs refer to `docs/DECISIONS.md`.

## 2026-11-08 — Session 015: company-side overview (branch `company/docs/company-side-overview`)

### Added
- `docs/company/company-side-overview.md`: what the company side does across the product and what is left.

## 2026-11-08 — Session 014: company portal (branch `company/feat/company-portal`)

### Added
- `apps/company-web`: Vite + React + TypeScript portal on port 5175, reading only `/v1/company/*` (contract 2.2). Tabs: Side effects (CO-01: share of reporting patients per term by cohort, week over week, change in percentage points, severe counts with `<5`, terms not on the FDA label flagged), Check-ins (CO-02: completion, missed, voice/text/mixed), Survey (CO-03: load the live version, edit, publish as `company_admin`, 422 field errors shown), Program & export (cohorts with source trial arms, public documents, CO-07 JSON/CSV export as `company_safety`). Program picker for all three programs. Every chart has a table view, legend and direct end labels; four-series palette validated in light and dark (D-084).
- CI: `company-web` job runs lint and build.
- `README.md`: portal run command.

## 2026-11-08 — Session 013: end-to-end check across personas (branch `company/test/e2e-check`)

### Added
- `scripts/e2e_check.py`: starts a throwaway service (temp data dir, free port, scheduler off), seeds it, and drives one check-in through every persona over real HTTP: patient device via `SentinelClient` (consent, record, one envelope per organization, severe alert), doctors as doctor-web does (personal and org keys, key grants, decrypt and hash check, ack, emergency access), caregiver alerts, company export and aggregates. 58 checks covering the automatable items of Scoping Doc 26.15 (D-083).
- CI: the end-to-end check runs in the `contract-and-service` job.
- `README.md`: the check is listed under Check and in the layout table.

## 2026-11-08 — Session 012: real-data seed, contract 2.2 (branch `company/feat/real-data-seed`)

### Added
- Fictional sponsor Halvaren Therapeutics (D-078).
- Two more programs: Rybrevant (MARIPOSA arms) and Beyfortus for infants (MELODY arms, parent-answered, parent survey) (D-081).
- `data/company/`:
  - ClinicalTrials.gov extracts and FDA label caches, with fetch scripts.
  - `trial_map.json`.
  - A PDF fetcher into gitignored `documents/` (D-080).
- Company endpoints `GET /v1/company/programs`, `/documents`, `/terms` and `/cohorts/{cohort_id}/survey`.
- Completion rows gain `voice_records`, `text_records` and `mixed_records`.
- Tests: `test_terms_labels.py`, plus real-rate, documents, migration and second-program tests.

### Changed
- Contract 2.2 (additive): `cohort_id` is a pattern, and there are 6 new term codes (D-079, D-081).
- `terms.json` `drug_scope` is verified against the FDA labels; this closes task C2.
- Seed: cohorts are sampled from real trial-arm rates. The invented story and openFDA weights are removed (D-053 superseded).
  - Walter's cohort_B is FLAURA's osimertinib arm; cohort labels name the real arms.
- `db.py` adds new nullable columns to existing databases (D-082).
- `.gitignore`: trial PDFs.
- Updated docs: `data/README.md`, integration status, briefs, schema changelog.

## 2026-11-08 — Session 011: CODEOWNERS handles (branch `company/chore/codeowners-handles`)

### Changed
- `CODEOWNERS`: patient folders → `@Poornimatagaram`, doctor folders → `@Swetha-Jalluri` (D-077; resolves D-046).

### Noted
- Teammates merged #7 (patient runtime skeleton), #8 and #9 (doctor web scaffold, org keys and per-org sync); all changes stayed inside their own folders. #10 (patient voice check-in) is open.

## 2026-11-08 — Session 010: missed check-in scheduler (branch `company/feat/missed-checkin-scheduler`)

### Added
- `apps/service/sentinel_service/scheduler.py`: due-day detection per cohort schedule and patient window, missed scheduler records, level 1–3 alerts with deliveries; background loop in the service (D-074).
- `apps/service/sentinel_service/demo.py`: `close-window` and `run-scheduler` demo controls (D-076).
- `apps/service/tests/test_scheduler.py` (9 tests); service suite 44 tests.
- Decisions D-074 to D-076.

### Changed
- Contract 2.1 (additive): `enrollment.synthetic`; `CONTRACT_VERSION` 2.1 in both contract packages; OpenAPI regenerated (D-075).
- `schema/demo_fixtures.json`: Priya's emergency contact (911) and `demo_missed_tail: 2` (D-076); seed honours both and flags synthetic enrollments.
- Tests read `CONTRACT_VERSION` instead of a hard-coded version.
- `docs/INTEGRATION_STATUS.md` and the doctor brief describe the live scheduler and demo controls.

## 2026-11-07 — Session 009: main brought up to date; merge workflow fixed (branch `company/docs/merge-workflow`)

### Merged into `main`
- #2 `feat(service): persist data in SQLite with seeded cohort history` (`59e2660`).
- #5 `docs(research): add dataset research and use-case requirements` (`0a8463d`), replacing #3, which GitHub closed when #2's branch was deleted.
- #4 `feat(service)!: move care records to organizations with emergency access` (`6ede5ba`).

### Changed
- `CONTRIBUTING.md`: keep `main` current by merging each PR when green; stacked-PR rules (retarget before the parent merges, update by merging `main`, no force-pushes) (D-072, D-073).
- `docs/company/CLAUDE.md`: company agents squash-merge their own green, conflict-free PRs (D-072).
- D-052 superseded by D-072; D-063's stacked-PR procedure superseded by D-073.

## 2026-11-07 — Session 008: contract 2.0, care teams, emergency access and escalation (branch `company/feat/contract-v2`, stacked on `company/docs/dataset-research`)

### Added
- `docs/design/contract-2.0.md`: design for organization-held records, emergency access, emergency contacts and escalation.
- Relay store: organizations, members, key grants, care and emergency links, emergency contacts, care inbox, alert deliveries, relay access log (D-064, D-065, D-067, D-068).
- Service: organization endpoints (members, keys, key grants, patients, envelopes, alerts, acks), `POST /v1/orgs/{org_id}/emergency-access`, `GET /v1/doctors/{id}/orgs`, `GET /v1/orgs/{org_id}/public-key`, `POST /v1/care-envelopes`; `escalation.py` (one recipient rule set).
- Seed: fictional organizations and doctors, care and emergency links, Walter's emergency contacts, proxy reporters (~15%), input modes, historical escalation levels with deliveries.
- Tests: contract-py 24 (fixture and consent rules), service 35 (doctor change, emergency access, consent, escalation levels, proxy reporting).
- Decisions D-064 to D-071.

### Changed
- Contract 2.0 (breaking, D-070): `care_envelope.json` replaces `doctor_envelope.json`; consent, company record, doctor payload, alert and survey schemas at 2.0; `relay.sql`, `patient.sql`, `doctor_view.sql`, `company.sql`, `enums.json`, `demo_fixtures.json`; `CONTRACT_VERSION` 2.0 in both contract packages; client `fetch_org_key` and `build_envelope(…, org_id, …)`; OpenAPI and TypeScript types regenerated.
- `scripts/send_demo_envelope.py`: sends to the care team and consented emergency organizations.
- Teammate briefs and `docs/INTEGRATION_STATUS.md` rewritten for 2.0.
- D-025 superseded by D-064; open parts of D-060, D-061 and D-062 resolved.

### Removed
- `/v1/doctor-envelopes`, `/v1/doctors/{id}/public-key` (patient read), `/v1/doctors/{id}/patients|envelopes|alerts` and the doctor ack.

## 2026-11-07 — Session 007: dataset research and new use-case requirements (branch `company/docs/dataset-research`, stacked on `company/feat/sqlite-store`)

### Added
- `docs/research/datasets.md`: public datasets for authentic demo data, verified against live APIs where possible; covers patients aged 0–100 with proxy reporting, licence rules for a public repository, and open questions (D-057).
- Decisions D-057 to D-063: data strategy, all ages with proxy reporting, configurable cadence and input methods, 3-step missed check-in escalation, multi-drug company with real trial documents, doctor and hospital record continuity, stacked PRs.
- `CONTRIBUTING.md`: stacked pull-request flow.

### Changed
- `.github/workflows/ci.yml`: runs on every pull request, not only PRs into `main` (D-063).

## 2026-11-07 — Session 006: Step 2, SQLite service and seed (branch `company/feat/sqlite-store`)

### Added
- `apps/service/sentinel_service/store.py`, `db.py`, `common.py`: SQLite store for `company.db` and `relay.db` (D-055).
- `apps/service/sentinel_service/seed.py`: `python -m sentinel_service.seed` with 1,000 enrollments and ~26,000 synthetic check-ins weighted by openFDA counts (D-053).
- `data/company/fetch_openfda.py` and `data/company/openfda/tagrisso_reaction_counts.json`; `data/README.md` source table (D-053).
- `scripts/reset_all.sh` (D-056).
- `GET /healthz`.
- Tests: `apps/service/tests/conftest.py`, `test_seed.py`; `test_stub_service.py` renamed `test_api.py` (27 service tests).
- Decisions D-053 to D-056.

### Changed
- Contract 1.1: `alert.received_at` in `relay.sql`; alert responses include `received_at`; `since` pages on it; microsecond server timestamps; `CONTRACT_VERSION` in both contract packages; `schema/openapi.json` and `api.d.ts` regenerated (D-054).
- `docs/INTEGRATION_STATUS.md` rewritten for the SQLite service; doctor and patient-runtime briefs, root and service READMEs updated.
- D-020 superseded by D-055.

### Removed
- `apps/service/sentinel_service/stub_store.py`.

## 2026-11-07 — Session 005: Conventional Commits and pull-request workflow (branch `company/chore/git-workflow`)

### Added
- `CONTRIBUTING.md`: branch naming `<area>/<type>/<description>`, Conventional Commits 1.0.0 with project scopes, pull-request flow, squash merging (D-048, D-049, D-050).
- `.github/workflows/ci.yml`: ownership, commit-message and PR-title checks; contract, service and TypeScript tests; generated-file sync check (D-051).
- `.github/pull_request_template.md` (D-050).
- `scripts/check_commits.sh`: local Conventional Commits check, also used by CI (D-051).
- Decisions D-048 to D-052.

### Changed
- `README.md`: the git workflow section now points to `CONTRIBUTING.md`.
- Root `CLAUDE.md`, `docs/company/CLAUDE.md`, `docs/briefs/*.md`: workflow is branch → Conventional Commits → checks → rebase → push → PR; company agents do not merge PRs unless asked (D-052).
- `scripts/check_ownership.sh`: messages updated for the new branch format.
- D-044 merge step superseded by D-049 and D-050.

### Removed
- Merged local branches `company/repo-structure`, `company/teammate-onboarding`, `company/shared-remote`, `company/log-push` (never pushed).

## 2026-11-07 — Session 004: shared GitHub repo (branch `company/shared-remote`)

### Added
- Remote `origin` = `https://github.com/Poornimatagaram/SafeSignal.git`; its initial commit merged (unrelated histories, no force push) (D-041). `main` pushed as fast-forward `4db7bc0..60ae124` and verified from a fresh clone.
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
