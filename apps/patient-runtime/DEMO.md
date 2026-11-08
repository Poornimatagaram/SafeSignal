# Patient side: demo guide

For the team on demo day. It covers how to start the patient side (runtime and screen) against the Sentinel service, which ports and settings it uses, and a checklist for the morning of the demo. Everything here is synthetic: Walter (`pt_4b82d0c6`) is a demo patient.

## What runs where

| Piece | Folder | Port | Who calls it |
| --- | --- | --- | --- |
| Sentinel service (company) | `apps/service` | 8000 | the patient runtime's egress gate, doctor-web, company-web |
| **Patient runtime** | `apps/patient-runtime` | **8001** (binds 127.0.0.1) | only the patient screen on this computer |
| **Patient screen** | `apps/patient-web` | **5173** | Walter, in the browser |
| Doctor view | `apps/doctor-web` | 5174 | Dr. Patel, Dr. Okafor |
| Company portal | `apps/company-web` | 5175 | the safety team |
| Ollama (local model) | installed app | 11434 (loopback only) | the patient runtime's `extract.py` only |

Speech-to-text (faster-whisper `base.en`), text-to-speech (macOS `say`, gentle rate), the personal-data filter and the extraction model all run on this computer. The only network traffic leaving the patient side goes through the egress gate to port 8000. The screen's "What this computer sent" page lists every such request.

## Start commands

Run each in its own terminal, from the repository root.

```bash
# 1. Sentinel service (company owner's app; the patient side needs it for the first check-in and for sharing)
(cd apps/service && uv run uvicorn sentinel_service.main:app --port 8000)

# 2. Local model (if Ollama isn't already running as an app)
ollama serve

# 3. Patient runtime
(cd apps/patient-runtime && uv run uvicorn sentinel_patient.main:app --port 8001)

# 4. Patient screen
(cd apps/patient-web && npm run dev)            # http://127.0.0.1:5173

# Doctor view, to show the sealed copies arriving
(cd apps/doctor-web && npm run dev)             # http://localhost:5174
```

Quick health checks:

```bash
curl -s 127.0.0.1:8000/healthz                  # {"status":"ok","contract_version":"<current>","seeded":true}
                                                # an older contract_version means a service started from old code
curl -s 127.0.0.1:8001/health                   # {"status":"ok","patient_ref":"pt_4b82d0c6","profile_loaded":true,...}
curl -s 127.0.0.1:11434/api/tags | grep llama3.2:3b
```

## Settings (environment variables)

Defaults are what the demo uses; you normally set nothing.

| Variable | Default | What it does |
| --- | --- | --- |
| `SENTINEL_ACTOR_ID` | `pt_4b82d0c6` (Walter) | the patient this device belongs to |
| `SENTINEL_BASE_URL` | `http://127.0.0.1:8000` | the Sentinel service |
| `PATIENT_DB_PATH` | `var/patient/patient.db` | local database. Drafts and retry state sit beside it in `var/patient/drafts/` and `var/patient/retry_state.json` |
| `PATIENT_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | which browser pages may call the runtime (CORS), comma-separated |
| `PATIENT_WHISPER_MODEL` | `base.en` | speech-to-text model, from local files only |
| `PATIENT_TTS_ENGINE` | `say` | `say` (macOS) or `piper` (with `PATIENT_PIPER_MODEL`, optionally `PATIENT_PIPER_BIN`) |
| `PATIENT_TTS_VOICE` | "Ava (Premium)", else "Samantha (Enhanced)", else the system default | a `say` voice name (`say -v '?'` lists them). Install Ava in System Settings → Accessibility → Spoken Content → Manage Voices |
| `PATIENT_OLLAMA_HOST` | `http://127.0.0.1:11434` | must be loopback; the runtime refuses to start otherwise |
| `PATIENT_OLLAMA_MODEL` | `llama3.2:3b` | extraction model |
| `VITE_PATIENT_RUNTIME_URL` | `http://127.0.0.1:8001` | (patient screen) where the runtime is |

**Origins:** the runtime accepts browser calls only from the origins in `PATIENT_ALLOWED_ORIGINS`, and audio only from this computer (loopback clients). If you open the screen on another host or port, add that origin, for example `PATIENT_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:4173` for `npm run preview`.

## Demo-morning checklist

Do these in order, about 30 minutes before the demo.

**The night before (needs the network, once):**
- [ ] `cd apps/patient-runtime && uv sync`, then `uv run python -m sentinel_patient.stt --download`, then `ollama pull llama3.2:3b`.
- [ ] `cd apps/patient-web && npm install`.

**Morning:**
1. [ ] **Pull `main`** and check you're on it: `git switch main && git pull`.
2. [ ] **Stop anything on the ports:** `lsof -nP -iTCP:8000,8001,5173,5174 -sTCP:LISTEN`. An old runtime on 8001 means the screen talks to old code, so stop it.
3. [ ] **Reset and seed the service.** This is the service owner's step; run it only if you are allowed to. Stop the service first, then run `scripts/reset_all.sh --seed`. This deletes `var/` (service and patient databases) and reseeds Walter's history up to yesterday. Live tests and rehearsals add synthetic records, envelopes, consent changes and throwaway org keys, so the morning reset is what makes the demo clean.
4. [ ] **Start the service, Ollama, the runtime and the screen** (commands above), then run the three health checks.
5. [ ] **Doctor side keys:** in doctor-web, Dr. Patel (Northgate admin) registers Northgate's care-team key and grants it to himself. Dr. Okafor does the same for Lakeside. Also clear doctor-web's site data after a reset, because the browser holds the keys. Until a key is registered, Walter's sealed copy shows "waiting for the hospital's lock" and is sent automatically later.
6. [ ] **Browser:** open http://127.0.0.1:5173 in Chrome, allow the microphone, and turn the volume up (questions are spoken). Check that the top bar says **Mute** (not Unmute). Walter can also type an answer in the box under the talk button.
7. [ ] **Rehearsal check-in** (one short check-in, then reset again if you want a clean list): say "I have an itchy rash on my arms", "moderate", "two days ago". Check the summary, tap **Share this**, and check that the receipt says Shared with a fingerprint. "What this computer sent" should list the record, the sealed copies and the two configuration downloads.
8. [ ] **Network-off moment (optional):** stop the service (Ctrl-C on port 8000) and do a check-in. The receipt says it is saved and will be sent automatically. Start the service again, and within a few seconds the receipt turns to Shared.
9. [ ] **Run the checks** if there's time: `cd apps/patient-runtime && uv run pytest -q` and `cd ../.. && uv run --project apps/patient-runtime python evals/patient/leakage_eval.py` (must say PASS).

**If something goes wrong:**
- **"today's questions have not been downloaded yet" (503):** the service wasn't reachable at the first check-in. Start it and tap Start again.
- **The runtime won't start, saying the database was created for another schema version:** stop it, delete `var/patient/patient.db` (synthetic data only) and start again.
- **The model is unavailable:** Ollama isn't running or the model isn't pulled (`ollama pull llama3.2:3b`).
- **Speech isn't recognized:** run `uv run python -m sentinel_patient.stt --download` once with the network on.
- **A sealed copy stays "waiting":** the hospital's key isn't registered (step 5), or the service is down. Nothing is lost; it is sent once the key exists.

## What never leaves the device

The recording, the transcript, Walter's own words, his name (except inside the sealed copies only his care team or emergency hospital can open), his date of birth, his phone, contact names and exposure descriptions. The company record carries coded fields and a random ID only. See the screen's "What this computer sent" page during the demo.
