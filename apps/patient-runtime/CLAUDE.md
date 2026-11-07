# Patient runtime: agent instructions

Owner: patient teammate. Root `CLAUDE.md` rules also apply.

## Your job
Build the on-device check-in engine: spoken questions, local speech-to-text, answer rating and re-asking, personal-data filtering, extraction into coded fields, and sending ONLY schema-valid payloads through one egress gate. Scope and acceptance checks: `docs/scoping-document.md` Sections 12.1–12.5, 14, 17 and the Patient layer brief in 26.14.

## Setup
- Python package `sentinel_patient` in this folder, own `pyproject.toml` and lockfile. Port **8001** (patient-web calls you on localhost).
- Contract code as a path dependency:
  ```toml
  [project]
  dependencies = ["sentinel-contract"]
  [tool.uv.sources]
  sentinel-contract = { path = "../../packages/contract-py", editable = true }
  ```
- Database: `var/patient/patient.db`, created on first launch by applying `schema/patient.sql` (safe to re-run). Do not add, rename or drop tables or columns.
- Seed the device profile and consent from `schema/demo_fixtures.json` → `device_profiles` (Walter `pt_4b82d0c6`).
- Env: `SENTINEL_BASE_URL` (default `http://127.0.0.1:8000`), `SENTINEL_ACTOR_ID` (your `pt_` ID); your own settings use the `PATIENT_` prefix.
- Run the service locally: see `docs/INTEGRATION_STATUS.md`.

## How to talk to the service
Use only `from sentinel_contract.client import SentinelClient, build_envelope` (it validates, hashes and sends):

| Need | Call | Endpoint |
| --- | --- | --- |
| Today's questions | `fetch_survey(cohort_id)` | `GET /v1/survey` |
| Term list | `fetch_terms(program_id)` | `GET /v1/terms` |
| Doctor's key | `fetch_doctor_key(doctor_id)` | `GET /v1/doctors/{id}/public-key` |
| Company record | `send_record(record)` | `POST /v1/records` |
| Doctor envelope | `send_envelope(build_envelope(...))` | `POST /v1/doctor-envelopes` |
| Severe alert | `send_alert(alert)` | `POST /v1/alerts` |
| Consent change | `send_consent(consent)` | `PUT /v1/consent/{patient_ref}` |

- Sends return `SendResult(status_code, payload_sha256, fields_sent, ...)`: write `egress_log` from it and show it as the receipt.
- `ContractError`: payload invalid, nothing was sent; fix the code that built it.
- `SendRejected` (401/403/409/422): do not retry.
- `SendRetryable` (5xx or no network): keep in `outbox`, retry with `BACKOFF_SECONDS`.

## Changed from the scoping doc (these override Sections 25–26)
- **Every payload carries `"schema_version": "1.0"`.** The envelope and alert examples in 26.6 (`envelope_version`, `alert_version`) are wrong (D-014).
- **Consent payload** also carries `doctor_id` and `caregiver_id` (may be null): see `schema/consent_update.json` (D-014).
- **Alerts:** devices send only `alert_type: "severe"`; the service creates `missed` alerts (D-016).
- **`known_side_effect`** = the term's `known_for_program` from `/v1/terms`; store it in `term_cache.known_for_program` (D-007). `severe_trigger` terms or severity `severe` → send a severe alert.
- **`term_code`** must be one of `schema/enums.json` → `term_code`; anything unmapped is `SE_OTHER_REVIEW` (D-015).
- **`patient_profile.drug_name`** is new; it feeds the doctor payload (D-010).
- **Records must match the enrollment:** `program_id`, `cohort_id` and `drug_version` from the profile, and `patient_ref` = your actor ID; otherwise 422/403 (D-006).
- **Envelope retries:** store the built envelope in `outbox` and resend it unchanged; re-encrypting gives a new ciphertext and a 409 (D-021).
- **Doctor key** returns 404 until the doctor has registered one; queue the envelope and retry later (D-025).
- **Survey format:** `questions[] = {question_id, purpose, asks[3]}`; `asks[0]` first ask, `asks[1]` simpler, `asks[2]` choices or yes/no (D-017).
- Paths: `device_runtime/` → this folder; `device_runtime/patient.db` → `var/patient/patient.db`; `clients/sentinel_client.py` → `sentinel_contract.client` (D-030).

## Always
- `sentinel_patient/egress_gate.py` is the ONLY module that imports `sentinel_contract.client` or any HTTP library.
- Write each payload to `outbox` before sending; create `rec_`/`env_`/`alt_` IDs (8 lowercase hex) before sending and reuse them on retry.
- Encrypt doctor payloads only when consent and a care link are active.
- Make the check-in work with the network off.
- Run the leakage evaluation (`evals/`) before every commit.
- Log your changes in `apps/patient-runtime/CHANGELOG.md`.

## Never
- Send `transcript_text`, `patient_words`, `display_name` (except inside the encrypted doctor payload), `date_of_birth`, `phone`, exposure descriptions or audio anywhere.
- Add free-text fields or any field not in the schema.
- Use the browser SpeechRecognition API, cloud speech, cloud AI APIs, analytics or error reporting.
- Read or write the service databases or the doctor's browser storage.

## Done when
- A check-in produces a record accepted by `/v1/records` with 201, the receipt hash equals the service's `payload_sha256`, and the network log shows only the calls above.
- The Patient and Privacy items of the Scoping Doc 26.15 checklist pass.
