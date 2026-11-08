# Doctor view

- **Owner:** Doctor side (see `CODEOWNERS`)
- **Package name:** `@sentinel/doctor-web`
- **Port:** 5174
- **Runtime data:** IndexedDB `sentinel_doctor_view`, stores per `schema/doctor_view.sql`
- **Contract:** read `schema/`; never edit it. Hashing and types come from `packages/` (see the root README).
- **Agent instructions:** `CLAUDE.md` in this folder; it imports the brief `docs/briefs/doctor-web.md` (company-maintained) and holds your own notes. `AGENTS.md` points to both.
- **Service status:** `docs/INTEGRATION_STATUS.md` · **Demo IDs:** `schema/demo_fixtures.json`
- **Contract:** 2.0 (`docs/design/contract-2.0.md`).

Structure inside this folder is up to its owner.

## Run
```bash
npm install
cp .env.example .env.local     # VITE_DOCTOR_SERVICE_URL=http://127.0.0.1:8000
npm run dev                    # doctor: http://localhost:5174 · patient: /#/patient/<ref> · full record: /#/patient/<ref>/record · caregiver: /#/caregiver
```
Start the service first (`docs/INTEGRATION_STATUS.md`) with `http://localhost:5174` and `http://127.0.0.1:5174` in `SENTINEL_ALLOWED_ORIGINS`. Each origin holds one doctor (DW-19).

Checks: `npm run build` (includes `check-secrets`) · `npx eslint src scripts`.
Architecture: `ARCHITECTURE.md` · decisions and open requests: `DECISIONS.md` · progress: `SESSION_LOG.md`.
