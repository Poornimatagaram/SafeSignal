# Session log: apps/doctor-web

Newest first. Per session: what was done, state at the end, next steps.

## 2026-11-07 · Session 3 (team repo, contract 2.0)
**Done**
- Found the team repo is `Poornimatagaram/SafeSignal` (the earlier PRs went to the fork; closed). In this clone `origin` is now the team repo and `fork` is `Swetha-Jalluri/SafeSignal`.
- The team repo moved to contract 2.0 (organizations, key grants, emergency access, escalation). Planned the rebuild as one branch per component (`ARCHITECTURE.md` §5); started with `doctor/feat/app-scaffold`.

- Merged #8 (scaffold). Built `src/lib/` for 2.0 on `doctor/feat/org-key-sync`; headless e2e against the seeded SQLite service passed: key setup, grant, sync with reporter and escalation levels, doctor change (Shah 403, Rivera full history), emergency access with notifications, bad reason 422.

**State**
- 1.x app saved on the fork branches `doctor/scaffold` … `doctor/caregiver-view` and `doctor/access-checks`, for reference only.

**Next**
1. Merge `doctor/feat/org-key-sync`.
2. Then the org admin, timeline, emergency access, caregiver and access-check branches, in order.

## 2026-11-07 · Session 2 (1.x, real stub service)
- Ported the staging app into `apps/doctor-web` and verified it against the 1.x stub with `scripts/send_demo_envelope.py`. Hash vectors 8/8.

## 2026-11-07 · Session 1 (staging)
- Read the scoping doc; built the doctor and caregiver app in `~/sentinel-staging/web/doctor` against an in-browser mock.
