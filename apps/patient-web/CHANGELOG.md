# Changelog: apps/patient-web

Changes in this app, newest first. Owned by this app's owner (root `CLAUDE.md`).

## 2026-11-08
- Added: approve-before-share (PV-04). "Start check-in" opens a runtime session (`POST /checkin/sessions`; 503 says in plain words that today's questions were never downloaded) and every answer carries its `session_id`. After the last question the screen shows "Your summary" (`GET /checkin/sessions/{id}/summary`): each problem with how bad and when it started ("today", "1 to 3 days ago", … "start not known"), marked "For review", never as a cause; "You did not report any new problems." when empty; "How bad is the …?" with Mild / Moderate / Severe for any missing severity (choice shown with a tick and words).
- Added: "What will be shared": destination, coded answers only ("no name, no words you said, no recording"), a plain list built from the field names, and a "Show exactly what is sent" toggle with the field names and the record JSON.
- Added: one full-width "Share this" button, disabled until every severity is chosen, the only path to `POST /checkin/sessions/{id}/approve`; "Not now" ends with "Nothing was shared." and a way back to the summary.
- Added: egress receipt (PV-05): status in plain words (Shared / Saved on this device, sent when back online / Not accepted), destination, local time, record number, every field sent and the full `payload_sha256` fingerprint; then "Thank you, that's all for today."
- Added: plain-words errors for an unknown session (Start again), an already shared check-in, a missing severity (409), a record refused by the contract check (422) and a runtime that is not answering (sharing again never sends twice).
- Added: `src/shareFlow.ts` state machine (no React), `src/ShareScreen.tsx`, `src/summaryText.ts`; tests for the new API calls, a mocked end-to-end check that no approve request is made before the tap (plus a static check that only `share()` calls it), and server-rendered view tests. Vitest now also runs `tests/**/*.test.tsx`.

## 2026-11-07
- Added: Vite + React + TypeScript app `@sentinel/patient-web` on 127.0.0.1:5173 (strict port), plain CSS, system fonts.
- Added: first check-in screen for Walter: Start check-in (unlocks audio), question in large text spoken by the runtime's local text-to-speech, "Hear it again" and "Slower" (VC-07), full-width tap-to-start/tap-to-stop push-to-talk with no silence cut-off (VC-03), "You said" and symptoms "Noted for review", Next question, closing "Thank you" screen. Text 24 px and up, question 36 px and up, tap targets 64 px and up, visible focus outlines (NF-08, NF-09).
- Added: runtime client for `GET /checkin/question`, `GET /checkin/question/audio`, `POST /checkin/turn` (raw MediaRecorder blob, WebM/Opus or MP4); plain-words errors for a blocked microphone, runtime not running, speech model missing and audio not understood.
- Added: vitest checks: static privacy scan of `src/` (no Web Speech API, no browser storage, no URL but the runtime), API client and recording-format tests. Built pages carry a Content-Security-Policy limited to this page and the runtime.
