"""Sentinel service API (Scoping Doc 26.7). Run: uv run uvicorn sentinel_service.main:app --port 8000

Demo-grade auth: every request carries X-Role and X-Actor-Id. The service logs IDs, roles, paths and status
codes only, never request bodies (26.12).
"""

from __future__ import annotations

import csv
import io
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Literal, Optional

from fastapi import Body, Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from sentinel_contract import CONTRACT_VERSION, enums

from . import models as m
from .errors import ApiError, forbidden
from .store import SqliteStore

log = logging.getLogger("sentinel")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ROLES = set(enums()["roles"])
COMPANY_READ = {"company_reader", "company_admin", "company_safety"}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tests may install their own store before startup; otherwise open var/service (or $SERVICE_DATA_DIR).
    opened = getattr(app.state, "store", None) is None
    if opened:
        app.state.store = SqliteStore.open()
    yield
    if opened:
        app.state.store.close()
        app.state.store = None


app = FastAPI(
    title="Sentinel service",
    version=CONTRACT_VERSION,
    description="SafeSignal / Sentinel API. Contract source of truth: schema/ in the repository. "
    "Every request except /healthz needs X-Role and X-Actor-Id headers.",
    lifespan=lifespan,
)
app.state.store = None

_origins = [o.strip() for o in os.environ.get("SENTINEL_ALLOWED_ORIGINS", "").split(",") if o.strip()]
if _origins:
    app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["GET", "POST", "PUT"],
                       allow_headers=["X-Role", "X-Actor-Id", "Content-Type"], expose_headers=["X-Schema-Version"])


@app.middleware("http")
async def schema_header_and_log(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Schema-Version"] = CONTRACT_VERSION
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


def store(request: Request) -> SqliteStore:
    return request.app.state.store


ERRORS = {401: {"model": m.ErrorBody}, 403: {"model": m.ErrorBody}, 404: {"model": m.ErrorBody},
          409: {"model": m.ErrorBody}, 422: {"model": m.ErrorBody}}
Payload = dict[str, Any]


@app.get("/healthz", response_model=m.Health, tags=["ops"], summary="Liveness and seed state (no auth)")
def healthz(s: SqliteStore = Depends(store)):
    seeded = s.db.company.execute("SELECT 1 FROM program LIMIT 1").fetchone() is not None
    return {"status": "ok", "contract_version": CONTRACT_VERSION, "seeded": seeded}


# ---------------- patient_device ----------------

@app.get("/v1/survey", response_model=m.SurveyResponse, responses=ERRORS, tags=["patient_device"])
def get_survey(cohort_id: str, a: Actor = Depends(actor), s: SqliteStore = Depends(store)):
    need(a, "patient_device")
    return s.get_survey(cohort_id)


@app.get("/v1/terms", response_model=m.TermsResponse, responses=ERRORS, tags=["patient_device"])
def get_terms(program_id: str, a: Actor = Depends(actor), s: SqliteStore = Depends(store)):
    need(a, "patient_device")
    return s.get_terms(program_id)


@app.post("/v1/records", response_model=m.RecordAccepted, status_code=201, responses=ERRORS,
          tags=["patient_device"], summary="Company record (schema/company_record.json)")
def post_record(response: Response, payload: Payload = Body(...), a: Actor = Depends(actor),
                s: SqliteStore = Depends(store)):
    need(a, "patient_device")
    code, body = s.put_record(a.id, payload)
    response.status_code = code
    return body


@app.post("/v1/care-envelopes", response_model=m.EnvelopeAccepted, status_code=201, responses=ERRORS,
          tags=["patient_device"], summary="Care envelope sealed to an organization (schema/care_envelope.json)")
def post_envelope(response: Response, payload: Payload = Body(...), a: Actor = Depends(actor),
                  s: SqliteStore = Depends(store)):
    need(a, "patient_device")
    code, body = s.put_envelope(a.id, payload)
    response.status_code = code
    return body


@app.post("/v1/alerts", response_model=m.AlertAccepted, status_code=201, responses=ERRORS,
          tags=["patient_device"], summary="Severe alert (schema/alert_event.json)")
def post_alert(response: Response, payload: Payload = Body(...), a: Actor = Depends(actor),
               s: SqliteStore = Depends(store)):
    need(a, "patient_device")
    code, body = s.put_alert(a.id, payload)
    response.status_code = code
    return body


@app.put("/v1/consent/{patient_ref}", response_model=m.ConsentState, responses=ERRORS, tags=["patient_device"],
         summary="Consent update: care team, caregiver, emergency organizations and contacts "
                 "(schema/consent_update.json)")
def put_consent(patient_ref: str, payload: Payload = Body(...), a: Actor = Depends(actor),
                s: SqliteStore = Depends(store)):
    need(a, "patient_device", match=patient_ref)
    return s.put_consent(a.id, patient_ref, payload)


@app.get("/v1/orgs/{org_id}/public-key", response_model=m.OrgKeyResponse, responses=ERRORS, tags=["patient_device"],
         summary="Care-team key of a linked organization (care team or consented emergency)")
def get_org_key(org_id: str, a: Actor = Depends(actor), s: SqliteStore = Depends(store)):
    need(a, "patient_device")
    return s.get_org_key(a.id, org_id)


# ---------------- doctor and organization ----------------

@app.put("/v1/doctors/{doctor_id}/public-key", response_model=m.PublicKeyResponse, responses=ERRORS,
         tags=["doctor"], summary="Register the doctor's personal key (receives key grants)")
def put_doctor_key(doctor_id: str, body: m.PublicKeyBody, a: Actor = Depends(actor), s: SqliteStore = Depends(store)):
    need(a, "doctor", match=doctor_id)
    return s.put_doctor_key(doctor_id, body.public_key)


@app.get("/v1/doctors/{doctor_id}/orgs", response_model=list[m.OrgMembership], responses=ERRORS, tags=["doctor"],
         summary="Organizations the doctor is an active member of")
def doctor_orgs(doctor_id: str, a: Actor = Depends(actor), s: SqliteStore = Depends(store)):
    need(a, "doctor", match=doctor_id)
    return s.doctor_orgs(doctor_id)


@app.put("/v1/orgs/{org_id}/public-key", response_model=m.OrgKeyResponse, responses=ERRORS, tags=["doctor"],
         summary="Register the organization's care-team key (admin)")
def put_org_key(org_id: str, body: m.PublicKeyBody, a: Actor = Depends(actor), s: SqliteStore = Depends(store)):
    need(a, "doctor")
    return s.put_org_key(a.id, org_id, body.public_key)


@app.put("/v1/orgs/{org_id}/members/{doctor_id}", response_model=m.MemberState, responses=ERRORS, tags=["doctor"],
         summary="Add, change or revoke a member (admin); revoking removes their key grant")
def put_member(org_id: str, doctor_id: str, body: m.MemberBody, a: Actor = Depends(actor),
               s: SqliteStore = Depends(store)):
    need(a, "doctor")
    return s.put_member(a.id, org_id, doctor_id, body.role, body.status)


@app.post("/v1/orgs/{org_id}/key-grants", response_model=m.KeyGrantReceipt, status_code=201, responses=ERRORS,
          tags=["doctor"], summary="Give a member the org key, sealed to their personal key (admin)")
def post_key_grant(org_id: str, body: m.KeyGrantBody, a: Actor = Depends(actor), s: SqliteStore = Depends(store)):
    need(a, "doctor")
    return s.put_key_grant(a.id, org_id, body.doctor_id, body.wrapped_key)


@app.get("/v1/orgs/{org_id}/key-grants/{doctor_id}", response_model=m.KeyGrant, responses=ERRORS, tags=["doctor"],
         summary="The calling doctor's own key grant")
def get_key_grant(org_id: str, doctor_id: str, a: Actor = Depends(actor), s: SqliteStore = Depends(store)):
    need(a, "doctor", match=doctor_id)
    return s.get_key_grant(doctor_id, org_id)


@app.get("/v1/orgs/{org_id}/patients", response_model=list[m.LinkedPatient], responses=ERRORS, tags=["doctor"],
         summary="Patients whose care team is this organization (members)")
def org_patients(org_id: str, a: Actor = Depends(actor), s: SqliteStore = Depends(store)):
    need(a, "doctor")
    return s.org_patients(a.id, org_id)


@app.get("/v1/orgs/{org_id}/envelopes", response_model=list[m.Envelope], responses=ERRORS, tags=["doctor"],
         summary="Care-team envelopes since a time (members)")
def org_envelopes(org_id: str, since: Optional[str] = None, a: Actor = Depends(actor),
                  s: SqliteStore = Depends(store)):
    need(a, "doctor")
    return s.org_envelopes(a.id, org_id, since)


@app.post("/v1/orgs/{org_id}/envelopes/{envelope_id}/ack", response_model=m.EnvelopeAck, responses=ERRORS,
          tags=["doctor"])
def ack_envelope(org_id: str, envelope_id: str, a: Actor = Depends(actor), s: SqliteStore = Depends(store)):
    need(a, "doctor")
    return s.ack_envelope(a.id, org_id, envelope_id)


@app.get("/v1/orgs/{org_id}/alerts", response_model=list[m.Alert], responses=ERRORS, tags=["doctor"],
         summary="Alerts delivered to this care team since a time (members)")
def org_alerts(org_id: str, since: Optional[str] = None, a: Actor = Depends(actor), s: SqliteStore = Depends(store)):
    need(a, "doctor")
    return s.org_alerts(a.id, org_id, since)


@app.post("/v1/orgs/{org_id}/emergency-access", response_model=m.EmergencyAccessResult, responses=ERRORS,
          tags=["doctor"], summary="Emergency access to a patient's envelopes (members of a consented emergency "
                                   "organization; coded reason; logged; notifies caregiver and care team)")
def emergency_access(org_id: str, body: m.EmergencyAccessBody, a: Actor = Depends(actor),
                     s: SqliteStore = Depends(store)):
    need(a, "doctor")
    return s.emergency_access(a.id, org_id, body.patient_ref, body.reason)


# ---------------- caregiver ----------------

@app.get("/v1/caregivers/{caregiver_id}/alerts", response_model=list[m.Alert], responses=ERRORS,
         tags=["caregiver"])
def caregiver_alerts(caregiver_id: str, a: Actor = Depends(actor), s: SqliteStore = Depends(store)):
    need(a, "caregiver", match=caregiver_id)
    return s.caregiver_alerts(caregiver_id)


# ---------------- company ----------------

@app.get("/v1/company/cohorts/weekly", response_model=list[m.CohortWeeklyRow], responses=ERRORS, tags=["company"])
def cohorts_weekly(program_id: str, a: Actor = Depends(actor), s: SqliteStore = Depends(store)):
    need(a, *COMPANY_READ)
    s.log_access(a.role, a.id, "read", f"v_cohort_weekly:{program_id}")
    return s.cohorts_weekly(program_id)


@app.get("/v1/company/completion", response_model=list[m.CompletionRow], responses=ERRORS, tags=["company"])
def completion(program_id: str, a: Actor = Depends(actor), s: SqliteStore = Depends(store)):
    need(a, *COMPANY_READ)
    s.log_access(a.role, a.id, "read", f"v_completion_weekly:{program_id}")
    return s.completion(program_id)


@app.put("/v1/company/cohorts/{cohort_id}/survey", response_model=m.SurveyPublished, status_code=201,
         responses=ERRORS, tags=["company"], summary="Publish a survey version (schema/survey_config.json)")
def publish_survey(cohort_id: str, payload: Payload = Body(...), a: Actor = Depends(actor),
                   s: SqliteStore = Depends(store)):
    need(a, "company_admin")
    s.log_access(a.role, a.id, "publish_survey", cohort_id)
    return s.publish_survey(a.id, cohort_id, payload)


@app.get("/v1/company/records/export", response_model=list[m.ExportRecord], responses=ERRORS, tags=["company"],
         summary="Pseudonymized records as JSON or CSV (one CSV row per symptom)")
def export_records(program_id: str, format: Literal["json", "csv"] = Query("json"), a: Actor = Depends(actor),
                   s: SqliteStore = Depends(store)):
    need(a, "company_safety")
    s.log_access(a.role, a.id, f"export_{format}", program_id)
    rows = s.export_records(program_id)
    if format == "json":
        return rows
    buf = io.StringIO()
    cols = ["record_id", "patient_ref", "program_id", "cohort_id", "drug_version", "iso_week", "status", "source",
            "reporter", "input_mode", "unanswered_questions", "term_code", "severity", "onset", "known_side_effect",
            "possible_link_flag"]
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    for r in rows:
        base = {k: r[k] for k in cols[:11]}
        for sym in r["symptoms"] or [{}]:
            w.writerow({**base, **sym})
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{program_id}_records.csv"'})
