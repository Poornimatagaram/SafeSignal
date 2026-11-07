"""Sentinel service API (Scoping Doc 26.7). Run: uv run uvicorn sentinel_service.main:app --port 8000

Demo-grade auth: every request carries X-Role and X-Actor-Id. The service logs IDs, roles, paths and status
codes only, never request bodies (26.12).
"""

from __future__ import annotations

import csv
import io
import logging
import os
from typing import Any, Literal, Optional

from fastapi import Body, Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from sentinel_contract import SCHEMA_VERSION, enums

from . import models as m
from .errors import ApiError, forbidden
from .stub_store import StubStore

log = logging.getLogger("sentinel")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ROLES = set(enums()["roles"])
COMPANY_READ = {"company_reader", "company_admin", "company_safety"}

app = FastAPI(
    title="Sentinel service",
    version=SCHEMA_VERSION,
    description="Side-Effect Sentinel API. Contract source of truth: schema/ in the repository. "
    "Every request needs X-Role and X-Actor-Id headers.",
)
app.state.store = StubStore()

_origins = [o.strip() for o in os.environ.get("SENTINEL_ALLOWED_ORIGINS", "").split(",") if o.strip()]
if _origins:
    app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["GET", "POST", "PUT"],
                       allow_headers=["X-Role", "X-Actor-Id", "Content-Type"], expose_headers=["X-Schema-Version"])


@app.middleware("http")
async def schema_header_and_log(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Schema-Version"] = SCHEMA_VERSION
    log.info("%s %s role=%s actor=%s status=%s", request.method, request.url.path,
             request.headers.get("x-role", "-"), request.headers.get("x-actor-id", "-"), response.status_code)
    return response


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, exc: ApiError):
    body = m.ErrorBody(error=exc.error, detail=exc.detail, errors=[m.FieldError(**e) for e in exc.errors])
    return JSONResponse(status_code=exc.status, content=body.model_dump())


class Actor:
    def __init__(self, role: str, actor_id: str):
        self.role = role
        self.id = actor_id


def actor(request: Request) -> Actor:
    role = request.headers.get("x-role")
    actor_id = request.headers.get("x-actor-id")
    if not role or not actor_id:
        raise ApiError(401, "missing_headers", "X-Role and X-Actor-Id headers are required")
    if role not in ROLES:
        raise ApiError(401, "missing_headers", f"unknown role '{role}'")
    return Actor(role, actor_id)


def need(a: Actor, *roles: str, match: Optional[str] = None) -> None:
    if a.role not in roles:
        raise forbidden(f"role '{a.role}' may not call this endpoint")
    if match is not None and a.id != match:
        raise forbidden("X-Actor-Id does not match the ID in the path")


def store(request: Request) -> StubStore:
    return request.app.state.store


ERRORS = {401: {"model": m.ErrorBody}, 403: {"model": m.ErrorBody}, 404: {"model": m.ErrorBody},
          409: {"model": m.ErrorBody}, 422: {"model": m.ErrorBody}}
Payload = dict[str, Any]


# ---------------- patient_device ----------------

@app.get("/v1/survey", response_model=m.SurveyResponse, responses=ERRORS, tags=["patient_device"])
def get_survey(cohort_id: str, a: Actor = Depends(actor), s: StubStore = Depends(store)):
    need(a, "patient_device")
    return s.get_survey(cohort_id)


@app.get("/v1/terms", response_model=m.TermsResponse, responses=ERRORS, tags=["patient_device"])
def get_terms(program_id: str, a: Actor = Depends(actor), s: StubStore = Depends(store)):
    need(a, "patient_device")
    return s.get_terms(program_id)


@app.post("/v1/records", response_model=m.RecordAccepted, status_code=201, responses=ERRORS,
          tags=["patient_device"], summary="Company record (schema/company_record.json)")
def post_record(response: Response, payload: Payload = Body(...), a: Actor = Depends(actor),
                s: StubStore = Depends(store)):
    need(a, "patient_device")
    code, body = s.put_record(a.id, payload)
    response.status_code = code
    return body


@app.post("/v1/doctor-envelopes", response_model=m.EnvelopeAccepted, status_code=201, responses=ERRORS,
          tags=["patient_device"], summary="Doctor envelope (schema/doctor_envelope.json)")
def post_envelope(response: Response, payload: Payload = Body(...), a: Actor = Depends(actor),
                  s: StubStore = Depends(store)):
    need(a, "patient_device")
    code, body = s.put_envelope(a.id, payload)
    response.status_code = code
    return body


@app.post("/v1/alerts", response_model=m.AlertAccepted, status_code=201, responses=ERRORS,
          tags=["patient_device"], summary="Severe alert (schema/alert_event.json)")
def post_alert(response: Response, payload: Payload = Body(...), a: Actor = Depends(actor),
               s: StubStore = Depends(store)):
    need(a, "patient_device")
    code, body = s.put_alert(a.id, payload)
    response.status_code = code
    return body


@app.put("/v1/consent/{patient_ref}", response_model=m.ConsentState, responses=ERRORS, tags=["patient_device"],
         summary="Consent update (schema/consent_update.json)")
def put_consent(patient_ref: str, payload: Payload = Body(...), a: Actor = Depends(actor),
                s: StubStore = Depends(store)):
    need(a, "patient_device", match=patient_ref)
    return s.put_consent(a.id, patient_ref, payload)


@app.get("/v1/doctors/{doctor_id}/public-key", response_model=m.PublicKeyResponse, responses=ERRORS,
         tags=["patient_device"])
def get_public_key(doctor_id: str, a: Actor = Depends(actor), s: StubStore = Depends(store)):
    need(a, "patient_device")
    return s.get_public_key(a.id, doctor_id)


# ---------------- doctor ----------------

@app.put("/v1/doctors/{doctor_id}/public-key", response_model=m.PublicKeyResponse, responses=ERRORS,
         tags=["doctor"])
def put_public_key(doctor_id: str, body: m.PublicKeyBody, a: Actor = Depends(actor), s: StubStore = Depends(store)):
    need(a, "doctor", match=doctor_id)
    return s.put_public_key(doctor_id, body.public_key)


@app.get("/v1/doctors/{doctor_id}/patients", response_model=list[m.LinkedPatient], responses=ERRORS,
         tags=["doctor"])
def doctor_patients(doctor_id: str, a: Actor = Depends(actor), s: StubStore = Depends(store)):
    need(a, "doctor", match=doctor_id)
    return s.doctor_patients(doctor_id)


@app.get("/v1/doctors/{doctor_id}/envelopes", response_model=list[m.Envelope], responses=ERRORS, tags=["doctor"])
def doctor_envelopes(doctor_id: str, since: Optional[str] = None, a: Actor = Depends(actor),
                     s: StubStore = Depends(store)):
    need(a, "doctor", match=doctor_id)
    return s.doctor_envelopes(doctor_id, since)


@app.post("/v1/doctors/{doctor_id}/envelopes/{envelope_id}/ack", response_model=m.EnvelopeAck, responses=ERRORS,
          tags=["doctor"])
def ack_envelope(doctor_id: str, envelope_id: str, a: Actor = Depends(actor), s: StubStore = Depends(store)):
    need(a, "doctor", match=doctor_id)
    return s.ack_envelope(doctor_id, envelope_id)


@app.get("/v1/doctors/{doctor_id}/alerts", response_model=list[m.DoctorAlert], responses=ERRORS, tags=["doctor"])
def doctor_alerts(doctor_id: str, since: Optional[str] = None, a: Actor = Depends(actor),
                  s: StubStore = Depends(store)):
    need(a, "doctor", match=doctor_id)
    return s.doctor_alerts(doctor_id, since)


# ---------------- caregiver ----------------

@app.get("/v1/caregivers/{caregiver_id}/alerts", response_model=list[m.CaregiverAlert], responses=ERRORS,
         tags=["caregiver"])
def caregiver_alerts(caregiver_id: str, a: Actor = Depends(actor), s: StubStore = Depends(store)):
    need(a, "caregiver", match=caregiver_id)
    return s.caregiver_alerts(caregiver_id)


# ---------------- company ----------------

@app.get("/v1/company/cohorts/weekly", response_model=list[m.CohortWeeklyRow], responses=ERRORS, tags=["company"])
def cohorts_weekly(program_id: str, a: Actor = Depends(actor), s: StubStore = Depends(store)):
    need(a, *COMPANY_READ)
    s.log_access(a.role, a.id, "read", f"v_cohort_weekly:{program_id}")
    return s.cohorts_weekly(program_id)


@app.get("/v1/company/completion", response_model=list[m.CompletionRow], responses=ERRORS, tags=["company"])
def completion(program_id: str, a: Actor = Depends(actor), s: StubStore = Depends(store)):
    need(a, *COMPANY_READ)
    s.log_access(a.role, a.id, "read", f"v_completion_weekly:{program_id}")
    return s.completion(program_id)


@app.put("/v1/company/cohorts/{cohort_id}/survey", response_model=m.SurveyPublished, status_code=201,
         responses=ERRORS, tags=["company"], summary="Publish a survey version (schema/survey_config.json)")
def publish_survey(cohort_id: str, payload: Payload = Body(...), a: Actor = Depends(actor),
                   s: StubStore = Depends(store)):
    need(a, "company_admin")
    s.log_access(a.role, a.id, "publish_survey", cohort_id)
    return s.publish_survey(a.id, cohort_id, payload)


@app.get("/v1/company/records/export", response_model=list[m.ExportRecord], responses=ERRORS, tags=["company"],
         summary="Pseudonymized records as JSON or CSV (one CSV row per symptom)")
def export_records(program_id: str, format: Literal["json", "csv"] = Query("json"), a: Actor = Depends(actor),
                   s: StubStore = Depends(store)):
    need(a, "company_safety")
    s.log_access(a.role, a.id, f"export_{format}", program_id)
    rows = s.export_records(program_id)
    if format == "json":
        return rows
    buf = io.StringIO()
    cols = ["record_id", "patient_ref", "program_id", "cohort_id", "drug_version", "iso_week", "status", "source",
            "unanswered_questions", "term_code", "severity", "onset", "known_side_effect", "possible_link_flag"]
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    for r in rows:
        base = {k: r[k] for k in cols[:9]}
        for sym in r["symptoms"] or [{}]:
            w.writerow({**base, **sym})
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{program_id}_records.csv"'})
