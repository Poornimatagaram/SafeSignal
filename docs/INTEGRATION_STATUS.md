# Integration Status

What the Sentinel service (`apps/service`) actually does today. Maintained by the company owner only; check it before debugging anything that touches the service.

**Last updated:** 2026-11-07 · Session 006 · contract `1.1` (payload `schema_version` stays `1.0`)

## Current mode: SQLite (H3 switch-over done)

- **Data persists** in `var/service/company.db` and `var/service/relay.db` (gitignored) across restarts. Wipe with `scripts/reset_all.sh`.
- **Seeded by** `python -m sentinel_service.seed` (safe to re-run; `--reset` starts over):
  - Program `prog_demo_01` (Tagrisso), cohorts A–D = v1–v4, term list, survey v1 per cohort.
  - 1,000 enrollments: Walter `pt_4b82d0c6` (cohort_B), Priya `pt_9c1d2e3f` (cohort_A) and 998 synthetic patients. IDs: `schema/demo_fixtures.json`.
  - About 26,000 daily check-ins from Monday of 2026-W42 through **yesterday**. Today is empty, so the live check-in is today's record.
  - Dr. Shah `dr_3a7f10b2` linked to Walter and Priya with **no public key** until the doctor web app registers one. Anna `cg_7e21c9a4` linked to Walter (alerts only).
  - A few historical relay alerts (missed or severe) for Walter and Priya only.
- **Company views aggregate real records**, including records sent by the patient runtime. The synthetic story: rash and nail changes rise week over week in cohort_B (v2); fewer GI events in cohort_C; more fatigue in cohort_D.
- **Rules enforced:** schema validation (422 names the field), role and actor checks (401/403), enrollment match (D-006), care-link and consent checks, idempotency (200 same ID and hash, 409 different), `since` paging.

## Changes in contract 1.1 that affect you

- **Doctor and caregiver alerts** now include `received_at` (service time). Use it as your `since` cursor for alerts, as you already do for envelopes. `created_at` is when the event happened on the device and can be older (offline queue) (D-054).
- **Server timestamps** have microseconds: `2026-11-07T14:05:00.123456Z`. `?since=` accepts any ISO 8601 UTC time.
- **`GET /healthz`** (no headers): `{"status", "contract_version", "seeded"}`. Use it to check the service is up and seeded.

## Endpoints

| Endpoint | Status | Notes |
| --- | --- | --- |
| `GET /healthz` | Real | No auth |
| `GET /v1/survey`, `GET /v1/terms` | Real | Latest published survey version per cohort |
| `POST /v1/records` | Real | Feeds the company views immediately |
| `POST /v1/doctor-envelopes` | Real | 403 without an active care link |
| `POST /v1/alerts` | Real | `severe` only from devices |
| `PUT /v1/consent/{patient_ref}` | Real | Revoking stops new envelopes and hides undelivered ones (D-013) |
| `PUT`/`GET /v1/doctors/{id}/public-key` | Real | GET is 404 until the key is registered (D-025); the key is lost on `reset_all.sh` |
| `GET /v1/doctors/{id}/patients`, `/envelopes`, `/alerts`; `POST .../ack` | Real | |
| `GET /v1/caregivers/{id}/alerts` | Real | `summary` detail level is the same as `alerts_only` (D-008 open) |
| `/v1/company/*` | Real | Under-5 suppression applied (NF-03) |
| Missed check-in scheduler | **Not built (H5)** | Only seeded history contains missed check-ins |

## Switch-over plan (Scoping Doc 26.11)

| When | Becomes real | What teammates do |
| --- | --- | --- |
| H3 | **Done:** SQLite store, seed, company views on real records | Nothing changes in your code; data now survives restarts |
| H5 | Missed check-in scheduler | Doctor and caregiver views see new `missed` alerts within 1 minute |
| H6 | Integration run on the team hotspot | Run the Scoping Doc 26.15 checklist together |

## Running it for your app

```bash
cd apps/service && uv sync
uv run python -m sentinel_service.seed
SENTINEL_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174,http://localhost:5175 \
  uv run uvicorn sentinel_service.main:app --port 8000
```

- Browser apps need their origin in `SENTINEL_ALLOWED_ORIGINS`; without it the service sends no CORS headers and browser calls fail.
- Doctor side, to get test data before the patient runtime exists: register your key from the doctor web app, then run `uv run --project packages/contract-py python scripts/send_demo_envelope.py --alert` from the repo root.
- Start clean: `scripts/reset_all.sh --seed` (stop the service first).

## Reporting a problem

A 422 response names the failing field; check your payload against `schema/` and `schema/examples/` first. If the contract itself looks wrong, ask the company owner; do not work around it.
