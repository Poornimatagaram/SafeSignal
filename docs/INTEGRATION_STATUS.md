# Integration Status

What the Sentinel service (`apps/service`) actually does today. Maintained by the company owner only; check it before debugging anything that touches the service.

**Last updated:** 2026-11-07 · Session 003 · schema `1.0`

## Current mode: in-memory stub

- **Data resets on every restart.** Envelopes, alerts, consent changes and registered doctor keys are lost.
- **Enrolled:** Walter `pt_4b82d0c6` (cohort_B, v2) and Priya `pt_9c1d2e3f` (cohort_A, v1) only. Records for anyone else get 403. IDs: `schema/demo_fixtures.json`.
- **Seeded:** Dr. Shah `dr_3a7f10b2`, linked to both patients, with **no public key** until the doctor web app registers one. Anna `cg_7e21c9a4` is linked to Walter (alerts only). One `missed` alert exists for Priya.
- **Company views** return fixed synthetic numbers (4 cohorts × 4 weeks), not aggregates of records you send.
- **Rules already enforced exactly as the real service will:** schema validation (422 names the field), role and actor checks (401/403), enrollment match (D-006), care-link and consent checks, idempotency (200 same ID and hash, 409 different), `since` paging.

## Endpoints

| Endpoint | Status | Notes |
| --- | --- | --- |
| `GET /v1/survey`, `GET /v1/terms` | Stub (real rules) | Same survey for all cohorts until the company publishes a new version |
| `POST /v1/records` | Stub (real rules) | Stored in memory; not yet aggregated into company views |
| `POST /v1/doctor-envelopes` | Stub (real rules) | 403 without an active care link |
| `POST /v1/alerts` | Stub (real rules) | `severe` only from devices |
| `PUT /v1/consent/{patient_ref}` | Stub (real rules) | Revoking stops new envelopes and hides undelivered ones (D-013) |
| `PUT`/`GET /v1/doctors/{id}/public-key` | Stub (real rules) | GET is 404 until the key is registered (D-025) |
| `GET /v1/doctors/{id}/patients`, `/envelopes`, `/alerts`; `POST .../ack` | Stub (real rules) | |
| `GET /v1/caregivers/{id}/alerts` | Stub (real rules) | `summary` detail level is the same as `alerts_only` (D-008 open) |
| `/v1/company/*` | Stub (fixed data) | |
| Missed check-in scheduler | **Not built** | Only the one seeded missed alert exists |

## Switch-over plan (Scoping Doc 26.11)

| When | Becomes real | What teammates do |
| --- | --- | --- |
| H3 | SQLite store and seed: records, survey, terms; company views aggregate real records | Nothing changes in your code; data now survives restarts |
| H5 | Relay endpoints on SQLite, missed check-in scheduler | Doctor and caregiver views see scheduler alerts within 1 minute |
| H6 | Integration run on the team hotspot | Run the Scoping Doc 26.15 checklist together |

## Running it for your app

```bash
cd apps/service && uv sync
SENTINEL_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174,http://localhost:5175 \
  uv run uvicorn sentinel_service.main:app --port 8000
```

- Browser apps need their origin in `SENTINEL_ALLOWED_ORIGINS`; without it the service sends no CORS headers and browser calls fail.
- Doctor side, to get test data before the patient runtime exists: register your key from the doctor web app, then run `uv run --project packages/contract-py python scripts/send_demo_envelope.py --alert` from the repo root.

## Reporting a problem

A 422 response names the failing field; check your payload against `schema/` and `schema/examples/` first. If the contract itself looks wrong, ask the company owner; do not work around it.
