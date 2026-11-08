# Changelog: apps/doctor-web

Changes in this app, newest first. Owned by this app's owner (root `CLAUDE.md`).

## 2026-11-08
- Changed: doctor UI rebuilt from the confirmed prototype (DW-29). Home: hero with patient finder and a day-by-day player of the open patient's 21 days; term cards from `schema/terms.json`; alerts card (5 most urgent, Show all, Mark seen, who is told); pre-visit summary as notes; patient list and patient page (new alerts, facts, latest symptom report, 21-day grid with pinned symptom names); symptoms-per-check-in chart; who-is-told table (D-068); privacy, compare and questions. Detailed view per patient: check-in log, alert history, sharing and access, field meanings, screen map. New `#/guide` and `#/admin` (keys, members, emergency access, reset). Removed `PatientList` and `PatientPage`.
- Added: light, dark and system modes: labelled switch in the top bar and in the phone menu, remembered in this browser, applied before the first render.
- Changed: theme tokens in `src/theme.css`; Tailwind colours (including slate and violet) point at them. Fonts: Fredoka, DM Sans, DM Mono (self-hosted); Nunito and Poppins removed.
- Changed: the hospital menu shows each organization's role and key status and links to Admin & access.

## 2026-11-07
- Changed: doctor UI rebuilt in the pastel theme as three screens: patient list with alerts; patient page with latest check-in, pre-visit summary, 21-day history (tap a day) and alerts; full record with check-in log, alert history (who is told), sharing and access, and field meanings. Admin tools and emergency access moved behind "Admin & access". Removed the old DoctorView and Timeline and the `recharts` dependency.
- Added: public home page (`#/`) and Learn more (`#/learn`) in the pastel soft-UI theme: example check-in with play, one-week "what your doctor sees", who sees what, questions, topics with expandable answers, "Bigger text" (remembered). Doctor view moved to `#/doctor`; doctor and caregiver headers restyled with a link home. Fonts self-hosted.
- Fixed: a key grant made in another browser no longer blanks every organization; the org shows what to do instead (DW-25).
- Added: `DEMO.md`: setup, window layout, 90-second script with lines, and fixes for the doctor and caregiver part of the demo video.
- Added: `data/doctor/send_demo_history.py` (branch `doctor/feat/demo-history`): fixed synthetic 3-week history for Walter and Priya, re-runnable.
- Added: `evals/doctor/access_checks.py` for contract 2.0 (branch `doctor/test/access-checks`): 19/19 pass on a freshly seeded service; 17/17 when the doctor app holds the org keys.
- Added: caregiver view at `#/caregiver` for Anna: alert type, escalation level (2nd and 3rd missed in a row, emergency contacts notified), emergency-access notices and time only; no symptom details (AL-03). The doctor sync runs only on the doctor route.
- Added: emergency access for emergency hospitals: patient ID plus coded reason, confirmation, banner with reason, time and who was notified; history decrypted in memory only (DW-21), "Close and forget".
- Added: doctor view for 2.0: care-team patient list sorted by urgency (age, drug version, trend), symptom grid marking who answered, severity chart, template pre-visit summary (age, proxy answers, escalation), alerts with escalation level and emergency-access type.
- Added: first-launch identity picker; Organizations panel with key status, "Copy my public key", and admin tools (create care-team key, add and grant with a pasted key, revoke).
- Added: `src/lib/` for contract 2.0: personal and org keys, key grants (wrap/unwrap), admin add/grant/revoke, per-org sync on `received_at`, IndexedDB with the six 2.0 stores, emergency-access read (memory only), caregiver alerts client.
- Added: Vite/React/TS/Tailwind app on port 5174 with a placeholder screen; `scripts/check-secrets.sh` runs after every build.
- Added: `ARCHITECTURE.md` (contract 2.0), `DECISIONS.md`, `SESSION_LOG.md`; trimmed `CLAUDE.md`.
