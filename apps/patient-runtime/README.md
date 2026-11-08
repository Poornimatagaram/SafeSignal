# Patient runtime (on-device)

- **Owner:** Patient side (see `CODEOWNERS`)
- **Package name:** `sentinel_patient`
- **Port:** 8001
- **Runtime data:** `var/patient/patient.db` from `schema/patient.sql`
- **Contract:** read `schema/`; never edit it. Hashing and types come from `packages/` (see the root README).
- **Agent instructions:** `CLAUDE.md` in this folder; it imports the brief `docs/briefs/patient-runtime.md` (company-maintained) and holds your own notes. `AGENTS.md` points to both.
- **Service status:** `docs/INTEGRATION_STATUS.md` · **Demo IDs:** `schema/demo_fixtures.json`
- **Original brief:** Scoping Doc 26.14, Patient layer brief. Paths in that brief map to this repo as: `device_runtime/` → `apps/patient-runtime/`; `clients/sentinel_client.py` → `from sentinel_contract.client import SentinelClient`; `device_runtime/egress_gate.py` → `apps/patient-runtime/sentinel_patient/egress_gate.py`.

Structure inside this folder is up to its owner.

**Demo day:** start commands, ports, settings and the morning checklist are in [`DEMO.md`](DEMO.md).

## Setup (once, needs the network; check-ins never do)
```bash
cd apps/patient-runtime && uv sync                     # includes the spaCy model used by the filter
uv run python -m sentinel_patient.stt --download        # public Whisper base.en model into the local cache
ollama pull llama3.2:3b                                 # local model for extraction (Ollama must be installed and running)
```

## Run
```bash
cd apps/patient-runtime && uv run uvicorn sentinel_patient.main:app --port 8001   # http://127.0.0.1:8001/health
cd apps/patient-web && npm install && npm run dev                                 # http://127.0.0.1:5173
```
Settings:

| Variable | Default |
| --- | --- |
| `SENTINEL_ACTOR_ID` | Walter, `pt_4b82d0c6` |
| `SENTINEL_BASE_URL` | `http://127.0.0.1:8000` |
| `PATIENT_DB_PATH` | `var/patient/patient.db` |
| `PATIENT_ALLOWED_ORIGINS` | patient-web on port 5173 |
| `PATIENT_WHISPER_MODEL` | `base.en` |
| `PATIENT_TTS_ENGINE` | `say`, or `piper` with `PATIENT_PIPER_MODEL` |
| `PATIENT_TTS_VOICE` | system default voice |
| `PATIENT_OLLAMA_HOST` | `http://127.0.0.1:11434`; loopback only |
| `PATIENT_OLLAMA_MODEL` | `llama3.2:3b` |

The Sentinel service must be reachable for the first check-in, because that is when the survey and term list are downloaded. Check-ins after that work offline. For local testing, run `apps/service` on port 8000 (`docs/INTEGRATION_STATUS.md`).

## API (localhost only)
- `GET /health`
- `POST /checkin/sessions`: refreshes the survey and term list through the egress gate (the cache is kept when offline) and starts a check-in. Returns `{session_id, total}`; 503 if the questions were never downloaded.
- `GET /checkin/question?index=&ask=`: the question text, from the cached survey.
- `GET /checkin/question/audio?index=&ask=&slow=`: the question as WAV.
- `POST /checkin/turn?session_id=&question_id=&ask=`: send the raw audio body; returns `{transcript, symptoms, extraction, rating, next}`. `next` is `{action: "reask", ask, text}` or `{action: "next"}`, with `unanswered: true` after 2 re-asks.
- `GET /checkin/sessions/{id}/summary`: plain words, `needs_severity`, and the exact record that would be shared. Sends nothing.
- `GET /checkin/sessions/{id}/summary/audio`: the summary read aloud (template text, never model text).
- `POST /checkin/sessions/{id}/correction`: one change before sharing, as JSON `{term_code, severity|onset|remove}` or as a spoken recording.
- `GET /checkin/sessions/{id}/receipt`: the current receipt, so a queued record can be polled until the retry worker sends it.
- `POST /checkin/sessions/{id}/approve` with body `{"severities": {...}}`: the only route that sends. Returns the receipt: `{status, record_id, destination, method, url, fields_sent, payload_sha256, sent_at, response_code, alert}`. A severe symptom also queues a minimal alert, which is sent first. Queued items are retried automatically with backoff.

## Check
```bash
cd apps/patient-runtime && uv run pytest -q
cd ../.. && uv run --project apps/patient-runtime python evals/patient/leakage_eval.py   # PV-01 leakage eval; needs Ollama
uv run --project apps/patient-runtime python evals/patient/reask_eval.py                # VC-04 re-ask eval (target 16 of 20)
uv run --project apps/patient-runtime pytest -q evals/patient
npm test --prefix apps/patient-web
```
