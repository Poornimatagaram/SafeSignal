# Instructions

## Sources of truth (read before working)
- `docs/scoping-document.md`: product scope; Section 26 is the data contract. Its old paths map per D-030.
- `docs/DECISIONS.md`: overrides the scoping document wherever they differ.
- `schema/`: SQL, JSON Schemas, `enums.json`, `terms.json`, `examples/`, `openapi.json`. Never invent fields, tables or endpoints outside it.
- `docs/SESSION_LOG.md`: read the latest session's "Next" before starting.
- `README.md` and `CODEOWNERS`: layout, ownership, ports, names. Edit only folders we own (D-027).

## Every work block, before you finish
Update all four, even when it feels redundant:
1. `CHANGELOG.md`: every change made.
2. `docs/DECISIONS.md`: every decision taken (new ID, never renumber; supersede instead of editing).
3. `docs/SESSION_LOG.md`: append this session's goal, outputs, verification, open items and next steps.
4. `CLAUDE.md`: only if these instructions change. Keep it to instructions and pointers.

## Rules
- Schema changes: follow Scoping Doc 26.11 protocol; bump `schema_version`, update `schema/CHANGELOG.md`, run `uv run --project packages/contract-py python scripts/build_examples.py` and `uv run --project apps/service python scripts/export_openapi.py`, then regenerate `packages/contract-ts/src/api.d.ts`.
- Security rules in Scoping Doc 26.12 are blocking; never log payload bodies, never commit `*.db`, `.env`, keys or audio.
- Before finishing, all must pass: `uv run pytest -q` in `packages/contract-py` and in `apps/service`; `npm test --prefix packages/contract-ts`.
- Work on a `company/<topic>` branch; merge into `main` only when the user asks.
- Commit only when the user asks.
