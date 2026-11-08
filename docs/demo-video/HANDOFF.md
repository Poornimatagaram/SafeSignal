# Demo video handoff

Read this first in a new session. It says where the demo videos stand and how to carry on. Written 2026-11-08 at the end of scene 3 of Video 1. Committed on branch `company/docs/demo-video-script` (two commits, not pushed, no pull request yet).

## The goal

Three pieces for the HACK1984 demo (the slot is about 3 minutes in total):

1. **Video 1, the problem (60 s, animated 2D stick figures).** Patient, doctor and company are each failing quietly; a daily check-in plus a 1-2-3 missed-day safety net fixes that.
2. **Video 2, the story (60 s, animated).** One morning end to end: 9 a.m. notification, type or speak (two patients side by side, Priya types on the left, Walter speaks on the right, the focus is on the speaker), only coded fields leave the phone, company dashboard, sealed copy to the doctor, the visit.
3. **Piece 3 (about 60 s, recorded by the owner on the real apps).** Shot list and closing points are in the script. The owner writes the closing lines.

**The script is approved and is the source of truth: `docs/demo-video-script.md`** (scene tables, narration, on-screen text, sound cue IDs, claims to avoid, decisions table). Facts behind it: `docs/privacy-measures.md`, `docs/DECISIONS.md`, `docs/scoping-document.md`. No market numbers in these videos, by decision.

## Decisions already made (do not reopen)

- 2D stick figures with soft depth (parallax layers, drop shadows, slow camera drift). Palette: the company portal's "Clinical Mist" (`docs/design/company-web-ui.md`): ink `#13233A`, teal `#0E7C7B`, porcelain `#F6F8FA`, butter `#FBF0CF`, signal `#C2410C` (missed-day alerts only). Font Montserrat. Labels are at least 28 px.
- Characters: Walter (92, grey hair, glasses, teal cardigan), Priya (58, types), Anna (caregiver), Dr. Shah (dark hair, glasses, white coat, stethoscope), Dr. Lee (company).
- Voice: Kokoro (local, free), a 60/40 blend of `af_heart` and `af_nicole`, speed 0.95, same for both videos. Pauses are set by us, not the model: default is **sentence-end mode** (comma 0.30 s, colon/semicolon 0.40, dash 0.35, period/exclamation 0.60, question 0.65, ellipsis 0.90, line break 1.0 s, `[pause N]` exact). `--split clause` (pauses at commas too) is the fallback if time allows.
- Time budget: about 3 minutes in total. If a narration runs long, shorten pauses first, then words.
- The owner wants control of every element, including sound effects: show results and ask before moving on, one scene at a time.
- Missed-day alerts are shown as notifications (real calls and texts are version 1). Emergency contact is a checklist (a person you trust such as mother or father, a hospital or clinic, emergency services). Never say it calls 911, never say "the only", never say data is encrypted at rest.

## State of Video 1 (`docs/demo-video/video-1/`)

| Scene | Time | Status |
| --- | --- | --- |
| 1. Walter, the pill bottle | 0.0-6.0 s | Built |
| 2. Rash, form, bubble and padlock, calendar | 6.0-16.2 s | Built |
| 3. Doctor's ten minutes, "Fine.", forgetting, blank page | 16.2-28.9 s | Built (wording changed once: now includes "He's forgotten how he felt two months ago. So the months in between stay blank.") |
| 4. Drug company: thin, late, unstructured signal | | **Next.** Script row 4 in `docs/demo-video-script.md` section 3 (Dr. Lee, dashboard with a thin dotted line and a "late" tag, scraps of paper arriving) |
| 5. "What if someone simply checked in, every day" (calendar fills with teal ticks) | | To build |
| 6. The 1-2-3 escalation ladder with the emergency-contact checklist | | To build |
| 7. Title card "SafeSignal. Someone is looking out for you." | | To build |

Total so far 28.9 s; the narration for the whole video measures about 54 s, so the finished video should be about 58-60 s (not yet confirmed). Video 2 and the recorded piece are not started. The owner can change wording of any scene; scene 3's wording was changed after the script was approved, and the script row was updated.

## How the project works

- Project: `docs/demo-video/video-1/` (HyperFrames: HTML composition rendered to video). `index.html` mounts each scene as a sub-composition from `compositions/scene-N.html`. All ids and classes inside scene N are prefixed `sN-` so scenes cannot clash. Each scene's script is wrapped in an IIFE and registers its own timeline `window.__timelines["scene-N"]`. Start a new scene by copying the structure of `compositions/scene-3.html`.
- **Narration drives timing.** `video-1/narration.json` holds the narration text per scene. Rebuild audio and cue files with:
  ```bash
  docs/demo-video/tools/.venv/bin/python docs/demo-video/tools/build_narration.py docs/demo-video/video-1 [s2 s3]
  ```
  (add `--voice af_heart --speed 0.92` and so on to change the voice; names after the project path select scenes). It writes `assets/audio/sN-narration.wav` and `sN-narration.cues.json/.js` (sentence start and end times). The `.wav` files are gitignored; they are rebuilt from `narration.json`.
- Each scene loads its cues (`window.NARRATION_SN`, script tag in `index.html`) and places its beats from sentence times, so a new voice or pace re-times the scene. After a rebuild, read the printed durations and update, in `index.html`, each scene host's `data-duration` and the root `data-duration`, and the scene's `SCENE_LEN` constant (it warns in the console if narration is longer). Scene length is narration start (about 0.4 s) + narration duration + about 0.2 s.
- To add a scene: add its text to `narration.json`, run the build, add `<script src="assets/audio/sN-narration.cues.js">` and a host `<div id="scene-N-host" data-composition-id="scene-N" data-composition-src="compositions/scene-N.html" data-start=... data-duration=...>` to `index.html`, and write the scene.
- Commands (from `docs/demo-video/video-1/`): `npm run check` (must pass; 3 audio-basis warnings and layout notices from camera zooms are expected), `npx --yes hyperframes@0.9.22 snapshot --at <seconds,...>` (then read the contact sheet), `npx --yes hyperframes@0.9.22 render -o renders/<name>.mp4`. Always run check, look at snapshots, then render a preview and send it; ask the owner before building the next scene.
- If the narration tool's Python environment is missing: `uv venv docs/demo-video/tools/.venv --python 3.12 && uv pip install --python docs/demo-video/tools/.venv/bin/python kokoro-onnx soundfile`. The Kokoro model downloads on first use to `~/.cache/hyperframes/tts/`; fonts cache to `~/.cache/hyperframes/fonts/`.
- Design hook: it keeps flagging `overflow: hidden` on scene roots (it is the video frame crop, a false positive) and the Montserrat font (a bundled, non-banned family). Both have file-scoped or value ignores recorded with `impeccable hooks ignore-value` in `.impeccable/config.json` at the repo root and in `docs/demo-video/video-1/`; add the same ignore for each new scene file (reason: fixed video frame, overflow hidden is the canvas crop). Those configs are gitignored.
- Camera helper used in scenes 2 and 3: with `transformOrigin: "0 0"`, `x = 960 - s*Px`, `y = 540 - s*Py`, `scale = s` centres the world point (Px, Py).

## Open items

- **Music and sound effects** are not added. Cue IDs are in the script (section 2). Sources: free local generation, or the HeyGen catalogue (needs a sign-in; the `heygen` command is not installed). Ask the owner which route; add them once all scenes exist. Scene 1 leaves about 1.3 s of silence between scenes for transition sounds.
- Video 2 narration and scenes, and piece 3 (the owner records it).
- Git: the script, the privacy audit and the project are committed on `company/docs/demo-video-script` (cut from `origin/main` on 2026-11-08, not pushed). `docs/demo-video/video-1/renders/*.mp4` and `.hyperframes/` are untracked and not gitignored; do not commit them. To publish: push the branch and open a pull request per `CONTRIBUTING.md` (only when the owner asks). Work on later scenes can continue on this branch.
- Also written in this session: `docs/privacy-measures.md` (the privacy audit).
