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
npm test          # vitest: privacy scan, API client, approve-before-share, summary and receipt views, recording format
npm run build     # tsc -b + vite build into dist/
```

| Variable | Default | Meaning |
| --- | --- | --- |
| `VITE_PATIENT_RUNTIME_URL` | `http://127.0.0.1:8001` | The only server this screen talks to |

## What the screen does

Voice-first check-in for Walter (Scoping Doc 3.2, 9.2, 12.1; NF-08, NF-09):

1. **Start check-in**: one big button. The tap also unlocks audio playback and opens today's check-in session.
2. Each question is shown in large text and spoken by the runtime's local text-to-speech. **Hear it again** and **Slower** replay it (VC-07).
3. **Tap to answer** starts recording; **Listening… tap when you're done** stops it. It is a toggle, not a hold, and pauses never end the answer (VC-03).
4. The recording goes only to the runtime. The screen shows **You said: …** and any symptoms as **Noted for review** (never as a cause).
5. **Next question** until the end, then **Your summary** (PV-04): each problem with how bad and when it started, marked **For review**; **How bad is the …?** with Mild / Moderate / Severe for any problem without a severity; **What will be shared** (destination, coded answers only, and a **Show exactly what is sent** toggle with the field names and the record JSON).
6. **Share this** is the only thing that sends, and it stays disabled until every severity is chosen. **Not now** ends with "Nothing was shared." (and a way back to the summary).
7. After the tap, the **receipt** (PV-05): Shared / Saved on this device / Not accepted, destination, local time, every field sent and the full fingerprint (`payload_sha256`). Then "Thank you, that's all for today."

Runtime calls (all in `src/api.ts`):

| Call | When |
| --- | --- |
| `POST /checkin/sessions` (no body) | **Start check-in** (503 = today's questions were never downloaded) |
| `GET /checkin/question?index=N&ask=0` | Each question (404 = no more questions) |
| `GET /checkin/question/audio?index=N&ask=0&slow=false\|true` | Speak it; replay or slower |
| `POST /checkin/turn?session_id=ses_…&question_id=qN&ask=0` (body: the recording, `Content-Type` = its type) | Each answer (404 unknown session, 409 already shared) |
| `GET /checkin/sessions/{id}/summary` | After the last question; sends nothing |
| `POST /checkin/sessions/{id}/approve` (`{"severities": {...}}`) | **Only** on the **Share this** tap (409 = a severity is missing); returns the receipt |

The approval flow is a small state machine in `src/shareFlow.ts` (no React); its `share()` is the only code that calls `approve`, and `tests/approval.test.ts` checks that no approve request is made before it.

## Privacy rules (checked by `tests/privacy.test.ts`)

- No Web Speech API (speech recognition or browser voices): audio and voices can go to the cloud.
- No browser storage of any kind; the transcript lives in memory until the next question.
- Nothing leaves this computer until the patient taps **Share this** (`tests/approval.test.ts`).
- No URL other than the runtime; `fetch` only in `src/api.ts`. Built pages also carry a Content-Security-Policy that allows connections only to this page and the runtime.
- No analytics, tracking, error reporting, CDN fonts or scripts. System fonts only.
