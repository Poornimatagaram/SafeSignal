# Demo runbook: doctor and caregiver (about 90 seconds of the video)

Shows the Privacy-First answer from the care side: the hospital reads the history, the service never can, a doctor change keeps continuity, and an emergency hospital gets in only through audited emergency access. All data is synthetic.

## 1. Setup (10 minutes before recording)

```bash
# Terminal 1: fresh service (stop it first if running)
scripts/reset_all.sh --seed
cd apps/service && SENTINEL_ALLOWED_ORIGINS=http://localhost:5174,http://127.0.0.1:5174 \
  uv run uvicorn sentinel_service.main:app --port 8000

# Terminal 2: doctor web app
cd apps/doctor-web && npm run dev -- --host 127.0.0.1
```

Browser windows: each doctor needs separate storage (DW-19). Use separate Chrome profiles, or guest windows. Incognito windows share one storage, so they don't work for this.

| Window | Open | Pick |
|---|---|---|
| A | `http://127.0.0.1:5174` | Dr. Patel (Northgate admin) |
| B | `http://localhost:5174` | Dr. Shah (Northgate attending) |
| C | another profile, `http://127.0.0.1:5174` | Dr. Okafor (Lakeside admin) |
| D | another profile, `http://localhost:5174` | Dr. Rivera (not yet a member) |
| E | `http://127.0.0.1:5174/#/caregiver` | Anna's view |

If a window still holds an old identity: **Reset this browser**.

Keys and history (off camera, or on camera for the privacy story):
1. A (Patel): open **Admin & access** (hospital menu in the top bar, or `#/admin`), then **Create care-team key**.
2. C (Okafor): **Admin & access**, then **Create care-team key**.
3. B (Shah): **Admin & access**, then **Copy my public key**. Then in A, pick Dr. Shah and **attending**, paste the key, and click **Add and grant**.
4. Terminal: `uv run --project packages/contract-py python data/doctor/send_demo_history.py` (3 weeks for Walter and Priya; also sealed to Lakeside).
5. B: **Sync now**. Walter and Priya appear.

## 2. Script (on camera)

| Time | Show | Say |
|---|---|---|
| 0:00 | B: home (player, alerts, summary), then Walter in Patients (latest report, 21-day history; tap a day; **See full record**) | "This is Dr. Shah at Northgate. Walter's check-ins were spoken at home and processed on his device. What arrives here is sealed to Northgate's care-team key, and only this browser can open it." |
| 0:10 | B: top bar, **Clinic** | "This is what Dr. Shah opens every morning: only the alerts, the patients and the one patient she's looking at." Then back to **Guided** |
| 0:12 | Point at the grid: rash mild → moderate, "C" days, purple dots | "Rash started 12 days ago and is getting worse. 'C' means his caregiver answered that day. Purple means a possible link, for review: a flag, never a cause." |
| 0:25 | Pre-visit summary | "The summary is built from templates. No AI model sees patient data." |
| 0:32 | Terminal: `scripts/send_demo_envelope.py --alert`, then B: **Sync now** | "He reports something severe right now." The severe alert tops the list. |
| 0:40 | E: Anna's view | "His daughter sees that something happened and when. No symptoms." |
| 0:48 | A: revoke Shah; D: copy key; A: add and grant Rivera; D: **Sync now**; B: **Sync now** | "Dr. Shah leaves. The admin revokes him and grants Dr. Rivera. She sees the full history at once, and Dr. Shah sees nothing." |
| 1:08 | C: **Admin & access**, **Emergency access**, `pt_4b82d0c6`, Emergency admission, **Open history** | "Walter is brought into Lakeside, the emergency hospital he chose. They can't read routinely. They state a reason, and it's logged." |
| 1:20 | C: violet banner; E: reload | "The history opens, and Anna and Northgate are told it happened. Close it, and nothing stays in this browser." |
| 1:28 | Optional: terminal `evals/doctor/access_checks.py` summary line | "Every access rule is checked: 19 of 19 pass." |

## 3. If something goes wrong

| Symptom | Fix |
|---|---|
| "Waiting for a key grant" | The admin hasn't granted this doctor, or pasted the wrong key. Grant again. |
| Patients don't appear | The history was sent before the org key existed. Run `send_demo_history.py` again; then **Sync now**. |
| Lakeside: "No check-ins have been sealed to this hospital" | Okafor's key was created after the history was sent. Run `send_demo_history.py` again. |
| Red "envelope(s) rejected" | The org key in this browser doesn't match the registered one (for example, after a service reseed). Reset this browser and redo the setup. |
| Calls fail in the browser console (CORS) | Start the service with both origins in `SENTINEL_ALLOWED_ORIGINS`. |

## 4. After the event
`scripts/reset_all.sh`, then **Reset this browser** in every window (Scoping Doc 26.12).
