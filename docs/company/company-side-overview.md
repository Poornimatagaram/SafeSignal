# What the company side does

**Date:** 2026-11-08 · **Owner:** company side · **Contract:** 2.2

This is a plain summary of the company side's job in SafeSignal and of what is left. Details live in the linked files. `docs/DECISIONS.md` overrides this page wherever they differ, and `docs/INTEGRATION_STATUS.md` says what the service does today.

## 1. The contract everyone builds against

**Where:** `schema/`, `packages/contract-py`, `packages/contract-ts`

- Defines every payload, table, ID pattern, enum, term code and API endpoint that the patient, doctor and company apps share. The current release is 2.2; payloads carry `schema_version` `"2.0"`.
- Ships helpers for both languages:
  - Python (`sentinel_contract`): canonical JSON, payload hashing, validation and `SentinelClient` for the patient device.
  - TypeScript (`@sentinel/contract`): hashing and API types generated from `schema/openapi.json`.
- Builds privacy into the payload shapes:
  - The company record has no free text, no names and only ISO-week dates.
  - The doctor payload travels sealed, so only the hospital's care team can open it.
  - Emergency contacts live only in the relay store.

## 2. The central service

**Where:** `apps/service` (FastAPI and SQLite, port 8000). `company.db` and `relay.db` are kept separate under `var/service/`.

- **Records:** accepts the patient device's minimal check-in record and stores it, pseudonymized, in the company database. Requests are idempotent and checked against the patient's enrollment.
- **Care envelopes:** relays the patient's sealed history to the care-team organization (hospital or clinic). The service cannot read them.
- **Consent:** records consent to the care team, the caregiver, emergency hospitals and up to 3 emergency contacts.
- **Care teams:**
  - Organization keys are generated in the browser.
  - An admin grants each member the key, and revokes it when a doctor leaves.
  - The record stays with the hospital, not with one doctor (D-064).
- **Emergency access:**
  - Only hospitals the patient chose can read the history, and only with a coded reason (D-065).
  - Every use is logged and notified.
- **Alerts:**
  - Severe symptoms go to the caregiver and care team.
  - Missed check-ins escalate at levels 1, 2 and 3; level 3 also reaches consented emergency contacts and 911 (D-068).
  - A background scheduler raises missed check-ins within one interval of a window closing (D-074).
- **Access control:** checks the role on every request (`patient_device`, `doctor`, `caregiver`, `company_reader`, `company_admin`, `company_safety`) and writes access logs.

## 3. The drug company's own product

This is what the buyer, the drug company, gets.

- **Fictional company:** Halvaren Therapeutics (D-078). It runs three programs, each with 4 cohorts of 250 patients whose side-effect rates come from real trial arms (D-081):

| Program | Real source | Cohorts |
| --- | --- | --- |
| Tagrisso `prog_demo_01` | FLAURA `NCT02296125` | A comparator, **B osimertinib (Walter)**, C osimertinib (China), D comparator (China) |
| Rybrevant `prog_rybrevant_01` | MARIPOSA `NCT04487080` | ryb_A and ryb_B amivantamab + lazertinib, ryb_C osimertinib, ryb_D lazertinib |
| Beyfortus `prog_beyfortus_01` | MELODY `NCT03979313` (infants; a parent answers) | inf_A–C nirsevimab, inf_D placebo |

- **Safety signals:**
  - Weekly side-effect rates per cohort. A row needs at least 5 patients, and severe counts of 1–4 show as "<5" (D-004).
  - Completion and missed rates.
  - Voice, text and mixed answers.
- **Surveys:** the company edits and publishes each cohort's questions and check-in cadence. Only the questions go to patients' devices.
- **Known side effects:** the term list is checked against each drug's FDA label (D-079). Each report says whether the effect is on the label for that drug.
- **Documents:** each program's real trial protocol, statistical analysis plan and FDA label, linked to their public sources (D-080).
- **Records export:** JSON or CSV for the safety team only, with no receipt times and no identifiers (D-009).
- **Company portal** (`apps/company-web`, port 5175): shows all of the above with a role switcher.

## 4. Data and demo setup

- **Real public data** is cached in `data/company/`, with sources and licences in `data/README.md`:
  - ClinicalTrials.gov results
  - FDA label sections
  - openFDA report counts
- Trial PDFs are downloaded locally and never committed.
- **Seed** (`python -m sentinel_service.seed`):
  - 3,000 synthetic patients and about 81,000 check-ins, sampled from the real arm rates.
  - The demo people: Walter, Priya, Anna, Drs. Shah, Patel, Rivera and Okafor, Northgate and Lakeside.
  - History ends yesterday, so today is free for the live demo.
- **Demo controls** (`python -m sentinel_service.demo`): fire Priya's level 3 missed check-in alert on cue.
- **End-to-end check** (`scripts/e2e_check.py`): plays every role against a throwaway service.

## 5. Running the project

- Keeps the project logs: `CHANGELOG.md`, `docs/DECISIONS.md`, `docs/SESSION_LOG.md`, `docs/INTEGRATION_STATUS.md` and the teammates' briefs in `docs/briefs/`.
- Owns CI and the repository rules:
  - branch names
  - Conventional Commits
  - folder ownership (`CODEOWNERS`)
  - squash-merging when green (D-072)

## 6. What is left

| Item | Owner | Status |
| --- | --- | --- |
| Branch protection on `main` (no force pushes, required CI, squash only, auto-delete branches) | Repo owner (only admin) | Requested through the company owner (D-045, D-050) |
| D-008: keep or drop the caregiver `summary` detail level | Product owner, then company | Open |
| Team integration run of all three apps against one service (Scoping Doc 26.15) | Company coordinates | After the patient egress gate exists |
| Reseed on demo day: `scripts/reset_all.sh --seed` | Company | On the day |
| Document assistant over the program documents; regulator exchange-format export | Company | Optional ("Could" this weekend, or v1) |

## 7. Handled by the other owners

- **Patient egress gate** (task A4, `apps/patient-runtime/sentinel_patient/egress_gate.py`): sends records, envelopes, alerts and consent, and fetches the cohort survey. A patient-side teammate is building it. The service and `SentinelClient` already support every call it needs.
- **Doctor app:** the feature branches (timeline, organization admin, emergency access, caregiver view, demo history, landing page) are merged by the doctor owner.
- **App user interfaces** belong to their owners.
