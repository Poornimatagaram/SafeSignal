# Architecture: apps/doctor-web (contract 2.2)

How the doctor and caregiver views fit into the SafeSignal repo. Names, ports and calls match `README.md`, `CODEOWNERS`, `schema/`, `docs/briefs/doctor-web.md` and `docs/design/contract-2.0.md`. If this file disagrees with them, they win.

## 1. Whole system

```mermaid
flowchart LR
  subgraph PATIENT["Patient side · Walter's device"]
    PW["apps/patient-web :5173"] -->|localhost only| PR["apps/patient-runtime :8001<br/>on-device speech-to-text → filter → egress gate"]
    PR --- PDB[("var/patient/patient.db")]
  end

  subgraph COMPANY["Company side"]
    SVC["apps/service :8000<br/>API · relay · escalation"]
    SVC --- CDB[("var/service/company.db")]
    SVC --- RDB[("var/service/relay.db<br/>ciphertext + wrapped keys only")]
    CW["apps/company-web :5175"] -->|/v1/company/*| SVC
  end

  subgraph DOCTOR["Doctor side · apps/doctor-web :5174"]
    DV["Doctor view<br/>Northgate: Dr. Shah, Dr. Patel (admin), Dr. Rivera<br/>Lakeside: Dr. Okafor (emergency)"]
    CG["Caregiver view #/caregiver · Anna"]
    HOME["Public pages #/ and #/learn<br/>no service calls"]
    DV --- IDB[("IndexedDB sentinel_doctor_view<br/>dr_patient · dr_timeline_entry · dr_alert<br/>dr_key · dr_org_key · dr_sync_state")]
  end

  SCH["schema/ + packages/ (contract, company-owned)"] -.-> PR & SVC & DV

  PR -->|"POST /v1/care-envelopes (sealed to org key)<br/>POST /v1/records · /v1/alerts · PUT /v1/consent"| SVC
  DV -->|"keys · grants · members<br/>org patients / envelopes / alerts / ack<br/>emergency-access"| SVC
  CG -->|"GET /v1/caregivers/{id}/alerts"| SVC
```

Privacy line: the service only holds ciphertext and wrapped keys. Organization private keys exist only in member doctors' browsers (`dr_org_key`); nothing decrypted leaves the browser.

## 2. Keys: how a doctor gets to read an organization's records

```mermaid
sequenceDiagram
  participant M as Member doctor's browser (e.g. Dr. Shah)
  participant A as Admin's browser (Dr. Patel)
  participant S as apps/service
  M->>M: first launch: personal X25519 pair → dr_key
  M->>S: PUT /v1/doctors/{me}/public-key
  A->>A: once per org: org key pair → dr_org_key
  A->>S: PUT /v1/orgs/{org}/public-key
  M-->>A: member's public key (copied by hand in the demo; no lookup endpoint yet)
  A->>A: crypto_box_seal(org private key, member public key)
  A->>S: POST /v1/orgs/{org}/key-grants {doctor_id, wrapped_key}
  M->>S: GET /v1/orgs/{org}/key-grants/{me}
  M->>M: crypto_box_seal_open → dr_org_key
  Note over A,S: Doctor change: admin PUTs members/{old} status "revoked" (grant deleted), grants the new doctor, who reads the full history.
```

## 3. Sync, per organization

```mermaid
sequenceDiagram
  participant B as Doctor browser
  participant S as apps/service
  loop every poll / "Sync now", for each org with a key in dr_org_key
    B->>S: GET /v1/orgs/{org}/patients (care-team patients)
    B->>S: GET /v1/orgs/{org}/envelopes?since=<org>:envelopes
    B->>B: open with org key → payloadSha256 matches → schema 2.0 valid?
    alt valid
      B->>B: upsert dr_patient (age, drug) and dr_timeline_entry (reporter)
      B->>S: POST /v1/orgs/{org}/envelopes/{id}/ack
    else invalid
      B->>B: reject, no ack, cursor still advances
    end
    B->>S: GET /v1/orgs/{org}/alerts?since=<org>:alerts → dr_alert (escalation level)
    B->>B: patients no longer listed → shared = 0 (kept, read-only)
  end
```

Emergency organizations (Lakeside) do not sync routinely. A member states a coded reason, `POST /v1/orgs/{org}/emergency-access` returns the envelopes, and the app shows an "Emergency access" banner with the reason. The service logs it and notifies Anna and Northgate.

## 4. Inside the app

See `README.md` §10–§13 for the current screens, routes, Guided and Clinic views, code structure and browser data, each with a diagram.

## 5. What is on `main`

| Pull request | Contents |
|---|---|
| #8 | Vite/React/TS setup, secret check, app docs |
| #9 | `src/lib/`: keys, grants, per-org sync, IndexedDB 2.0 |
| #16 | `evals/doctor/`: 26.15 access and privacy checks (19/19 on contract 2.2) |
| #17 | `data/doctor/`: synthetic 3-week demo history |
| #18 | Key grant made in another browser no longer blanks every organization |
| #28 | Doctor UI (DW-29): home, patients, detailed view, guide, Admin & access, caregiver view, emergency access, light/dark/system |
| #30 | Accessibility pass (DW-31) |
| #35 | Clinic view (DW-32) |

New work goes on a `doctor/<type>/<topic>` branch from `main` and into a pull request (CONTRIBUTING).
