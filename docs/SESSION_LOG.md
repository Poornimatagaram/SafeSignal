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
