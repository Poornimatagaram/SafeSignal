# Session Log

One entry per working session, newest at the bottom. Each entry: goal, outputs, verification, decisions, open items, next.

---

## Session 001 — 2026-11-07 (Sat) · H1 handover package

**Goal:** Read the scoping document; plan the company-side build; deliver Step 1 (the H1 "Schema frozen" handover in Scoping Doc 26.10–26.11) and set up the four project documents.

**Outputs**
- Plan of action agreed: Step 1 handover → Step 2 seed data and real record path → Step 3 relay, consent, scheduler → Step 4 company portal → Step 5 Could items.
- `schema/` v1.0: 4 SQL files, 6 JSON Schemas, `enums.json`, `terms.json`, `openapi.json`, examples (valid + invalid per payload), hash vectors and JS checker, schema changelog.
- `contract/` shared hashing and validation module.
- `sentinel_service/` stub: every 26.7 endpoint, real rule enforcement over in-memory demo data.
- `clients/sentinel_client.py` (patient side) and `clients/sentinel_api.d.ts` (doctor side types).
- Project docs: `CLAUDE.md`, `docs/DECISIONS.md`, `docs/SESSION_LOG.md`, `CHANGELOG.md`.

**Verification**
- `uv run pytest -q`: 38 passed (public key 404 until registered, examples valid/invalid, hash vectors, no free text in company schema, enums consistent, SQL idempotent, under-5 suppression, 401/403/409/422/200/201 paths, company cannot reach relay, consent revocation, real sealed-box envelope round trip, client refuses free text before sending).
- `node schema/examples/check_hash_vectors.mjs`: 8/8 PASS (Python and JS hashes byte-identical).
- Live `uvicorn` on port 8000: `/docs` 200; free-text record → 422 naming `/notes`; valid record → 201 with matching hash; server log has no payload content.

**Decisions:** D-001 to D-025 (D-008 and D-012 open).

**Open items (need the team)**
- D-008: caregiver `summary` detail level, keep or drop.
- D-012: who builds the doctor UI.
- Team sign-off on schema 1.0 to pass the H1 gate.
- `terms.json` rows must be checked against cached openFDA label text (task C2).
- Note: port 8765 is used by an unrelated local process; the service uses 8000.

**Next (Step 2)**
1. `sentinel_service/db.py`: apply `company.sql` and `relay.sql` to separate SQLite files at startup; SQLite store replacing `StubStore` behind the same methods.
2. `sentinel_service/seed.py`: program, 4 cohorts, 1,000 enrollments, terms, surveys, demo doctor/caregiver/links, 3–4 weeks of synthetic history with a per-version side-effect mix (openFDA-informed).
3. `scripts/reset_all.sh`.
4. Commit the teammates' agent briefs (26.14) into their folders once D-012 is settled.

---

## Session 002 — 2026-11-07 (Sat) · Centralized repo structure

**Goal:** Give the three people (company, patient, doctor) one repo structure where independent UIs and databases cannot collide; restructure on a branch and merge into `main`.

**Outputs**
- Structure proposed, then approved with one change: we are the pharmaceutical company persona only; the doctor teammate owns `apps/doctor-web/` (D-027, closes D-012).
- Baseline commit on `main` (`0d106df`), then branch `company/repo-structure` with the restructure (D-026 to D-032).
- New layout: `schema/` · `packages/contract-py` · `packages/contract-ts` · `apps/{service, company-web, patient-runtime, patient-web, doctor-web}` · `evals/` · `data/` · `scripts/` · `docs/` · `var/` (gitignored).
- `README.md`, `CODEOWNERS`, ownership README in every app folder with the scoping-doc path mapping.

**Verification**
- `packages/contract-py`: 21 passed. `apps/service`: 17 passed (38 total, same as Session 001).
- `npm test --prefix packages/contract-ts`: 8/8 hash vectors pass with the Web Crypto implementation.
- `scripts/build_examples.py` and `scripts/export_openapi.py` regenerate `schema/` byte-identically (no diff).

**Decisions:** D-026 to D-032; D-012 and D-019 superseded.

**Open items**
- D-008: caregiver `summary` detail level (still open).
- Shared GitHub remote: none yet; fill real handles into `CODEOWNERS` once it exists, and push `main`.
- Teammates: move their code into `apps/<their app>/` and depend on `packages/` as a path dependency.
- Team sign-off on schema 1.0 (H1 gate).

**Next (Step 2)**
1. `apps/service/sentinel_service/db.py`: SQLite store at `var/service/company.db` and `var/service/relay.db` replacing `StubStore`.
2. `apps/service/sentinel_service/seed.py`: program, 4 cohorts, 1,000 enrollments, terms, surveys, demo links, 3–4 weeks of history.
3. `scripts/reset_all.sh` (wipes `var/`).

---

## Session 003 — 2026-11-07 (Sat) · Teammate onboarding

**Goal:** Make the repo self-explanatory for the patient and doctor teammates and their coding agents, with no outside briefing needed beyond what cannot live in a repo.

**Gaps found and fixed**
1. Root `CLAUDE.md` held company-only rules that teammates' agents would also load → split into team-wide root plus `docs/company/CLAUDE.md` (D-034).
2. Shared logs would conflict → per-app changelogs; root logs company-owned (D-035).
3. Scoping doc briefs and 26.6 examples are outdated → per-app `CLAUDE.md` with corrected paths and every contract change that affects that app.
4. No statement of service behaviour → `docs/INTEGRATION_STATUS.md` (D-036).
5. Demo IDs lived inside our app; no device profile for Walter → `schema/demo_fixtures.json` (D-033).
6. Doctor side had no way to get test data → `scripts/send_demo_envelope.py` (D-037).

**Verification**
- `packages/contract-py`: 22 passed (new fixture test). `apps/service`: 17 passed. `packages/contract-ts`: 8/8.
- Live: `send_demo_envelope.py` exits with a clear message before the doctor key exists; after registering a key, envelope 201 and severe alert 201 (routed to doctor and caregiver); the envelope decrypts with the doctor's private key and its hash matches.
- `@sentinel/contract` installed as a `file:` dependency into a scratch project and imported correctly.

**Decisions:** D-033 to D-039 (D-039 open).

**Open items**
- D-008 (caregiver `summary`) and D-039 (who builds the caregiver view).
- Needs people, not the repo: shared GitHub remote and handles for `CODEOWNERS`; model downloads for the patient runtime (Ollama 3B, faster-whisper, spaCy); schema 1.0 sign-off; hotspot IP on the day.

**Next (Step 2)**
1. SQLite store at `var/service/` replacing the stub; seed from `schema/demo_fixtures.json` plus 1,000 synthetic enrollments and history.
2. `scripts/reset_all.sh`.
3. Update `docs/INTEGRATION_STATUS.md` at the H3 switch-over.

---

## Session 004 — 2026-11-07 (Sat) · Push to the shared repo, conflict-proofing

**Goal:** Push everything to `main` on `github.com/Poornimatagaram/SafeSignal` without conflicts, and make it hard for any person or agent to create conflicts later.

**Findings**
- Remote `main` had one commit (README "SafeSignal", MIT LICENSE, GitHub Python `.gitignore`), unrelated to our history. Repo is public; we have push, not admin; `main` is unprotected.
- The template `.gitignore` ignores `lib/` at any depth, which would silently drop frontend `src/lib/` code.

**Outputs**
- Merge of the remote's initial commit with only the two add/add conflicts resolved (README, `.gitignore`), then a separate guard-rail commit: `.gitattributes`, `AGENTS.md` as plain files, `scripts/check_ownership.sh`, README git workflow, per-area `evals/` and `data/`, `CODEOWNERS` handle, instruction updates.
- Pushed `main` to `origin` as a fast-forward `4db7bc0..60ae124` (no force).
- Fresh clone from GitHub as a teammate: contract-py 22, service 17, contract-ts 8/8 pass; a `doctor/timeline` branch writing `apps/doctor-web/src/lib/crypto.ts` passes `check_ownership.sh` and the file is not ignored; no tracked file is ignored.

**Verification**
- `git check-ignore`: app source under `src/lib/`, `components/parts/` kept; `var/`, `.venv`, `node_modules`, `.env`, `keys/` ignored; no tracked file newly ignored.
- `check_ownership.sh` in a scratch clone: doctor branch editing `apps/doctor-web` passes; editing `schema/` fails naming the file; patient writing `evals/patient/` passes.
- Tests: contract-py 22, service 17, contract-ts 8/8 (see push step).
- Process note: a first attempt bundled guard-rail edits into the merge commit (zsh does not word-split `$VAR`); it was local only, reset and redone so the merge commit holds only conflict resolutions.

- `check_ownership.sh company` flagged that we were maintaining files inside teammates' folders → briefs moved to `docs/briefs/` and imported (D-047). The check still lists our bootstrap files in teammate folders for this first push (origin had none of our history); that is the one-time handover, after which those files are theirs.

**Decisions:** D-040 to D-047 (D-045, D-046 open).

**Open items**
- D-045: ask the repo owner to protect `main` (no force push, no deletion).
- D-046: patient and doctor GitHub handles for `CODEOWNERS`.
- D-008, D-039 still open.

**Next (Step 2)**
1. SQLite store at `var/service/` replacing the stub; seed from `schema/demo_fixtures.json` plus 1,000 synthetic enrollments and history.
2. `scripts/reset_all.sh`.
3. Update `docs/INTEGRATION_STATUS.md` at the H3 switch-over.

---

## Session 005 — 2026-11-07 (Sat) · Conventional Commits and pull-request workflow

**Goal:** From now on, every main piece of work follows industry-standard git practice: its own branch, Conventional Commit messages split by type, push the branch, confirm no conflicts with `main`, open a pull request.

**Outputs**
- `CONTRIBUTING.md` (branches, commit types and scopes, PR steps, squash merging), PR template, CI workflow, `scripts/check_commits.sh`.
- All instruction files point to `CONTRIBUTING.md`; company agents open PRs but merge only when asked.
- This work itself followed the new flow on `company/chore/git-workflow` with four commits: `docs(repo)`, `ci`, `chore(github)`, `docs`.

**Verification**
- `check_commits.sh`: accepts `feat(service): ...` and `feat(schema)!: ...`; rejects "Added stuff", uppercase descriptions, trailing periods, unknown types and subjects over 72 characters.
- Generated `schema/` files regenerate with no diff (the new CI step passes locally).
- Branch checks, push, conflict check and PR status: see the PR.

**Decisions:** D-048 to D-052.

**Open items**
- Repo owner settings (D-045, D-050): protect `main`, require CI, squash merging only, auto-delete head branches.
- D-046 handles; D-008, D-039 still open.

**Next (Step 2)** on `company/feat/sqlite-store`:
1. SQLite store at `var/service/` replacing the stub; seed from `schema/demo_fixtures.json` plus 1,000 synthetic enrollments and history.
2. `scripts/reset_all.sh`.
3. Update `docs/INTEGRATION_STATUS.md` at the H3 switch-over.

---

## Session 006 — 2026-11-07 (Sat) · Step 2: SQLite service, seed, reset

**Goal:** Merge PR #1, then deliver Step 2: persistent SQLite storage replacing the stub, a seed with realistic synthetic history, and `reset_all.sh`.

**Outputs**
- PR #1 squash-merged (`58b63be`); branch deleted.
- Branch `company/feat/sqlite-store`: commits `feat(data)`, `feat(schema)`, `feat(service)`, `test(service)`, `feat(scripts)`, `build(contract)`, `docs(docs)`, `docs`.
- Contract fix found while building (D-054): alerts paged on device time could be skipped; contract 1.1 pages on service `received_at`.

**Verification**
- Tests: contract-py 22, service 27 (API on SQLite plus full-scale seed: 1,000 patients, valid hashed records, v2 signal, no identifiers in `company.db`, restart safety), contract-ts 8/8.
- Live: seed 1,000 patients / 25,990 check-ins / 8,506 symptom reports in under a second; `/healthz` seeded; cohort_B rash rises 16% → 21% of reporting patients over W42–W45 while other cohorts stay 7–14%; completion about 75%; a record POSTed before a restart returns 200 after it; service logs hold no patient content.
- `reset_all.sh --seed` wipes `var/` and reseeds.

**Findings**
- openFDA reports for Tagrisso include dyspnoea (546) and cough (306), which `schema/terms.json` lists as Rybrevant-only. Seeded records therefore mark them `known_side_effect: false`. Label check of `terms.json` (task C2) is still needed.

**Decisions:** D-053 to D-056 (D-020 superseded).

**Open items**
- Teammates: contract 1.1 changes the doctor alert cursor to `received_at` (brief updated).
- D-008, D-039 open; D-045, D-046 need the repo owner and handles; C2 label check for `terms.json`.

**Next (Step 3)** on `company/feat/missed-checkin-scheduler`:
1. APScheduler job: for each active enrollment whose window closed today with no record, insert a `missed` scheduler record (D-003) and a relay `missed` alert routed by links; alert within 1 minute (AL-01).
2. Demo control to set a patient's window so the missed alert fires on cue (Scoping Doc 21.3).
3. Then Step 4: company portal (`apps/company-web`).

---

## Session 007 — 2026-11-07 (Sat) · Dataset research and use-case requirements

**Goal:** Find real datasets that make the demo authentic (real data is messy), save the research, and record the product owner's clarified use case.

**Outputs**
- `docs/research/datasets.md`. Verified live through the ClinicalTrials.gov API: per-arm adverse events for FLAURA (4 arms), MARIPOSA (3 arms) and MELODY (infants, 2 arms), and protocol and statistical analysis plan PDFs for FLAURA, MARIPOSA, AURA3, FLAURA2 and MELODY.
- Requirements recorded: ages 0–100 with proxy reporting (D-058); trial-set cadence, wellbeing questions, voice or typing (D-059); escalation at 1, 2 and 3 missed check-ins including the hospital and public-service medical experts (D-060); several drug programs, 4 groups of 250, 1–2 real documents per trial (D-061); doctor sees medical history only, with hospital-level continuity (D-062).
- CI now runs on stacked PRs (D-063).

**Findings**
- No public dataset has daily per-patient check-ins on these drugs; the demo keeps generating them, but from real per-arm rates.
- PRO-CTCAE items cannot be altered or used in a product for sale; we follow its structure only.
- FLAURA reports shortness of breath and cough on osimertinib, confirming that `schema/terms.json` needs correcting (OnSIDES).
- The UCI download link for the Drugs.com reviews has moved.

**Decisions:** D-057 to D-063 (open parts in D-060, D-061, D-062).

**Open items (need the product owner)**
- D-060: who the public-service medical experts are, and patient consent to inform them.
- D-061: confirm the portfolio (Tagrisso, Rybrevant, infant nirsevimab) and a fictional company name.
- D-062: care-team or hospital key design for record continuity.
- PR #2 still open; this branch is stacked on it.

**Next**
1. Contract 1.2 proposal: reporter field (D-058), survey schedule (D-059), escalation level and hospital recipients on alerts (D-060, D-062), multiple programs (D-061). Teammate briefs updated with it.
2. Step 3, extended: scheduler with the 3-step escalation ladder.
3. Real-data seed: per-arm rates from ClinicalTrials.gov, term list corrected from OnSIDES, trial documents fetched into the company `document` table.

---

## Session 008 — 2026-11-07 (Sat) · Contract 2.0: care teams, emergency access, escalation

**Goal:** Turn the product owner's answers into the next phase: records held by hospitals (doctors change), emergency access for a hospital the patient chose, user-defined emergency contacts with consent, the 1/2/3 missed check-in escalation, patients of any age with proxies, schedules, and voice or typing.

**Product owner answers recorded**
- Public-service medical expert = 911 or the hospital the user prefers, set at setup with consent (D-067).
- Records must stay with the hospital; emergencies must not be blocked by permissions (D-064, D-065).
- Fictional company name with real public data (D-071).

**Outputs**
- Design doc, contract 2.0 schemas and fixtures, service endpoints, escalation module, seed, tests, demo script, briefs, integration status (branch `company/feat/contract-v2`, stacked on PR #3).

**Verification**
- Tests: contract-py 24, service 35, contract-ts 8/8.
- Live on a running server: the demo script stops with a clear message until Northgate's key exists; after Dr. Patel registers it, Walter's envelope is accepted and visible to Dr. Shah; the severe alert reaches the care team and Anna; Northgate's alert feed shows Priya's escalation levels; the service log contains no names or phone numbers.
- Found and fixed a false positive in the leakage test ("911" occurs inside hex hashes); it now checks stored values.

**Decisions:** D-064 to D-071 (D-025 superseded; D-060, D-061, D-062 resolved).

**Open items**
- D-008 (caregiver `summary` detail), D-039 (who builds the caregiver view).
- Key rotation after a doctor leaves (v1).
- PR #2 and PR #3 still open; this branch is stacked on #3.

**Next**
1. Missed check-in scheduler: detect due check-ins per schedule and window, write scheduler records, raise level 1/2/3 alerts through `escalation.py`, within 1 minute; demo control to fire Priya's alert on cue.
2. Real-data seed: fictional company name, per-arm rates from ClinicalTrials.gov, OnSIDES-corrected terms, trial documents in the company `document` table, an infant program (MELODY).

---

## Session 009 — 2026-11-07 (Sat) · Bring `main` up to date

**Goal:** `main` must match what has been built, without conflicts. Three PRs were open and stacked (#2 ← #3 ← #4).

**What happened**
- Merged #2 (squash). GitHub did not retarget #3; it closed #3 because #3's base branch was deleted.
- A rebase plus force-push to move #3 onto `main` was blocked by the permission system as history rewriting. Used a non-destructive method instead: merged `main` into the branch; the only conflicts were in the three append-only log files, where the branch was a strict superset (verified: no line from `main` missing).
- Opened #5 from the same branch to replace #3, **retargeted #4 to `main` before merging #5** so it could not be closed too, merged #5.
- Merged `main` into #4's branch: many textual conflicts, all caused by squashed duplicates. Proved `main` was identical to #4's base (`git diff` empty), so resolved every file to #4's version and verified the result byte for byte. Merged #4.

**Verification**
- `main` = `6ede5ba`; byte-for-byte equal to the finished contract 2.0 work; no open PRs; only `main` on the remote.
- Fresh clone of `main`: contract-py 24, service 35, contract-ts 8/8 pass; CI on `main` green.

**Decisions:** D-072 (merge own PRs when green and conflict-free; supersedes D-052), D-073 (stacked-PR procedure; supersedes the D-063 rebase steps).

**Next**
1. Missed check-in scheduler with the 3-level escalation (`company/feat/missed-checkin-scheduler`).
2. Real-data seed: fictional company name, ClinicalTrials.gov per-arm rates, OnSIDES terms, trial documents, infant program.

---

## Session 010 — 2026-11-08 (Sun) · Missed check-in scheduler

**Goal:** Make the 1/2/3 missed check-in escalation live: alerts within a minute of a window closing, and a way to fire one on cue in the demo.

**Outputs**
- Scheduler module and in-service loop (30 s); demo CLI; contract 2.1 (`enrollment.synthetic`); Priya set up to reach level 3 on demo day.

**Verification**
- Service tests: 44 passed (9 new: due days and midnight-crossing windows, nothing while windows are open, level 3 reaching the emergency contact, idempotent runs, a check-in prevents the alert, synthetic patients never marked, cadence skips non-due days, the care team sees the level, demo window control). Contract-py 24 passed.
- Live (service with a 5 s interval, real clock 2026-11-08 02:18 UTC): no false alerts while windows were open; `close-window` on Walter raised his miss at level 2 (continuing yesterday's seeded miss) within one interval; the service log has no names or phone numbers.

**Decisions:** D-074 to D-076.

**Open items**
- A late device check-in after midnight UTC counts for the day it arrives (edge case; fine for the demo).
- D-008, D-039; teammates' GitHub handles; branch protection on `main`.

**Next**
1. Real-data seed: fictional company name, ClinicalTrials.gov per-arm rates (FLAURA, MARIPOSA), OnSIDES-corrected terms, trial documents in the company `document` table, an infant program (MELODY).
2. Company portal (`apps/company-web`).

---

## Session 011 — 2026-11-08 (Sun) · Scheduler merged; teammates active; CODEOWNERS

**Outputs**
- #11 (missed check-in scheduler) squash-merged; CI on `main` green with the teammates' work included.
- Teammates' merged PRs #7, #8, #9 changed only their own folders (checked file by file). #10 open (patient).
- `CODEOWNERS` handles filled in (D-077).

**Note for the next session:** PR numbers are shared with teammates now; always read the PR number from `gh pr create` output rather than assuming the next one.

**Next**
1. Real-data seed: fictional company name, ClinicalTrials.gov per-arm rates (FLAURA, MARIPOSA), OnSIDES-corrected terms, trial documents in the company `document` table; an infant program (MELODY) needs new term codes, so it is a contract change.
2. Company portal (`apps/company-web`).
3. Ask the repo owner to protect `main` and require CI (D-045).

---

## Session 012 — 2026-11-08 (Sun) · Real-data seed, contract 2.2

**Goal:** Ground the fictional company in real public data: a company name, real per-arm rates, label-verified terms, real trial documents and several programs (handoff item 1).

**Outputs**
- Fictional company **Halvaren Therapeutics** (D-078).
- `data/company/`:
  - `fetch_ctgov.py` → `ctgov/` (FLAURA, MARIPOSA, MELODY extracts).
  - `fetch_labels.py` → `labels/` (Tagrisso, Rybrevant, Beyfortus).
  - `fetch_documents.py` → gitignored `documents/` (6 PDFs, 19 MB).
  - `trial_map.json` and `surveys/infant_v1.json`.
- Contract 2.2, additive (D-079, D-081):
  - `cohort_id` is a pattern.
  - 6 new term codes.
  - Label-verified `drug_scope`.
  - `company` table, plus program, cohort and document credit columns.
  - Input-mode counts on completion.
  - 4 company endpoints.
- Seed: 3 programs × 4 cohorts × 250 patients, sampled from real arm rates. The invented `STORY` and the openFDA weights are gone (D-053 superseded).
- `db.py` adds new columns to existing databases (D-082).

**Verification**
- Tests: contract-py 24, service 52 (was 44), contract-ts 8/8.
- New tests:
  - Arm rates match the extracts.
  - Each seeded cohort's share of patients ever reporting a term is within 0.12 of its arm's trial share.
  - Infusion reactions appear only in the amivantamab cohorts.
  - Infant check-ins are all `parent`.
  - Every `drug_scope` row matches the label text.
  - The documents and their links.
  - The column migration.
- Live seed (scratch directory): 3 programs, 3,000 patients, 80,990 check-ins, 44,821 symptom reports, 9 documents, in about 3 s.
- Examples: no diff from `build_examples.py`. OpenAPI and `api.d.ts` regenerated.

**Findings**
- openFDA's label API has no harmonized `brand_name` for Tagrisso. It matches on `spl_product_data_elements` instead.
- FLAURA's China arms report mouth sores as "Mouth ulceration", not "Stomatitis". Non-serious events are listed only above 5%, so rare terms are 0 in the small China arms. Both are kept as real messiness.
- "Corvane" was rejected as a name because it is too close to Corvus Pharmaceuticals.

**Decisions:** D-078 to D-082 (D-053 superseded; D-061 and D-071 resolved).

**Open items**
- D-008, D-039.
- Branch protection on `main` needs the repo owner (D-045).

**Next**
1. Company portal (`apps/company-web`) on the 2.2 endpoints.
2. Ask the repo owner to protect `main`.

