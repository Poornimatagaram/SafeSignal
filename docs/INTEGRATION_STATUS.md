# Integration Status

What the Sentinel service (`apps/service`) actually does today. Maintained by the company owner only; check it before debugging anything that touches the service.

**Last updated:** 2026-11-08 · Session 012 · **contract `2.2`** (payload `schema_version` `"2.0"`; the service accepts only 2.0 payloads)

## Contract 2.0 in one paragraph

Records belong to a **hospital or clinic (organization)**, not to one doctor: patients seal envelopes to the organization's care-team key, and an admin gives member doctors that key. A new doctor reads the full history; a revoked doctor loses access. An **emergency hospital** the patient chose at setup can read the history only through **audited emergency access**. Missed check-ins **escalate** at 1, 2 and 3 consecutive misses; level 3 also reaches the user-defined emergency contacts (for example 911). Payloads gain `reporter` (self or a proxy), `input_mode` (voice or text) and, for doctors, `age_years`. Full design: `docs/design/contract-2.0.md`.

## Current mode: SQLite

- **Data persists** in `var/service/company.db` and `var/service/relay.db` (gitignored). Wipe with `scripts/reset_all.sh`.
- **Seeded by** `python -m sentinel_service.seed` (safe to re-run; `--reset` starts over):
  - Company **Halvaren Therapeutics** `co_halvaren` (fictional) with **3 programs**, each 4 cohorts of 250 patients whose side-effect rates come from a **real trial arm** (D-081):
    - `prog_demo_01` Tagrisso ← FLAURA: cohort_A comparator (gefitinib or erlotinib), **cohort_B osimertinib (Walter)**, cohort_C osimertinib (China), cohort_D comparator (China). Priya is in cohort_A.
    - `prog_rybrevant_01` Rybrevant ← MARIPOSA: `cohort_ryb_A`/`_B` amivantamab + lazertinib, `_C` osimertinib, `_D` lazertinib.
    - `prog_beyfortus_01` Beyfortus ← MELODY (infants; every check-in answered by a `parent`): `cohort_inf_A`–`_C` nirsevimab, `_D` placebo; parent-facing survey.
  - Term list with label-verified `drug_scope` and 6 new codes (D-079); survey v1 per cohort with `schedule.every_days = 1`; 9 documents (protocol, analysis plan and FDA label per program, with public links).
  - 3,000 enrollments: Walter `pt_4b82d0c6`, Priya `pt_9c1d2e3f` and 2,998 synthetic patients; about 15% of adult check-ins are answered by a caregiver; voice, text and mixed input.
  - About 81,000 daily check-ins from Monday of 2026-W42 through **yesterday**. Today is empty, so the live check-in is today's record.
  - Organizations (all fictional): **Northgate Medical Center** `org_5e1a2b3c` is the care team for Walter and Priya (Dr. Shah attending, **Dr. Patel admin**); **Lakeside Emergency Hospital** `org_8f4d6a2e` is Walter's emergency hospital (**Dr. Okafor admin**). Dr. Rivera `dr_c71e0f9a` is registered but not a member (doctor-change demo).
  - **No keys are seeded**: every doctor and organization key is generated in the doctor's browser.
  - Anna `cg_7e21c9a4` is Walter's caregiver (alerts only). Walter's emergency contacts: 911 and Lakeside.
  - Historical missed check-in alerts with escalation levels, each with its delivery records. **Priya missed the last 2 days**, and she consented to one emergency contact (911): when **today's** window closes (13:00–14:00 UTC) without a check-in, the scheduler raises **level 3**, notifying Priya, Northgate and her emergency contact (in-app record).
  - History runs through yesterday relative to the day you seed. Reseed on demo day.
- **Company views aggregate real records**, including records sent by the patient runtime.

## Endpoints

| Endpoint | Status | Notes |
| --- | --- | --- |
| `GET /healthz` | Real | No auth; `contract_version` and `seeded` |
| `GET /v1/survey`, `GET /v1/terms` | Real | Survey includes `schedule` |
| `POST /v1/records` | Real | 2.0 record with `reporter` and `input_mode` |
| `GET /v1/orgs/{org_id}/public-key` (patient) | Real | 404 until the org admin registers the care-team key |
| `POST /v1/care-envelopes` | Real | 403 without an active care or emergency link |
| `POST /v1/alerts` | Real | `severe` only from devices; delivered to caregiver and care team |
| `PUT /v1/consent/{patient_ref}` | Real | Care team, caregiver, emergency organizations and contacts (with consent) |
| Doctor: `/v1/doctors/{id}/public-key`, `/v1/doctors/{id}/orgs` | Real | |
| Organization: `/public-key`, `/members/{doctor_id}`, `/key-grants` (admin) | Real | Revoking a member deletes their key grant |
| Organization: `/key-grants/{doctor_id}`, `/patients`, `/envelopes`, `/ack`, `/alerts` (members) | Real | Routine access covers care-team patients only |
| `POST /v1/orgs/{org_id}/emergency-access` | Real | Emergency organizations only; coded reason; logged; notifies caregiver and care team |
| `GET /v1/caregivers/{id}/alerts` | Real | Includes `escalation_level` and `emergency_access` alerts |
| `/v1/company/*` | Real | Weekly cohort rows, completion (with voice/text/mixed counts), survey read and publish, export (`company_safety`), and 2.2 `programs`, `documents`, `terms` |
| Missed check-in scheduler | **Real** | Runs every 30 s (`SERVICE_SCHEDULER_INTERVAL`; off with `SERVICE_SCHEDULER=off`). Watches demo (non-synthetic) patients only; alert within one interval after a window closes; level = consecutive misses (max 3) |

## Switch-over plan

| When | Becomes real | What teammates do |
| --- | --- | --- |
| H3 | **Done:** SQLite store, seed | — |
| Done | Contract 2.0 | Build against 2.0 (briefs updated); there is no 1.x compatibility |
| Done | Contract 2.2: three programs on real trial rates; new term codes | Patient extraction picks up new codes from `enums.json`; existing databases gain the new columns automatically, but reseed to get the programs |
| Done | Missed check-in scheduler with the 3-level escalation | Poll `/alerts?since=`: new `missed` alerts appear within one scheduler interval |
| Then | Integration run on the team hotspot | Run the Scoping Doc 26.15 checklist together |

## Running it for your app

```bash
cd apps/service && uv sync
uv run python -m sentinel_service.seed
SENTINEL_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174,http://localhost:5175 \
  uv run uvicorn sentinel_service.main:app --port 8000
```

- Browser apps need their origin in `SENTINEL_ALLOWED_ORIGINS`; without it the service sends no CORS headers and browser calls fail.
- Doctor side, to get test data before the patient runtime exists: as Dr. Patel, register Northgate's care-team key (and grant it to yourself), then run `uv run --project packages/contract-py python scripts/send_demo_envelope.py --alert` from the repo root. Register Lakeside's key as Dr. Okafor to also receive Walter's emergency envelope.
- **Company portal:** `cd apps/company-web && npm install && npm run dev` (port 5175; reads `/v1/company/*` only).
- Start clean: `scripts/reset_all.sh --seed` (stop the service first; also clear the doctor browser's site data, which holds the keys).
- **Demo controls** (from `apps/service`): `uv run python -m sentinel_service.demo close-window pt_9c1d2e3f --in 60` makes Priya's window close in about a minute so the level 3 alert fires on cue; `... demo run-scheduler` runs one pass immediately. Walter checks in live today: if his window closes first, he gets a missed alert too, so set his window with `close-window pt_4b82d0c6 --in 3600` before the demo if needed.

## Reporting a problem

A 422 response names the failing field; check your payload against `schema/` and `schema/examples/` first. If the contract itself looks wrong, ask the company owner; do not work around it.
