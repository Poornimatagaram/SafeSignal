# Company-side instructions (contract owner)

Applies when working in folders the company side owns: `schema/`, `packages/`, `apps/service/`, `apps/company-web/`, `scripts/`, `docs/`, root files. Root `CLAUDE.md` rules also apply.

## Sources
- `docs/scoping-document.md` (Section 26 is the contract we own), `docs/DECISIONS.md`, latest "Next" in `docs/SESSION_LOG.md`.

## Every work block, before you finish
Update all four, even when it feels redundant:
1. `CHANGELOG.md`: every change made.
2. `docs/DECISIONS.md`: every decision taken (new ID, never renumber; supersede instead of editing).
3. `docs/SESSION_LOG.md`: append this session's goal, outputs, verification, open items and next steps.
4. `CLAUDE.md` / this file / `docs/briefs/*.md`: only if instructions change. Keep them to instructions and pointers.

Also update `docs/INTEGRATION_STATUS.md` whenever service behaviour changes.

## Rules
- Schema changes: follow Scoping Doc 26.11 protocol; bump `schema_version`, update `schema/CHANGELOG.md`, run `uv run --project packages/contract-py python scripts/build_examples.py` and `uv run --project apps/service python scripts/export_openapi.py`, regenerate `packages/contract-ts/src/api.d.ts`, and update the "Changed from the scoping doc" list in each affected `docs/briefs/*.md`. Never edit files inside teammates' app folders (D-047).
- Before finishing, all must pass: `uv run pytest -q` in `packages/contract-py` and in `apps/service`; `npm test --prefix packages/contract-ts`.
- Work on a `company/<topic>` branch; `scripts/check_ownership.sh company` must pass; commit, merge into `main` and push to `origin` only when the user asks. Never force-push.
