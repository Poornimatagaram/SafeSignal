// DR-04: pre-visit summary built by templates from structured records only (no model, no cloud).
// Every sentence is traceable to stored fields; links are worded "for review", never as a cause.
import type { DrAlert, DrPatient, DrTimelineEntry } from '../lib/types'
import type { CheckinDay } from '../lib/sync'
import { ONSET_LABELS, REPORTER_LABELS, termLabel } from '../lib/terms'
import { ago } from './model'

const list = (items: string[]) =>
  items.length <= 1 ? items.join('') : items.slice(0, -1).join(', ') + ' and ' + items[items.length - 1]

export interface SummarySection {
  title: string
  items: string[]
}

export function summarySections(p: DrPatient, days: CheckinDay[], entries: DrTimelineEntry[], alerts: DrAlert[]): SummarySection[] {
  // `days` holds only check-ins that reported symptoms (doctor_view.sql has no row for symptom-free or missed days).
  const since = new Date(Date.now() - 21 * 864e5).toISOString().slice(0, 10)
  const recent = days.filter((d) => d.date >= since)
  const checkins: string[] = [
    `${recent.length} check-in${recent.length === 1 ? '' : 's'} with symptoms in the last 21 days. Last check-in ${ago(p.last_checkin)}.`,
  ]
  const proxies = [...new Set(recent.filter((d) => d.reporter !== 'self').map((d) => REPORTER_LABELS[d.reporter].toLowerCase()))]
  if (proxies.length) checkins.push(`${recent.filter((d) => d.reporter !== 'self').length} answered by someone else (${list(proxies)}), not the patient.`)
  const last3 = days.slice(-3).map((d) => d.trend)
  if (last3.length > 1) checkins.push(`Patient-reported trend over the last ${last3.length} symptom reports: ${last3.join(' → ')}.`)

  const latest: string[] = []
  const lastDay = days[days.length - 1]
  if (p.last_checkin && (!lastDay || p.last_checkin > lastDay.date)) latest.push(`No symptoms reported at the last check-in (${ago(p.last_checkin)}).`)
  else if (lastDay)
    latest.push(
      ...entries
        .filter((e) => e.checkin_date === lastDay.date)
        .map((e) => `${termLabel(e.term_code)}: ${e.severity}, started ${ONSET_LABELS[e.onset]} (${ago(lastDay.date)}).`),
    )

  const review: string[] = []
  const linked = [...new Set(entries.filter((e) => e.possible_link_flag).map((e) => termLabel(e.term_code).toLowerCase()))]
  if (linked.length) review.push(`${list(linked).replace(/^./, (c) => c.toUpperCase())} flagged as a possible link. A flag, not a cause.`)
  const unlisted = [...new Set(entries.filter((e) => !e.known_side_effect).map((e) => termLabel(e.term_code).toLowerCase()))]
  if (unlisted.length) review.push(`Not on the drug label: ${list(unlisted)}.`)

  const out: SummarySection[] = [{ title: 'Check-ins', items: checkins }]
  if (latest.length) out.push({ title: 'Latest report', items: latest })
  if (review.length) out.push({ title: 'For review', items: review })

  const severe = alerts.filter((a) => a.alert_type === 'severe').length
  const missed = alerts.filter((a) => a.alert_type === 'missed')
  const topLevel = Math.max(0, ...missed.map((a) => a.escalation_level ?? 0))
  const emergency = alerts.filter((a) => a.alert_type === 'emergency_access').length
  if (severe || missed.length || emergency)
    out.push({
      title: 'Alerts on record',
      items: [
        `${severe} severe-symptom, ${missed.length} missed check-in${topLevel ? ` (highest escalation level ${topLevel})` : ''}${emergency ? `, ${emergency} emergency access` : ''}.`,
      ],
    })
  return out
}

