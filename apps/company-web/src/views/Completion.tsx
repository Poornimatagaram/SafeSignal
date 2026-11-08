// CO-02: check-in completion by cohort. Data: v_completion_weekly via /v1/company/completion.
// Missed days come from the service scheduler (D-003), so missed_rate is measured, not inferred.
import type { CompletionRow } from '../lib/api'
import { completionSeries, pct, seriesColor, versionLabel, weeksOf, type Version } from '../lib/data'
import { ChartOrTable, VersionLines } from '../components/VersionLines'

export default function Completion({ rows, versions }: { rows: CompletionRow[]; versions: Version[] }) {
  if (!rows.length) return <div className="card">No completion rows yet.</div>
  const weeks = weeksOf(rows)
  const latest = weeks[weeks.length - 1]
  const now = rows.filter((r) => r.iso_week === latest)
  const mean = (f: (r: CompletionRow) => number) => now.reduce((n, r) => n + f(r), 0) / now.length
  const answered = now.reduce((n, r) => n + r.voice_records + r.text_records + r.mixed_records, 0)
  const voice = answered ? now.reduce((n, r) => n + r.voice_records, 0) / answered : null

  return (
    <div className="stack">
      <div className="kpis">
        <div className="kpi"><div className="label">Completion, {latest}</div><div className="value">{pct(mean((r) => r.completion_rate))}</div></div>
        <div className="kpi"><div className="label">Missed check-ins, {latest}</div><div className="value">{pct(mean((r) => r.missed_rate))}</div></div>
        <div className="kpi"><div className="label">Answered by voice, {latest}</div><div className="value">{pct(voice)}</div></div>
      </div>
      <div className="card">
        <ChartOrTable
          title="Check-in completion rate by cohort"
          note="Completed check-ins ÷ check-ins due. The current week is still in progress."
          chart={<VersionLines data={completionSeries(rows, versions)} versions={versions} label={versionLabel} yDomain={[0, 1]} />}
          table={
            <table>
              <thead>
                <tr><th>Week</th><th>Cohort</th><th>Patients</th><th>Records</th><th>Completed</th><th>Missed</th>
                  <th>Voice</th><th>Text</th><th>Mixed</th></tr>
              </thead>
              <tbody>
                {weeks.flatMap((w) => versions.map((v, i) => {
                  const r = rows.find((x) => x.iso_week === w && x.cohort_id === v.cohort_id)
                  return r ? (
                    <tr key={`${w}-${v.cohort_id}`}>
                      <td>{w}</td>
                      <td><span className="key" style={{ background: seriesColor(i) }} />{versionLabel(v)}</td>
                      <td>{r.patients}</td><td>{r.records.toLocaleString()}</td>
                      <td>{pct(r.completion_rate)}</td><td>{pct(r.missed_rate)}</td>
                      <td>{r.voice_records.toLocaleString()}</td><td>{r.text_records.toLocaleString()}</td>
                      <td>{r.mixed_records.toLocaleString()}</td>
                    </tr>
                  ) : null
                }))}
              </tbody>
            </table>
          }
        />
      </div>
    </div>
  )
}
