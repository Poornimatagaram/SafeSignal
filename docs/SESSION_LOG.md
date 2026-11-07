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
