# Changelog: apps/patient-runtime

Changes in this app, newest first. Owned by this app's owner (root `CLAUDE.md`).

## 2026-11-08: Task A6, spoken summary, voice commands, network-off queue, severe alerts (branch `patient/feat/summary-offline`)

### Added
- `summary.py` (VC-08):
  - The spoken summary is built from coded fields by a template, never from model text.
  - `parse_correction` reads one spoken change (new severity, new onset, or "I don't have that"); anything unclear returns None.
- `commands.py` (VC-07): "repeat" and "slower" at any time, only when the utterance is just the command.
- Endpoints:
  - `GET /checkin/sessions/{id}/summary/audio`: the summary read aloud.
  - `POST /checkin/sessions/{id}/correction`: one change, by tap (JSON) or by voice (audio). A change that isn't understood doesn't use up the one correction.
  - `GET /checkin/sessions/{id}/receipt`: the current receipt, for polling.
- `/checkin/turn` returns `command` and `next.action` "repeat" or "slower" without storing an answer.
- Severe alerts (AL-02, SE-03):
  - Approving a check-in that has a severe symptom, or any term with `severe_trigger`, queues a minimal `alert_event` and sends it first through the egress gate.
  - Only if the patient shares with the care team or the caregiver.
- `egress_gate.RetryWorker` (PV-07): queued records and alerts are retried automatically with backoff (2, 4, 8, 16, 32, 60, 60 s) until accepted. It starts with the app.
- Tests: `test_summary.py`, `test_commands.py`, plus alert and retry tests in `test_egress_gate.py` and new flow tests in `test_checkin_api.py`; 650 runtime tests in total.

## 2026-11-08: Task A5, answer rating and re-asking (branch `patient/feat/reask`)

### Added
- `rating.py` (VC-04, VC-06): rates each answer complete, partial, off_topic, rambling or no_answer.
  - Rules run first and override the local model.
  - The model only judges what the rules can't, and only through `extract.py`'s loopback client.
  - For a rambling answer, `relevant_text` holds only the sentences that answer the question, copied from the patient's own words and never written by the model.
  - If the model fails, the rules decide (`source: rules_fallback`).
- Re-ask flow (VC-05):
  - `POST /checkin/turn` now returns `rating` and `next`.
  - An answer that isn't complete is re-asked with `asks[1]`, then `asks[2]`. After 2 re-asks the question is given up and counted as unanswered.
  - Ratings are stored in `answer_turn.rating`.
  - Only the relevant part of a rambling answer is used for symptoms, severity and onset; off-topic and no-answer replies add nothing.
- Tests: `test_rating.py`, plus re-ask tests in `test_checkin_api.py`; 541 runtime tests in total.

### Changed
- A question counts as answered only when an answer was rated complete.

## 2026-11-08: Task A4, egress gate, approve before sharing, receipt (branch `patient/feat/egress-gate`)

### Added
- `egress_gate.py` (PV-04 to PV-08), the only module that sends:
  - Builds the 2.0 company record and validates it against the schema.
  - Writes it to the outbox before sending, sends it with `SentinelClient.send_record`, and writes `egress_log` (field names and hash).
  - Returns a receipt.
  - Never sends twice; a payload kept while offline is resent unchanged.
  - `refresh_config` fetches the survey and term list into `survey_cache` and `term_cache`, checking each reply against the contract first.
- `checkin.py`: check-in sessions.
  - Answers are stored as `answer_turn` rows, and coded symptoms collect in a draft.
  - Only wellbeing, symptom-screen and exposure questions can add symptoms.
  - Severity and onset answers apply to the symptoms from the latest answer that reported any.
  - A missing severity is chosen by the patient, never guessed.
  - At approval, `symptom_event` rows, the session status and the outbox row are written in one transaction.
- Endpoints:
  - `POST /checkin/sessions`
  - `GET /checkin/sessions/{id}/summary`: what would be shared; sends nothing.
  - `POST /checkin/sessions/{id}/approve`: the only route that sends.
  - `/checkin/turn` now requires `session_id`, and the model runs only for questions that ask about symptoms.
- `extract.py` helpers: `severity_in_text` and `onset_in_text`, which are rule-based and return None when unclear.
- Tests: `test_egress_gate.py` (including live tests against the service on port 8000) and a rewritten `test_checkin_api.py` (approve before sending, no double send, offline queue, missing severity); 450 runtime tests in total on contract 2.2. Term counts in tests follow `schema/terms.json`.

### Changed
- `extract.py`: when the model isn't sure, the symptom is coded `SE_OTHER_REVIEW` instead of a guessed term ("chest feels tight" is no longer `SE_COUGH`).
  - A code is kept only when the text contains a cue for it.
  - Symptoms the patient denies, or says have stopped, are dropped.
  - Severity and onset are kept only when the text supports them.
- `survey.py`: questions come only from the survey downloaded from the service; the example-survey stand-in is gone.

## 2026-11-07: Tasks A2 and A3, voice, filter and extraction (branch `patient/feat/voice-and-filter`)

### Added
- `stt.py` (VC-02, VC-03, PV-03):
  - faster-whisper `base.en` on CPU, loaded from local files only.
  - Audio is decoded in memory with PyAV; only browser formats are accepted.
  - Speech on both sides of a 3 s pause is kept, and silence returns "".
  - Size cap 10 MB, length cap 300 s.
  - `python -m sentinel_patient.stt --download` fetches the model once.
- `tts.py` (VC-01, VC-07): one `Speaker` interface with macOS `say` (default) and Piper (`PATIENT_TTS_ENGINE`), returning WAV, with a slower rate option.
- `filter.py` (PV-01): Presidio with spaCy `en_core_web_lg` plus regex patterns. It replaces names, addresses, phones, emails, dates of birth, places and ID numbers with placeholders, and keeps symptom, severity and relative-time words.
- `extract.py` (PV-02, SE-01):
  - Ollama `llama3.2:3b` on loopback only, with JSON-schema output limited to the term list in `schema/terms.json`.
  - Unknown terms map to `SE_OTHER_REVIEW`.
  - Severity is None when not stated (VC-10).
- `survey.py`: today's questions from `survey_cache`, or the contract's example survey until A4.
- Endpoints:
  - `GET /checkin/question` and `GET /checkin/question/audio`: the question as text and as local speech.
  - `POST /checkin/turn`: raw audio from localhost only; returns the transcript and coded symptoms. The model sees only the filtered text.
- At startup, the runtime refuses a non-loopback model host and pre-loads the filter.
- Tests: `test_voice.py`, `test_filter.py`, `test_extract.py` (including live Ollama cases) and `test_checkin_api.py`; 231 runtime tests in total.
- Dependencies: `faster-whisper`, `presidio-analyzer`, `presidio-anonymizer`, `ollama`, `en-core-web-lg` 3.8.0 (pinned wheel).

### Changed
- Import guard: `huggingface_hub` and `ollama` are now on the network list; `ollama` is allowed only in `extract.py`.
- Seeding test: expectations now come from `schema/demo_fixtures.json` for every device profile, instead of hard-coded values; Priya's fixture changed in PR #11.
- `README.md` and `CLAUDE.md`: setup steps for the models, plus how to run the leakage eval and the patient screen.

## 2026-11-07: Task A1, runtime skeleton (branch `patient/feat/runtime-skeleton`)

### Added
- `pyproject.toml` and `uv.lock`: package `sentinel_patient` with FastAPI, uvicorn and `sentinel-contract` as an editable path dependency on `../../packages/contract-py`.
- `sentinel_patient/main.py`: FastAPI app for port 8001; `GET /health` reports `status`, `schema_version`, `patient_ref` and `profile_loaded` from local state only (no network). CORS allows patient-web (`localhost:5173`, `127.0.0.1:5173`).
- `sentinel_patient/db.py` (contract 2.0): creates `var/patient/patient.db` on startup by applying `schema/patient.sql` (safe to re-run) and writes `schema_meta`. On first launch only, seeds the profile, consent, emergency organizations and emergency contacts (labels kept local) from `schema/demo_fixtures.json`; Walter `pt_4b82d0c6` is the default. Refuses to start on a database created for another schema version.
- `sentinel_patient/config.py`: settings from `SENTINEL_ACTOR_ID`, `SENTINEL_BASE_URL`, `PATIENT_DB_PATH`, `PATIENT_ALLOWED_ORIGINS`.
- Placeholder modules (docstring only): `stt`, `tts`, `rating`, `filter`, `extract`, `egress_gate`.
- `tests/test_runtime.py`: health, schema tables, seeding (with and without emergency consent), re-run without reseeding, schema-version guard, CORS, and a guard that only `egress_gate.py` imports `sentinel_contract.client` or any HTTP library.
- `SESSION.md`: running session log.

### Changed
- `CLAUDE.md` owner notes: update `CHANGELOG.md` and `SESSION.md` after every task; edit scope; run and check commands.
- `README.md`: run and check commands.
