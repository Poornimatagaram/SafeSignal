# Patient web: agent instructions

Owner: patient teammate. Maintained by the company owner (contract changes land here); imported by `apps/patient-web/CLAUDE.md`. Root `CLAUDE.md` rules also apply.

## Your job
The patient's screen (Walter, 92): large-text, voice-first check-in UI, spoken summary and approval, egress receipt, network log view and consent toggles. Scope and acceptance checks: `docs/scoping-document.md` Sections 3.2, 9.2, 12.1, 12.2, 12.5, 13 (NF-08, NF-09), 21.

## Setup
- npm package `@sentinel/patient-web` in `apps/patient-web/`, own `package.json` and lockfile. Dev server port **5173**.
- Talks ONLY to the patient runtime on `http://127.0.0.1:8001` (its API is defined by `apps/patient-runtime`, same owner). Never call the Sentinel service directly: every outbound byte goes through the runtime's egress gate.
- Optional shared helpers: `"@sentinel/contract": "file:../../packages/contract-ts"` (`canonical`, `payloadSha256`, API types at `@sentinel/contract/api`) to re-check receipt hashes in the UI.
- Env vars use the `PATIENT_` prefix (Vite: `VITE_PATIENT_*`).

## Changed from the scoping doc
- **Contract 2.0** (`docs/design/contract-2.0.md`): patients of any age, answered by the patient or a proxy (parent, caregiver); voice **or typing**; setup screens for consent to the care team, the caregiver, emergency hospitals and up to 3 emergency contacts (for example 911 or a preferred hospital), each explained in plain words and opt-in (D-058, D-059, D-067). Show who is answering on every screen.
- Paths: `web/patient/` → `apps/patient-web/` (D-030).
- The receipt lists field names from the runtime's `SendResult.fields_sent` (format `symptoms[].term_code`) and the `payload_sha256`.

## Always
- Microphone capture with MediaRecorder, audio sent only to the runtime on localhost.
- Text at least 24 px, high contrast, no small tap targets (NF-08); support "repeat" and "slower" (VC-07).
- Show "possible link" flags as "for review", never as a cause.
- Log your changes in `apps/patient-web/CHANGELOG.md`.

## Never
- Use the Web Speech API's SpeechRecognition or online text-to-speech voices (audio goes to the cloud).
- Add analytics, tracking or error-reporting scripts, or load fonts or scripts from third-party CDNs at runtime.
- Store transcripts or patient words anywhere except through the runtime.

## Done when
- `scripts/check_ownership.sh` and `scripts/check_commits.sh` pass on your branch, and the pull request into `main` is green with no conflicts (`CONTRIBUTING.md`; commit scope `patient-web`).
- Walter's full check-in runs from this screen, the receipt matches the runtime's egress log, and the network-off run completes (Scoping Doc 21.1).
