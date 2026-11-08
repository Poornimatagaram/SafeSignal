// Emergency access, "break glass" (D-065). Only for members of an emergency organization; every use is logged by
// the service and notifies the patient's caregiver and care team. Decrypted history is held in memory only (DW-21).
import { useState } from 'react'
import { doctorApi } from '../lib/api'
import { db } from '../lib/db'
import { fmtTime } from '../lib/format'
import type { OrgStatus } from '../lib/keys'
import { checkinDays, emergencyRead, timelineEntries, type EmergencyView } from '../lib/sync'
import type { DrKey, DrPatient, EmergencyReason } from '../lib/types'
import { PreVisitSummary } from './PreVisitSummary'
import { HistoryGrid } from '../doctor/HistoryGrid'

const REASONS: { value: EmergencyReason; label: string }[] = [
  { value: 'emergency_admission', label: 'Emergency admission' },
  { value: 'unresponsive_patient', label: 'Patient is unresponsive' },
  { value: 'escalation_level_3', label: 'Level-3 missed check-in escalation' },
]
const reasonLabel = (r: string) => REASONS.find((x) => x.value === r)?.label ?? r

export function EmergencyAccess({ me, orgs }: { me: DrKey; orgs: OrgStatus[] }) {
  const usable = orgs.filter((o) => o.hasLocalKey)
  const [orgId, setOrgId] = useState(usable[0]?.org_id ?? '')
  const [patientRef, setPatientRef] = useState('')
  const [reason, setReason] = useState<EmergencyReason>('emergency_admission')
  const [view, setView] = useState<EmergencyView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  if (!usable.length) return null
  const org = usable.find((o) => o.org_id === orgId) ?? usable[0]

  const open = async () => {
    const ref = patientRef.trim()
    if (!confirm(`Open ${ref}'s history through emergency access?\n\nReason: ${reasonLabel(reason)}\nThis is logged, and the patient's caregiver and care team are notified.`)) return
    setBusy(true)
    setError(null)
    try {
      const key = await db.orgKey(org.org_id)
      if (!key) throw new Error('This browser does not hold the organization key.')
      setView(await emergencyRead(doctorApi(me.doctor_id), key, ref, reason))
    } catch (e) {
      const status = (e as { status?: number }).status
      setError(status === 403 ? 'Refused: this organization has no emergency link to that patient, or you are not a member.' : (e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="rounded-lg border border-violet-200 bg-white">
      <details open={!!view}>
        <summary className="cursor-pointer px-4 py-2.5 text-sm font-semibold text-violet-900">Emergency access</summary>
        <div className="space-y-3 border-t border-violet-100 px-4 py-3">
          {!view && (
            <>
              <p className="text-xs text-slate-500">
                For an emergency hospital the patient chose at setup. State a reason; the access is logged and the patient's caregiver
                and care team are told. Nothing is stored in this browser.
              </p>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                {usable.length > 1 && (
                  <select value={org.org_id} onChange={(e) => setOrgId(e.target.value)} className="rounded border border-slate-300 px-2 py-1">
                    {usable.map((o) => <option key={o.org_id} value={o.org_id}>{o.display_name}</option>)}
                  </select>
                )}
                <input value={patientRef} onChange={(e) => setPatientRef(e.target.value)} placeholder="Patient ID (pt_…)" className="w-44 rounded border border-slate-300 px-2 py-1 font-mono text-xs" />
                <select value={reason} onChange={(e) => setReason(e.target.value as EmergencyReason)} className="rounded border border-slate-300 px-2 py-1">
                  {REASONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
                <button disabled={busy || !/^pt_[0-9a-f]{8}$/.test(patientRef.trim())} onClick={open} className="rounded bg-violet-700 px-3 py-1 text-white disabled:opacity-50">
                  Open history
                </button>
              </div>
              {error && <p className="text-xs text-red-700">{error}</p>}
            </>
          )}
          {view && <EmergencyHistory view={view} onClose={() => setView(null)} />}
        </div>
      </details>
    </section>
  )
}

function EmergencyHistory({ view, onClose }: { view: EmergencyView; onClose: () => void }) {
  const items = [...view.payloads].sort((a, b) => a.payload.checkin_date.localeCompare(b.payload.checkin_date))
  const entries = items.flatMap((x) => timelineEntries(x.envelope, x.payload))
  const latest = items[items.length - 1]?.payload
  const done = items.filter((x) => x.payload.status !== 'missed').map((x) => x.payload.checkin_date)
  const patient: DrPatient | null = latest
    ? { patient_ref: latest.patient_ref, org_id: view.org_id, display_name: latest.display_name, age_years: latest.age_years, drug_name: latest.drug_name, drug_version: latest.drug_version, last_checkin: done[done.length - 1] ?? null, shared: 1 }
    : null
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 rounded bg-violet-700 px-3 py-2 text-sm text-white">
        <span className="font-semibold">Emergency access</span>
        <span>· {reasonLabel(view.reason)} · {fmtTime(view.accessed_at)}</span>
        <span>· notified: {view.notified.map((n) => n.replace(/_/g, ' ')).join(', ') || 'nobody'}</span>
        <button onClick={onClose} className="ml-auto rounded bg-white/15 px-2 py-0.5 text-xs hover:bg-white/25">Close and forget</button>
      </div>
      {view.rejected.length > 0 && <p className="text-xs text-red-700">{view.rejected.length} envelope(s) failed the hash or schema check and are not shown.</p>}
      {patient ? (
        <>
          <div className="flex flex-wrap items-baseline gap-x-3">
            <h2 className="text-lg font-semibold">{patient.display_name}</h2>
            <span className="text-sm text-slate-600">Age {patient.age_years} · {patient.drug_name} · version {patient.drug_version}</span>
          </div>
          <PreVisitSummary patient={patient} days={checkinDays(entries)} entries={entries} alerts={[]} />
          <HistoryGrid entries={entries} />
        </>
      ) : (
        <p className="text-sm text-slate-500">No check-ins have been sealed to this hospital for {view.patient_ref} yet.</p>
      )}
    </div>
  )
}
