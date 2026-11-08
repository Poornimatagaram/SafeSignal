// Shapes from schema/doctor_payload.json, schema/doctor_view.sql and schema/openapi.json (contract 2.0, source of truth).
import type { components } from '@sentinel/contract/api'

export type Severity = 'mild' | 'moderate' | 'severe'
export type Onset = 'today' | '1_3_days' | '4_7_days' | 'over_7_days' | 'unknown'
export type Trend = 'better' | 'same' | 'worse' | 'unknown'
export type CheckinStatus = 'completed' | 'partial' | 'missed'
export type Reporter = 'self' | 'parent' | 'caregiver' | 'other'
export type AlertType = 'missed' | 'severe' | 'emergency_access'
export type EmergencyReason = 'unresponsive_patient' | 'emergency_admission' | 'escalation_level_3'

export interface SymptomEntry {
  term_code: string
  severity: Severity
  onset: Onset
  known_side_effect: boolean
  possible_link_flag: boolean
}

// Plaintext inside a care envelope (schema/doctor_payload.json, 2.0)
export interface DoctorPayload {
  schema_version: string
  patient_ref: string
  display_name: string
  drug_name: string
  drug_version: string
  checkin_date: string
  status: CheckinStatus
  trend: Trend
  symptoms: SymptomEntry[]
  reporter: Reporter
  age_years: number
}

// Service responses (generated from schema/openapi.json)
type S = components['schemas']
export type Envelope = S['Envelope']
export type Alert = S['Alert']
export type LinkedPatient = S['LinkedPatient']
export type OrgMembership = S['OrgMembership']
export type KeyGrant = S['KeyGrant']
export type MemberState = S['MemberState']
export type EmergencyAccessResult = S['EmergencyAccessResult']

// IndexedDB stores (schema/doctor_view.sql)
export interface DrPatient {
  patient_ref: string
  org_id: string
  display_name: string
  age_years: number
  drug_name: string
  drug_version: string
  last_checkin: string | null
  shared: 0 | 1
}

export interface DrTimelineEntry {
  entry_id: string // '<envelope_id>:<term_code>'
  patient_ref: string
  envelope_id: string
  checkin_date: string
  status: CheckinStatus
  reporter: Reporter
  term_code: string
  severity: Severity
  onset: Onset
  known_side_effect: 0 | 1
  possible_link_flag: 0 | 1
  trend: Trend
}

export interface DrAlert {
  alert_id: string
  org_id: string
  patient_ref: string
  alert_type: AlertType
  escalation_level: number | null
  created_at: string
  received_at: string
  seen_at: string | null
}

export interface DrKey {
  doctor_id: string
  public_key: string // base64 standard
  private_key: string // never exported, logged or transmitted
  created_at: string
}

export interface DrOrgKey {
  org_id: string
  public_key: string
  private_key: string // never exported, logged or transmitted
  obtained_at: string
}
