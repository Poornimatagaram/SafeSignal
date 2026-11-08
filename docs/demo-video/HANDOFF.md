# Demo video handoff

Read this first in a new session. It says where the demo videos stand and how to carry on. Rewritten 2026-11-08 after Video 2 was finished (ten scenes, narration only). Branch `company/docs/demo-video-script` (not pushed, no pull request yet). Video 1 scenes 4-7, all of `video-2/` and the doc edits are NOT committed yet (see Open items).

## The goal

Three pieces for the HACK1984 demo (the slot is about 3 minutes in total):

1. **Video 1, the problem (61.5 s, animated 2D stick figures).** Patient, doctor and company are each failing quietly; a daily check-in plus a 1-2-3 missed-day safety net fixes that. Finished.
2. **Video 2, the story (73.1 s, animated).** One morning end to end: 9 a.m. notification, type or speak (Priya types on the left, Walter speaks on the right), only coded fields leave the phone, company dashboard, sealed copy to the doctor, the visit, then three closing scenes (Walter looked after, doctor and company benefit, SafeSignal logo). Finished.
3. **Piece 3 (about 60 s, recorded by the owner on the real apps).** Shot list and closing points are in the script. The owner writes the closing lines.

**The script is approved and is the source of truth: `docs/demo-video-script.md`** (scene tables including the closing scenes, narration, on-screen text, claims to avoid, decisions table). Facts behind it: `docs/privacy-measures.md`, `docs/DECISIONS.md`, `docs/scoping-document.md`. No market numbers in these videos, by decision.

## Decisions already made (do not reopen)

- 2D stick figures with soft depth (parallax layers, drop shadows, slow camera drift). Palette: the company portal's "Clinical Mist" (`docs/design/company-web-ui.md`): ink `#13233A`, teal `#0E7C7B`, porcelain `#F6F8FA`, butter `#FBF0CF`, signal `#C2410C` (missed-day alerts only). Font Montserrat. Labels are at least 28 px.
- Characters: Walter (92, grey hair, glasses, teal cardigan), Priya (58, types), Anna (caregiver), Dr. Shah (dark hair, glasses, white coat, stethoscope), Dr. Lee (company).
- Voice: Kokoro (local, free), a 60/40 blend of `af_heart` and `af_nicole`, speed 0.95, same for both videos. Pauses are set by us: sentence-end mode by default (comma 0.30 s, colon/semicolon 0.40, dash 0.35, period/exclamation 0.60, question 0.65, ellipsis 0.90, line break 1.0 s, `[pause N]` exact). `--split clause` adds pauses at commas.
- **Narration only: no music, no sound effects** in either video (script decision 6).
- The owner wants control of every element: show results and ask before moving on, one scene at a time.
- Missed-day alerts are shown as notifications (real calls and texts are version 1). Emergency contact is a checklist (a person you trust such as mother or father, a hospital or clinic, emergency services). Never say it calls 911, never say "the only", never say data is encrypted at rest.
- Video 2 closing scenes (script decision 7): Walter looked after, split screen doctor/company, logo close with Video 1's tagline repeated on purpose.

## State of Video 1 (`docs/demo-video/video-1/`): finished

Seven scenes, 61.5 s, 1.5 s over the 60 s target. Scenes: 1 Walter and the pill bottle, 2 rash/form/bubble and padlock/calendar, 3 doctor's ten minutes, 4 drug company (thin, late, unstructured), 5 "what if someone simply checked in", 6 the 1-2-3 escalation ladder, 7 title card. Latest render: `video-1/renders/video-1-narration-only.mp4`. To reach 60 s: shorten pauses first (`--scale 0.8`, options of `tools/narrate.py`, passed through `build_narration.py`), then words. The owner may still ask for changes to any scene.

## State of Video 2 (`docs/demo-video/video-2/`): finished

Ten scenes, 73.1 s. Narration text is in `video-2/narration.json` (scenes `s1`..`s10`); scene lengths are in the comment and host `data-duration` values of `video-2/index.html`. Latest render: `video-2/renders/video-2-full-narration-only.mp4`.

| Scene | Time | What it shows |
| --- | --- | --- |
| 1 | 0.0-6.2 s | Bedroom sunrise, clock to 9:00, phone card "Good morning, Walter." Tag "9:00 AM" |
| 2 | 6.2-10.6 s | Split screen: Priya types (small, dimmed), Walter speaks (large, bright), camera drifts to him. Tag "Type or speak" |
| 3 | 10.6-19.8 s | Question card, waveform, transcript on the phone, padlock "Stays on this phone" |
| 4 | 19.8-27.8 s | Name and place blocked out, summary "Rash, moderate, 1-3 days ago", Walter taps Share. Tag "He approves every send" |
| 5 | 27.8-39.2 s | Padlock over transcript and mic, coded JSON card (real schema fields) flies out, "No audio / words / name" struck out, receipt with hash. Pills "Stays: everything he said", "Leaves: coded fields" |
| 6 | 39.2-45.3 s | Halvaren Therapeutics dashboard: bars, trend, cohort tiles, "Under 5 hidden", Dr. Lee nods. Tag "Patterns, not people" |
| 7 | 45.3-57.4 s | Sealed envelope from phone to Northgate, cut to the cabin: Walter walks in and sits, "Walter's weeks" timeline, suggested question "Where did the rash start?", Walter points to his arm, both smile |
| 8 | 57.4-61.0 s | Walter in an armchair, ticks fill in, Anna's message "Thinking of you". Tag "Looked after" |
| 9 | 61.0-68.1 s | Split: Dr. Shah "More time to guide" (left), Dr. Lee "Earlier signals" (right) |
| 10 | 68.1-73.1 s | SafeSignal mark, name, tagline, round portraits of Walter, Dr. Shah, Dr. Lee on a dotted ring |

## Time budget: open

Video 1 (61.5 s) + Video 2 (73.1 s) + Piece 3 (about 60 s) is about 195 s, about 15 s over the 3-minute slot (script decision 8, open). Options: Video 1 to 60 s, tighter pauses on both (`--scale 0.85`, saves a few seconds), a shorter Piece 3, or trimming a Video 2 scene. Ask the owner which.

## How the project works

- Each video is a HyperFrames project (HTML composition rendered to video): `docs/demo-video/video-N/`. `index.html` mounts each scene as a sub-composition from `compositions/scene-N.html`. All ids and classes inside scene N are prefixed `sN-` so scenes cannot clash. Each scene's script is wrapped in an IIFE and registers its own timeline `window.__timelines["scene-N"]`. Start a new scene by copying `compositions/scene-7.html` of Video 1 (simplest), `scene-3.html` of Video 1 (camera moves), or `scene-2.html` of Video 2 (split screen).
- **Narration drives timing.** `narration.json` holds the narration text per scene. Rebuild audio and cue files with (from the repo root):
  ```bash
  docs/demo-video/tools/.venv/bin/python docs/demo-video/tools/build_narration.py docs/demo-video/video-2 [s2 s3]
  ```
  (add `--voice af_heart --speed 0.92` and so on to change the voice; names after the project path select scenes). It writes `assets/audio/sN-narration.wav` and `sN-narration.cues.json/.js` (sentence start and end times). The `.wav` files are gitignored; they are rebuilt from `narration.json`.
- Each scene loads its cues (`window.NARRATION_SN`, script tag in `index.html`) and places its beats from sentence times, so a new voice or pace re-times the scene. After a rebuild, read the printed durations and update, in `index.html`, each scene host's `data-duration` and `data-start`, the root `data-duration`, and the scene's `SCENE_LEN` constant (it warns in the console if narration is longer). Scene length is narration start (about 0.4 s) + narration duration + about 0.2 s (more for a closing beat).
- To add a scene: add its text to `narration.json`, run the build, add `<script src="assets/audio/sN-narration.cues.js">` and a host `<div id="scene-N-host" data-composition-id="scene-N" data-composition-src="compositions/scene-N.html" data-start=... data-duration=...>` to `index.html`, and write the scene.
- Commands (from `docs/demo-video/video-N/`): `npm run check` (must pass; layout notices from camera zooms are expected), `npx --yes hyperframes@0.9.22 snapshot --at <seconds,...>` (times are on the root timeline, not the scene's; then read the contact sheet), `npx --yes hyperframes@0.9.22 render -o renders/<name>.mp4`. Always run check, look at snapshots, then render a preview and send it; ask the owner before building the next scene.
- If the narration tool's Python environment is missing: `uv venv docs/demo-video/tools/.venv --python 3.12 && uv pip install --python docs/demo-video/tools/.venv/bin/python kokoro-onnx soundfile`. The Kokoro model downloads on first use to `~/.cache/hyperframes/tts/`; fonts cache to `~/.cache/hyperframes/fonts/`.
- Design hook: it flags `overflow: hidden` on scene roots (the video frame crop, a false positive) and the Montserrat font (a bundled, non-banned family). Both have ignores recorded with `impeccable hooks ignore-value` in `.impeccable/config.json` (gitignored): the font ignore is global, the overflow ignore is file-scoped, so add one for each new scene file (reason: fixed video frame, overflow hidden is the canvas crop).
- Camera helper: with `transformOrigin: "0 0"`, `x = 960 - s*Px`, `y = 540 - s*Py`, `scale = s` centres the world point (Px, Py).

## Open items

- **Time budget** (above): the owner decides how to bring the three pieces to about 180 s.
- **Piece 3** (about 60 s) is recorded by the owner on the real apps; its shot list is in the script section 6, the closing lines are the owner's.
- **Git:** committed so far: the script, privacy audit and scenes 1-3 of Video 1. Uncommitted: Video 1 `compositions/scene-4..7.html`, `assets/audio/s4..s7-narration.cues.*`, edits to its `index.html` and `narration.json`; all of `docs/demo-video/video-2/` (untracked); this file and `docs/demo-video-script.md`. `video-N/renders/*.mp4`, `.hyperframes/` and `assets/audio/*.wav` must not be committed. Commit only when the owner asks; publish per `CONTRIBUTING.md` (push the branch, open a pull request). Check `git status` first.
- The four project docs (memory note "Four project docs": CLAUDE.md, DECISIONS, SESSION_LOG, CHANGELOG) were updated only partly in this video work; ask the owner before editing root files. `CHANGELOG.md` and `docs/SESSION_LOG.md` already have uncommitted edits from earlier.
- Also written earlier: `docs/privacy-measures.md` (the privacy audit).

## Lessons (save time)

- Scene layout: the corner label (`#sN-tag`, left 120 px, top 108 px, 60 px type) collides with anything placed above y 190 and with a head near y 200; lower the camera or move the content. Check every snapshot for overlap, clipped text and badges covered by other shapes before rendering.
- Text is at least 28 px. A dimming overlay or a foreground plant can push a label under the contrast threshold; put labels above the dim layer and drop the foreground plant where it covers them.
- A closing line needs at least 2 s on screen (the check warns otherwise).
- For SVG groups drawn inside a transformed wrapper `<g transform=...>`, GSAP `svgOrigin` uses root coordinates, so compute the pivot in root space; rotating an arm about a computed pivot inside a shifted group went wrong once (Video 2 scene 9), so prefer a small translate for gestures there.
- The checker flags text hidden behind another element as an overlap; reveal things with an animated `clipPath` height (receipt printing in scene 5) instead of sliding them out from behind a card.
- macOS `sed -i` needs `''`; prefer the Edit tool or Python for edits.
- `npx --yes hyperframes@0.9.22 render` takes about 40-60 s per 60 s of video.
