# Doctor view

- **Owner:** Doctor side (see `CODEOWNERS`)
- **Package name:** `@sentinel/doctor-web`
- **Port:** 5174
- **Runtime data:** IndexedDB `sentinel_doctor_view`, stores per `schema/doctor_view.sql`
- **Contract:** read `schema/`; never edit it. Hashing and types come from `packages/` (see the root README).
- **Agent instructions:** `CLAUDE.md` in this folder (`AGENTS.md` is a link to it) — start there.
- **Service status:** `docs/INTEGRATION_STATUS.md` · **Demo IDs:** `schema/demo_fixtures.json`
- **Original brief:** Scoping Doc 26.14, Doctor layer brief. Paths in that brief map to this repo as: `web/doctor/` → `apps/doctor-web/`; generated types → `import type { paths } from "@sentinel/contract/api"`; hashing → `import { payloadSha256 } from "@sentinel/contract"`.

Structure inside this folder is up to its owner.
