# Patient runtime: agent instructions

@../../docs/briefs/patient-runtime.md

<!-- The brief above is maintained by the company owner; request changes from them. Everything below is yours to edit. -->

## Owner notes

### After every task
Update both files in this folder before you report the task done:
- `CHANGELOG.md`: what changed in this app, newest first, under a dated heading.
- `SESSION.md`: the running log. Add to **Done**, **Decisions** (with the reason), **Errors and fixes** (what broke and how it was fixed), and rewrite **Next** so it is current.

### Edit scope
Only `apps/patient-runtime/`, `apps/patient-web/`, `evals/patient/` and `data/patient/`. Never root files, `schema/` or `docs/`; ask the company owner for those. Synthetic data only.

### Run and check
```bash
cd apps/patient-runtime && uv sync
uv run uvicorn sentinel_patient.main:app --port 8001   # binds 127.0.0.1; creates var/patient/patient.db
uv run pytest -q
```
