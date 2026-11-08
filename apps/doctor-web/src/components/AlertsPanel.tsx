// DR-03: missed check-in (with escalation level), severe-symptom and emergency-access alerts (D-068).
import type { DrAlert } from '../lib/types'
import { alertText, fmtTime } from '../lib/format'

const BADGE = 'whitespace-nowrap rounded-full px-2.5 py-0.5 text-[11px] font-extrabold text-plum'

export function AlertBadge({ a }: { a: Pick<DrAlert, 'alert_type' | 'escalation_level'> }) {
  if (a.alert_type === 'severe') return <span className={`${BADGE} bg-rose-tint`}>Severe</span>
  if (a.alert_type === 'emergency_access') return <span className={`${BADGE} bg-mauve`}>Emergency access</span>
  const level = a.escalation_level ?? 1
  const tone = level >= 3 ? 'bg-plum !text-white' : level === 2 ? 'bg-rose-tint' : 'bg-butter-tint'
  return <span className={`${BADGE} ${tone}`}>Missed · L{level}</span>
}

export function AlertsPanel(props: {
  alerts: DrAlert[]
  nameOf: (ref: string) => string
  onSeen: (id: string) => void
  onOpen?: (ref: string) => void
}) {
  const unseen = props.alerts.filter((a) => !a.seen_at).length
  return (
    <section className="self-start rounded-lg border border-slate-200 bg-white">
      <header className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
        <h2 className="text-sm font-semibold text-slate-800">Alerts</h2>
        <span className="text-xs text-slate-500">{unseen} new</span>
      </header>
      <ul className="max-h-96 divide-y divide-slate-100 overflow-y-auto">
        {props.alerts.length === 0 && <li className="px-4 py-3 text-sm text-slate-500">No alerts.</li>}
        {props.alerts.map((a) => (
          <li key={a.alert_id} className={`flex items-center gap-3 px-4 py-2.5 ${a.seen_at ? 'opacity-60' : ''}`}>
            <AlertBadge a={a} />
            <button className="min-w-0 flex-1 text-left" onClick={() => props.onOpen?.(a.patient_ref)}>
              <div className="truncate text-sm font-medium text-slate-800">{props.nameOf(a.patient_ref)}</div>
              <div className="text-xs text-slate-500">{alertText(a)} · {fmtTime(a.created_at)}</div>
            </button>
            {!a.seen_at && (
              <button onClick={() => props.onSeen(a.alert_id)} className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50">
                Mark seen
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
