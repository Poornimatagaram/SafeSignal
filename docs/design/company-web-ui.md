# Company UI brief: Halvaren landing page and safety portal

**Status:** superseded by D-092 (centered product-page layout; see `apps/company-web/PRODUCT.md`); kept for the content and product truths in sections 2–3 · **Date:** 2026-11-08 · **Owner:** company side
**Builds in:** `apps/company-web` only (React 19, Vite, TypeScript, Recharts, port 5175)
**For:** the agent who builds it. Read this whole page, then `docs/company/company-side-overview.md`.

## 1. Decisions already made (do not reopen)

| Decision | Choice |
| --- | --- |
| Scope | A public **landing page** (`#/`) and a redesigned **portal** (`#/portal/...`), in one visual language |
| Structure reference | **Stripe / Linear-grade product UI** (Direction C, chosen 2026-11-08 after a design critique): white page, sections divided by whitespace and 1 px rules, underline tabs, tables first, at most one bordered container per view |
| Not from the reference | Floating cards, drop shadows, pastel washes, pill buttons, eyebrow labels, KPI tile rows. The earlier flipads.ai reference is withdrawn: it read as a generic AI template |
| Palette | **Clinical Mist**: cool porcelain base, navy ink, teal accent (section 4) |
| Main viewing context | **Projector demo for judges**: high contrast, generous whitespace, one finding per section |
| Appearance | **Light only** (no dark mode) |
| Sibling, not twin | The doctor app uses plum/cream with Poppins/Nunito. The company UI shares its softness but must not reuse its colors or fonts |

## 2. Who it is for and what it must show

- **Dr. Lee**, drug-safety lead (`company_safety`): watches side-effect signals per drug version and cohort, and exports records.
- **Marco**, medical affairs (`company_reader`): compares cohorts and drug versions.
- **Survey admin** (`company_admin`): edits the questions and check-in cadence per cohort.
- **The judges** (landing page and demo): must understand in under a minute that:
  - patients talk;
  - only coded, minimal fields leave the phone;
  - the company sees cohort signals grounded in real trials and never sees identities.

The demo story to support: open the landing page, then the portal, then pick Tagrisso. In the signals view, cohort A (the comparator) shows more acne-like rash than cohort B (osimertinib), as in the real FLAURA trial. Then show a check-in arriving, the survey editor and the documents.

## 3. Product truths the UI must respect

- The company sees **pseudonymized, aggregated data only**: ISO weeks, never exact dates; no names; no relay data.
  - Weekly rows with fewer than 5 patients are already dropped by the service.
  - `severe_patients: null` means 1–4 patients and must render as **"<5"** (D-004).
- **Halvaren Therapeutics is fictional.** Every number comes from public trials and labels (FLAURA, MARIPOSA, MELODY; FDA labels).
  - The footer and the About text must say so: "Fictional company. Rates and documents from public sources; Halvaren is not the sponsor of these trials."
- **No invented claims.** No customer logos, testimonials, pricing, certifications or user counts.
  - Allowed figures: those in the repo, with their source. For example, "only about 6% of adverse drug reactions are reported (2022 review, Scoping Doc 2)"; trial sizes from `/v1/company/programs`; the 3 programs and 4 cohorts of 250.
- **Roles gate actions:**
  - export: `company_safety` only;
  - survey publish: `company_admin` only;
  - everything else: any company role.
  - Show gated actions disabled with a one-line reason; never hide the section.
- **Privacy rules (Scoping Doc 26.12):** no analytics, no tracking, no third-party requests.
  - **Fonts are bundled** (npm `@fontsource/*`), never loaded from Google Fonts.

## 4. Visual system: Clinical Mist

Define these as CSS custom properties on `:root` and reference them by role only; no raw hex in components.

### Color

| Token | Hex | Use | Contrast |
| --- | --- | --- | --- |
| `--page` | `#FFFFFF` | Page background, landing and portal | n/a |
| `--subtle` | `#F6F8FA` | Table headers, row hover, selected segment | n/a |
| `--base` | `#F2F5F8` | Tags, skeletons, disabled buttons | n/a |
| `--line` | `#E3E9F0` | 1 px section rules, table rows, table borders | n/a |
| `--line-strong` | `#CFD8E3` | Input, select and button borders; chart baseline | n/a |
| `--ink` | `#13233A` | Headings, body, numbers | 15.8:1 on white |
| `--ink-2` | `#4A5A70` | Secondary text, labels, captions, axis labels | 7.0:1 on white |
| `--ink-3` | `#64748B` | Disabled link text only, on white only (4.4:1 on `--base`) | 4.8:1 on white |
| `--accent` | `#0E7C7B` | Primary buttons, links, focus ring, selected tab | white text on it 5.0:1 |
| `--accent-deep` | `#0A5E5D` | Accent hover; text on mint tint | 6.3:1 on mint |
| `--tint-sky` | `#DCEBFA` | Not used in the UI (kept as a reserve token) | ink on it 13.0:1 |
| `--tint-mint` | `#D8F0E8` | Provenance chip background only | `--accent-deep` on it 6.3:1 |
| `--tint-lilac` | `#E8E2F7` | Not used in the UI (kept as a reserve token) | n/a |
| `--tint-butter` | `#FBF0CF` | "Edited" tag on the survey editor only | ink on it 13.9:1 |
| `--signal` | `#C2410C` | **"Rising" signals only**, always with an icon and a word | 5.2:1 on white |

Rules:
- Teal means "you can act here" (buttons, links, the active tab's 2 px underline, focus ring). Tints are background only, never text.
- No pastel washes on sections or cards. Mint appears only on the provenance chip; butter only on the "Edited" tag.
- `--signal` marks one thing: a side effect × cohort rate that rose by 2 points or more since last week, always with an up-arrow icon and the word "Rising". Suppressed counts ("<5") are plain `--ink-2` text, never `--signal`.

### Chart series (cohorts)

Validated with the dataviz validator (light; worst adjacent colorblind ΔE 23.1, normal-vision 24.0):

| Slot | Hex | Cohort |
| --- | --- | --- |
| 1 | `#2a78d6` blue | A |
| 2 | `#1baf7a` aqua | B |
| 3 | `#6250d6` violet | C |
| 4 | `#eda100` yellow | D |

- Aqua and yellow are below 3:1 on white, so **every chart needs direct line-end labels plus a "Show table" toggle**. Identity is never carried by color alone.
- Series colors appear only as marks: lines, 10 px dots, sparklines, small bars. **Never as text**, and never as a fill behind text.
- Wherever a cohort appears, write "Cohort A" in ink next to a dot in its series color.
- Colors follow the cohort letter in every program and every filter state; never re-cycle them.
- No orange series, so nothing can be confused with `--signal`.

### Typography (bundled with `@fontsource`)

- **Display:** Plus Jakarta Sans, 700/800. Use it only for the landing hero, landing section titles and the portal page title (the drug name).
- **Body and UI:** Inter (variable) for everything else, with tabular figures (`font-feature-settings: 'tnum'`) for every number.

Each level differs from the next in size, weight or color, not size alone:

| Style | Size / line-height | Weight, color |
| --- | --- | --- |
| Hero headline (landing) | `clamp(38px, 5vw, 60px)` / 1.04 | Jakarta 800, tracking −0.03em, left-aligned |
| Landing section title | `clamp(26px, 2.6vw, 32px)` / 1.15 | Jakarta 800 |
| Portal page title | 28 px / 1.15 | Jakarta 700, generic name after it in Inter 17 px `--ink-2` |
| Section heading (portal) | 18 px / 1.3 | Inter 600 |
| Finding sentence above a chart | 17 px / 1.4 | Inter 600, `--ink` |
| Body | 15 px / 1.55 | 400 |
| UI: tables, controls, tabs | 14 px | 500–600 |
| Meta: captions, axis labels, table headers | 13 px minimum | 400–600, `--ink-2` |
| Stat value | 24 px / 1.2 | Inter 600 (no oversized KPI numbers) |

- Sentence case everywhere. No uppercase eyebrow labels above headings, ever.
- Never set text under 13 px. Chart text is drawn at real pixel size (the SVG width equals the container width), so axis labels stay 13 px and never scale up to 20 px.

### Shape, depth and spacing

- **No cards.** Sections are separated by 32 px (portal) or 96 px (landing) of space and a 1 px `--line` rule. Only data gets a border: a table wrapper, the chart panel, the landing product frame.
- Radii:
  - 4 px: tags
  - 6 px: buttons, inputs, selects, segmented controls
  - 8 px: table wrappers and the chart panel
  - 12 px: the landing product frame and survey figure
  - 999 px: **the provenance chip only**
- Shadow: none on content. One shadow, `0 8px 24px rgb(19 35 58 / 0.14)`, on floating layers only (tooltip, popover). No hover lift.
- Controls: buttons 36 px tall (44 px for the landing primary CTA); tabs are underline tabs with a 2 px teal bottom border on the active one.
- Spacing scale (px): 4, 8, 12, 16, 24, 32, 48, 64, 96.
  - Landing sections use 96 vertical (64 under 560 px).
  - The portal uses 24 side gutters and 32 between sections.
- Max content width: 1120 px. Layout must still work at 1024 px wide (projector) and degrade cleanly to 375 px.

### Motion

- Hover and press: 150 ms ease-out, color and border only.
- The one authored moment: chart lines draw once on load (600 ms, exponential ease-out). No hero entrance animation.
- No marquees, carousels or parallax.
- Everything is off under `prefers-reduced-motion`.

### Signature element: the provenance chip

The one thing this UI is remembered by: **every number shows where it came from.** A small pill chip, for example `FLAURA · arm EG000 · ClinicalTrials.gov ↗`:
- sits in the program header, on every cohort row, beside every chart finding and on every document row;
- uses the mint tint with `--accent-deep` text and an external-link icon, and opens the public source;
- comes from `program.source_trial`, `source_url` and `cohort.source_arm`.

It is the visual proof of "real data, fictional company". Spend the boldness here and keep everything around it quiet. It is the only pill-shaped element in the UI; nothing else may share its shape or its mint color. On document rows it replaces the separate "Open source" button and links to the document itself.

### Icons

One outline set, Lucide (`lucide-react`), at 1.75 stroke, sized to adjacent text. No emoji. Every icon-only button has an `aria-label`.

## 5. Landing page (`#/`): Persuade mode

White page, left-aligned, sections separated by a 1 px rule and 96 px of space. Use real UI as the visual (a flat, untilted portal frame), not stock images, illustrations or floating cards.

1. **Nav** (sticky, white, 64 px, 1 px bottom line):
   - wordmark "Halvaren" plus "Safety" in teal text (no pill);
   - links: How it works · Real trials · Privacy · FAQ;
   - primary button **"Open the safety portal"**.
2. **Hero** (left-aligned, headline max 15ch):
   - Headline (proposal): "Hear from every patient. Not just the 6% who report."
   - Sub: "Patients check in by voice. Only coded side-effect fields leave their phone. Your safety team sees every cohort, week by week."
   - Primary CTA "Open the safety portal"; secondary text link "See how it works".
   - Under the text, full width: a flat product frame (1 px border, 12 px radius) holding the portal's real signal table for Tagrisso, the top 4 rows with the provenance chip in its header bar.
3. **How it works:** 3 numbered steps in one row, separated by 1 px vertical rules, no cards or tints. Each has an icon inline with its title:
   - **Patient talks** (voice or typing, on their device)
   - **Only codes leave** (e.g. `SE_RASH · moderate · 1–3 days`; no words, no names)
   - **You see cohorts** (weekly rates by drug version, updated as check-ins arrive)
4. **Built on real trials:** a 3-row table (Tagrisso / FLAURA, Rybrevant / MARIPOSA, Beyfortus / MELODY), with one row per program showing:
   - trial name, patients in the real trial, number of arms;
   - one real headline rate quoted straight from the trial, e.g. "Acne-like rash: 49% on comparator TKIs vs 26% on osimertinib (136/277 vs 73/279)";
   - the provenance chip.
   - Numbers come from the API, or from a static file generated from `data/company/ctgov`. Never type them by hand.
5. **What you see, what you never see:** two columns of ruled lists, no background wash:
   - **You see:** weekly side-effect rates, completion, voice vs text, survey control, documents, pseudonymous export.
   - **You never see:** names, phone numbers, exact dates, transcripts, doctor notes.
   - Check icons in `--accent-deep`, cross icons in `--ink-2`.
6. **Survey control:** text on the left; on the right a bordered figure showing one question with its first ask, simpler re-ask and choice re-ask as label/value rows, plus "Publish to cohort B". Explains that the company tailors questions, not data access.
7. **FAQ:** 5 expandable items separated by 1 px rules (no boxes):
   - Is this real patient data?
   - Who is Halvaren?
   - What leaves the phone?
   - How are rates calculated?
   - What does the doctor see?
8. **Final CTA:** "See the signal for yourself" plus the portal button, on white, after a rule. No colored band.
9. **Footer:** fictional-company disclaimer, sources (ClinicalTrials.gov, openFDA, DailyMed), links to the doctor and patient demo apps, and "Synthetic patients only".

## 6. Portal (`#/portal/...`): Operate mode

### Shell

- **Top bar** (white, 56 px, 1 px bottom rule, sticky):
  - wordmark;
  - **program switcher** as a select showing "Tagrisso · FLAURA";
  - on the right: a quiet connection indicator, then the **role switcher** (select: "Dr. Lee · Safety", "Marco · Reader", "Survey admin · Admin").
  - The role switcher sets `X-Role` and `X-Actor-Id` (already in `lib/config.ts` and `lib/api.ts`).
- **Section tabs** in the same white header, underline style (14 px, active tab 600 weight with a 2 px teal underline):
  - Overview · Side effects · Check-ins · Surveys · Documents · Export.
  - Use hash routes, so each is deep-linkable and the browser back button works.
  - Six tabs fit one row at 1024 px; no sidebar.
- **Program header** on every section: drug name (Jakarta 28 px) with the generic name after it, then one meta row separated by thin dividers: indication | population | "Latest week 2026-W45" | provenance chip.

### Overview (new)

This is the screen to put up first in the demo. It answers "what is rising?", not "what is big?".

- **Stat strip:** four inline stats separated by 1 px vertical rules, no boxes, values at 24/600:
  - enrolled patients;
  - check-ins completed this week;
  - patients reporting a side effect;
  - number of side effect × cohort pairs rising this week.
  - Each has a one-line comparison to last week (an arrow plus words, not color alone).
- **Signal table**, sorted by change since last week. It shows the top 8 rows with "Show all 24". Columns:
  - side effect;
  - cohort (dot plus "Cohort A");
  - arm label;
  - this week %;
  - change vs last week ("Rising +2.3 pts" in `--signal` when the rise is 2 points or more, otherwise a muted arrow and value);
  - a 10-week sparkline in the cohort color;
  - the real trial rate for that arm.
- **Cohorts table:** columns are cohort, arm, provenance chip (with arm ID), enrolled, completed this week, and most reported side effect.

### Side effects (existing `views/Signals.tsx`, restyled)

- Two columns. On the left, a 240 px side-effect list sorted by this week's average rate. Each row shows the term, the rate and "On label" / "Not on label" from `/v1/company/terms`. The selected row has a teal wash and a 2 px inset left edge.
- On the right:
  - a **finding sentence** in 17/600 (e.g. "Cohort A reports rash most often: 33.9% this week, 2.0× cohort D.");
  - one muted line comparing it with the real trial arms, plus the provenance chip;
  - then one bordered chart panel. It plots % of reporting patients by ISO week, one line per cohort, with direct labels at the line ends, round axis ticks (0/10/20/30/40%), a crosshair and tooltip, and a "Show table" text toggle.
  - The finding sentence is also the chart's accessible label.
- Under it, a **cohort × side-effect comparison table** for the latest week:
  - cells shaded with a single-hue blue ramp from `#EEF4FB` to `#5B8DCC`, always with ink text, value right-aligned;
  - a muted "severe N" or "severe <5" line under each value (no pill, no `--signal`).

### Check-ins (existing `views/Completion.tsx`, restyled)

- A finding sentence ("Completion this week ranges from 84% (cohort D) to 89% (cohort B).") above one chart panel. A small segmented control switches between Completed and Missed.
- **Voice vs text vs mixed:** one 14 px-high 100% stacked bar per cohort, built from `voice_records`, `text_records` and `mixed_records`, with 2 px gaps between segments. Values are written beside the bar ("Voice 62% · Text 29% · Mixed 9%"), not inside it.

### Surveys (existing `views/Survey.tsx`, restyled)

- A cohort select in the section header. Each question is a ruled row: purpose and question ID on the left (220 px), and its three asks (first, simpler re-ask, choice re-ask) as labelled inputs on the right. No cards.
- Edit `schedule.every_days` with a stepper (1–30) showing the words "Every N days".
- Edited inputs get a butter border. Changed questions show an "Edited" tag, and a changed cadence shows "Edited · was every N days".
- **Publish** and **Discard changes** sit in the action row at the bottom. Publish is enabled only for the admin and only when something has changed; without changes the row says "No changes to publish."
- Publishing shows inline success ("Published version 3 to cohort B") or inline field errors from the 422 response, next to the field.
- Not admin: the button is disabled with "Only the survey admin can publish".

### Documents (from `views/Program.tsx`)

- A table per program: kind, title, version, "Approved by" (role, not a person's email), and a source column. The source is the provenance chip linking to the document itself, so there is no separate button.

### Export (from `views/Program.tsx`)

- CSV and JSON buttons in the section header, enabled for `company_safety` only; otherwise disabled with the reason underneath.
- A ruled definition list of what is in the export (pseudonymous IDs, ISO weeks only, side-effect code, severity, onset window, mode), then a sample-rows table.

### States (all sections)

- **Loading:** skeleton lines in the layout's own shape, no spinners over 300 ms.
- **Empty:** a sentence plus the next action, e.g. "No check-ins yet this week. They appear as patients answer."
- **Error:** inline banner naming what failed and a Retry button. If the service is down, say "Can't reach the service at <url>. Is it running on port 8000?"

## 7. Constraints for the building agent

- **Folders:** edit only `apps/company-web/` (plus its own `CHANGELOG.md`).
  - No changes to `schema/`, `packages/` or `apps/service/`.
  - No new endpoints; everything needed exists: `programs`, `cohorts/weekly`, `completion`, `terms`, `documents`, `cohorts/{id}/survey` (GET and PUT), `records/export`.
- **Keep** `src/lib/api.ts`, `src/lib/config.ts` and `src/lib/data.ts`; restyle and recompose the views.
  - Add `react-router` only if hash routing by hand gets messy; prefer a tiny hash router.
- **New dependencies allowed:** `@fontsource/plus-jakarta-sans`, `@fontsource-variable/inter`, `lucide-react`. Nothing that phones home.
- **Run locally:** service with `SENTINEL_ALLOWED_ORIGINS=http://localhost:5175`, after `scripts/reset_all.sh --seed`.
- **CI:** "Company portal (lint and build)" must pass.
- **Git:** follow `CONTRIBUTING.md`:
  - branch `company/feat/<description>`;
  - Conventional Commits with scope `company-web`;
  - squash-merge when green.

## 8. Acceptance checklist

- [ ] `#/` landing page and `#/portal/*` sections all deep-linkable; back button works.
- [ ] Clinical Mist tokens only; no beige or cream anywhere; no raw hex in components.
- [ ] Body 15 px, no text under 13 px; all text contrast ≥ 4.5:1 (big text ≥ 3:1); no text in series colors.
- [ ] No content shadows, no cards around sections, only the provenance chip is pill-shaped.
- [ ] Overview leads with the signal table sorted by week-on-week change; "Rising" is the only use of `--signal`.
- [ ] Every chart: legend or direct labels, tooltip, and a table view; cohort colors fixed by letter.
- [ ] "<5" rendered for suppressed severe counts; only ISO weeks shown, never dates.
- [ ] Provenance chip in the program header, cohort rows, chart findings and documents, linking to the public source.
- [ ] Role-gated actions disabled with a reason, never hidden.
- [ ] Visible focus ring (teal, 2 px offset) on everything interactive; keyboard-only path through every section.
- [ ] `prefers-reduced-motion` removes all motion.
- [ ] No external network requests except the service (fonts bundled).
- [ ] Fictional-company disclaimer on the landing footer and the portal's About.
- [ ] Checked by screenshot at 1440, 1024 and 375 px wide.

## 9. Anti-patterns (reject on sight)

- Cream or beige base, terracotta or coral accent, purple-pink gradients, glassmorphism.
- Floating cards with drop shadows as page structure, hover lift on things that are not clickable, pastel section washes, tilted product shots.
- Uppercase eyebrow labels above headings; rows of big-number KPI tiles; avatar-style colored letter circles.
- Pill-shaped buttons, tabs or filters (the provenance chip is the only pill).
- Emoji as icons; numbers on every chart point; dual-axis charts; rainbow heatmaps.
- Invented logos, testimonials, statistics or "trusted by" strips.
- Hidden role restrictions; alerts or modals for routine feedback.

## 10. Open questions for the product owner

1. The hero headline is a proposal. Keep it, or supply the line you want?
2. Should the landing page link to the doctor and patient demo apps (their ports), or stay company-only?
