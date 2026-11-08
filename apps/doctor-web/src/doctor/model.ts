// Display model for the doctor screens, derived from the dr_* stores. No service calls here.
import type { DrAlert, DrPatient, DrTimelineEntry, Reporter, Severity, Trend } from '../lib/types'
import { ONSET_LABELS, REPORTER_LABELS, termLabel } from '../lib/terms'

export const SEV_RANK: Record<Severity, number> = { mild: 1, moderate: 2, severe: 3 }
// Pastel severity scale; also differs in lightness, not hue alone.
export const SEV_BG: Record<Severity, string> = { mild: 'bg-butter', moderate: 'bg-rose', severe: 'bg-[#a8365e]' }
export const TREND_BG: Record<Trend, string> = { worse: 'bg-rose-tint', better: 'bg-mint-tint', same: 'bg-mauve', unknown: 'bg-cream' }

// Local calendar date as YYYY-MM-DD (checkin_date is a calendar date, not an instant).
export const isoDay = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
export const daysAgo = (n: number) => {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return isoDay(d)
}
const parse = (iso: string) => new Date(iso + 'T12:00:00')
export const ago = (iso: string | null) => {
  if (!iso) return 'not yet'
  const n = Math.round((parse(isoDay(new Date())).getTime() - parse(iso).getTime()) / 864e5)
  return n <= 0 ? 'today' : n === 1 ? 'yesterday' : `${n} days ago`
}
export const longDate = (iso: string) => {
  const a = ago(iso)
  return a === 'today' ? 'Today' : a === 'yesterday' ? 'Yesterday' : parse(iso).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
}
export const dayNum = (iso: string) => parse(iso).getDate()

export interface SymptomView {
  term: string
  severity: Severity
  onset: string
  forReview: boolean
  offLabel: boolean
}
export interface DayView {
  date: string
  status: DrTimelineEntry['status']
  reporter: Reporter
  trend: Trend
  symptoms: SymptomView[]
}

// One row per check-in date that reported symptoms (doctor_view.sql has no row for symptom-free check-ins).
export function byDay(entries: DrTimelineEntry[]): Map<string, DayView> {
  const m = new Map<string, DayView>()
  for (const e of [...entries].sort((a, b) => a.checkin_date.localeCompare(b.checkin_date))) {
    const d = m.get(e.checkin_date) ?? { date: e.checkin_date, status: e.status, reporter: e.reporter, trend: e.trend, symptoms: [] }
    d.status = e.status
    d.reporter = e.reporter
    d.trend = e.trend
    if (!d.symptoms.some((s) => s.term === termLabel(e.term_code)))
      d.symptoms.push({ term: termLabel(e.term_code), severity: e.severity, onset: ONSET_LABELS[e.onset] ?? e.onset, forReview: !!e.possible_link_flag, offLabel: !e.known_side_effect })
    m.set(e.checkin_date, d)
  }
  return m
}

export const latestTrend = (days: Map<string, DayView>): Trend => [...days.values()].pop()?.trend ?? 'unknown'

export const reporterLabel = (r: Reporter) => (r === 'self' ? 'the patient' : REPORTER_LABELS[r].toLowerCase())

// Who is told, by the escalation rules (D-068). The doctor app does not receive delivery records.
export function whoIsTold(a: Pick<DrAlert, 'alert_type' | 'escalation_level'>): string {
  if (a.alert_type === 'severe') return 'The caregiver and the care team.'
  if (a.alert_type === 'emergency_access') return 'The caregiver and the care team.'
  return (a.escalation_level ?? 1) >= 3
    ? 'The patient (reminder), the caregiver, the care team and the emergency contacts the patient chose.'
    : 'The patient (reminder), the caregiver and the care team.'
}

// Theme colours for severity (theme.css tokens): the same scale in light and dark.
export const SEV_VAR: Record<Severity, string> = { mild: 'var(--mild)', moderate: 'var(--moderate)', severe: 'var(--severe)' }
export const worstOf = (s: { severity: Severity }[]): Severity | null =>
  s.reduce<Severity | null>((m, x) => (!m || SEV_RANK[x.severity] > SEV_RANK[m] ? x.severity : m), null)

// The 21 days shown on every history view. Ends today, or at the newest check-in if its date is later
// (device dates are UTC, the browser is local; DW-28).
export const WINDOW = 21
export function windowDates(days: Map<string, DayView>): string[] {
  const newest = [...days.keys()].pop()
  const shift = newest && newest > daysAgo(0) ? Math.round((parse(newest).getTime() - parse(daysAgo(0)).getTime()) / 864e5) : 0
  return Array.from({ length: WINDOW }, (_, i) => daysAgo(WINDOW - 1 - i - shift))
}
export const weekdayLetter = (iso: string) => parse(iso).toLocaleDateString('en-US', { weekday: 'narrow' })
export const shortDate = (iso: string) => parse(iso).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })

export const patientName =(p: DrPatient | undefined, ref: string) => p?.display_name ?? `Patient ${ref.slice(3, 7)}`

export const nameFor = (rows: { patient_ref: string; patient: DrPatient }[]) => (ref: string) => patientName(rows.find((r) => r.patient_ref === ref)?.patient, ref)
