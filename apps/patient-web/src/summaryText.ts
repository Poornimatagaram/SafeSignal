// Plain words for the summary, the "what will be shared" box and the egress receipt.
// Symptoms are always "for review", never described as caused by anything.
import { envelopeAsList, type CareEnvelope, type EnvelopeState, type LinkType, type OrgName, type Onset, type ReceiptAlert, type ReceiptStatus, type Severity, type SummaryItem } from './api.ts'

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

/** SE-04: shown under an item marked for review. Timing only: never worded as a cause. */
export const POSSIBLE_LINK_TEXT =
  'Marked for review: this started within a week of something new you began. That does not mean one caused the other.'

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
      return 'Saved on this computer.'
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

/** Said under the queued heading (PV-07). */
export const QUEUED_EXPLANATION = 'It will be sent automatically when the connection is back.'

/** The severe-symptom alert line (AL-02). Never names the symptom or any detail of it. */
export function alertText(alert: ReceiptAlert): string {
  switch (alert.status) {
    case 'sent':
      return 'Your care team was told about the severe symptom.'
    case 'queued':
      return 'Your care team will be told about the severe symptom when the connection is back.'
    case 'failed':
      return 'I could not tell your care team about the severe symptom. Please call them, or tell your helper.'
  }
}

/** The onset choices for a tapped correction, in plain words. */
export const ONSET_CHOICES: Record<Onset, string> = {
  today: 'Today',
  '1_3_days': '1 to 3 days ago',
  '4_7_days': '4 to 7 days ago',
  over_7_days: 'More than a week ago',
  unknown: 'Not sure',
}

/** What is inside the care team's sealed record, in plain words (it holds the name: only the care team can open it). */
const CARE_PARTS: ReadonlyArray<{ text: string; matches: (field: string) => boolean }> = [
  { text: 'Your name', matches: (field) => field === 'display_name' },
  { text: 'Your age', matches: (field) => field === 'age_years' },
  { text: 'The date of this check-in', matches: (field) => field === 'checkin_date' },
  { text: 'Your medicine', matches: (field) => field === 'drug_name' || field === 'drug_version' },
  {
    text: 'Your symptoms: what each one is, how bad, and when it started',
    matches: (field) => field.startsWith('symptoms[]'),
  },
  { text: 'How you are doing compared with before', matches: (field) => field === 'trend' },
  { text: 'Who answered', matches: (field) => field === 'reporter' || field === 'input_mode' },
  { text: 'Whether the check-in was finished', matches: (field) => field === 'status' },
  {
    text: 'A code for your file, and the version of this record format',
    matches: (field) => field === 'patient_ref' || field === 'schema_version',
  },
]

/** The plain-words list of what is inside the care team's sealed record. */
export function careTeamPartsText(fields: readonly string[]): string[] {
  const parts = CARE_PARTS.filter((part) => fields.some(part.matches)).map((part) => part.text)
  const unexplained = fields.some((field) => !CARE_PARTS.some((part) => part.matches(field)))
  if (unexplained) parts.push('Other details (see the exact list)')
  return parts
}

export const CARE_TEAM_SEALED = 'Sent to your care team, sealed: only your doctors can read it.'
export const CARE_TEAM_OFF = 'Your doctor gets nothing from this check-in: sharing with your doctor is off.'

/** Where the care team's sealed record goes, when the runtime gives no name for it. */
export const CARE_TEAM_DESTINATION = 'Your care team (sealed: only your doctors can read it)'

/** Where an emergency hospital's sealed copy goes, when the runtime gives no name for it. */
export const EMERGENCY_DESTINATION = 'Your emergency hospital (sealed: opened only in an emergency, and that is logged)'

/** "Also sealed for an emergency: City Hospital and Lakeside Hospital. ..." or null when none. */
export function emergencyCopyText(orgs: readonly OrgName[]): string | null {
  if (orgs.length === 0) return null
  const names = orgs.map((org) => org.display_name)
  const list = names.length === 1 ? names[0] : `${names.slice(0, -1).join(', ')} and ${names.at(-1)}`
  return `Also sealed for ${list}: they can open it only in an emergency, and that is logged.`
}

/** Plain words for who a sealed copy is for. */
export function sealedCopyDestination(copy: CareEnvelope): string {
  if (copy.label.trim() !== '') return copy.label
  return copy.link_type === 'emergency' ? EMERGENCY_DESTINATION : CARE_TEAM_DESTINATION
}

/** The heading of a sent sealed copy on the receipt. */
export function sealedCopyHeading(linkType: LinkType): string {
  return linkType === 'emergency' ? "Emergency hospital's sealed copy" : "Your doctor's sealed copy"
}

/** One plain line about one sealed copy on the receipt. */
export function sealedCopyText(copy: CareEnvelope): string {
  const emergency = copy.link_type === 'emergency'
  const noun = emergency ? "The emergency hospital's sealed copy" : "Your doctors' sealed copy"
  const refused = `The service did not accept ${emergency ? "the emergency hospital's" : "your doctors'"} sealed copy. Please tell your helper.`
  const offline = `${noun} is saved on this computer. It will be sent when you're back online.`
  if (copy.receipt) {
    switch (copy.receipt.status) {
      case 'sent':
        return emergency
          ? 'Your emergency hospital got a sealed copy: they can open it only in an emergency, and that is logged.'
          : 'Your doctors got a sealed copy: only they can read it.'
      case 'queued':
        return offline
      case 'failed':
        return refused
    }
  }
  switch (copy.waiting) {
    case 'no_key':
      return `${noun} is waiting: ${emergency ? 'that hospital has' : 'their hospital has'} not set up its lock yet. It will be sent later by itself.`
    case 'offline':
      return offline
    case 'refused':
      return refused
    default:
      return `${noun} is waiting on this computer. It will be sent later by itself.`
  }
}

/** One plain line about the care team's sealed record (the single `envelope` field), or null when not sharing. */
export function envelopeText(envelope: EnvelopeState): string | null {
  const [copy] = envelopeAsList(envelope)
  return copy ? sealedCopyText(copy) : null
}
