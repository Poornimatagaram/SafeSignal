# Patient screen

- **Owner:** Patient side (see `CODEOWNERS`)
- **Package name:** `@sentinel/patient-web`
- **Port:** 5173
- **Runtime data:** none (talks only to patient-runtime on localhost)
- **Contract:** read `schema/`; never edit it. Hashing and types come from `packages/` (see the root README).
- **Agent instructions:** `CLAUDE.md` in this folder; it imports the brief `docs/briefs/patient-web.md` (company-maintained) and holds your own notes. `AGENTS.md` points to both.
- **Service status:** `docs/INTEGRATION_STATUS.md` · **Demo IDs:** `schema/demo_fixtures.json`
- **Original brief:** Scoping Doc 26.14, Patient layer brief. Paths in that brief map to this repo as: `web/patient/` → `apps/patient-web/`.

Structure inside this folder is up to its owner.
