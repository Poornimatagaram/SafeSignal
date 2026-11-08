// Plain words for the summary, the "what will be shared" box and the egress receipt. The words live in
// src/strings.ts; this module picks and joins them. Symptoms are always "for review", never described as caused.
import { envelopeAsList, type CareEnvelope, type EnvelopeState, type LinkType, type OrgName, type Onset, type ReceiptAlert, type ReceiptStatus, type Severity, type SummaryItem } from './api.ts'
import { S } from './strings.ts'

const P = S.plain

const ONSET_WORDS: Record<string, string> = P.onset

/** "today", "1 to 3 days ago", … or "start not known". */
export function onsetText(onset: string | null | undefined): string {
  return (onset && ONSET_WORDS[onset]) || P.onsetUnknown
}

/** "Started 1 to 3 days ago" or "Start not known". */
export function onsetSentence(onset: string | null | undefined): string {
  const words = onsetText(onset)
  return words === P.onsetUnknown ? P.onsetUnknownSentence : P.onsetSentence(words)
}

export const SEVERITY_WORDS: Record<Severity, string> = P.severity

/** "Mild", "Moderate", "Severe", or "Not known". */
export function severityText(severity: string | null | undefined): string {
  return (severity && SEVERITY_WORDS[severity as Severity]) || P.severityUnknown
}

/** "How bad is the rash?" */
export function severityQuestion(label: string): string {
  const name = label ? label.charAt(0).toLowerCase() + label.slice(1) : P.problem
  return P.severityQuestion(name)
}

/** The label of a coded symptom in the summary, or a plain fallback. */
export function itemLabel(items: readonly SummaryItem[], termCode: string): string {
  return items.find((item) => item.term_code === termCode)?.label ?? P.problem
}

/** SE-04: shown under an item marked for review. Timing only: never worded as a cause. */
export const POSSIBLE_LINK_TEXT = P.possibleLink

export const NOTHING_TO_REPORT = P.nothingToReport

/** What each part of the outbound record means, in plain words. Every part is a code, a number or a random ID. */
const SHARED_PARTS: ReadonlyArray<{ text: string; matches: (field: string) => boolean }> = [
  { text: P.sharedParts.symptoms, matches: (field) => field.startsWith('symptoms[]') },
  { text: P.sharedParts.unanswered, matches: (field) => field === 'unanswered_questions' },
  { text: P.sharedParts.status, matches: (field) => field === 'status' },
  { text: P.sharedParts.week, matches: (field) => field === 'iso_week' },
  { text: P.sharedParts.ref, matches: (field) => field === 'patient_ref' || field === 'record_id' },
  {
    text: P.sharedParts.program,
    matches: (field) => field === 'program_id' || field === 'cohort_id' || field === 'drug_version',
  },
  { text: P.sharedParts.reporter, matches: (field) => field === 'reporter' || field === 'input_mode' },
  { text: P.sharedParts.consent, matches: (field) => field.startsWith('consent.') },
  { text: P.sharedParts.schema, matches: (field) => field === 'schema_version' },
]

/** The short plain-words list of what will be shared, built from the field names the runtime will send. */
export function sharedPartsText(fields: readonly string[]): string[] {
  const parts = SHARED_PARTS.filter((part) => fields.some(part.matches)).map((part) => part.text)
  const unexplained = fields.some((field) => !SHARED_PARTS.some((part) => part.matches(field)))
  if (unexplained) parts.push(P.sharedParts.other)
  return parts
}

/** Receipt status in plain words. */
export function receiptStatusText(status: ReceiptStatus): string {
  return P.receiptStatus[status]
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
export const QUEUED_EXPLANATION = P.queuedExplanation

/** The severe-symptom alert line (AL-02). Never names the symptom or any detail of it. */
export function alertText(alert: ReceiptAlert): string {
  return P.alert[alert.status]
}

/** The onset choices for a tapped correction, in plain words. */
export const ONSET_CHOICES: Record<Onset, string> = P.onsetChoices

/** What is inside the care team's sealed record, in plain words (it holds the name: only the care team can open it). */
const CARE_PARTS: ReadonlyArray<{ text: string; matches: (field: string) => boolean }> = [
  { text: P.careParts.name, matches: (field) => field === 'display_name' },
  { text: P.careParts.age, matches: (field) => field === 'age_years' },
  { text: P.careParts.date, matches: (field) => field === 'checkin_date' },
  { text: P.careParts.medicine, matches: (field) => field === 'drug_name' || field === 'drug_version' },
  { text: P.careParts.symptoms, matches: (field) => field.startsWith('symptoms[]') },
  { text: P.careParts.trend, matches: (field) => field === 'trend' },
  { text: P.careParts.reporter, matches: (field) => field === 'reporter' || field === 'input_mode' },
  { text: P.careParts.status, matches: (field) => field === 'status' },
  { text: P.careParts.ref, matches: (field) => field === 'patient_ref' || field === 'schema_version' },
]

/** The plain-words list of what is inside the care team's sealed record. */
export function careTeamPartsText(fields: readonly string[]): string[] {
  const parts = CARE_PARTS.filter((part) => fields.some(part.matches)).map((part) => part.text)
  const unexplained = fields.some((field) => !CARE_PARTS.some((part) => part.matches(field)))
  if (unexplained) parts.push(P.careParts.other)
  return parts
}

export const CARE_TEAM_SEALED = P.careTeamSealed
export const CARE_TEAM_OFF = P.careTeamOff

/** Where the care team's sealed record goes, when the runtime gives no name for it. */
export const CARE_TEAM_DESTINATION = P.careTeamDestination

/** Where an emergency hospital's sealed copy goes, when the runtime gives no name for it. */
export const EMERGENCY_DESTINATION = P.emergencyDestination

/** "Also sealed for an emergency: City Hospital and Lakeside Hospital. ..." or null when none. */
export function emergencyCopyText(orgs: readonly OrgName[]): string | null {
  if (orgs.length === 0) return null
  const names = orgs.map((org) => org.display_name)
  const list = names.length === 1 ? names[0] : `${names.slice(0, -1).join(', ')} ${P.and} ${names.at(-1)}`
  return P.emergencyCopy(list)
}

/** Plain words for who a sealed copy is for. */
export function sealedCopyDestination(copy: CareEnvelope): string {
  if (copy.label.trim() !== '') return copy.label
  return copy.link_type === 'emergency' ? EMERGENCY_DESTINATION : CARE_TEAM_DESTINATION
}

/** The heading of a sent sealed copy on the receipt. */
export function sealedCopyHeading(linkType: LinkType): string {
  return linkType === 'emergency' ? P.sealedHeading.emergency : P.sealedHeading.care
}

/** One plain line about one sealed copy on the receipt. */
export function sealedCopyText(copy: CareEnvelope): string {
  const emergency = copy.link_type === 'emergency'
  const W = P.sealed
  const noun = emergency ? W.nounEmergency : W.nounCare
  const refused = emergency ? W.refusedEmergency : W.refusedCare
  const offline = W.offline(noun)
  if (copy.receipt) {
    switch (copy.receipt.status) {
      case 'sent':
        return emergency ? W.sentEmergency : W.sentCare
      case 'queued':
        return offline
      case 'failed':
        return refused
    }
  }
  switch (copy.waiting) {
    case 'no_key':
      return W.noKey(noun, emergency)
    case 'offline':
      return offline
    case 'refused':
      return refused
    default:
      return W.waiting(noun)
  }
}

/** One plain line about the care team's sealed record (the single `envelope` field), or null when not sharing. */
export function envelopeText(envelope: EnvelopeState): string | null {
  const [copy] = envelopeAsList(envelope)
  return copy ? sealedCopyText(copy) : null
}
