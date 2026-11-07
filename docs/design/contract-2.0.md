# Contract 2.0: care teams, emergency access and escalation

**Date:** 2026-11-07 · **Owner:** company side · **Decisions:** D-064 to D-070 · **Replaces:** the doctor-centred parts of contract 1.x

## Why 2.0

The product owner's requirements (D-058 to D-062) change who receives the patient's record:

1. **The record belongs with the hospital or clinic, not one doctor.** Doctors change; a new doctor must be able to read the history.
2. **Emergencies must not be blocked by permissions.** A hospital the patient chose for emergencies must be able to see the history when it matters.
3. **Missed check-ins escalate** over 1, 2 and 3 missed check-ins, reaching the user-defined emergency contacts (for example 911 or a preferred hospital) on the 3rd, with consent given at setup.

In 1.x, doctor envelopes were sealed to one doctor's personal key, so neither 1 nor 2 was possible. The changes are breaking, so this is a major version. No teammate code depended on 1.x yet.

## 1. Care teams (organizations) replace individual doctors as recipients

```
Patient device ──seals to──▶ Organization key (hospital/clinic care team)
                                   │
         admin wraps the org private key to each member doctor's personal key
                                   ▼
                 Doctor's browser: unwrap org key → decrypt envelopes
```

- An **organization** (`org_…`, type `hospital` or `clinic`) has a care-team key pair. Its admin generates the pair in the browser and registers only the public key.
- **Members** are doctors with a role (`attending`, `on_call`, `admin`). The admin gives each member access by **wrapping** the org private key to that doctor's personal public key (a sealed box) and uploading it as a **key grant**. The service stores key grants but cannot open them.
- **Doctor changes:** the admin revokes the leaving doctor's membership (the service stops serving them anything) and grants the new doctor. The new doctor reads the full history at once, because every envelope was sealed to the organization, not to a person.
- **Patients consent to an organization** (`care_link`), not to a doctor. Envelopes are sealed to the organization's public key.
- Known limit, stated openly: a revoked doctor who kept a copy of the org key could still decrypt envelopes they can no longer download. v1 adds key rotation.

## 2. Emergency access ("break glass")

- At setup, the patient may name **emergency hospitals** (with consent). The device then also seals each envelope to those organizations' keys, so the history is ready before any emergency happens.
- Those envelopes sit in the emergency organization's inbox, but **the service releases them only through the emergency access endpoint**: an active member must state a coded reason (`unresponsive_patient`, `emergency_admission`, `escalation_level_3`).
- Every emergency access is written to the relay access log and **notifies the patient's caregiver and care team**. Nothing is silent.
- The care-team organization reads routinely; emergency organizations read only through emergency access.

## 3. Emergency contacts (user-defined, with consent)

Set at setup inside the consent update: up to 3 contacts, each with a coded type (`emergency_service`, `hospital`, `person`), a phone number (E.164, or a short emergency number like `911`), an optional registered `org_id`, and a priority. They are stored only in the relay store (never in the company DB), used only by escalation level 3, and never logged. No free text: names of contacts stay on the device.

In the demo, notifications are shown in the app; no real calls or texts are placed (Scoping Doc 11.1).

## 4. Missed check-in escalation

A check-in is **due** on each scheduled day (the cohort's `every_days` cadence) within the patient's window. When the window closes with no record, the scheduler records a missed check-in and raises an alert whose level is the number of **consecutive** missed check-ins, capped at 3:

| Level | When | Notified (each delivery recorded) |
| --- | --- | --- |
| 1 | 1st missed check-in | Patient reminder, caregiver, care-team organization |
| 2 | 2nd consecutive | Same, marked urgent |
| 3 | 3rd consecutive (and each one after) | Same, plus every consented emergency contact |

A completed check-in resets the count. Severe symptoms still raise an immediate `severe` alert to the caregiver and the care team. Every notification is a row in `alert_delivery`, so the hospital keeps a record of who was told what, and when, regardless of which doctor is on duty.

## 5. Other 2.0 changes

| Change | Where | Decision |
| --- | --- | --- |
| `reporter`: `self`, `parent`, `caregiver`, `other` (patients aged 0–100; proxies answer) | Company record, doctor payload | D-058 |
| `input_mode`: `voice`, `text`, `mixed` (measures voice vs typing completion, Scoping Doc 7.2) | Company record | D-059 |
| `age_years` (doctor only, encrypted) | Doctor payload | D-058 |
| `schedule`: `every_days` (cadence set per cohort) | Survey configuration | D-059 |
| `escalation_level` and `received_at` on alerts | Relay alerts, API | D-060 |
| Every payload carries `schema_version: "2.0"` | All payloads | D-064 |

## 6. API changes at a glance

| 1.x | 2.0 |
| --- | --- |
| `GET /v1/doctors/{id}/public-key` (patient) | `GET /v1/orgs/{org_id}/public-key` |
| `POST /v1/doctor-envelopes` | `POST /v1/care-envelopes` (`org_id` instead of `doctor_id`) |
| `GET /v1/doctors/{id}/patients`, `/envelopes`, `/alerts`, `.../ack` | `GET /v1/orgs/{org_id}/patients`, `/envelopes`, `/alerts`; `POST .../envelopes/{id}/ack` (active members) |
| (none) | `GET /v1/doctors/{id}/orgs` (memberships) |
| (none) | `PUT /v1/orgs/{org_id}/public-key`, `POST /v1/orgs/{org_id}/key-grants`, `PUT /v1/orgs/{org_id}/members/{doctor_id}` (admin) |
| (none) | `GET /v1/orgs/{org_id}/key-grants/{doctor_id}` (that doctor) |
| (none) | `POST /v1/orgs/{org_id}/emergency-access` (member of an emergency organization; coded reason; audited; notifies) |
| `PUT /v1/doctors/{id}/public-key` | Unchanged: the doctor's personal key, used for key grants |
| `PUT /v1/consent/{patient_ref}` | Body gains care organization, emergency organizations, emergency contacts and emergency consent |
| Caregiver and company endpoints | Unchanged, except alerts gain `escalation_level` |
