---
workflow: general-video
flow: companion
storyboard: no
message: "Walter checks in by voice; only coded fields leave his phone, and his doctor gets a sealed copy."
destination: demo
aspect: 1920x1080
language: en
length: 60s
angle: story
---

## Intent

Video 2 of 2 for the SafeSignal hackathon demo (the slot is about 3 minutes in total, so this one is 60 s). One morning end to end: the 9 a.m. notification, type or speak (Priya types on the left, Walter speaks on the right, focus on Walter), only coded fields leave the phone, the company dashboard, the sealed copy to the doctor, the visit. Full script: `docs/demo-video-script.md` section 4. Handoff and lessons: `docs/demo-video/HANDOFF.md`.

## Customizations

- Same look and voice as Video 1: Clinical Mist palette, Montserrat, labels at least 28 px, Kokoro 60/40 `af_heart`/`af_nicole`, speed 0.95, sentence-end pauses. Narration only, no music or sound effects.
- Narration text is in `narration.json`; rebuild with `tools/build_narration.py`.

## Notes

- Scene lengths follow the narration (start about 0.4 s, plus narration, plus about 0.2 s).
- Claims to avoid: calls 911, "the only", "encrypted at rest". Groups under five are hidden. Everything is synthetic.
