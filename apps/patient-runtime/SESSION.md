# Session log: apps/patient-runtime

Running log for this app. Update it after every task (see `CLAUDE.md` owner notes). Newest entries go at the top of each section.

## Done
- **2026-11-07, A1 shipped for review.** Renamed the branch to `patient/feat/runtime-skeleton` to follow CONTRIBUTING.md, rebased on `origin/main` (now contract 2.0), adapted seeding, and committed as `feat(patient-runtime): add runtime skeleton with health endpoint` for a pull request into `main`.
- **2026-11-07, A1 runtime skeleton (contract 2.0).** FastAPI app on port 8001 with `GET /health`. On startup, `var/patient/patient.db` is created from `schema/patient.sql`. On first launch it is seeded with Walter's synthetic profile, consent, emergency organization (Lakeside `org_8f4d6a2e`) and two emergency contacts. `sentinel-contract` is a path dependency. Docstring-only modules: `stt`, `tts`, `rating`, `filter`, `extract`, `egress_gate`. 9 tests pass (`uv run pytest -q`). Live check: server listens on 127.0.0.1:8001 only, `/health` returns `{"status":"ok","schema_version":"2.0","patient_ref":"pt_4b82d0c6","profile_loaded":true}`, the CORS preflight from `localhost:5173` gets 200, and `scripts/check_ownership.sh` passes.

## Decisions
- **A1 scope follows the user's definition**: skeleton, database, health endpoint and empty modules. Scoping Doc 20.2 A1 also says "Ollama and faster-whisper running; a test call returns text and a model reply". That moves to A2 and A3, where those modules get built.
- **Seeding is part of A1**: the brief's Setup section puts it with database creation. Everything is seeded in one transaction, and only on first launch (when this patient's profile row is missing). A restart therefore never brings back a contact the patient removed and never overwrites a consent change. If `SENTINEL_ACTOR_ID` is not in `device_profiles`, nothing is seeded and `/health` shows `profile_loaded: false`.
- **Refuse a database from another schema version.** `CREATE TABLE IF NOT EXISTS` cannot upgrade old tables, so startup stops with a clear message telling you to delete the file. Reason: the brief forbids changing tables ourselves, and the data is synthetic.
- **`/health` checks local state only** and never calls the service. Reason: the brief says the network log may show only the listed `/v1/...` calls, all made through `egress_gate`.
- **`/health` returns only `patient_ref`**, the one ID shared off-device. It never returns `display_name`, `date_of_birth` or `phone`, and a test enforces this.
- **Schema location comes from `sentinel_contract.SCHEMA_DIR`** (which honours `SENTINEL_SCHEMA_DIR`), not a second path calculation of our own.
- **Project layout mirrors `apps/service`**: `[tool.uv] package = false` and pytest `pythonpath = ["."]`.
- **Import guard test**: no module except `egress_gate.py` may import `sentinel_contract.client`, `httpx`, `requests`, `urllib`, `urllib3`, `http.client`, `aiohttp`, `socket` or `websockets`. A planted offender confirmed the guard catches all three import styles.
- **Host 127.0.0.1** (uvicorn's default) so the runtime is not reachable from the network. CORS defaults to patient-web on port 5173 and can be changed with `PATIENT_ALLOWED_ORIGINS`.

## Errors and fixes
- **The rebase onto `main` broke seeding.** `main` had moved to contract 2.0 (PR #4): `doctor_id` and `share_doctor` were replaced by `care_org_id` and `share_care_team`, `emergency_org` and `emergency_contact` were added, and the schema version became 2.0. The tests failed with `table patient_profile has no column named doctor_id`. Fixed by rewriting the seeding for 2.0 (profile, consent, emergency organizations, contacts) and adding tests for it.
- **The local `var/patient/patient.db` still had the 1.0 tables** from the first live check. The new version guard refused it as intended. I deleted it (synthetic seed only, no check-ins or outbox rows) and the next start recreated it on 2.0.
- **`gh` CLI not installed**, so the pull request can't be opened from the terminal. Workaround: open it in the browser from the link `git push` prints. Install `gh` (`brew install gh`, then `gh auth login`) to open PRs from the terminal.
- **Wrong requirement IDs in module docstrings.** The first draft cited PV-02 on `filter` and PV-03 on `extract`. Section 12.2 has PV-02 = schema-only fields (`extract`) and PV-03 = delete audio after transcription (`stt`). Fixed after checking the scoping doc.
- **Warning, not an error:** `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated`. It comes from FastAPI's `TestClient` in current Starlette. No action taken; `apps/service` gets the same warning.

## Next
- **A1 pull request:** get CI green, squash-merge into `main` and delete the branch. Record the PR number here.
- **A2 voice loop:** faster-whisper in `stt`, Piper or a system voice in `tts`, and endpoints for patient-web. Install Ollama and a 3B model, and add the scoping doc's "test call returns text and a model reply" check.
- **Leakage evaluation in `evals/patient/`:** the brief requires it before every commit, but it does not exist yet. Build it with A3, using synthetic transcripts from `data/patient/`.
- **Ask the company owner** to add a `apps/patient-runtime` pytest job to `.github/workflows/ci.yml`. CI does not run these tests today, and that file is theirs.
- **patient-web skeleton** (Vite + React on port 5173) has not been started.
- **Contract 2.0 scope for later tasks** (brief and `docs/design/contract-2.0.md`): proxy reporters (`reporter`, wording about the patient), typed input (`input_mode`), the check-in schedule (`schedule.every_days`), one sealed envelope per consented organization (`POST /v1/care-envelopes`, `fetch_org_key`), and the consent update with emergency contacts.
