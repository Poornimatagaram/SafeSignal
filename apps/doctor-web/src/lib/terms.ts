// Display labels from the contract's term list (schema/terms.json).
import terms from '../../../../schema/terms.json'

export interface Term {
  term_code: string
  label_term: string
  everyday_words: string[]
  drug_scope: string[]
}
export const TERMS = (terms as { terms: Term[] }).terms

const LABELS = new Map<string, string>(TERMS.map((t) => [t.term_code, t.label_term]))

export const termLabel = (code: string) =>
  LABELS.get(code) ?? code.replace(/^SE_/, '').replace(/_/g, ' ').toLowerCase().replace(/^./, (c) => c.toUpperCase())

export const SEVERITY_RANK = { mild: 1, moderate: 2, severe: 3 } as const

export const ONSET_LABELS: Record<string, string> = {
  today: 'today',
  '1_3_days': '1–3 days',
  '4_7_days': '4–7 days',
  over_7_days: 'over 7 days',
  unknown: 'unknown',
}

export const REPORTER_LABELS: Record<string, string> = {
  self: 'Patient',
  parent: 'Parent',
  caregiver: 'Caregiver',
  other: 'Someone else',
}
