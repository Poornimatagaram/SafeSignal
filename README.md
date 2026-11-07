# SafeSignal

Patients report side effects by voice; everything is processed on their device. Drug companies get minimal, structured side-effect data by drug version and cohort, and doctors get a consent-based symptom timeline before each visit. Built at HACK1984.

Code and packages use the working name **Sentinel** (`sentinel_*`, `@sentinel/*`); see `docs/DECISIONS.md` D-040.

Scope: `docs/scoping-document.md`. Decisions that override it: `docs/DECISIONS.md`.

**New here?** Open your app folder's `CLAUDE.md` (also `AGENTS.md`): it is the full brief for you and your coding agent. What the service does today: `docs/INTEGRATION_STATUS.md`. Demo IDs: `schema/demo_fixtures.json`.

## Layout and ownership

| Path | What | Owner | Port | Runtime data |
| --- | --- | --- | --- | --- |
| `schema/` | The contract: SQL, JSON Schemas, enums, terms, OpenAPI, examples | Company | — | — |
| `packages/contract-py/` | Python `sentinel_contract`: hashing, validation, `SentinelClient` | Company | — | — |
| `packages/contract-ts/` | npm `@sentinel/contract`: hashing, generated API types | Company | — | — |
| `apps/service/` | Python `sentinel_service`: company DB, relay store, API, scheduler | Company | 8000 | `var/service/company.db`, `var/service/relay.db` |
| `apps/company-web/` | Company portal (`@sentinel/company-web`) | Company | 5175 | — |
| `apps/patient-runtime/` | Python `sentinel_patient`: speech-to-text, model, filter, egress gate | Patient | 8001 | `var/patient/patient.db` |
| `apps/patient-web/` | Patient screen (`@sentinel/patient-web`) | Patient | 5173 | — |
| `apps/doctor-web/` | Doctor view (`@sentinel/doctor-web`) | Doctor | 5174 | IndexedDB `sentinel_doctor_view` |
| `evals/<area>/` | Leakage, F1 and re-ask evaluations, one subfolder per area | Each area | — | — |
| `data/<area>/` | Public data (openFDA cache) and synthetic generators, one subfolder per area | Each area | — | — |
| `scripts/` | Shared tooling, incl. `send_demo_envelope.py` (fake Walter device for doctor-web testing) | Company | — | — |
| `var/` | All runtime databases (gitignored) | — | — | — |

## Rules
- Edit only your own folders (`CODEOWNERS`). Contract changes go through the company owner (Scoping Doc 26.11).
- Log changes in your app's `CHANGELOG.md`; root `CHANGELOG.md` and `docs/` belong to the company owner.
- Each app is its own project with its own lockfile; there is no root lockfile. Use the contract as a path dependency:
  - Python: `[tool.uv.sources] sentinel-contract = { path = "../../packages/contract-py", editable = true }`
  - JS: `"@sentinel/contract": "file:../../packages/contract-ts"`
- Python packages are named `sentinel_<app>`; npm packages `@sentinel/<app>`; env vars `SENTINEL_*` (shared) or `SERVICE_*` / `PATIENT_*` / `DOCTOR_*` / `COMPANY_*`.

## Contributing
Branches, Conventional Commit messages and the pull-request flow are in `CONTRIBUTING.md`; CI enforces them. Folders never overlap, so following it means no merge conflicts.

## Run
```bash
cd apps/service && uv sync
uv run python -m sentinel_service.seed                       # once; safe to re-run
uv run uvicorn sentinel_service.main:app --port 8000         # API docs: http://127.0.0.1:8000/docs
scripts/reset_all.sh --seed                                  # from the repo root: wipe var/ and reseed
```

## Check
```bash
(cd packages/contract-py && uv run pytest -q)
(cd apps/service && uv run pytest -q)
npm test --prefix packages/contract-ts
```
