// Shapes the two company views into what the screens draw. Pure functions, no fetching.
import type { CohortInfo, CohortWeeklyRow, CompletionRow } from './api'

// Cohorts keep the program's order, so each keeps its color whatever is selected.
export type Version = Pick<CohortInfo, 'cohort_id' | 'drug_version' | 'label'>

export const versionLabel = (v: Version) => `${v.drug_version} · ${v.label}`

export const weeksOf = (rows: { iso_week: string }[]) => [...new Set(rows.map((r) => r.iso_week))].sort()

// Share of the cohort's reporting patients who reported the term that week.
export const rate = (r: CohortWeeklyRow) => (r.reporting_patients > 0 ? r.patients / r.reporting_patients : 0)

export function termsByVolume(rows: CohortWeeklyRow[]): string[] {
  const total = new Map<string, number>()
  for (const r of rows) total.set(r.term_code, (total.get(r.term_code) ?? 0) + r.patients)
  return [...total.entries()].sort((a, b) => b[1] - a[1]).map(([t]) => t)
}

export type WeekPoint = { iso_week: string } & Record<string, number | null | string>

export function termSeries(rows: CohortWeeklyRow[], term: string, versions: Version[]): WeekPoint[] {
  return weeksOf(rows).map((w) => {
    const p: WeekPoint = { iso_week: w }
    for (const v of versions) {
      const r = rows.find((x) => x.iso_week === w && x.cohort_id === v.cohort_id && x.term_code === term)
      p[v.cohort_id] = r ? rate(r) : null
    }
    return p
  })
}

export function completionSeries(rows: CompletionRow[], versions: Version[]): WeekPoint[] {
  return weeksOf(rows).map((w) => {
    const p: WeekPoint = { iso_week: w }
    for (const v of versions) {
      const r = rows.find((x) => x.iso_week === w && x.cohort_id === v.cohort_id)
      p[v.cohort_id] = r ? r.completion_rate : null
    }
    return p
  })
}

export const pct = (x: number | null | undefined, digits = 1) =>
  x === null || x === undefined ? '–' : `${(x * 100).toFixed(digits)}%`

// Categorical slots 1–4 (validated light and dark); a program has at most 4 cohorts, so slots never cycle.
export const seriesColor = (i: number) => `var(--series-${(i % 4) + 1})`
