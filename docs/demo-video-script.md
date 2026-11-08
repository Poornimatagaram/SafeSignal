# SafeSignal demo videos: script and production plan

Status: **script approved on 2026-11-08.** Nothing is built yet. Decisions taken: 2D stick figures; two patients in the type-or-speak beat (left types, right speaks, focus on the speaker); the emergency contact is shown as a checklist; the closing lines in section 6 are written by the owner; the narration voice is still to be chosen.
Facts come from `docs/scoping-document.md` and `docs/DECISIONS.md` (they win over the scoping doc), plus `docs/privacy-measures.md`. No market numbers in these videos, by decision.

## The three pieces

| Piece | Length | Made how | What it says |
| --- | --- | --- | --- |
| **Video 1: The problem** | 60 s | Animated (2D) | Three people are failing quietly: patient, doctor, company. A daily check-in and a 1-2-3 missed-day safety net fix that. |
| **Video 2: The story** | 60 s | Animated (2D) | One morning, end to end: notification, voice check-in, only coded data leaves the phone, company view, sealed copy to the doctor, the visit. |
| **Piece 3: The real demo** | about 60 s | Screen recording by the team, not animated | The same flow on the real apps, then the closing statement. |

Videos 1 and 2 are built and approved separately, so each gets time and care. Piece 3 is recorded by you; its shot list and closing lines are in section 6.

## 1. Look and feel (locked unless you change it)

- **Style:** flat 2D with stick-figure-simple people (round head, line body, big expressive hands). Depth comes from 3 parallax layers (background, room, foreground), soft drop shadows and a slow camera drift. No Minecraft blocks unless you prefer them; the 2D version is faster to make and edit.
- **Palette:** the company portal's "Clinical Mist": porcelain background, navy ink, teal accent. Alert red-orange (`--signal`) is used only for the missed-day alerts.
- **Type:** the same fonts as the company portal (`@fontsource`). Large and high contrast, since Walter is 92. Every on-screen line holds long enough to read (about 0.3 s per word).
- **Mood:** warm, calm, people first. Never frightening. Alerts feel like "someone is coming", not "alarm".
- **Characters** (all fictional, from the scoping doc):
  - **Walter**, 92, patient. Grey hair, cardigan, steady shaking hands.
  - **Anna**, his caregiver. Phone in hand.
  - **Dr. Shah**, Walter's doctor. White coat, glasses.
  - **Dr. Lee**, the drug-safety lead at the company. Laptop, dashboard.
- **Place names:** Northgate Medical Center for the clinic. Halvaren Therapeutics for the company (fictional, per D-078).
- **Phone screen:** the real patient screen's layout, simplified. Large text, large buttons.

## 2. Sound plan (you control every cue)

Every cue has an ID so you can change one without touching the rest. Levels are relative: music bed 0.15 under voice, 0.4 when alone.

| ID | Sound | Used in |
| --- | --- | --- |
| M-01 | Soft warm piano or acoustic bed, slow tempo, no drums | Both videos, ducked under voice |
| V-01 | Narration, one calm voice, same for both videos | Both videos |
| S-01 | Quiet room tone (kitchen or bedroom) | V1 S1; V2 S1 |
| S-02 | Phone buzz, short | V2 S1 |
| S-03 | Soft notification chime | V2 S1 |
| S-04 | Screen tap, light | V2 S2 and S4 |
| S-05 | Keyboard clicks, 2 s | V2 S2 |
| S-06 | Mic-on ping | V2 S3 |
| S-07 | Gentle transcript "typing" tick, one per line | V2 S3 |
| S-08 | Lock click | V1 S2; V2 S3 and S5 |
| S-09 | Soft "scrub" swoosh (names removed) | V2 S4 |
| S-10 | Data swoosh (JSON leaves the phone) | V2 S5 |
| S-11 | Receipt print, short | V2 S5 |
| S-12 | Chart tick, one per bar | V2 S6 |
| S-13 | Sealed-envelope swoosh | V2 S7 |
| S-14 | Door open, footsteps, chair | V2 S7 |
| S-15 | Paper rustle (history opens) | V2 S7 |
| E-01 | Escalation tone, level 1: one soft note | V1 S6 |
| E-02 | Escalation tone, level 2: two notes rising | V1 S6 |
| E-03 | Escalation tone, level 3: three notes rising, resolves warmly | V1 S6 |
| T-01 | Title sting, one warm chord | V1 S7 |

Music and sound-effect files must be royalty-free or generated, with the source noted in the project. Silence is a tool: V1 S2 and S3 use almost none.

## 3. Video 1: The problem (60 s)

Narration is about 120 words, with gaps for effects.

| # | Time | Picture | Narration (V-01) | On-screen text | Sound |
| --- | --- | --- | --- | --- | --- |
| 1 | 0:00-0:06 | Walter at a kitchen table, one pill bottle, morning light. Slow push-in. | "Walter is ninety-two. Three weeks ago he started a new medicine." | "Walter, 92" | S-01, M-01 in |
| 2 | 0:06-0:16 | His hands shake. A rash appears on his arm. A paper form on the table; he pushes it away. A small padlock icon over a speech bubble (he doesn't want his words sent anywhere). Calendar page "next visit" flips to months away. | "Now his hands shake, and a rash is spreading. Forms are hard. He doesn't want his words sent anywhere. So he says nothing." | "Patient: unheard" | S-08 on the padlock |
| 3 | 0:16-0:29 | Dr. Shah's clinic. A "10 min" clock drains. The doctor asks "How have you been?"; Walter answers "Fine." Walter's thought cloud shows "2 months ago" and a rash icon that fades into a question mark. The camera moves to a wall chart with two visits and a long empty stretch between them; a blank sheet lands in the gap. | "His doctor gets ten minutes, every few months. How have you been? Fine. He's forgotten how he felt two months ago. So the months in between stay blank." | "Doctor: a blank page" | quiet |
| 4 | 0:25-0:34 | Dr. Lee at a desk. Dashboard with a thin dotted line and a "late" tag. A few scraps of paper arrive one at a time. | "The drug company has to watch for side effects. What reaches them is thin, late and unstructured." | "Company: thin, late signal" | quiet; one paper tick per scrap |
| 5 | 0:34-0:40 | Mood lifts. A calendar fills with soft teal ticks, one per day. Walter smiles at his phone. | "What if someone simply checked in, every day, at a time Walter chooses?" | "A check-in, at a time you choose" | M-01 swells slightly |
| 6 | 0:40-0:55 | Three calendar days side by side. **Day 1** missed: Anna's phone glows, the care team's screen glows. **Day 2** missed: the glow turns amber and a "needs attention" flag rises. **Day 3** missed: an emergency-contact checklist appears with three ticked options, "A person you trust (mother, father...)", "A hospital or clinic" and "Emergency services", and the ticked ones light up. Walter stays at the centre, small and safe, with a halo of people growing around him. | "Miss one day, and his caregiver and care team are alerted. Miss two, and it escalates. Miss three, and his emergency contacts are told. Nobody goes quiet alone." | "Day 1: alert" / "Day 2: escalation" / "Day 3: emergency contacts" | E-01, E-02, E-03 on each day |
| 7 | 0:55-1:00 | Walter looks up, relieved. Title card. | "SafeSignal. Someone is looking out for you." | "SafeSignal" | T-01, music resolves |

How the safety net really works (so the animation is honest): missed check-ins escalate at 1, 2 and 3 consecutive misses (D-060, D-068). Levels 1 and 2 notify the patient, caregiver and care team; level 3 also notifies the emergency contacts the patient chose, with consent. In the current build these are in-app notifications. Real calls and texts are version 1.

## 4. Video 2: The story (60 s)

Narration is about 115 words.

| # | Time | Picture | Narration (V-01) | On-screen text | Sound |
| --- | --- | --- | --- | --- | --- |
| 1 | 0:00-0:05 | Bedroom, sunrise. A clock turns to 9:00. Walter's phone lights: "Good morning, Walter. Time for today's check-in." | "Nine a.m. Walter's phone: time for today's check-in." | "9:00 AM" | S-01, S-02, S-03 |
| 2 | 0:05-0:11 | Screen splits into two sides. **Left:** a second patient (Priya, 58, at a desk) taps **Type** and types on her phone, small and brief. **Right:** Walter taps **Speak** and lifts the phone; this side is larger and brighter, and the camera drifts toward it. | "Some people type. Walter just talks." | "Type or speak" | S-04, S-05 (left, quiet), S-04 (right) |
| 3 | 0:11-0:22 | Split screen. Left: Walter speaking to the phone, a soft waveform. Right: the question card ("Have you noticed any new symptoms?"). His words appear as a transcript on the phone with a small lock icon and the label "stays on this phone". | "The questions are simple. He answers in his own words. The transcript appears right on his phone, and only there." | "Stays on this phone" | S-06, S-07, S-08 |
| 4 | 0:22-0:28 | The transcript is scrubbed: a name and a place become blocks. A plain-words summary appears: "Rash, moderate, started 1-3 days ago." Walter taps **Share**. | "Names and details are stripped out on the device. Walter reads what would be shared, and he approves it." | "He approves every send" | S-09, S-04 |
| 5 | 0:28-0:37 | The phone splits in two. The transcript and a microphone icon stay behind a padlock. A small JSON card flies out (real fields: symptom code, severity, onset, week, cohort, a random patient ID). A receipt prints with a short hash. | "Only coded fields leave: symptom, severity, week. No audio. No words. No name. And he gets a receipt." | "Leaves: coded fields. Stays: everything he said." | S-10, S-08, S-11 |
| 6 | 0:37-0:46 | The JSON lands in a dashboard (Halvaren Therapeutics). Bars grow week by week, a trend line bends. A box greys out: "under 5 hidden". Dr. Lee nods. | "The company sees patterns, never people. Groups under five are hidden." | "Patterns, not people" | S-12 (one per bar) |
| 7 | 0:46-1:00 | A sealed envelope leaves the phone and reaches Northgate. Cut to the doctor's cabin: Walter walks in and sits. Dr. Shah opens a timeline of his past weeks and asks about the rash. Walter points to his arm. Both smile. | "His doctor gets a sealed copy only his care team can open. When Walter walks in, the history is already there, and the follow-up questions write themselves." | "Sealed: only his care team can open it" | S-13, S-14, S-15 |

Rules used here: no audio or transcript leaves the device; the company sees only coded fields and ISO weeks; groups under 5 patients are hidden; the doctor copy is sealed to the care-team organization's key and sent only with consent. Both viewers' screens are mock-ups made from the real UI styles, with synthetic data.

## 5. How the downstream work flows

1. Approve this script (you).
2. Lock the voice: pick one of the text-to-speech voices or record your own, then make the narration track first. Scene lengths flex to the voice, not the other way round.
3. Storyboard frames per scene for your review (HyperFrames storyboard step), one change round.
4. Build Video 1, review, render. Then Video 2, review, render.
5. Mix: you adjust each cue in section 2.
6. Piece 3: you record while I check the shot list against the real flow.

Tooling: HyperFrames' `general-video` workflow in companion mode with a storyboard pass, text-to-speech and audio through `/media-use`. `/brag` is not used for these two videos, because it is limited to 15-25 seconds. It could make a 20-second teaser later.

## 6. Piece 3: the real demo and the closing (you record, about 60 s)

Record on the real apps (patient screen, company portal, doctor view) with synthetic data.

| Time | Shot | Say |
| --- | --- | --- |
| 0:00-0:10 | Patient screen: a spoken check-in, the transcript on screen | "This is the real thing, running on this laptop." |
| 0:10-0:20 | The summary and approval, then the receipt with the hash | "He approves, and gets a receipt." |
| 0:20-0:30 | Network log: only the record send appears | "This is every request the app made. No audio, no words." |
| 0:30-0:42 | Company portal: the record, the weekly chart, the suppressed group | "The company gets patterns, not people." |
| 0:42-0:52 | Doctor view: the timeline, then the missed-day alert from the care team's side | "The doctor sees the history, and a missed day raises an alert." |
| 0:52-1:00 | Closing card (below) | Closing lines |

**Closing lines:** written by the owner. Points to cover: local AI, nothing he says leaves the phone, privacy rules followed, someone checks in every day, patients first.

## 7. Claims to avoid (accuracy)

- Don't say "the only" product. If a claim about competitors is needed, say "we did not find another."
- Don't say it calls 911. Say the emergency contact is notified (in-app today).
- Don't show real people, real patient data or a real company name. Everything is fictional and synthetic.
- Don't say the data is encrypted at rest. It isn't yet (stated gap in `docs/privacy-measures.md`).

## 8. Decisions

| # | Decision | Status |
| --- | --- | --- |
| 1 | Characters: 2D stick figures | Decided |
| 2 | Narration voice: Kokoro (local), a 60/40 blend of `af_heart` and `af_nicole`, speed 0.95, same in both videos | Decided |
| 2a | Pauses: set by us, not by the model. Default is **sentence-end** mode (the model's own commas, exact pauses after `.` `?` `!` `…` and line breaks). **Comma** mode (also cuts at commas, colons and dashes) is the fallback if there is time to spare. Pause lengths: comma 0.30 s, colon or semicolon 0.40 s, dash 0.35 s, period or exclamation 0.60 s, question 0.65 s, ellipsis 0.90 s, line break 1.0 s, `[pause N]` exact. | Decided |
| 2b | Time limit: the demo slot is about 3 minutes, so the three pieces total about 180 s. Narration that runs long is tightened by shortening pauses first, then words. | Decided |
| 3 | Type or speak: two patients side by side, Priya types on the left, Walter speaks on the right, focus on Walter | Decided |
| 4 | Closing lines: written by the owner | Decided |
| 5 | Video 1 scene 6: emergency contact shown as a checklist (a person you trust, a hospital or clinic, emergency services) | Decided |
