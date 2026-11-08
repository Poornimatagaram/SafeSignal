# Company portal

- **Owner:** Company side (see `CODEOWNERS`)
- **Package name:** `@sentinel/company-web`
- **Port:** 5175
- **Runtime data:** none (reads the service's `/v1/company/*` endpoints only; never relay, doctor or patient endpoints)
- **Contract:** read `schema/`; never edit it. API types come from `@sentinel/contract/api` (`packages/contract-ts`).
- **Brief:** Scoping Doc 12.6 (CO-01 to CO-07) and 26.8 (company layer).

## Look
Same layout and controls as the doctor view (D-090) with a professional look of its own (D-091): Inter and IBM Plex Mono, slate and clinical blue, light / dark / system, bundled fonts. Tabs are hash routes: `#/signals`, `#/completion`, `#/survey`, `#/program`.

## What it shows

| Tab | Requirement | Endpoint | Role |
| --- | --- | --- | --- |
| Side effects | CO-01: share of reporting patients per side effect, by cohort, week over week; flags terms not on the FDA label | `GET /v1/company/cohorts/weekly`, `/terms` | `company_reader` |
| Check-ins | CO-02: completion and missed rates by cohort; voice, text and mixed answers | `GET /v1/company/completion` | `company_reader` |
| Survey | CO-03: load the live survey for a cohort, edit and publish a new version | `GET`/`PUT /v1/company/cohorts/{id}/survey` | `company_reader` / `company_admin` |
| Program & export | Cohorts and their source trial arms, public documents, CO-07 JSON/CSV export | `/programs`, `/documents`, `/records/export` | `company_reader` / `company_safety` |

CO-04 holds by construction: the service only ever returns coded, pseudonymized rows and hides groups under 5 patients. Every chart has a table view and direct labels (two light-mode series colors sit under 3:1 contrast). CO-05 and CO-06 (document assistant, FDA report draft) are not built.

## Run
```bash
# service (from apps/service), with this origin allowed
SENTINEL_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174,http://localhost:5175 \
  uv run uvicorn sentinel_service.main:app --port 8000
# portal
cd apps/company-web && npm install && npm run dev      # http://localhost:5175
```
Settings (optional, in `apps/company-web/.env.local`, git-ignored): `VITE_COMPANY_SERVICE_URL` (default `http://127.0.0.1:8000`), `VITE_COMPANY_PROGRAM_ID` (default `prog_demo_01`), `VITE_COMPANY_ACTOR_ID` (default `co_demo_analyst`; demo-grade identity header).

## Check
```bash
cd apps/company-web && npm run lint && npm run build
```
