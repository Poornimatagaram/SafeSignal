# Doctor web: agent instructions

Owner: doctor teammate. Maintained by the company owner (contract changes land here); imported by `apps/doctor-web/CLAUDE.md`. Root `CLAUDE.md` rules also apply. **Contract 2.0:** read `docs/design/contract-2.0.md` first.

## Your job
The doctor's view: the patient's **medical history only** (D-062), a one-screen symptom timeline, alerts with their escalation level, and an optional pre-visit summary. Records belong to the **hospital or clinic (organization)**, not to one doctor, so a new doctor continues where the last one stopped, and an emergency hospital the patient chose can read the history through audited emergency access. Scope and acceptance checks: `docs/scoping-document.md` Sections 3.7, 9.4, 12.7, 14.

## Setup
- npm package `@sentinel/doctor-web` in `apps/doctor-web/`, own `package.json` and lockfile. Dev server port **5174**.
- Contract helpers: `"@sentinel/contract": "file:../../packages/contract-ts"`:
  - `import { canonical, payloadSha256 } from "@sentinel/contract"` (`payloadSha256` is async, Web Crypto)
  - `import type { paths, components } from "@sentinel/contract/api"` (generated from `schema/openapi.json`)
- Validate decrypted payloads against `schema/doctor_payload.json` (JSON Schema draft 2020-12; for example Ajv's `ajv/dist/2020`).
- Encryption: `libsodium-wrappers` (`crypto_box_keypair`, `crypto_box_seal`, `crypto_box_seal_open`); keys, ciphertext and wrapped keys are standard base64.
- Browser database: IndexedDB named `sentinel_doctor_view`, one object store per table in `schema/doctor_view.sql`: `dr_patient`, `dr_timeline_entry`, `dr_alert`, `dr_key`, `dr_org_key`, `dr_sync_state`.
- Demo people (`schema/demo_fixtures.json`, `demo_notes`): Northgate Medical Center `org_5e1a2b3c` (care team for Walter and Priya; Dr. Shah attending, **Dr. Patel admin**); Dr. Rivera not yet a member (joins in the doctor-change demo); Lakeside Emergency Hospital `org_8f4d6a2e` (Walter's emergency hospital; **Dr. Okafor admin**). Env vars use the `DOCTOR_` prefix (Vite: `VITE_DOCTOR_*`).
- Run the service with your origin allowed, and generate test envelopes without the patient app: see `docs/INTEGRATION_STATUS.md`.

## Keys: how a doctor gets to read an organization's records
1. **Every doctor, first launch:** generate a personal X25519 key pair; keep the private key only in `dr_key`; `PUT /v1/doctors/{doctor_id}/public-key`.
2. **Organization admin, once per organization:** generate the care-team key pair; `PUT /v1/orgs/{org_id}/public-key`; keep the private key in `dr_org_key`.
3. **Admin, for each member** (including themselves): seal the org private key to the member's personal public key (`crypto_box_seal`) and `POST /v1/orgs/{org_id}/key-grants` with `{doctor_id, wrapped_key}`. The admin reads the member's public key from that doctor (for the demo, both run in one browser profile per doctor; v1 adds a lookup endpoint).
4. **Member:** `GET /v1/orgs/{org_id}/key-grants/{doctor_id}`, open it with the personal private key (`crypto_box_seal_open`), store the org key in `dr_org_key`.
5. **Doctor change:** the admin `PUT /v1/orgs/{org_id}/members/{doctor_id}` with `status: "revoked"` (the service deletes their key grant and refuses them), then adds the new doctor and grants them (step 3). The new doctor reads the full history.

## How to talk to the service
Headers on every request: `X-Role: doctor`, `X-Actor-Id: <your doctor_id>`. Allowed calls only:

| Call | Who | Body or response |
| --- | --- | --- |
| `PUT /v1/doctors/{id}/public-key` | self | `{public_key}` → `{doctor_id, public_key}` |
| `GET /v1/doctors/{id}/orgs` | self | `[{org_id, display_name, org_type, role, org_key_registered, has_key_grant}]` |
| `PUT /v1/orgs/{org_id}/public-key` | admin | `{public_key}` → `{org_id, public_key}` |
| `PUT /v1/orgs/{org_id}/members/{doctor_id}` | admin | `{role, status}` → member state |
| `POST /v1/orgs/{org_id}/key-grants` | admin | `{doctor_id, wrapped_key}` → receipt (201) |
| `GET /v1/orgs/{org_id}/key-grants/{doctor_id}` | self, member | `{wrapped_key, granted_by, granted_at, ...}` |
| `GET /v1/orgs/{org_id}/patients` | member | `[{patient_ref, granted_at}]` (care-team patients only) |
| `GET /v1/orgs/{org_id}/envelopes?since=` | member | `[{envelope_id, patient_ref, ciphertext, payload_sha256, received_at}]` (care-team patients only) |
| `POST /v1/orgs/{org_id}/envelopes/{envelope_id}/ack` | member | `{envelope_id, fetched_at}` |
| `GET /v1/orgs/{org_id}/alerts?since=` | member | `[{alert_id, patient_ref, alert_type, escalation_level, created_at, received_at}]` |
| `POST /v1/orgs/{org_id}/emergency-access` | member of an emergency organization | `{patient_ref, reason}` → `{envelopes, notified, notification_alert_id, ...}` |

`since` returns items strictly after the timestamp, oldest first, at most 100 per call. Keep the newest **`received_at`** per organization and stream in `dr_sync_state` (`<org_id>:envelopes`, `<org_id>:alerts`) and pass it as `since`; never page on `created_at` (D-054).

## Changed from the scoping doc and from contract 1.x (these override Sections 25–26)
- **Organizations replace individual doctors** as recipients: `/v1/doctors/{id}/patients|envelopes|alerts` and `/ack` are now under `/v1/orgs/{org_id}/...` (D-064).
- **Emergency access** (D-065): reasons are `unresponsive_patient`, `emergency_admission`, `escalation_level_3`. Every use is logged and notifies the patient's caregiver and care team; show a clear "emergency access" banner and the reason.
- **Alerts** (D-068, D-074): `alert_type` is `missed`, `severe` or `emergency_access`; `escalation_level` is 1, 2 or 3 for missed check-ins (3 = emergency contacts were notified). The service scheduler raises `missed` alerts within one interval (30 s) after a window closes. Show `created_at` as the event time (when the window closed).
- **Doctor payload 2.0**: adds `reporter` (`self`, `parent`, `caregiver`, `other`) and `age_years` (0–120; patients of every age, D-058). Show who answered on every timeline entry.
- **`doctor_view.sql`**: `dr_org_key`; `org_id` on `dr_patient` and `dr_alert`; `age_years`, `shared`; `reporter` on timeline entries; `dr_sync_state` keyed per organization.
- **Timeline entry ID** is `<envelope_id>:<term_code>`; an envelope with no symptoms still updates `dr_patient.last_checkin`.
- **Revoked consent:** the service stops returning that patient; keep stored data and set `dr_patient.shared = 0` (D-038).
- Paths: `web/doctor/` → `apps/doctor-web/`; hash vectors are tested in `packages/contract-ts` (D-029, D-030).

## Always
- For each envelope: decrypt with the organization key, parse, recompute `payloadSha256` and compare with `payload_sha256`, validate against `schema/doctor_payload.json`; reject on any failure; upsert into the `dr_*` stores; then POST the ack.
- Show only the medical history: symptoms, severity, onset, trend, flags, reporter, age, drug and version. "Possible link" flags read "for review", never as a cause.
- Log your changes in `apps/doctor-web/CHANGELOG.md`.

## Never
- Send decrypted data, or anything derived from it, to the service or any other host.
- Export, log or transmit a personal or organization private key.
- Call `/v1/company/*` or any patient endpoint, or read any database file.
- Use emergency access without a real reason, or hide that it happened.
- Use cloud AI APIs on decrypted data; the pre-visit summary uses templates or a local model only.
- Log decrypted payload contents to the console or anywhere else.

## Done when
- `scripts/check_ownership.sh` and `scripts/check_commits.sh` pass on your branch, and the pull request into `main` is green with no conflicts (`CONTRIBUTING.md`; commit scope `doctor-web`).
- Walter's envelopes decrypt for Dr. Shah, pass hash and schema checks, and render on the timeline; alerts show their escalation level within 1 minute.
- Doctor change: after Dr. Patel revokes Dr. Shah and grants Dr. Rivera, Dr. Rivera sees Walter's full history and Dr. Shah sees nothing.
- Emergency: Dr. Okafor at Lakeside reads Walter's history only through emergency access, and Anna and Northgate get an `emergency_access` alert.
