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
- Every main piece of work: new branch `company/<type>/<description>` from the latest `origin/main`; Conventional Commits split by type (`CONTRIBUTING.md`); `scripts/check_ownership.sh company` and `scripts/check_commits.sh` pass; `git fetch origin` and confirm no conflicts with `main`; push the branch; open a PR with `gh pr create --base main` using the template; when CI is green and the PR shows no conflicts, **squash-merge it and delete the branch** so `main` stays current (D-072). Avoid stacked PRs; if one is unavoidable, follow the stacked-PR rules in `CONTRIBUTING.md` (D-073). Never force-push or rewrite shared history.
