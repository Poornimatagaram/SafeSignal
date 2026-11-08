// DR-04: pre-visit summary built by templates from structured records only (no model, no cloud).
// Every sentence is traceable to stored fields; links are worded "for review", never as a cause.
import type { DrAlert, DrPatient, DrTimelineEntry } from '../lib/types'
import type { CheckinDay } from '../lib/sync'
import { summarySections } from '../doctor/summary'

// The summary as chat-style notes (also used inside emergency access).
export function PreVisitSummary(props: { patient: DrPatient; days: CheckinDay[]; entries: DrTimelineEntry[]; alerts: DrAlert[] }) {
  const sections = summarySections(props.patient, props.days, props.entries, props.alerts)
  return (
    <div className="chat">
      <div className="chat-head">
        <span className="av">{props.patient.display_name[0]}</span>
        <div>
          <b>Pre-visit summary</b>
          <div className="small">
            {props.patient.display_name}, {props.patient.age_years} · {props.patient.drug_name} {props.patient.drug_version} · last 21 days
          </div>
        </div>
        <span className="tag">Template · no AI</span>
      </div>
      <div className="chat-body">
        {sections.map((s, i) => (
          <div key={s.title} className="bubble" style={{ animationDelay: `${i * 0.08}s` }}>
            <h4>{s.title}</h4>
            <ul>
              {s.items.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}
