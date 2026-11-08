# Decision log: apps/doctor-web

This app's own decisions, newest first. Repo-wide decisions are in `docs/DECISIONS.md` and win on conflict. Supersede rather than delete.

| # | Date | Decision | Why | By |
|---|---|---|---|---|
| DW-21 | 2026-11-07 | Emergency-access data is decrypted in memory only and never stored; each look is a new audited request | Break-glass reads should not leave a standing copy in an emergency hospital's browser | Claude |
| DW-20 | 2026-11-07 | When a doctor's membership or key grant is gone, drop that org key and everything read through that org from this browser | Brief: after a doctor change, the old doctor "sees nothing" | Claude |
| DW-19 | 2026-11-07 | One doctor identity per browser origin, picked on first launch from `schema/demo_fixtures.json`. For the demo, use separate origins (`localhost:5174`, `127.0.0.1:5174`) or browser profiles | `dr_org_key` is keyed by org only, so two doctors sharing one database would share org keys; a revoked doctor must see nothing | Claude |
| DW-18 | 2026-11-07 | Admin gets a member's public key by copy and paste | The brief has no lookup endpoint yet (v1 adds one) | Repo |
| DW-17 | 2026-11-07 | Drop the in-browser mock (supersedes DW-04) | The SQLite service seeds the whole demo; a 2.0 mock would duplicate org keys, grants and emergency access | Claude |
| DW-16 | 2026-11-07 | Rebuild for contract 2.0: organizations, org keys and key grants, per-org sync, escalation levels, reporter and age, emergency access | Team repo moved to 2.0 (D-064 to D-070) | Repo |
| DW-15 | 2026-11-07 | Work goes to the team repo `Poornimatagaram/SafeSignal`, one `doctor/<type>/<topic>` branch per component, merged when green before the next starts (supersedes DW-14) | `CONTRIBUTING.md`; the fork PRs were invisible to the team | User |
| DW-14 | 2026-11-07 | ~~Stacked branches on the fork~~ | Superseded by DW-15 | User |
| DW-13 | 2026-11-07 | Selection follows the most urgent patient until the doctor clicks one | A new severe alert should surface without a click | Claude |
| DW-12 | 2026-11-07 | Revoked patients stay, read-only, under "No longer shared" (`dr_patient.shared = 0`) | D-038 | Repo |
| DW-09 | 2026-11-07 | Sort patients: unseen severe or level-3 alert → worsening trend → unseen alerts → name | Most urgent first | Claude |
| DW-08 | 2026-11-07 | `last_checkin` ignores `status: missed` envelopes | A missed day is not a check-in | Claude |
| DW-06 | 2026-11-07 | Rejected envelopes are not acked; the cursor still advances | Avoids refetch loops | Claude |
| DW-05 | 2026-11-07 | Re-register the personal public key on every start | Keeps the service on this browser's key | Claude |
| DW-04 | 2026-11-07 | ~~In-browser mock service~~ | Superseded by DW-17 | Claude |
| DW-02 | 2026-11-07 | Caregiver view lives in this app | Team decision (closes D-039 once recorded) | User |
| DW-01 | 2026-11-07 | Doctor app is its own Vite app on port 5174 | D-026 | User |

DW-03, DW-07, DW-10 and DW-11 applied to contract 1.x and are retired.

## Sponsor credits (codes and keys never in the repo)
Rule: no cloud service touches patient data. Credits are spent at build time on public or synthetic data, or on the pitch.

| Credit | Use here | Never |
|---|---|---|
| Gradium 100K | Pre-rendered caregiver alert audio; synthetic voices for tests and video | Live check-ins or runtime calls |
| Exa $50 / Tavily 8K | Build-time cited label facts per term code, shipped as static JSON; pitch research | Queries containing anything from a decrypted payload |
| Sanity 1 yr | Company owner's call (non-patient content) | Records or alerts |
| Bravado $200, Claude Pro | Pending | — |

## Open: requests to the company owner
1. **D-039:** record "caregiver view in doctor-web" and add `GET /v1/caregivers/{id}/alerts` to the doctor brief's allowed calls.
2. **CODEOWNERS:** replace `@DOCTOR_OWNER` with `@Swetha-Jalluri` (D-046).
3. **Audio:** root `.gitignore` drops `*.mp3`/`*.wav`. Gradium clips are synthetic, non-patient audio: allow a path (for example `apps/doctor-web/public/audio/`) or regenerate them at build time.
4. **Check-in rows:** check-ins with no symptoms, and missed ones, leave no `dr_timeline_entry`, so the timeline can't show them. Proposed: a `dr_checkin(envelope_id PK, org_id, patient_ref, checkin_date, status, trend, reporter)` store.
5. **Public-key lookup:** an admin-only `GET /v1/orgs/{org_id}/members/{doctor_id}/public-key` would remove the copy-and-paste step (DW-18).
6. **INTEGRATION_STATUS:** says Priya's seeded missed alerts have levels 1 and 2, but all are level 1 (her misses on Oct 18, 20 and 22 are not consecutive). Either the seed or the doc needs a fix.
