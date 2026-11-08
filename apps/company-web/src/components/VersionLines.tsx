// One line per drug version over ISO weeks. Single y-axis; legend + direct end labels so identity is never
// color-only (two light-mode series sit under 3:1 contrast, so labels and the table view are required).
import { useState, type ReactNode } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Version, WeekPoint } from '../lib/data'
import { seriesColor } from '../lib/data'
import { pct } from '../lib/data'


interface Props {
  data: WeekPoint[]
  versions: Version[]
  label: (v: Version) => string
  yDomain?: [number | 'auto', number | 'auto']
  height?: number
}

interface TipProps {
  active?: boolean
  label?: string
  payload?: { dataKey: string; value: number | null }[]
  versions: Version[]
  labelOf: (v: Version) => string
}

function Tip({ active, label, payload, versions, labelOf }: TipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="tooltip" role="status">
      <div className="t">{label}</div>
      {versions.map((v, i) => {
        const p = payload.find((x) => x.dataKey === v.cohort_id)
        return (
          <div className="r" key={v.cohort_id}>
            <span>
              <span className="key" style={{ background: seriesColor(i) }} />
              {labelOf(v)}
            </span>
            <strong>{pct(p?.value ?? null)}</strong>
          </div>
        )
      })}
    </div>
  )
}

export function Legend({ versions, label }: { versions: Version[]; label: (v: Version) => string }) {
  return (
    <div className="legend">
      {versions.map((v, i) => (
        <span key={v.cohort_id}>
          <span className="key" style={{ background: seriesColor(i) }} />
          {label(v)}
        </span>
      ))}
    </div>
  )
}

// End labels: each cohort's label moves down past any other cohort's label placed too close to it. Keyed by
// cohort, because recharts may render a label more than once per pass.
function placeLabel(placed: Map<string, number>, id: string, y: number) {
  const seen = placed.get(id)
  if (seen !== undefined) return seen
  let out = y
  const others = [...placed.values()].sort((a, b) => a - b)
  for (const p of others) if (Math.abs(out - p) < 14) out = p + 14
  placed.set(id, out)
  return out
}

export function VersionLines({ data, versions, label, yDomain = [0, 'auto'], height = 260 }: Props) {
  const last = data.length - 1
  const placed = new Map<string, number>()
  return (
    <>
      <Legend versions={versions} label={label} />
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 8, right: 64, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis dataKey="iso_week" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} tickLine={false}
            axisLine={{ stroke: 'var(--border)' }} padding={{ left: 12, right: 12 }} />
          <YAxis domain={yDomain} tickFormatter={(x: number) => pct(x, 0)} width={44}
            tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} tickLine={false} axisLine={false} />
          <Tooltip cursor={{ stroke: 'var(--text-muted)', strokeWidth: 1 }}
            content={<Tip versions={versions} labelOf={label} />} />
          {versions.map((v, i) => (
            <Line key={v.cohort_id} dataKey={v.cohort_id} name={label(v)} stroke={seriesColor(i)} strokeWidth={2}
              dot={{ r: 4, fill: seriesColor(i), stroke: 'var(--surface-1)', strokeWidth: 2 }}
              activeDot={{ r: 5, stroke: 'var(--surface-1)', strokeWidth: 2 }} connectNulls isAnimationActive={false}
              label={(p: { index?: number; x?: number | string; y?: number | string }) =>
                p.index === last ? (
                  <text key={`l-${v.cohort_id}`} x={Number(p.x ?? 0) + 10} y={placeLabel(placed, v.cohort_id, Number(p.y ?? 0) + 4)} fontSize={12}
                    fill="var(--text-secondary)">{v.drug_version}</text>
                ) : <g key={`n-${v.cohort_id}-${p.index}`} />
              } />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </>
  )
}

// Every chart ships with a table view (relief rule: two light-mode series sit under 3:1 contrast).
export function ChartOrTable({ title, note, chart, table }: { title: string; note: string; chart: ReactNode; table: ReactNode }) {
  const [view, setView] = useState<'chart' | 'table'>('chart')
  return (
    <>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: '1 1 320px' }}>
          <h2>{title}</h2>
          <p className="note">{note}</p>
        </div>
        <div className="seg" role="group" aria-label="Chart or table">
          <button aria-pressed={view === 'chart'} onClick={() => setView('chart')}>Chart</button>
          <button aria-pressed={view === 'table'} onClick={() => setView('table')}>Table</button>
        </div>
      </div>
      {view === 'chart' ? chart : <div className="scroll-x">{table}</div>}
    </>
  )
}
