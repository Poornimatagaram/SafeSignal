# Instructions

## Sources of truth (read before working)
- `Side-Effect Sentinel — Scoping Document.md`: product scope; Section 26 is the data contract.
- `docs/DECISIONS.md`: overrides the scoping document wherever they differ.
- `schema/`: SQL, JSON Schemas, `enums.json`, `terms.json`, `examples/`, `openapi.json`. Never invent fields, tables or endpoints outside it.
- `docs/SESSION_LOG.md`: read the latest session's "Next" before starting.

## Every work block, before you finish
Update all four, even when it feels redundant:
1. `CHANGELOG.md`: every change made.
2. `docs/DECISIONS.md`: every decision taken (new ID, never renumber; supersede instead of editing).
3. `docs/SESSION_LOG.md`: append this session's goal, outputs, verification, open items and next steps.
4. `CLAUDE.md`: only if these instructions change. Keep it to instructions and pointers.

## Rules
- Schema changes: follow Scoping Doc 26.11 protocol; bump `schema_version`, update `schema/CHANGELOG.md`, run `uv run python scripts/build_examples.py` and `uv run python scripts/export_openapi.py`.
- Security rules in Scoping Doc 26.12 are blocking; never log payload bodies, never commit `*.db`, `.env`, keys or audio.
- Before finishing: `uv run pytest -q` and `node schema/examples/check_hash_vectors.mjs` must pass.
- Commit only when the user asks.
