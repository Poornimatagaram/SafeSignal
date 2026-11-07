"""Response models for the Sentinel API (Scoping Doc 26.7). These drive /docs and the generated TypeScript types.

Request bodies are validated against the published JSON Schemas in schema/, not against these models.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

Severity = Literal["mild", "moderate", "severe"]
AlertType = Literal["missed", "severe", "emergency_access"]
Reporter = Literal["self", "parent", "caregiver", "other"]
InputMode = Literal["voice", "text", "mixed"]


class Health(BaseModel):
    status: Literal["ok"]
    contract_version: str
    seeded: bool


class FieldError(BaseModel):
    field: str
    message: str


class ErrorBody(BaseModel):
    error: Literal["missing_headers", "forbidden", "conflict", "schema_validation", "not_found"]
    detail: str
    errors: list[FieldError] = []


class SurveyQuestion(BaseModel):
    question_id: str
    purpose: Literal["wellbeing", "symptom_screen", "severity", "onset", "adherence", "exposure"]
    asks: list[str]


class Schedule(BaseModel):
    every_days: int  # check-in cadence for the cohort (D-059)


class SurveyResponse(BaseModel):
    config_id: str
    cohort_id: str
    version: int
    published_at: str
    schedule: Schedule
    questions: list[SurveyQuestion]


class Term(BaseModel):
    term_code: str
    label_term: str
    everyday_words: list[str]
    severe_trigger: bool
    known_for_program: bool


class TermsResponse(BaseModel):
    program_id: str
    drug_name: str
    terms: list[Term]


class RecordAccepted(BaseModel):
    record_id: str
    payload_sha256: str


class EnvelopeAccepted(BaseModel):
    envelope_id: str
    payload_sha256: str


class AlertAccepted(BaseModel):
    alert_id: str
    routed_care_team: bool
    routed_caregiver: bool


class ConsentState(BaseModel):
    patient_ref: str
    care_org_id: Optional[str]
    share_care_team: bool
    caregiver_id: Optional[str]
    share_caregiver: bool
    caregiver_detail: Literal["alerts_only", "summary"]
    emergency_consent: bool
    emergency_org_ids: list[str]
    emergency_contact_count: int  # contacts themselves are never echoed back
    updated_at: str


class LinkedPatient(BaseModel):
    patient_ref: str
    granted_at: str


class Envelope(BaseModel):
    envelope_id: str
    patient_ref: str
    ciphertext: str
    payload_sha256: str
    received_at: str


class EnvelopeAck(BaseModel):
    envelope_id: str
    fetched_at: str


class Alert(BaseModel):
    alert_id: str
    patient_ref: str
    alert_type: AlertType
    escalation_level: Optional[int]  # 1, 2 or 3 for missed check-ins (D-068); null otherwise
    created_at: str   # event time (device or scheduler)
    received_at: str  # service time; use this as the `since` cursor (D-054)


class PublicKeyBody(BaseModel):
    public_key: str


class PublicKeyResponse(BaseModel):
    doctor_id: str
    public_key: str


class OrgKeyResponse(BaseModel):
    org_id: str
    public_key: str


class OrgMembership(BaseModel):
    org_id: str
    display_name: str
    org_type: Literal["hospital", "clinic"]
    role: Literal["attending", "on_call", "admin"]
    org_key_registered: bool
    has_key_grant: bool


class MemberBody(BaseModel):
    role: Literal["attending", "on_call", "admin"]
    status: Literal["active", "revoked"]


class MemberState(BaseModel):
    org_id: str
    doctor_id: str
    role: str
    status: str
    granted_at: str
    revoked_at: Optional[str]


class KeyGrantBody(BaseModel):
    doctor_id: str
    wrapped_key: str  # base64 sealed box of the org private key to the member's personal public key


class KeyGrantReceipt(BaseModel):
    org_id: str
    doctor_id: str
    granted_by: str
    granted_at: str


class KeyGrant(KeyGrantReceipt):
    wrapped_key: str


class EmergencyAccessBody(BaseModel):
    patient_ref: str
    reason: Literal["unresponsive_patient", "emergency_admission", "escalation_level_3"]


class EmergencyAccessResult(BaseModel):
    org_id: str
    patient_ref: str
    reason: str
    accessed_at: str
    notification_alert_id: str
    notified: list[str]  # recipient types told about this access
    envelopes: list[Envelope]


class CohortWeeklyRow(BaseModel):
    program_id: str
    cohort_id: str
    drug_version: str
    iso_week: str
    term_code: str
    patients: int
    severe_patients: Optional[int]  # None means 1-4 patients (suppressed, shown as "<5")
    reporting_patients: int


class CompletionRow(BaseModel):
    program_id: str
    cohort_id: str
    drug_version: str
    iso_week: str
    records: int
    patients: int
    completion_rate: float
    missed_rate: float


class SurveyPublished(BaseModel):
    config_id: str
    version: int


class ExportSymptom(BaseModel):
    term_code: str
    severity: Severity
    onset: str
    known_side_effect: bool
    possible_link_flag: bool


class ExportRecord(BaseModel):
    record_id: str
    patient_ref: str
    program_id: str
    cohort_id: str
    drug_version: str
    iso_week: str
    status: str
    source: Literal["device", "scheduler"]
    reporter: Optional[Reporter]     # null for scheduler records
    input_mode: Optional[InputMode]  # null for scheduler records
    unanswered_questions: int
    symptoms: list[ExportSymptom]
