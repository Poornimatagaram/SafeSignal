// DR-01: symptoms by day for the last 21 days. Columns are days (tap one), rows are symptoms, colour = severity.
import { useEffect, useRef, useState } from 'react'
import type { DrTimelineEntry } from '../lib/types'
import { SEV_VAR, byDay, dayNum, daysAgo, longDate, reporterLabel, shortDate, weekdayLetter, windowDates } from './model'

export function HistoryGrid({ entries, title = 'Last 21 days' }: { entries: DrTimelineEntry[]; title?: string }) {
  const days = byDay(entries)
  const dates = windowDates(days)
  const todayIso = daysAgo(0)
  const lastWithData = [...days.keys()].filter((d) => dates.includes(d)).pop()
  const [picked, setPicked] = useState<string | undefined>()
  const sel = picked ?? lastWithData ?? dates[dates.length - 1]
  const terms = [...new Set(dates.flatMap((d) => days.get(d)?.symptoms.map((s) => s.term) ?? []))]
  const d = days.get(sel)
  const scroller = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (scroller.current) scroller.current.scrollLeft = scroller.current.scrollWidth // newest days first on a phone
  }, [])

  return (
    <div className="grid-wrap">
      <div className="grid-head">
        <h4>{title}</h4>
        <Legend />
      </div>
      <div className="hgrid" ref={scroller}>
        <table>
          <colgroup>
            <col className="rc" />
            {dates.map((x) => <col key={x} />)}
          </colgroup>
          <thead>
            <tr>
              <th />
              {dates.map((date) => {
                const day = days.get(date)
                const on = date === sel
                return (
                  <th key={date}>
                    <button
                      type="button"
                      onClick={() => setPicked(date)}
                      aria-pressed={on}
                      aria-label={longDate(date) + (day ? '' : ', no symptom report')}
                      className={`dbtn ${on ? 'sel' : ''} ${date === todayIso ? 'today' : ''}`}
                    >
                      <span className="wd">{weekdayLetter(date)}</span>
                      <span className="dn">{dayNum(date)}</span>
                      <span className="rp">{day && day.reporter !== 'self' ? 'C' : ''}</span>
                    </button>
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {terms.map((term) => (
              <tr key={term}>
                <th className="rowh" title={term}>{term}</th>
                {dates.map((date) => {
                  const s = days.get(date)?.symptoms.find((x) => x.term === term)
                  return (
                    <td key={date}>
                      <div
                        className={`cell ${s ? s.severity : ''} ${s?.forReview ? 'rv' : ''} ${date === sel ? 'colsel' : ''}`}
                        title={s ? `${term}: ${s.severity}, started ${s.onset}, ${shortDate(date)}${s.forReview ? ', for review' : ''}` : shortDate(date)}
                      />
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
        {terms.length === 0 && <p className="small" style={{ padding: '10px 2px' }}>No symptoms reported in the last 21 days.</p>}
      </div>
      <p className="small">Tap a day to read it.</p>
      <div className="daybox" role="status" key={sel}>
        <div className="dh">
          <span>{longDate(sel)}</span>
          <span className="small">
            {d ? `${d.status === 'partial' ? 'partly answered' : 'completed'} · answered by ${reporterLabel(d.reporter)} · trend ${d.trend}` : 'No symptom report'}
          </span>
        </div>
        {d ? (
          d.symptoms.map((s) => (
            <div key={s.term} className="sym-line">
              <span className="sev" style={{ background: SEV_VAR[s.severity] }} />
              <b>{s.term}</b>
              <span className="small">{s.severity} · started {s.onset}</span>
              {s.forReview && <span className="tagx review">For review</span>}
              {s.offLabel && <span className="tagx">Not on the drug label</span>}
            </div>
          ))
        ) : (
          <p className="small">Either no check-in that day, or a check-in with no symptoms. Only check-ins that report a symptom reach this history.</p>
        )}
      </div>
    </div>
  )
}

export function Legend() {
  return (
    <div className="legend">
      {/* Key matches the cells: colour plus fill height (a third, two thirds, full) */}
      <span><i className="sev-k" style={{ '--sev': 'var(--mild)', '--fill': '34%' } as React.CSSProperties} />Mild</span>
      <span><i className="sev-k" style={{ '--sev': 'var(--moderate)', '--fill': '67%' } as React.CSSProperties} />Moderate</span>
      <span><i className="sev-k" style={{ '--sev': 'var(--severe)', '--fill': '100%' } as React.CSSProperties} />Severe</span>
      <span><i style={{ background: 'var(--review)', borderRadius: '50%' }} />For review</span>
      <span><b style={{ color: 'var(--coral-ink)' }}>C</b> Caregiver answered</span>
    </div>
  )
}
