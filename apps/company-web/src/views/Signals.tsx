// CO-01: side-effect share by drug version and cohort, week over week. Data: v_cohort_weekly via
// /v1/company/cohorts/weekly. The service hides groups under 5 patients; severe counts of 1–4 arrive as null.
import { useMemo, useState } from 'react'
import type { CohortWeeklyRow, TermsResponse } from '../lib/api'
import { pct, rate, seriesColor, termSeries, termsByVolume, versionLabel, weeksOf, type Version } from '../lib/data'
import { ChartOrTable, VersionLines } from '../components/VersionLines'

function Delta({ now, prev }: { now: number | null; prev: number | null }) {
  if (now === null || prev === null) return null
  const d = (now - prev) * 100
  if (Math.abs(d) < 0.5) return <span className="muted small"> ±0</span>
  return (
    <span className={`small ${d > 0 ? 'up' : 'down'}`}>
      {' '}{d > 0 ? '▲' : '▼'} {Math.abs(d).toFixed(1)} pp
    </span>
  )
}

interface Props {
  rows: CohortWeeklyRow[]
  versions: Version[]
  terms: TermsResponse | null
}

export default function Signals({ rows, versions, terms }: Props) {
  const weeks = useMemo(() => weeksOf(rows), [rows])
  const codes = useMemo(() => termsByVolume(rows), [rows])
  const info = useMemo(() => new Map((terms?.terms ?? []).map((t) => [t.term_code, t])), [terms])
  const label = (c: string) => info.get(c)?.label_term ?? c
  const [week, setWeek] = useState(() => weeks[weeks.length - 1] ?? '')
  const [term, setTerm] = useState(() => codes[0] ?? '')

  if (!rows.length) {
    return <div className="card">No cohort rows yet: every group is under 5 patients, or nothing has been reported.</div>
  }

  const prevWeek = weeks[weeks.indexOf(week) - 1]
  const cell = (w: string | undefined, c: string, t: string) =>
    rows.find((r) => r.iso_week === w && r.cohort_id === c && r.term_code === t)
  const reporting = versions.reduce(
    (n, v) => n + (rows.find((r) => r.iso_week === week && r.cohort_id === v.cohort_id)?.reporting_patients ?? 0), 0)

  // Largest week-over-week rise in any cohort points the reader at a possible signal.
  let top: { t: string; v: Version; d: number } | null = null
  for (const t of codes)
    for (const v of versions) {
      const a = cell(week, v.cohort_id, t)
      const b = cell(prevWeek, v.cohort_id, t)
      if (a && b && (!top || rate(a) - rate(b) > top.d)) top = { t, v, d: rate(a) - rate(b) }
    }
  const unlisted = codes.filter((c) => info.has(c) && !info.get(c)!.known_for_program)
  const series = termSeries(rows, term, versions)

  return (
    <div className="stack">
      <div className="row center">
        <label className="small muted" htmlFor="week">Week</label>
        <select id="week" value={week} onChange={(e) => setWeek(e.target.value)}>
          {weeks.map((w) => <option key={w}>{w}</option>)}
        </select>
        <span className="small muted">compared with {prevWeek ?? 'no earlier week'}</span>
      </div>

      <div className="kpis">
        <div className="kpi"><div className="label">Patients reporting, {week}</div><div className="value">{reporting.toLocaleString()}</div></div>
        <div className="kpi">
          <div className="label">Largest weekly rise</div>
          <div className="value text">
            {top && top.d > 0 ? <>{label(top.t)} · {top.v.drug_version} <span className="up small">▲ {(top.d * 100).toFixed(1)} pp</span></> : '—'}
          </div>
        </div>
        <div className="kpi">
          <div className="label">Reported but not on the label</div>
          <div className="value text">{unlisted.length ? unlisted.map(label).join(', ') : 'None'}</div>
        </div>
      </div>

      <div className="card">
        <ChartOrTable
          title={`${label(term)}: share of reporting patients, by cohort`}
          note="Distinct patients who reported it that week ÷ patients in the cohort who reported that week. Pick a side effect in the table below."
          chart={<VersionLines data={series} versions={versions} label={versionLabel} />}
          table={
            <table>
              <thead><tr><th>Week</th>{versions.map((v) => <th key={v.cohort_id}>{versionLabel(v)}</th>)}</tr></thead>
              <tbody>
                {series.map((p) => (
                  <tr key={p.iso_week}><td>{p.iso_week}</td>
                    {versions.map((v) => <td key={v.cohort_id}>{pct(p[v.cohort_id] as number | null)}</td>)}</tr>
                ))}
              </tbody>
            </table>
          }
        />
      </div>

      <div className="card">
        <h2>All side effects, {week}</h2>
        <p className="note">Share of reporting patients, with the change from {prevWeek ?? 'the previous week'} in percentage points. “Not on label” = not in this drug's FDA label. Severe counts of 1–4 show as “&lt;5”.</p>
        <div className="scroll-x">
          <table>
            <thead>
              <tr>
                <th>Side effect</th>
                {versions.map((v, i) => (
                  <th key={v.cohort_id} title={v.label}><span className="key" style={{ background: seriesColor(i) }} />{v.drug_version}</th>
                ))}
                <th>Severe (all cohorts)</th>
              </tr>
            </thead>
            <tbody>
              {codes.map((t) => {
                const here = versions.map((v) => cell(week, v.cohort_id, t)).filter(Boolean) as CohortWeeklyRow[]
                const hidden = here.some((r) => r.severe_patients === null)
                const known = here.reduce((n, r) => n + (r.severe_patients ?? 0), 0)
                const offLabel = info.has(t) && !info.get(t)!.known_for_program
                return (
                  <tr key={t} className="selectable" aria-selected={t === term} onClick={() => setTerm(t)}
                    tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && setTerm(t)}>
                    <td>{label(t)}{offLabel && <span className="tag">Not on label</span>}</td>
                    {versions.map((v) => {
                      const a = cell(week, v.cohort_id, t)
                      const b = cell(prevWeek, v.cohort_id, t)
                      return (
                        <td key={v.cohort_id}>
                          {a ? pct(rate(a)) : <span className="muted" title="Fewer than 5 patients">&lt;5</span>}
                          <Delta now={a ? rate(a) : null} prev={b ? rate(b) : null} />
                        </td>
                      )
                    })}
                    <td>{hidden ? (known ? `${known} + <5` : '<5') : known}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
