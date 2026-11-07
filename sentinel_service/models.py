"""Response models for the Sentinel API (Scoping Doc 26.7). These drive /docs and the generated TypeScript types.

Request bodies are validated against the published JSON Schemas in schema/, not against these models.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

Severity = Literal["mild", "moderate", "severe"]
AlertType = Literal["missed", "severe"]


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


class SurveyResponse(BaseModel):
    config_id: str
    cohort_id: str
    version: int
    published_at: str
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
    routed_doctor: bool
    routed_caregiver: bool


class ConsentState(BaseModel):
    patient_ref: str
    doctor_id: Optional[str]
    caregiver_id: Optional[str]
    share_doctor: bool
    share_caregiver: bool
    caregiver_detail: Literal["alerts_only", "summary"]
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


class DoctorAlert(BaseModel):
    alert_id: str
    patient_ref: str
    alert_type: AlertType
    created_at: str


class CaregiverAlert(BaseModel):
    alert_id: str
    patient_ref: str
    alert_type: AlertType
    created_at: str


class PublicKeyBody(BaseModel):
    public_key: str


class PublicKeyResponse(BaseModel):
    doctor_id: str
    public_key: str


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
    unanswered_questions: int
    symptoms: list[ExportSymptom]
