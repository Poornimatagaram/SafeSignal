// Per-organization sync: fetch → decrypt with the org key → hash → validate → store → ack (contract 2.0).
// Nothing decrypted is ever sent back: the only writes are keys, grants, membership changes and acks.
import { payloadSha256 } from '@sentinel/contract'
import type { DoctorApi } from './api'
import { openSealedText, type KeyPair } from './crypto'
import { db } from './db'
import type { AlertType, CheckinStatus, EmergencyReason, DoctorPayload, DrOrgKey, DrTimelineEntry, Envelope, Reporter, Trend } from './types'
import { validateDoctorPayload } from './validate'

export interface Rejection {
  envelope_id: string
  patient_ref: string
  reason: string // never contains decrypted content
  at: string
}

export interface SyncResult {
  accepted: number
  rejected: Rejection[]
  newAlerts: number
}

export interface CheckinDay {
  date: string
  status: CheckinStatus
  trend: Trend
  reporter: Reporter
}

const pair = (k: DrOrgKey): KeyPair => ({ publicKey: k.public_key, privateKey: k.private_key })

// Decrypt and verify one envelope. Throws with a reason that never includes payload content.
export async function openEnvelope(env: Envelope, key: DrOrgKey): Promise<DoctorPayload> {
  let raw: unknown
  try {
    raw = JSON.parse(await openSealedText(env.ciphertext, pair(key)))
  } catch {
    throw new Error('decryption failed (sealed to a different key?)')
  }
  if ((await payloadSha256(raw)) !== env.payload_sha256) throw new Error('payload_sha256 mismatch')
  const p = validateDoctorPayload(raw)
  if (p.patient_ref !== env.patient_ref) throw new Error('patient_ref does not match envelope')
  return p
}

export function timelineEntries(env: Envelope, p: DoctorPayload): DrTimelineEntry[] {
  return p.symptoms.map((s) => ({
    entry_id: `${env.envelope_id}:${s.term_code}`,
    patient_ref: p.patient_ref,
    envelope_id: env.envelope_id,
    checkin_date: p.checkin_date,
    status: p.status,
    reporter: p.reporter,
    term_code: s.term_code,
    severity: s.severity,
    onset: s.onset,
    known_side_effect: s.known_side_effect ? 1 : 0,
    possible_link_flag: s.possible_link_flag ? 1 : 0,
    trend: p.trend,
  }))
}

// last_checkin = newest day the patient actually checked in; a missed day is not a check-in (DW-08).
const newest = (prev: string | null, p: DoctorPayload) =>
  p.status === 'missed' ? prev : prev && prev > p.checkin_date ? prev : p.checkin_date

async function store(orgId: string, env: Envelope, p: DoctorPayload) {
  const prev = await db.getPatient(p.patient_ref)
  await db.putPatient({
    patient_ref: p.patient_ref,
    org_id: orgId,
    display_name: p.display_name,
    age_years: p.age_years,
    drug_name: p.drug_name,
    drug_version: p.drug_version,
    last_checkin: newest(prev?.last_checkin ?? null, p),
    shared: 1,
  })
  await db.putTimelineEntries(timelineEntries(env, p))
}

export async function syncOrg(api: DoctorApi, key: DrOrgKey): Promise<SyncResult> {
  const org = key.org_id
  const result: SyncResult = { accepted: 0, rejected: [], newAlerts: 0 }

  // Care-team patients right now; anyone stored from this org but no longer listed has revoked (D-038).
  const linked = new Set((await api.patients(org)).map((l) => l.patient_ref))

  for (const env of await api.envelopes(org, await db.getSince(org, 'envelopes'))) {
    try {
      await store(org, env, await openEnvelope(env, key))
      await api.ack(org, env.envelope_id)
      result.accepted++
    } catch (e) {
      // Not acked; the cursor still advances so one bad envelope can't block the stream (DW-06).
      result.rejected.push({ envelope_id: env.envelope_id, patient_ref: env.patient_ref, reason: (e as Error).message, at: new Date().toISOString() })
    }
    await db.setSince(org, 'envelopes', env.received_at)
  }

  for (const p of await db.allPatients()) {
    const shared = linked.has(p.patient_ref) ? 1 : 0
    if (p.org_id === org && p.shared !== shared) await db.putPatient({ ...p, shared })
  }

  for (const a of await api.alerts(org, await db.getSince(org, 'alerts'))) {
    await db.putAlert({ ...a, org_id: org, alert_type: a.alert_type as AlertType, seen_at: null })
    await db.setSince(org, 'alerts', a.received_at)
    result.newAlerts++
  }
  return result
}

// Emergency access (D-065): released envelopes are decrypted in memory only and never stored (DW-21),
// so every later look needs a new, audited request.
export interface EmergencyView {
  org_id: string
  patient_ref: string
  reason: string
  accessed_at: string
  notified: string[]
  payloads: { envelope: Envelope; payload: DoctorPayload }[]
  rejected: Rejection[]
}

export async function emergencyRead(api: DoctorApi, key: DrOrgKey, patientRef: string, reason: EmergencyReason): Promise<EmergencyView> {
  const r = await api.emergencyAccess(key.org_id, patientRef, reason)
  const view: EmergencyView = { org_id: r.org_id, patient_ref: r.patient_ref, reason: r.reason, accessed_at: r.accessed_at, notified: r.notified as string[], payloads: [], rejected: [] }
  for (const env of r.envelopes as Envelope[]) {
    try {
      view.payloads.push({ envelope: env, payload: await openEnvelope(env, key) })
    } catch (e) {
      view.rejected.push({ envelope_id: env.envelope_id, patient_ref: env.patient_ref, reason: (e as Error).message, at: new Date().toISOString() })
    }
  }
  return view
}

// One row per check-in that reported symptoms. Envelopes with no symptoms, or status 'missed', leave no
// timeline entry in schema/doctor_view.sql, so those days can't be shown yet (open request 4).
export function checkinDays(entries: DrTimelineEntry[]): CheckinDay[] {
  const byEnvelope = new Map<string, CheckinDay>()
  for (const e of entries) byEnvelope.set(e.envelope_id, { date: e.checkin_date, status: e.status, trend: e.trend, reporter: e.reporter })
  return [...byEnvelope.values()].sort((a, b) => a.date.localeCompare(b.date))
}
