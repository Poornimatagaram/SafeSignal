# Doctor web: agent instructions

@../../docs/briefs/doctor-web.md

<!-- The brief above is maintained by the company owner. Everything below is the doctor owner's. -->

## Read first
`ARCHITECTURE.md` (how it fits) · `DEMO.md` (demo runbook) · `DECISIONS.md` (why; open requests) · `SESSION_LOG.md` (where we stopped).
When you finish: add to `CHANGELOG.md` and `SESSION_LOG.md`; new decisions go in `DECISIONS.md`.

## Also in this app
Caregiver view at `#/caregiver`: `GET /v1/caregivers/{id}/alerts`, `X-Role: caregiver`, Anna `cg_7e21c9a4`. Alert type, escalation level and time only (DW-02).

## Commands
`npm run dev` · `npm run build` (includes `check-secrets`) · `npx eslint src scripts`

## Git
`CONTRIBUTING.md`: one `doctor/<type>/<topic>` branch per component, built on the previous unmerged one (DW-22); commit scope `doctor-web` (or `evals`); run `scripts/check_ownership.sh` and `scripts/check_commits.sh` before pushing; push the branch only; the user merges later (DW-22). Never push to `main`.

## Secrets
No promo codes or API keys anywhere (code, docs, logs, commits). Keys go only in `.env.local`. `VITE_*` values ship to the browser, so sponsor keys are never `VITE_*`.
