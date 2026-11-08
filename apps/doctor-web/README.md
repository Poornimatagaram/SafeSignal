# Doctor web (`apps/doctor-web`)

The doctor's side of SafeSignal. A care team reads its patients' side-effect check-ins, and the alerts about them, before each visit. Every check-in arrives sealed to the care team's key and is opened only in the doctor's browser. The service relays ciphertext and can never read it.

| | |
|---|---|
| **Owner** | Doctor side (`CODEOWNERS`: `apps/doctor-web/`, `evals/doctor/`, `data/doctor/`) |
| **Package** | `@sentinel/doctor-web` · Vite, React 19, TypeScript, Tailwind 3 |
| **Live** | `https://safesignal-doctor.onrender.com` (Render static site, built from `main`) |
| **Port** | 5174 (`http://127.0.0.1:5174` and `http://localhost:5174`) |
| **Contract** | 2.2, read-only from `schema/` and `packages/contract-ts`; never edit them |
| **Crypto** | `libsodium-wrappers` sealed boxes (X25519), keys in standard base64 |
| **Browser data** | IndexedDB `sentinel_doctor_view`, six stores from `schema/doctor_view.sql` |
| **Brief** | `docs/briefs/doctor-web.md` (company-maintained) · agent notes in `CLAUDE.md` (`AGENTS.md` points to both) |
| **Logs** | `DECISIONS.md` (DW-01…), `CHANGELOG.md`, `SESSION_LOG.md` · demo script in `DEMO.md` · `ARCHITECTURE.md` |
| **Service status** | `docs/INTEGRATION_STATUS.md` · demo IDs in `schema/demo_fixtures.json` |

All patients, doctors and records are synthetic.

---

## Contents
1. [Run it](#1-run-it) · [Deployed on Render](#deployed-on-render)
2. [Where it sits in SafeSignal](#2-where-it-sits-in-safesignal)
3. [The privacy line](#3-the-privacy-line)
4. [From a spoken check-in to the doctor's screen](#4-from-a-spoken-check-in-to-the-doctors-screen)
5. [Keys: how a doctor gets to read a care team's records](#5-keys-how-a-doctor-gets-to-read-a-care-teams-records)
6. [Sync, step by step](#6-sync-step-by-step)
7. [Doctor change](#7-doctor-change)
8. [Emergency access](#8-emergency-access)
9. [Alerts and escalation](#9-alerts-and-escalation)
10. [Screens and routes](#10-screens-and-routes)
11. [Guided and Clinic views](#11-guided-and-clinic-views)
12. [Inside the code](#12-inside-the-code)
13. [Browser data](#13-browser-data)
14. [Theme and accessibility](#14-theme-and-accessibility)
15. [Checks and tests](#15-checks-and-tests)

---

## 1. Run it

```bash
# 1. The service, with both doctor origins allowed (from the repo root)
scripts/reset_all.sh --seed
cd apps/service && SENTINEL_ALLOWED_ORIGINS=http://localhost:5174,http://127.0.0.1:5174 \
  uv run uvicorn sentinel_service.main:app --port 8000

# 2. The doctor app
cd apps/doctor-web
npm install
cp .env.example .env.local      # VITE_DOCTOR_SERVICE_URL=http://127.0.0.1:8000
npm run dev -- --host 127.0.0.1 # http://127.0.0.1:5174
```

| Address | What it is |
|---|---|
| `/#/` | Home: Guided or Clinic view, whichever this browser last chose |
| `/#/patient/<ref>` | Home with that patient open |
| `/#/patient/<ref>/record` | Detailed view: check-in log, alert history, sharing and access, field meanings, screen map |
| `/#/guide` | Field meanings and screen map, for every patient |
| `/#/admin` | Admin & access: care-team keys, members, emergency access, reset this browser |
| `/#/caregiver` | Anna's caregiver view (alerts only, never symptoms) |
| `/#/about`, `/#/learn` | Patient-facing pages; no service calls |

Each browser profile holds one doctor (DW-19). For the demo, use a separate Chrome profile per doctor (`DEMO.md`).

Changed `tailwind.config.js`? Restart `npm run dev`; the dev server does not reload it.

### Deployed on Render

```mermaid
flowchart LR
  GH["GitHub main<br/>apps/doctor-web · packages/contract-ts · schema"] -->|"commit in those paths"| BUILD["Render build<br/>npm ci && npm run build"]
  BUILD --> SITE["Static site<br/>safesignal-doctor.onrender.com"]
  SITE -->|"API calls (CORS: origin must be allowed)"| SVC["safesignal-service.onrender.com<br/>company-owned"]
  P1["Chrome profile: Dr. Patel"] & P2["Chrome profile: Dr. Shah"] & P3["Chrome profile: Dr. Okafor"] & P4["Chrome profile: Dr. Rivera"] --> SITE
```

| Render setting | Value |
|---|---|
| Type | Static Site, repo `Poornimatagaram/SafeSignal`, branch `main` |
| Root directory | `apps/doctor-web` |
| Build command | `npm ci && npm run build` (includes the secrets check) |
| Publish directory | `dist` |
| Environment | `VITE_DOCTOR_SERVICE_URL=https://safesignal-service.onrender.com` (no trailing slash) · `NODE_VERSION=22` |
| Build filters | `apps/doctor-web/**`, `packages/contract-ts/**`, `schema/**` |
| Rewrite | `/*` → `/index.html` |

- **One address, many doctors:** each doctor uses a separate Chrome profile on the same address; browser storage, and so the keys, is per profile (DW-19, DW-33).
- **Allowed origin:** the company owner lists `https://safesignal-doctor.onrender.com` in the service's `SENTINEL_ALLOWED_ORIGINS` (`docs/DEPLOY.md`). Check it with:
  ```bash
  curl -si -X OPTIONS https://safesignal-service.onrender.com/v1/terms \
    -H "Origin: https://safesignal-doctor.onrender.com" -H "Access-Control-Request-Method: GET" | grep -i access-control-allow-origin
  ```
- **`VITE_*` values are baked in at build time:** after changing one, use **Manual Deploy → Deploy latest commit**, not a restart.
- **Free tier:** the service sleeps after 15 idle minutes (the first call takes about 50 s; open `/healthz` a minute before a demo). Every service restart or deploy resets its data, so each doctor profile then uses **Reset this browser** and redoes the key setup.
- **Demo day:** set Auto-Deploy to **Off** so the site can't change mid-demo, and merge nothing to `main` in the last hour.

---

## 2. Where it sits in SafeSignal

```mermaid
flowchart LR
  subgraph PATIENT["Patient side · on Walter's device"]
    PW["patient-web :5173"] -->|localhost only| PR["patient-runtime :8001<br/>speech → label terms → egress gate"]
  end

  subgraph COMPANY["Company side"]
    SVC["service :8000<br/>API · relay · escalation scheduler"]
    CW["company-web :5175"]
    CW --> SVC
  end

  subgraph DOCTOR["Doctor side · doctor-web :5174"]
    NG["Northgate care team<br/>Dr. Patel (admin) · Dr. Shah · Dr. Rivera"]
    LS["Lakeside emergency hospital<br/>Dr. Okafor (admin)"]
    CG["Caregiver view<br/>Anna"]
  end

  PR -->|"sealed care envelopes<br/>one per organization"| SVC
  SVC -->|"ciphertext, alerts, key grants"| NG
  SVC -->|"only through emergency access"| LS
  SVC -->|"alert type and time only"| CG
```

---

## 3. The privacy line

The service stores and relays envelopes it cannot open. Private keys never leave the browsers that hold them.

```mermaid
flowchart TB
  subgraph DEVICE["Patient device"]
    V["Voice check-in"] --> T["Label terms, severity, onset, trend"]
    T --> E["Seal to the care team's public key"]
  end
  subgraph SERVICE["Service: can't read"]
    C[("Ciphertext<br/>+ payload hash")]
    W[("Wrapped org keys<br/>sealed to each doctor")]
  end
  subgraph BROWSER["Doctor's browser: the only place it opens"]
    K["Personal key + org key<br/>IndexedDB only"]
    O["Open → check hash → check schema"]
    S["Timeline, alerts, summary"]
  end
  E --> C --> O
  W --> K --> O --> S
  NEVER1["✕ audio and transcripts<br/>never leave the device"]
  NEVER2["✕ nothing decrypted<br/>is sent back"]
  V -.- NEVER1
  S -.- NEVER2
```

| Never leaves the patient's device | Never leaves the doctor's browser | Never in this app |
|---|---|---|
| Audio, transcripts, everyday words | Personal and org private keys, decrypted check-ins | Cloud AI on patient data, analytics, tracking, third-party fonts |

---

## 4. From a spoken check-in to the doctor's screen

```mermaid
sequenceDiagram
  autonumber
  actor W as Walter
  participant P as patient-runtime
  participant S as service
  participant B as Dr. Shah's browser
  W->>P: speaks the daily check-in
  P->>P: on-device: words → label terms, severity, onset, trend
  P->>S: POST /v1/care-envelopes (sealed to Northgate, and to Lakeside if chosen)
  S->>S: store ciphertext, scheduler watches for missed check-ins
  B->>S: GET /v1/orgs/{org}/envelopes?since=…
  S-->>B: envelopes (ciphertext)
  B->>B: open with Northgate's key → hash → schema 2.0
  B->>B: store in dr_patient and dr_timeline_entry
  B->>S: POST /v1/orgs/{org}/envelopes/{id}/ack
  B->>S: GET /v1/orgs/{org}/alerts?since=…
  Note over B: Every 10 s, or on Sync now. Alerts show within a minute of the event.
```

---

## 5. Keys: how a doctor gets to read a care team's records

```mermaid
sequenceDiagram
  autonumber
  participant M as Member (Dr. Shah)
  participant A as Admin (Dr. Patel)
  participant S as service
  M->>M: first launch: personal X25519 key pair → dr_key
  M->>S: PUT /v1/doctors/{me}/public-key
  A->>A: once per organization: care-team key pair → dr_org_key
  A->>S: PUT /v1/orgs/{org}/public-key
  M-->>A: public key, pasted by hand ("Copy my public key")
  A->>A: seal the org private key to the member's public key
  A->>S: POST /v1/orgs/{org}/key-grants {doctor_id, wrapped_key}
  M->>S: GET /v1/orgs/{org}/key-grants/{me}
  M->>M: open the grant → dr_org_key
  Note over M,A: All of this is under Admin & access (#/admin).
```

How a hospital's key status reads in the top bar's hospital menu:

```mermaid
stateDiagram-v2
  [*] --> NoKey: org has no care-team key
  NoKey --> Waiting: admin creates the key
  Waiting --> HasKey: admin grants this doctor, sync opens the grant
  HasKey --> Waiting: grant withdrawn (revoked)
  Waiting --> Mismatch: grant was made for this doctor's key in another browser
  Mismatch --> HasKey: admin grants again for this browser
  NoKey: No care-team key yet
  Waiting: Waiting for a key grant
  HasKey: Key in this browser
  Mismatch: Grant made for another browser
```

---

## 6. Sync, step by step

```mermaid
flowchart TD
  start(["Every 10 s or Sync now"]) --> reg["Register personal public key (first run)"]
  reg --> orgs["Fetch memberships → open any new key grant"]
  orgs --> forget{"Membership or grant gone?"}
  forget -- yes --> drop["Forget that org's key and its records in this browser"]
  forget -- no --> each["For each org key in dr_org_key"]
  drop --> each
  each --> pts["GET patients → anyone no longer listed: shared = 0, kept read-only"]
  pts --> env["GET envelopes since the org's cursor"]
  env --> open{"Opens with the org key?"}
  open -- no --> rej["Reject · no ack · cursor still moves"]
  open -- yes --> hash{"payload_sha256 matches?"}
  hash -- no --> rej
  hash -- yes --> schema{"Valid doctor_payload 2.0?"}
  schema -- no --> rej
  schema -- yes --> store["Upsert dr_patient and dr_timeline_entry"] --> ack["POST ack"]
  ack --> alerts["GET alerts since cursor → dr_alert"]
  rej --> alerts
  alerts --> ui(["Screens re-render · most urgent first"])
```

Rejection reasons are shown as a count ("n check-ins failed the safety checks") and never include decrypted content.

---

## 7. Doctor change

The record belongs to the care team, so the next doctor sees the full history and the one who left sees nothing.

```mermaid
sequenceDiagram
  autonumber
  participant A as Dr. Patel (admin)
  participant S as service
  participant O as Dr. Shah (leaving)
  participant N as Dr. Rivera (joining)
  A->>S: PUT /v1/orgs/{org}/members/{shah} {status: revoked}
  S->>S: delete Shah's key grant, refuse his calls (403)
  O->>S: next sync
  S-->>O: no membership
  O->>O: forget Northgate's key and records in this browser
  N-->>A: public key (Copy my public key)
  A->>S: set member + POST key grant for Dr. Rivera
  N->>S: sync
  S-->>N: grant + the whole history
  N->>N: Walter's three weeks appear at once
```

---

## 8. Emergency access

For an emergency hospital the patient chose at setup (Lakeside for Walter). It never reads routinely.

```mermaid
sequenceDiagram
  autonumber
  participant D as Dr. Okafor (Lakeside)
  participant S as service
  participant CG as Anna (caregiver)
  participant NG as Northgate care team
  D->>D: Admin & access → Emergency access: patient ID + coded reason
  Note right of D: emergency_admission · unresponsive_patient · escalation_level_3
  D->>S: POST /v1/orgs/{org}/emergency-access
  S->>S: check the patient chose this hospital, log the access
  S-->>D: envelopes sealed to Lakeside
  S->>CG: emergency_access alert
  S->>NG: emergency_access alert
  D->>D: open in memory only, show the banner (reason, time, who was told)
  D->>D: Close and forget: nothing stays in this browser
```

---

## 9. Alerts and escalation

```mermaid
stateDiagram-v2
  direction LR
  [*] --> OnTime: check-in received
  OnTime --> L1: a due check-in's window closes with nothing
  L1 --> L2: next one missed too
  L2 --> L3: third in a row
  L3 --> L3: more missed (capped at 3)
  L1 --> OnTime: check-in received
  L2 --> OnTime: check-in received
  L3 --> OnTime: check-in received
  L1: Level 1 · patient reminder, caregiver, care team
  L2: Level 2 · same people, marked urgent
  L3: Level 3 · also the emergency contacts the patient consented to
```

| Alert | Who is told (D-068) | Shown as |
|---|---|---|
| Missed check-in, level 1–2 | Patient (reminder), caregiver, care team | Clock icon, level bars |
| Missed check-in, level 3 | The same people, plus consented emergency contacts | Urgent, most urgent first |
| Severe symptom | Caregiver and care team | Warning icon, top of the queue |
| Emergency access | Caregiver and care team | Logged; shown on the patient's record |

The app shows these rules; it does not receive delivery records. Alerts are for the doctor's review and never diagnose.

---

## 10. Screens and routes

```mermaid
flowchart LR
  ID(["First launch:<br/>Who is using this browser?"]) --> HOME
  subgraph HOME["#/ Home"]
    direction TB
    G["Guided view"]
    C["Clinic view"]
    G <-->|"top-bar switch<br/>(remembered)"| C
  end
  HOME -->|"pick a patient"| PT["#/patient/ref<br/>patient open in the current view"]
  PT -->|"Full record"| REC["#/patient/ref/record<br/>log · alerts · sharing · fields · map"]
  REC -->|Back| PT
  HOME -->|"Detailed view, footer"| GUIDE["#/guide<br/>field meanings · screen map"]
  HOME -->|"hospital menu → Admin & access"| ADMIN["#/admin<br/>keys · members · emergency · reset"]
  HOME -.->|footer| CARE["#/caregiver<br/>Anna's alerts"]
```

---

## 11. Guided and Clinic views

Two views of the same app (DW-32): same data, sync and components, so they can't drift apart.

```mermaid
flowchart TB
  subgraph GUIDED["Guided: for new doctors and the demo"]
    direction TB
    g1["Hero: patient finder + day-by-day player"] --> g2["1 · Term cards: everyday words → label terms"]
    g2 --> g3["2 · Alerts card (5 most urgent, Show all)"]
    g3 --> g4["3 · Pre-visit summary"]
    g4 --> g5["Patients + patient page + 21-day grid"]
    g5 --> g6["History chart + who-is-told table"]
    g6 --> g7["Privacy · emergency promise · Signal on/off · FAQ · footer"]
  end
  subgraph CLINIC["Clinic: for doctors who use it every day"]
    direction LR
    subgraph LEFT["Left column"]
      direction TB
      c1["Today · search ( / )"]
      c2["Alerts queue<br/>Mark seen · who is told on demand"]
      c3["Patients<br/>All · Alerts · Worse · 21-day strip<br/>j / k to move"]
      c1 --> c2 --> c3
    end
    c4["Open patient<br/>facts · latest report · short summary<br/>21-day grid · Full record"]
    LEFT --> c4
  end
```

| Kept in Clinic | Only in Guided (and the Guide page) |
|---|---|
| Top bar: hospital, sync, appearance, view switch | Section links, hero, day-by-day player |
| Alerts queue with Mark seen | Term cards, numbered steps, arrow connectors |
| Patient list with a 21-day strip | Promise strip, access-checks card |
| Open patient: facts, latest report, summary, grid | Symptoms chart, who-is-told table |
| Full record, Admin & access | Privacy, emergency promise, Signal on/off, FAQ, footer |

On phones the view switch moves into the ☰ menu, next to Appearance.

---

## 12. Inside the code

```mermaid
flowchart TB
  MAIN["main.tsx<br/>applies the saved appearance before first render"] --> APP["App.tsx<br/>doctor routes · #/caregiver · #/about · #/learn"]
  APP --> DA["doctor/DoctorApp.tsx<br/>routes, hospital filter, toasts"]
  APP --> CGV["components/CaregiverView"]
  APP --> LAND["landing/: Landing, LearnMore"]

  DA --> NAV["doctor/Nav.tsx<br/>sections · Guided/Clinic · hospital menu · appearance · sync"]
  DA --> HOMEG["doctor/home/<br/>Hero · Live · Static"]
  DA --> WS["doctor/Workspace.tsx<br/>patient list + patient page"]
  DA --> CL["doctor/Clinic.tsx"]
  DA --> FR["doctor/FullRecord.tsx<br/>record tabs · Guide"]
  DA --> AD["doctor/AdminPage.tsx"]
  AD --> OP["components/OrgPanel"]
  AD --> EA["components/EmergencyAccess"]
  WS & CL & EA --> HG["doctor/HistoryGrid.tsx"]
  HOMEG & EA --> PVS["components/PreVisitSummary<br/>doctor/summary.ts (templates)"]

  subgraph LIB["lib/: no UI"]
    UDD["useDoctorData.ts<br/>identity · orgs · sync loop · rows"]
    KEYS["keys.ts"] --- CRY["crypto.ts (libsodium)"]
    SYNC["sync.ts"] --- VAL["validate.ts (Ajv, schema 2.0)"]
    API["api.ts (allowed calls only)"]
    DB["db.ts (IndexedDB)"]
    THEME["theme.ts · viewMode.ts<br/>stored in this browser only"]
  end
  DA --> UDD
  UDD --> KEYS & SYNC & DB
  SYNC & KEYS --> API
  API --> SVC[("service :8000")]
  NAV --> THEME
```

| Folder | Holds |
|---|---|
| `src/lib/` | Keys, crypto, sync, validation, API client, IndexedDB, appearance and view mode. No UI. |
| `src/doctor/` | Doctor screens, the display model (`model.ts`), routes, icons, the template summary. |
| `src/components/` | Shared pieces: identity picker, org panel, emergency access, pre-visit summary, caregiver view. |
| `src/landing/` | Patient-facing pages; static, no service calls. |
| `src/theme.css` | Theme tokens (light, dark) and the doctor screens' styles. Tailwind colours point at the same tokens. |

---

## 13. Browser data

IndexedDB `sentinel_doctor_view`, one store per table in `schema/doctor_view.sql`. "Reset this browser" (Admin & access) deletes all of it.

```mermaid
erDiagram
  dr_key {
    string doctor_id PK
    string public_key
    string private_key "never exported"
    string created_at
  }
  dr_org_key {
    string org_id PK
    string public_key
    string private_key "never exported"
    string obtained_at
  }
  dr_patient {
    string patient_ref PK
    string org_id FK
    string display_name
    int age_years
    string drug_name
    string drug_version
    string last_checkin
    int shared "0 = no longer shared"
  }
  dr_timeline_entry {
    string entry_id PK "envelope_id:term_code"
    string patient_ref FK
    string envelope_id
    string checkin_date
    string status
    string reporter
    string term_code
    string severity
    string onset
    int known_side_effect
    int possible_link_flag
    string trend
  }
  dr_alert {
    string alert_id PK
    string org_id FK
    string patient_ref FK
    string alert_type "missed, severe, emergency_access"
    int escalation_level "1 to 3"
    string created_at
    string seen_at
  }
  dr_sync_state {
    string sync_key PK "org:envelopes or org:alerts"
    string since "newest received_at seen"
  }
  dr_org_key ||--o{ dr_patient : "opens records of"
  dr_patient ||--o{ dr_timeline_entry : has
  dr_patient ||--o{ dr_alert : has
  dr_org_key ||--o{ dr_sync_state : "cursor per org"
```

Emergency-access data is never written here; it lives in memory until "Close and forget" (DW-21).

---

## 14. Theme and accessibility

```mermaid
flowchart LR
  pick["Appearance: Light · Dark · System<br/>(top bar or ☰ menu)"] --> save["Saved in this browser"]
  save --> boot["Applied before first render"]
  boot --> sys{"System?"}
  sys -- yes --> os["Follows the device's light/dark setting live"]
  sys -- no --> fixed["data-theme = light or dark"]
  os & fixed --> tokens["Theme tokens in theme.css"] --> all["Doctor screens, admin forms,<br/>caregiver and public pages"]
```

| Rule | How it's met |
|---|---|
| Text contrast 4.5:1 (3:1 for large text) | Light and dark tokens measured; rendered-page audit: 0 failures (DW-31) |
| Not by colour alone | Grid severity is colour **and** fill height (a third, two thirds, full); trend and alerts have words and icons |
| Readable sizes | Smallest text 11 px |
| Tap targets | Controls 24 px or more, grid day buttons spaced |
| Motion | Respects reduced motion; animations are short and optional |
| Keyboard | Visible focus; `/` search and `j`/`k` in Clinic; menus close with Esc |
| Fonts | Fredoka, DM Sans, DM Mono, self-hosted (no font CDN) |

---

## 15. Checks and tests

```bash
npm run lint          # ESLint
npm run build         # type-check + build + scripts/check-secrets.sh
# from the repo root:
uv run --project packages/contract-py python evals/doctor/access_checks.py    # 26.15 access and privacy checks: 19/19 on contract 2.2
uv run --project packages/contract-py python data/doctor/send_demo_history.py # synthetic 3-week history for Walter and Priya
scripts/check_ownership.sh && scripts/check_commits.sh                          # before every push
```

Before each pull request, the app was also checked in a headless browser against an isolated, freshly seeded service (72 checks):
- key setup, grants and sync
- every home section in both views
- patients, the grid and Mark seen
- the record tabs, the guide and admin
- emergency access
- light, dark and system modes
- routing
- no sideways scrolling from 390 to 1920 px
