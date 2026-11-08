---
workflow: general-video
flow: companion
storyboard: no
message: "Nobody is checking on Walter. SafeSignal makes sure someone is looking out for him."
destination: demo
aspect: 1920x1080
language: en
length: 60s
angle: story
---

## Intent

Video 1 of 2 for the SafeSignal hackathon demo (the demo slot is about 3 minutes in total, so this one is 60 s). The problem from three sides (patient, doctor, company), then the daily check-in with a 1-2-3 missed-day safety net. Warm, calm, people first; 2D stick figures with soft depth. Full script and timings: `docs/demo-video-script.md` section 3 (Video 1).

## Assets

- `assets/audio/s1-narration.wav` — scene 1 narration (Kokoro, Heart+Nicole blend, sentence-end pauses), 5.24 s, with `s1-narration.cues.json` / `.cues.js` (sentence times; scenes place their beats from these).
- `assets/audio/s2-narration.wav` — scene 2 narration, 9.62 s, with its cue files.

## Scenes built so far

- Scene 1, 0.0-6.0 s: `compositions/scene-1.html` (Walter, the pill bottle).
- Scene 2, 6.0-16.2 s: `compositions/scene-2.html` (the rash, the form, the bubble and padlock, the calendar; tag "Patient: unheard").
- Scene 3, 16.2-26.6 s: `compositions/scene-3.html` (Dr. Shah's ten minutes, "How have you been?" / "Fine.", the chart with the empty stretch, a blank page; tag "Doctor: a blank page"). Narration `assets/audio/s3-narration.wav`, 9.85 s.
- `index.html` mounts the scenes as sub-compositions. Scene lengths follow the narration: when a narration changes length, update the host `data-duration` and the root `data-duration` there.

## Customizations

- Narration is generated with `docs/demo-video/tools/narrate.py` (sentence-end mode by default; `--split clause` also pauses at commas).
- Palette from the company portal's "Clinical Mist" (`docs/design/company-web-ui.md`): ink `#13233A`, teal `#0E7C7B`, line `#E3E9F0`, porcelain `#F6F8FA`, butter `#FBF0CF`, signal `#C2410C` (missed-day alerts only).

## Notes

- Scene lengths follow the narration, not the other way round.
- Music and sound effects (cue IDs in the script, section 2) are not added yet; scene 1 has narration only.
- No real people, patient data or company names. Walter, Anna, Dr. Shah and Dr. Lee are fictional.
