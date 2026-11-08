# Patient screen

- **Owner:** Patient side (see `CODEOWNERS`)
- **Package name:** `@sentinel/patient-web`
- **Port:** 5173 (host 127.0.0.1, strict port; the runtime's CORS allows only this origin)
- **Runtime data:** none (talks only to patient-runtime on localhost)
- **Contract:** read `schema/`; never edit it. Hashing and types come from `packages/` (see the root README).
- **Agent instructions:** `CLAUDE.md` in this folder; it imports the brief `docs/briefs/patient-web.md` (company-maintained) and holds your own notes. `AGENTS.md` points to both.
- **Service status:** `docs/INTEGRATION_STATUS.md` · **Demo IDs:** `schema/demo_fixtures.json`
- **Original brief:** Scoping Doc 26.14, Patient layer brief. Paths in that brief map to this repo as: `web/patient/` → `apps/patient-web/`.

Structure inside this folder is up to its owner.

## Run

Needs Node 22 and npm 10. Start the patient runtime first (`apps/patient-runtime`, port 8001).

```sh
npm ci
npm run dev       # http://127.0.0.1:5173
npm test          # vitest: privacy scan, API client, recording format
npm run build     # tsc -b + vite build into dist/
```

| Variable | Default | Meaning |
| --- | --- | --- |
| `VITE_PATIENT_RUNTIME_URL` | `http://127.0.0.1:8001` | The only server this screen talks to |

## What the screen does

Voice-first check-in for Walter (Scoping Doc 3.2, 9.2, 12.1; NF-08, NF-09):

1. **Start check-in**: one big button. The tap also unlocks audio playback.
2. Each question is shown in large text and spoken by the runtime's local text-to-speech. **Hear it again** and **Slower** replay it (VC-07).
3. **Tap to answer** starts recording; **Listening… tap when you're done** stops it. It is a toggle, not a hold, and pauses never end the answer (VC-03).
4. The recording goes only to the runtime. The screen shows **You said: …** and any symptoms as **Noted for review** (never as a cause).
5. **Next question** until the end: "Thank you, that's all for today."

Runtime calls (all in `src/api.ts`):

| Call | When |
| --- | --- |
| `GET /checkin/question?index=N&ask=0` | Each question (404 = no more questions) |
| `GET /checkin/question/audio?index=N&ask=0&slow=false\|true` | Speak it; replay or slower |
| `POST /checkin/turn?question_id=qN&ask=0` (body: the recording, `Content-Type` = its type) | Each answer |

## Privacy rules (checked by `tests/privacy.test.ts`)

- No Web Speech API (speech recognition or browser voices): audio and voices can go to the cloud.
- No browser storage of any kind; the transcript lives in memory until the next question.
- No URL other than the runtime; `fetch` only in `src/api.ts`. Built pages also carry a Content-Security-Policy that allows connections only to this page and the runtime.
- No analytics, tracking, error reporting, CDN fonts or scripts. System fonts only.
