# Patient runtime (on-device)

- **Owner:** Patient side (see `CODEOWNERS`)
- **Package name:** `sentinel_patient`
- **Port:** 8001
- **Runtime data:** `var/patient/patient.db` from `schema/patient.sql`
- **Contract:** read `schema/`; never edit it. Hashing and types come from `packages/` (see the root README).
- **Agent instructions:** `CLAUDE.md` in this folder; it imports the brief `docs/briefs/patient-runtime.md` (company-maintained) and holds your own notes. `AGENTS.md` points to both.
- **Service status:** `docs/INTEGRATION_STATUS.md` · **Demo IDs:** `schema/demo_fixtures.json`
- **Original brief:** Scoping Doc 26.14, Patient layer brief. Paths in that brief map to this repo as: `device_runtime/` → `apps/patient-runtime/`; `clients/sentinel_client.py` → `from sentinel_contract.client import SentinelClient`; `device_runtime/egress_gate.py` → `apps/patient-runtime/sentinel_patient/egress_gate.py`.

Structure inside this folder is up to its owner.

## Run
```bash
cd apps/patient-runtime && uv sync
uv run uvicorn sentinel_patient.main:app --port 8001   # http://127.0.0.1:8001/health
```
Settings: `SENTINEL_ACTOR_ID` (default Walter `pt_4b82d0c6`), `SENTINEL_BASE_URL` (default `http://127.0.0.1:8000`), `PATIENT_DB_PATH` (default `var/patient/patient.db`), `PATIENT_ALLOWED_ORIGINS` (default patient-web on port 5173).

## Check
```bash
cd apps/patient-runtime && uv run pytest -q
```
