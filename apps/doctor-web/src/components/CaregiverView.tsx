// Caregiver alerts (AL-03): what happened, its escalation level, and when. No symptom details.
// Reads only its own alert endpoint (GET /v1/caregivers/{id}/alerts).
import { useCallback, useEffect, useState } from 'react'
import { caregiverApi } from '../lib/api'
import { config } from '../lib/config'
import { alertText, fmtTime } from '../lib/format'
import type { Alert } from '../lib/types'
import { AlertBadge } from './AlertsPanel'

// The caregiver already knows who they care for (Section 9.6); the name is local display config, not from the service.
const NAME = config.caregiverPatientLabel

const headline = (a: Alert | undefined) => {
  if (!a) return 'No alerts. Check-ins are on track.'
  if (a.alert_type === 'severe') return `${NAME} reported a severe symptom`
  if (a.alert_type === 'emergency_access') return `${NAME}'s emergency hospital opened their history`
  const level = a.escalation_level ?? 1
  if (level >= 3) return `${NAME} has missed 3 check-ins in a row. Emergency contacts were notified`
  if (level === 2) return `${NAME} has missed 2 check-ins in a row`
  return `${NAME} missed a check-in`
}
const urgent = (a: Alert | undefined) => !!a && (a.alert_type === 'severe' || (a.escalation_level ?? 0) >= 2)

export function CaregiverView() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setAlerts([...(await caregiverApi.alerts())].sort((x, y) => y.created_at.localeCompare(x.created_at)))
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, config.pollMs)
    return () => clearInterval(t)
  }, [load])

  const latest = alerts[0]
  return (
    <div className="mx-auto max-w-xl space-y-4">
      <div className={`rounded-xl p-6 ${urgent(latest) ? 'bg-red-50 ring-1 ring-red-200' : 'bg-white ring-1 ring-slate-200'}`}>
        <div className="text-sm text-slate-500">Caring for</div>
        <div className="text-2xl font-semibold text-slate-900">{NAME}</div>
        <div className="mt-3 text-lg text-slate-800">
          {headline(latest)}
          {latest && <span className="text-slate-500"> · {fmtTime(latest.created_at)}</span>}
        </div>
        <p className="mt-2 text-xs text-slate-500">You see alerts only. Health details stay with {NAME} and their care team unless they choose to share more.</p>
      </div>
      {error && <div className="rounded bg-amber-50 px-3 py-2 text-xs text-amber-800">{error}</div>}
      <ul className="divide-y divide-slate-100 rounded-lg bg-white ring-1 ring-slate-200">
        {alerts.map((a) => (
          <li key={a.alert_id} className="flex items-center gap-3 px-4 py-3">
            <AlertBadge a={{ alert_type: a.alert_type, escalation_level: a.escalation_level ?? null }} />
            <span className="flex-1 text-sm text-slate-700">{alertText({ alert_type: a.alert_type, escalation_level: a.escalation_level ?? null })}</span>
            <span className="text-xs text-slate-500">{fmtTime(a.created_at)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
