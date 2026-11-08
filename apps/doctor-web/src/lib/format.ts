// Display helpers shared by the doctor and caregiver views.
import type { DrAlert } from './types'

export const fmtTime = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })

export function alertText(a: Pick<DrAlert, 'alert_type' | 'escalation_level'>): string {
  if (a.alert_type === 'severe') return 'Severe symptom reported'
  if (a.alert_type === 'emergency_access') return 'History opened through emergency access'
  const level = a.escalation_level ?? 1
  if (level >= 3) return 'Check-in missed (3rd in a row): emergency contacts notified'
  if (level === 2) return 'Check-in missed (2nd in a row): urgent'
  return 'Check-in missed'
}
