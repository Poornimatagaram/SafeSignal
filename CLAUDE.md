# Instructions (every agent in this repo)

## Find your instructions
| You work in | Read |
| --- | --- |
| `apps/patient-runtime/` | `apps/patient-runtime/CLAUDE.md` (imports `docs/briefs/patient-runtime.md`) |
| `apps/patient-web/` | `apps/patient-web/CLAUDE.md` (imports `docs/briefs/patient-web.md`) |
| `apps/doctor-web/` | `apps/doctor-web/CLAUDE.md` (imports `docs/briefs/doctor-web.md`) |
| `schema/`, `packages/`, `apps/service/`, `apps/company-web/`, `scripts/`, `docs/`, root files | `docs/company/CLAUDE.md` |

## Sources of truth
- `schema/`: the contract (tables, payloads, enums, terms, demo IDs, API). Never invent fields, tables or endpoints outside it.
- `docs/DECISIONS.md`: overrides `docs/scoping-document.md` wherever they differ.
- `docs/INTEGRATION_STATUS.md`: what the service does today.
- `README.md` and `CODEOWNERS`: layout, ownership, ports, names.

## Rules for everyone
- Edit only the folders your owner owns (`CODEOWNERS`). `schema/` and `packages/` are read-only outside the company side; request changes from the company owner.
- Keep your log in your own folder (`apps/<app>/CHANGELOG.md`); never edit root `CHANGELOG.md`, `docs/DECISIONS.md` or `docs/SESSION_LOG.md` from an app.
- Git: follow the README "Git workflow". Work on a `<company|patient|doctor>/<topic>` branch, never commit to `main` directly, never force-push, and run `scripts/check_ownership.sh` before every push; it must pass. Commit and push only when your user asks.
- In `evals/` and `data/`, write only inside your area's subfolder (`evals/<area>/`, `data/<area>/`).
- Security (Scoping Doc 26.12) is blocking: synthetic data only; never commit `*.db`, `.env`, keys or audio; never log transcripts, patient words, names, decrypted payloads or request bodies; no cloud speech, cloud AI on patient data, analytics or tracking.
- Runtime databases live under `var/<app>/` only.
