# Changelog: apps/patient-runtime

Changes in this app, newest first. Owned by this app's owner (root `CLAUDE.md`).

## 2026-11-07: Task A1, runtime skeleton (branch `patient/feat/runtime-skeleton`)

### Added
- `pyproject.toml` and `uv.lock`: package `sentinel_patient` with FastAPI, uvicorn and `sentinel-contract` as an editable path dependency on `../../packages/contract-py`.
- `sentinel_patient/main.py`: FastAPI app for port 8001; `GET /health` reports `status`, `schema_version`, `patient_ref` and `profile_loaded` from local state only (no network). CORS allows patient-web (`localhost:5173`, `127.0.0.1:5173`).
- `sentinel_patient/db.py` (contract 2.0): creates `var/patient/patient.db` on startup by applying `schema/patient.sql` (safe to re-run) and writes `schema_meta`. On first launch only, seeds the profile, consent, emergency organizations and emergency contacts (labels kept local) from `schema/demo_fixtures.json`; Walter `pt_4b82d0c6` is the default. Refuses to start on a database created for another schema version.
- `sentinel_patient/config.py`: settings from `SENTINEL_ACTOR_ID`, `SENTINEL_BASE_URL`, `PATIENT_DB_PATH`, `PATIENT_ALLOWED_ORIGINS`.
- Placeholder modules (docstring only): `stt`, `tts`, `rating`, `filter`, `extract`, `egress_gate`.
- `tests/test_runtime.py`: health, schema tables, seeding (with and without emergency consent), re-run without reseeding, schema-version guard, CORS, and a guard that only `egress_gate.py` imports `sentinel_contract.client` or any HTTP library.
- `SESSION.md`: running session log.

### Changed
- `CLAUDE.md` owner notes: update `CHANGELOG.md` and `SESSION.md` after every task; edit scope; run and check commands.
- `README.md`: run and check commands.
