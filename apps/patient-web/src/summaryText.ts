// Plain words for the summary, the "what will be shared" box and the egress receipt.
// Symptoms are always "for review", never described as caused by anything.
import type { ReceiptStatus, Severity, SummaryItem } from './api.ts'

const ONSET_WORDS: Record<string, string> = {
  today: 'today',
  '1_3_days': '1 to 3 days ago',
  '4_7_days': '4 to 7 days ago',
  over_7_days: 'more than a week ago',
}

/** "today", "1 to 3 days ago", … or "start not known". */
export function onsetText(onset: string | null | undefined): string {
  return (onset && ONSET_WORDS[onset]) || 'start not known'
}

/** "Started 1 to 3 days ago" or "Start not known". */
export function onsetSentence(onset: string | null | undefined): string {
  const words = onsetText(onset)
  return words === 'start not known' ? 'Start not known' : `Started ${words}`
}

export const SEVERITY_WORDS: Record<Severity, string> = { mild: 'Mild', moderate: 'Moderate', severe: 'Severe' }

/** "Mild", "Moderate", "Severe", or "Not known". */
export function severityText(severity: string | null | undefined): string {
  return (severity && SEVERITY_WORDS[severity as Severity]) || 'Not known'
}

/** "How bad is the rash?" */
export function severityQuestion(label: string): string {
  const name = label ? label.charAt(0).toLowerCase() + label.slice(1) : 'problem'
  return `How bad is the ${name}?`
}

/** The label of a coded symptom in the summary, or a plain fallback. */
export function itemLabel(items: readonly SummaryItem[], termCode: string): string {
  return items.find((item) => item.term_code === termCode)?.label ?? 'problem'
}

export const NOTHING_TO_REPORT = 'You did not report any new problems.'

/** What each part of the outbound record means, in plain words. Every part is a code, a number or a random ID. */
const SHARED_PARTS: ReadonlyArray<{ text: string; matches: (field: string) => boolean }> = [
  {
    text: 'Each problem as a code: what it is, how bad, when it started, and whether it is marked for review',
    matches: (field) => field.startsWith('symptoms[]'),
  },
  { text: 'How many questions had no answer', matches: (field) => field === 'unanswered_questions' },
  { text: 'Whether the check-in was finished', matches: (field) => field === 'status' },
  { text: 'The week of this check-in, not the day', matches: (field) => field === 'iso_week' },
  { text: 'A random code instead of your name', matches: (field) => field === 'patient_ref' || field === 'record_id' },
  {
    text: 'Your study group and medicine version',
    matches: (field) => field === 'program_id' || field === 'cohort_id' || field === 'drug_version',
  },
  { text: 'Who answered, and whether by voice or typing', matches: (field) => field === 'reporter' || field === 'input_mode' },
  { text: 'Who you agreed may see your check-ins', matches: (field) => field.startsWith('consent.') },
  { text: 'The version of this record format', matches: (field) => field === 'schema_version' },
]

/** The short plain-words list of what will be shared, built from the field names the runtime will send. */
export function sharedPartsText(fields: readonly string[]): string[] {
  const parts = SHARED_PARTS.filter((part) => fields.some(part.matches)).map((part) => part.text)
  const unexplained = fields.some((field) => !SHARED_PARTS.some((part) => part.matches(field)))
  if (unexplained) parts.push('Other coded answers (see the exact list)')
  return parts
}

/** Receipt status in plain words. */
export function receiptStatusText(status: ReceiptStatus): string {
  switch (status) {
    case 'sent':
      return 'Shared'
    case 'queued':
      return 'Saved on this device; it will be sent when you are back online'
    case 'failed':
      return 'Not accepted'
  }
}

/** A receipt time (UTC ISO) in the patient's local time, for example "Sunday, November 8, 2026 at 9:03 AM". */
export function formatLocalTime(iso: string, locale?: string, timeZone?: string): string {
  const time = new Date(iso)
  if (Number.isNaN(time.getTime())) return iso
  return time.toLocaleString(locale, {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZone,
  })
}
