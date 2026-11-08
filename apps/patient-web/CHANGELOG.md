# Changelog: apps/patient-web

Changes in this app, newest first. Owned by this app's owner (root `CLAUDE.md`).

## 2026-11-07
- Added: Vite + React + TypeScript app `@sentinel/patient-web` on 127.0.0.1:5173 (strict port), plain CSS, system fonts.
- Added: first check-in screen for Walter: Start check-in (unlocks audio), question in large text spoken by the runtime's local text-to-speech, "Hear it again" and "Slower" (VC-07), full-width tap-to-start/tap-to-stop push-to-talk with no silence cut-off (VC-03), "You said" and symptoms "Noted for review", Next question, closing "Thank you" screen. Text 24 px and up, question 36 px and up, tap targets 64 px and up, visible focus outlines (NF-08, NF-09).
- Added: runtime client for `GET /checkin/question`, `GET /checkin/question/audio`, `POST /checkin/turn` (raw MediaRecorder blob, WebM/Opus or MP4); plain-words errors for a blocked microphone, runtime not running, speech model missing and audio not understood.
- Added: vitest checks: static privacy scan of `src/` (no Web Speech API, no browser storage, no URL but the runtime), API client and recording-format tests. Built pages carry a Content-Security-Policy limited to this page and the runtime.
