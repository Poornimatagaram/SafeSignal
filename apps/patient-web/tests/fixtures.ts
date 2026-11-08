// Synthetic runtime responses shared by the tests (no real patient data).
import type { CareShare, CheckinSummary, ConsentState, EgressReceipt, OutboxReceipt } from '../src/api.ts'

export const BASE = 'http://127.0.0.1:8001'
export const SID = 'ses_1a2b3c4d'
export const SERVICE_RECORDS = 'http://127.0.0.1:8000/v1/records'

export const FIELDS = [
  'consent.care_team',
  'consent.caregiver',
  'cohort_id',
  'drug_version',
  'input_mode',
  'iso_week',
  'patient_ref',
  'program_id',
  'record_id',
  'reporter',
  'schema_version',
  'status',
  'symptoms[].known_side_effect',
  'symptoms[].onset',
  'symptoms[].possible_link_flag',
  'symptoms[].severity',
  'symptoms[].term_code',
  'unanswered_questions',
]

export const RECORD = {
  schema_version: '2.0',
  record_id: 'rec_7f3c9a1e',
  patient_ref: 'pt_4b82d0c6',
  program_id: 'prog_demo_01',
  cohort_id: 'cohort_B',
  drug_version: 'v2',
  iso_week: '2026-W45',
  status: 'completed',
  reporter: 'self',
  input_mode: 'voice',
  symptoms: [
    { term_code: 'SE_RASH', severity: 'moderate', onset: '1_3_days', known_side_effect: true, possible_link_flag: false },
  ],
  unanswered_questions: 0,
  consent: { care_team: true, caregiver: false },
}

const SHARE = {
  destination: 'Drug company safety team (Sentinel service)',
  method: 'POST',
  url: SERVICE_RECORDS,
  fields: FIELDS,
  care: null,
}

/** A rash with everything known: ready to share. */
export const SUMMARY_READY: CheckinSummary = {
  session_id: SID,
  shared: false,
  items: [{ term_code: 'SE_RASH', label: 'Rash', severity: 'moderate', onset: '1_3_days', known_side_effect: true }],
  needs_severity: [],
  unanswered_questions: 0,
  text: 'You told me about: rash, moderate, started 1 to 3 days ago.',
  spoken: 'Here is what I heard. You have a rash. It is moderate. It started 1 to 3 days ago.',
  correction_used: false,
  share: { ...SHARE, record: RECORD },
}

/** A rash whose severity the patient still has to choose: no record yet. */
export const SUMMARY_NEEDS_SEVERITY: CheckinSummary = {
  ...SUMMARY_READY,
  items: [
    { term_code: 'SE_RASH', label: 'Rash', severity: null, onset: '1_3_days', known_side_effect: true },
    { term_code: 'SE_FATIGUE', label: 'Fatigue', severity: 'mild', onset: null, known_side_effect: true },
  ],
  needs_severity: ['SE_RASH'],
  text: 'You told me about: rash, started 1 to 3 days ago; fatigue, mild.',
  share: { ...SHARE, record: null },
}

/** Nothing to report: sharing still says "no new problems". */
export const SUMMARY_EMPTY: CheckinSummary = {
  ...SUMMARY_READY,
  items: [],
  unanswered_questions: 1,
  text: 'You did not tell me about any new problems.',
  share: { ...SHARE, record: { ...RECORD, symptoms: [], unanswered_questions: 1 } },
}

export const RECEIPT_SENT: EgressReceipt = {
  status: 'sent',
  record_id: 'rec_7f3c9a1e',
  destination: 'Drug company safety team (Sentinel service)',
  method: 'POST',
  url: SERVICE_RECORDS,
  fields_sent: FIELDS,
  payload_sha256: '3f2a9c0b7d1e4f5a6b8c9d0e1f2a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c',
  sent_at: '2026-11-08T14:03:12Z',
  response_code: 201,
  alert: null,
  envelope: null,
  envelopes: [],
}

export const RECEIPT_QUEUED: EgressReceipt = { ...RECEIPT_SENT, status: 'queued', sent_at: null, response_code: null }

export const RECEIPT_FAILED: EgressReceipt = { ...RECEIPT_SENT, status: 'failed', response_code: 422 }

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

/** A severe rash: the care team and caregiver were told (AL-02). */
export const ALERT_SENT = { status: 'sent', alert_id: 'alt_5d0e2b7c', sent_at: '2026-11-08T14:03:13Z' } as const
export const ALERT_QUEUED = { status: 'queued', alert_id: 'alt_5d0e2b7c', sent_at: null } as const

/** The summary after the one correction: the rash is now mild. */
export const SUMMARY_CORRECTED: CheckinSummary = {
  ...SUMMARY_READY,
  items: [{ ...SUMMARY_READY.items[0], severity: 'mild' }],
  text: 'You told me about: rash, mild, started 1 to 3 days ago.',
  spoken: 'Here is what I heard. You have a rash. It is mild. It started 1 to 3 days ago.',
  correction_used: true,
}

// ---- Care envelope and consent (CN-01, CN-03) ----

export const SERVICE_ENVELOPES = 'http://127.0.0.1:8000/v1/care-envelopes'

/** The fields inside the sealed care-team record. */
export const CARE_FIELDS = [
  'age_years',
  'checkin_date',
  'display_name',
  'drug_name',
  'drug_version',
  'patient_ref',
  'reporter',
  'schema_version',
  'status',
  'symptoms[].onset',
  'symptoms[].severity',
  'symptoms[].term_code',
  'trend',
]

export const CARE: CareShare = { org_id: 'org_demo_clinic', method: 'POST', url: SERVICE_ENVELOPES, sealed: true, fields: CARE_FIELDS, emergency: [] }

/** Ready to share, also with the care team (sealed). */
export const SUMMARY_WITH_CARE: CheckinSummary = { ...SUMMARY_READY, share: { ...SUMMARY_READY.share, care: CARE } }

export const ENVELOPE_SENT: OutboxReceipt = {
  status: 'sent',
  outbox_id: 'env_9c1d2e3f',
  destination: 'care_envelope',
  method: 'POST',
  url: SERVICE_ENVELOPES,
  fields_sent: ['ciphertext', 'envelope_id', 'org_id', 'patient_ref', 'payload_sha256', 'schema_version'],
  payload_sha256: '9b8a7c6d5e4f30211203f4e5d6c7b8a99a8b7c6d5e4f30211203f4e5d6c7b8a9',
  sent_at: '2026-11-08T14:03:14Z',
  response_code: 201,
  label: 'Your care team (sealed: only your doctors can read it)',
}
export const ENVELOPE_QUEUED: OutboxReceipt = { ...ENVELOPE_SENT, status: 'queued', sent_at: null, response_code: null }
export const ENVELOPE_NO_KEY = { status: 'waiting', reason: 'no_key' } as const
export const ENVELOPE_OFFLINE = { status: 'waiting', reason: 'offline' } as const
export const ENVELOPE_REFUSED = { status: 'waiting', reason: 'refused' } as const

export const CONSENT_RECEIPT_SENT: OutboxReceipt = {
  status: 'sent',
  outbox_id: 'con_1a2b3c4d',
  destination: 'consent',
  method: 'PUT',
  url: 'http://127.0.0.1:8000/v1/consent',
  fields_sent: ['care_team', 'caregiver', 'patient_ref'],
  payload_sha256: '1f2e3d4c5b6a79881f2e3d4c5b6a79881f2e3d4c5b6a79881f2e3d4c5b6a7988',
  sent_at: '2026-11-08T14:10:00Z',
  response_code: 200,
  label: null,
}
export const CONSENT_RECEIPT_QUEUED: OutboxReceipt = {
  ...CONSENT_RECEIPT_SENT,
  status: 'queued',
  sent_at: null,
  response_code: null,
}

/** Both switches on, both set up, nothing sent yet. */
export const CONSENT_ON: ConsentState = {
  share_care_team: true,
  share_caregiver: true,
  has_care_team: true,
  has_caregiver: true,
  receipt: null,
  setup: null,
  options: { organizations: [], caregivers: [] },
}
