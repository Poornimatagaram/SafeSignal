# Privacy measures in SafeSignal (Sentinel)

Audit of the codebase against the HACK1984 **Privacy-First** track. Written from reading the code on 2026-11-08; the tests and the leakage eval were not run for this document.

## Chosen path

`docs/scoping-document.md` §8: **Privacy-First is the primary track**, Most Startup-able is the second entry, Signal-to-Dose is a stretch (only if a teammate owns it), Surge is not targeted (web search would add outbound calls).

The track asks: what leaves the device, who can read it, and can you prove it?

## 1. What leaves the device

1. **One egress gate.** `apps/patient-runtime/sentinel_patient/egress_gate.py` is the only module allowed to import the HTTP client. `test_only_egress_gate_imports_network_code` fails if another module does.
2. **Schema-only payloads.** Every payload is validated against JSON Schemas with `additionalProperties: false`. Fields are coded values, numbers, booleans and random IDs; there are no free-text fields. Validation errors name the field, never the value.
3. **No transcript or audio in any payload.** The company record, alert and consent update copy only coded values, so names, dates of birth, phone numbers and patient words cannot reach them. Alerts carry IDs and a time only.
4. **Sensitive fields stay local.** Contact labels and the patient's own phone never leave. Emergency contact phones leave only inside the consent update, and only with emergency consent.
5. **The patient approves every send.** Nothing is sent until the patient confirms the on-screen summary.
6. **Outbox, receipts, egress log.**
   - The payload is written to an outbox with its SHA-256 hash before sending.
   - Each send returns a receipt: field names, destination, time and hash. The service echoes the hash back (contract 2.3, D-088) so the patient can compare.
   - Every request is recorded in `egress_log`, including configuration fetches (PV-06).
   - A retry resends the stored payload unchanged, so a record is never sent twice.
7. **Network-off check-ins.** A check-in completes with no network. A retry worker sends the queued record with backoff once back online (PV-07).

## 2. What happens on the device

- **Speech-to-text.** Whisper (faster-whisper) runs locally from a cache with `local_files_only`. Audio is decoded in memory and never written to disk. Only a whitelist of audio containers is accepted, so the decoder cannot be pointed at a URL or file.
- **Personal-data filter** (`filter.py`). Presidio, spaCy and custom patterns remove names, addresses, phones, emails, dates of birth, places and IDs before the model sees the text. Presidio debug logging is forced off so it cannot echo context.
- **Local model.** Extraction runs through Ollama (`llama3.2:3b`). `ollama_host()` refuses any non-loopback host; proxies and redirects are disabled.
- **Constrained extraction.** Output is forced into the schema enums and re-validated. A term with no supporting cue, or an "unsure" match, becomes `SE_OTHER_REVIEW`. Severity is never guessed.
- **Text-to-speech.** macOS `say` or Piper, both offline. Browser Speech APIs and cloud AI are banned.
- **Patient-web** (`tests/privacy.test.ts`) fails if the screen uses any of:
  - SpeechRecognition or speechSynthesis
  - localStorage, sessionStorage, IndexedDB or cookies
  - sendBeacon, WebSocket, XMLHttpRequest or EventSource
  - any absolute URL other than the runtime's localhost address
  - `fetch` outside the API client
- **Runtime hygiene.** The runtime binds to 127.0.0.1 and logs only method, path and status.

## 3. Who can read it

| Reader | What they can read | How it is enforced |
| --- | --- | --- |
| Doctors and hospitals | The patient's timeline, only with consent | Doctor payload sealed on the device (libsodium sealed box, X25519) to the organization's care-team key. The service stores ciphertext only. The org private key is generated in the doctor's browser and reaches members only as a sealed key grant the service cannot open. Revoking a member deletes their grant and blocks them at the service. Consent withdrawal stops future sealing. |
| Emergency hospital | History, only through audited emergency access | Dedicated endpoint, coded reason, every use written to `relay_access_log` and an alert raised to the caregiver and care team. Envelopes are sealed to it only if emergency consent was on when the check-in was approved. |
| Drug company | De-identified, aggregate data | ISO week only; `received_at` is never returned; views return NULL ("<5") for counts under 5 patients and `v_completion_weekly` has `HAVING COUNT(DISTINCT patient_ref) >= 5`. Three roles (reader, admin, safety); every read, publish and export is written to `access_log`. |
| Caregiver | Alerts only | No symptom details in alerts. |

Patients are identified by a random `pt_` ID. Free-text emergency contacts are not allowed.

## 4. Proof for the judges

- On-screen receipts with a hash that matches the service.
- The egress log of every outbound call.
- Schema tests that try to send forbidden fields.
- `evals/patient/leakage_eval.py` over synthetic transcripts (must say PASS before every commit; prints no text).
- `evals/doctor/access_checks.py` plays each role against a live service.
- `scripts/e2e_check.py` runs one check-in through every persona on a throwaway service; CI runs it.

## 5. Repo-level controls

- `.gitignore` excludes `*.db`, `.env*`, `var/`, audio files and PDFs. `apps/doctor-web/scripts/check-secrets.sh` scans the source and built bundle for key-like strings.
- Synthetic data only; the company is fictional (D-071, D-078).
- Rules ban analytics, tracking, cloud speech and cloud AI on patient data.
- Transcripts, payloads and request bodies are never logged. Error messages never quote values. The service logs IDs, roles, paths and status only.
- CI on every pull request: patient tests and evals, end-to-end check, TypeScript hash vectors, ownership check.

## 6. Stated gaps

These are the scoping document's own admitted shortcuts (§13, §14.6) plus open decisions.

- **Not encrypted at rest.** Patient data is in SQLite; the doctor's private keys are in plain IndexedDB (NF-04).
- **Demo-grade auth.** The service trusts `X-Role` and `X-Actor-Id` headers. No TLS on localhost.
- **Re-identification risk.** A rare symptom in a small cohort could still point to one person; the formal test is deferred to v1.
- **Revoked doctors.** A revoked doctor who kept the org key could decrypt envelopes they already have. Key rotation is v1 (D-064).
- **Open decisions.** D-045 (branch protection on `main`), D-008 (caregiver `summary` detail level), D-039 (who builds the caregiver view).
- **Escalation notifications** are in-app only (D-067).

## Suggested next steps

1. Encrypt data at rest (the gap judges are most likely to ask about).
2. Add a short "what leaves the device" table to the README (NF-13).
