# Changelog: apps/doctor-web

Changes in this app, newest first. Owned by this app's owner (root `CLAUDE.md`).

## 2026-11-07
- Fixed: a key grant made for this doctor in another browser no longer fails the whole sync; that organization is marked `grantMismatch` and the others keep working (DW-25).
- Added: `src/lib/` for contract 2.0: personal and org keys, key grants (wrap/unwrap), admin add/grant/revoke, per-org sync on `received_at`, IndexedDB with the six 2.0 stores, emergency-access read (memory only), caregiver alerts client.
- Added: Vite/React/TS/Tailwind app on port 5174 with a placeholder screen; `scripts/check-secrets.sh` runs after every build.
- Added: `ARCHITECTURE.md` (contract 2.0), `DECISIONS.md`, `SESSION_LOG.md`; trimmed `CLAUDE.md`.
