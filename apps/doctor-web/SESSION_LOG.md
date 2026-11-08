# Session log: apps/doctor-web

Newest first. Per session: what was done, state at the end, next steps.

## 2026-11-08 · Session 5 (Clinic view)
**Done**
- Split the doctor UI into Guided (tour and demo) and Clinic (daily use) after sorting every component by whether a regular doctor needs it. Prototyped Clinic in the artifact (23/23 checks), then built it on `doctor/feat/clinic-view`. Headless check on a freshly seeded service: 72/72 (52 earlier plus Clinic, widths 390 to 1920). Contrast audit on Clinic: no failures in light or dark.

## 2026-11-08 · Session 4 (doctor UI redesign)
**Done**
- Designed the doctor UI as a prototype artifact (Flip Ads layout as reference, doctor content only); iterated on alignment, arrows and a labelled light/dark/system switch. User confirmed it.
- Built it into the app on `doctor/feat/doctor-view-redesign` on top of the unchanged `src/lib/` (sync, keys, store). Headless test against an isolated seeded service (port 8010): key setup and grant, history to both hospitals, sync, home sections, patients, grid, Mark seen, record tabs, guide, admin, emergency access, modes, routing, desktop and phone with no sideways scroll.

**Next**
1. Merge the pull request when CI is green (DW-30); then refine in follow-up pull requests.
2. Restart the live service on 8000 with `scripts/reset_all.sh --seed` before the demo and redo the key setup.

## 2026-11-07 · Session 3 (team repo, contract 2.0)
**Done**
- Found the team repo is `Poornimatagaram/SafeSignal` (the earlier PRs went to the fork; closed). In this clone `origin` is now the team repo and `fork` is `Swetha-Jalluri/SafeSignal`.
- The team repo moved to contract 2.0 (organizations, key grants, emergency access, escalation). Planned the rebuild as one branch per component (`ARCHITECTURE.md` §5); started with `doctor/feat/app-scaffold`.

- Merged #8 (scaffold). Built `src/lib/` for 2.0 on `doctor/feat/org-key-sync`; headless e2e against the seeded SQLite service passed: key setup, grant, sync with reporter and escalation levels, doctor change (Shah 403, Rivera full history), emergency access with notifications, bad reason 422.

- Merged #9 (lib). Built the identity picker and org admin panel on `doctor/feat/org-admin`; headless UI test passed (Patel creates key, grants Shah from a pasted key, bad key rejected, Shah gets the key).
- New rule (DW-22): push branches only, no merging into `main`; merge `main` in every 30 minutes when clean.

- Built the timeline view on `doctor/feat/timeline-view` (on top of org-admin); headless UI check with screenshot passed.

- Built emergency access on `doctor/feat/emergency-access`; headless test passed (Okafor opens Walter's history, nothing stored; Shah at Northgate refused; Northgate gets the alert).

- Built the caregiver view on `doctor/feat/caregiver-view`; headless test passed (seeded missed L1, new severe alert, no symptom names).

- Ported the 26.15 doctor checks to 2.0 on `doctor/test/access-checks`: 19/19 pass (results in `evals/doctor/results/`). Service reseeded afterwards.

- Added `data/doctor/send_demo_history.py` on `doctor/feat/demo-history`; sent 16 days for Walter and 10 for Priya to Northgate on the live service; a re-run skips them (409).

- Wrote `DEMO.md` on `doctor/docs/demo-runbook`. Patient runtime (PR 10) doesn't send care envelopes yet, so live integration waits; `send_demo_history.py` stands in.

- Built the landing pages into the app on `doctor/feat/landing-page` (React + Tailwind). Headless test: 25/25 (routes, interactions, text size, doctor and caregiver still connect to the service). Found and fixed DW-25.

- Re-read the scope: doctor-only UI (3.7, 9.4, DR-01..04, D-062, D-066). Confirmed the screens in a prototype canvas, then built them on `doctor/feat/doctor-view-redesign`. Headless test against an isolated seeded service (port 8010): 26/26.

**State**
- 1.x app saved on the fork branches `doctor/scaffold` … `doctor/caregiver-view` and `doctor/access-checks`, for reference only.

**Next**
1. Pushed, not merged: `doctor/feat/org-admin`, `doctor/feat/timeline-view`, `doctor/feat/emergency-access`, `doctor/feat/caregiver-view`, `doctor/test/access-checks`, `doctor/feat/demo-history`, `doctor/docs/demo-runbook`. Merge order: org-admin → timeline-view → emergency-access → caregiver-view → access-checks → demo-history → demo-runbook.
2. Then the org admin, timeline, emergency access, caregiver and access-check branches, in order.

## 2026-11-07 · Session 2 (1.x, real stub service)
- Ported the staging app into `apps/doctor-web` and verified it against the 1.x stub with `scripts/send_demo_envelope.py`. Hash vectors 8/8.

## 2026-11-07 · Session 1 (staging)
- Read the scoping doc; built the doctor and caregiver app in `~/sentinel-staging/web/doctor` against an in-browser mock.
