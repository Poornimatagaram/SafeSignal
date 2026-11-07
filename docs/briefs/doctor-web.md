# Doctor web: agent instructions

Owner: doctor teammate. Maintained by the company owner (contract changes land here); imported by `apps/doctor-web/CLAUDE.md`. Root `CLAUDE.md` rules also apply.

## Your job
The doctor's view (Dr. Shah): consented patient list, one-screen symptom timeline, alerts, and an optional pre-visit summary, built from encrypted envelopes that only this browser can decrypt. Scope and acceptance checks: `docs/scoping-document.md` Sections 3.7, 9.4, 12.7, 14 and the Doctor layer brief in 26.14.

## Setup
- npm package `@sentinel/doctor-web` in `apps/doctor-web/`, own `package.json` and lockfile. Dev server port **5174**.
- Contract helpers: `"@sentinel/contract": "file:../../packages/contract-ts"`:
  - `import { canonical, payloadSha256 } from "@sentinel/contract"` (`payloadSha256` is async, Web Crypto)
  - `import type { paths, components } from "@sentinel/contract/api"` (generated from `schema/openapi.json`)
- Validate decrypted payloads against `schema/doctor_payload.json` (JSON Schema draft 2020-12; for example Ajv's `ajv/dist/2020`).
- Encryption: `libsodium-wrappers`, `crypto_box_seal_open`; keys and ciphertext are standard base64.
- Browser database: IndexedDB named `sentinel_doctor_view`, one object store per table in `schema/doctor_view.sql`, keyed by its primary key: `dr_patient`, `dr_timeline_entry`, `dr_alert`, `dr_key`, `dr_sync_state`.
- Your identity: Dr. Shah `dr_3a7f10b2` (`schema/demo_fixtures.json`). Env vars use the `DOCTOR_` prefix (Vite: `VITE_DOCTOR_*`).
- Run the service with your origin allowed, and generate test envelopes without the patient app: see `docs/INTEGRATION_STATUS.md`.

## How to talk to the service
Headers on every request: `X-Role: doctor`, `X-Actor-Id: dr_3a7f10b2`. Allowed calls only:

| Call | Body or response |
| --- | --- |
| `PUT /v1/doctors/{id}/public-key` | `{public_key}` (base64, 32 bytes) → `{doctor_id, public_key}` |
| `GET /v1/doctors/{id}/patients` | `[{patient_ref, granted_at}]` (active care links only) |
| `GET /v1/doctors/{id}/envelopes?since=` | `[{envelope_id, patient_ref, ciphertext, payload_sha256, received_at}]` |
| `POST /v1/doctors/{id}/envelopes/{envelope_id}/ack` | `{envelope_id, fetched_at}` |
| `GET /v1/doctors/{id}/alerts?since=` | `[{alert_id, patient_ref, alert_type, created_at}]` |

`since` returns items strictly after the timestamp, oldest first, at most 100 per call; keep the newest seen value in `dr_sync_state`.

## Changed from the scoping doc (these override Sections 25–26)
- **`doctor_view.sql` adds** `dr_timeline_entry.envelope_id` and `.status`, plus `dr_key` (your key pair) and `dr_sync_state` (cursors) (D-011).
- **Timeline entry ID** is `<envelope_id>:<term_code>`; an envelope with no symptoms still updates `dr_patient.last_checkin`.
- **Public key:** patients get 404 until you register it, so register on first launch (D-025).
- **Revoked consent:** the service stops returning that patient, their undelivered envelopes and alerts (D-013). Data you already stored stays in your browser; mark the patient as no longer shared.
- **Alerts:** `missed` comes from the service scheduler (not built yet), `severe` from the patient device (D-016).
- Paths: `web/doctor/` → `apps/doctor-web/`; hash vectors are tested in `packages/contract-ts` (D-029, D-030).

## Always
- Generate the X25519 key pair in the browser on first launch; keep the private key only in `dr_key`; register only the public key.
- For each envelope: decrypt, parse, recompute `payloadSha256` and compare with `payload_sha256`, validate against `schema/doctor_payload.json`; reject on any failure; upsert into the `dr_*` stores; then POST the ack.
- Show only patients with an active care link; show "possible link" flags as "for review".
- Log your changes in `apps/doctor-web/CHANGELOG.md`.

## Never
- Send decrypted data, or anything derived from it, to the service or any other host.
- Export, log or transmit the private key.
- Call `/v1/company/*` or any patient endpoint, or read any database file.
- Use cloud AI APIs on decrypted data; the pre-visit summary uses templates or a local model only.
- Log decrypted payload contents to the console or anywhere else.

## Done when
- `scripts/check_ownership.sh` passes on your branch (you changed only your own folders).
- Walter's envelopes decrypt, pass hash and schema checks, render on the timeline, and alerts appear within 1 minute.
- The Doctor and Access-control items of the Scoping Doc 26.15 checklist pass.
