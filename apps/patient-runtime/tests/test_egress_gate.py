"""Task A4 egress gate (PV-04, PV-05, PV-06, PV-08): build, outbox, send, receipt, egress_log and config refresh.

Offline tests drive the real SentinelClient against an in-memory stand-in for the service (httpx.MockTransport).
Live tests run against the local Sentinel service and skip when it is not reachable.
"""

import json
import logging
from contextlib import closing
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from sentinel_contract import SCHEMA_DIR, ContractError, canonical, payload_sha256
from sentinel_contract.client import SentinelClient, field_names as client_field_names
from sentinel_patient import egress_gate as gate
from sentinel_patient.config import WALTER, Settings
from sentinel_patient.db import connect, init_db, utc_now

BASE = "http://sentinel.test"
DEMO_DAY = datetime(2026, 11, 7, 15, 0, tzinfo=timezone.utc)  # Saturday of 2026-W45
LOCAL_ONLY = ("Walter", "1934-03-12", "555-0142")  # Walter's display_name, date_of_birth, phone (local only)
RASH = {"term_code": "SE_RASH", "severity": "moderate", "onset": "1_3_days", "known_side_effect": 1,
        "possible_link_flag": 0}
SCHEMA_FIELDS = set(json.loads((SCHEMA_DIR / "company_record.json").read_text())["properties"])

SURVEY = {"config_id": "cfg_cohort_b_v1", "cohort_id": "cohort_B", "version": 1,
          "published_at": "2026-09-27T12:00:00.000000Z",
          **json.loads((SCHEMA_DIR / "examples" / "survey_config.valid.json").read_text())}
TERMS = {"program_id": "prog_demo_01", "drug_name": "Tagrisso",
         "terms": [{"term_code": t["term_code"], "label_term": t["label_term"], "everyday_words": t["everyday_words"],
                    "severe_trigger": t["severe_trigger"], "known_for_program": "Tagrisso" in t["drug_scope"]}
                   for t in json.loads((SCHEMA_DIR / "terms.json").read_text())["terms"]]}
BODY_MARKER = "body-text-that-must-not-be-logged"


class FakeService:
    """Stand-in for the Sentinel service behind the real SentinelClient; records every request that reached it."""

    def __init__(self, *, status: int = 201, get_status: int = 200, down: bool = False, survey=None, terms=None):
        self.status, self.get_status, self.down = status, get_status, down
        self.survey, self.terms = survey or SURVEY, terms or TERMS
        self.requests: list[tuple[str, str, bytes]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("connection refused", request=request)
        self.requests.append((request.method, request.url.path, request.content))
        path = request.url.path
        if path == "/v1/records":
            if self.status >= 400:
                return httpx.Response(self.status, json={"error": BODY_MARKER})
            body = json.loads(request.content)
            return httpx.Response(self.status, json={"record_id": body["record_id"],
                                                     "payload_sha256": payload_sha256(body)})
        if self.get_status != 200:
            return httpx.Response(self.get_status, json={"error": BODY_MARKER})
        return httpx.Response(200, json=self.survey if path == "/v1/survey" else self.terms)

    def client(self) -> SentinelClient:
        return SentinelClient(base_url=BASE, patient_ref=WALTER,
                              http=httpx.Client(base_url=BASE, transport=httpx.MockTransport(self)))

    def sends(self) -> list:
        return [r for r in self.requests if r[0] == "POST"]


@pytest.fixture()
def db_path(tmp_path):
    path = tmp_path / "patient.db"
    init_db(path, WALTER)  # seeds Walter's profile and consent
    return path


def rows(db_path, sql, *args):
    with closing(connect(db_path)) as conn:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]


def profile_and_consent(db_path):
    with closing(connect(db_path)) as conn:
        return (conn.execute("SELECT * FROM patient_profile WHERE patient_ref = ?", (WALTER,)).fetchone(),
                conn.execute("SELECT * FROM consent ORDER BY consent_id DESC LIMIT 1").fetchone())


def make_record(db_path, record_id="rec_0a1b2c3d", symptoms=(RASH,), unanswered=0, now=DEMO_DAY, consent=None):
    profile, stored_consent = profile_and_consent(db_path)
    return gate.build_company_record(record_id=record_id, profile=profile, consent=consent or stored_consent,
                                     symptoms=list(symptoms), unanswered_questions=unanswered, reporter="self",
                                     input_mode="voice", now=now)


def queue(db_path, payload, destination="company_record", outbox_id=None):
    with closing(connect(db_path)) as conn, conn:
        gate.queue_payload(conn, outbox_id=outbox_id or payload["record_id"], session_id=None,
                           destination=destination, payload=payload)


# ---------- small helpers ----------

def test_ids_urls_client_and_field_names():
    assert all(gate.new_record_id().startswith("rec_") and len(gate.new_record_id()) == 12 for _ in range(5))
    assert all(set(gate.new_record_id()[4:]) <= set("0123456789abcdef") for _ in range(20))
    assert gate.records_url("http://127.0.0.1:8000/") == "http://127.0.0.1:8000/v1/records"
    client = gate.make_client(Settings(patient_ref=WALTER, sentinel_base_url="http://127.0.0.1:8000"))
    try:
        assert (client.base_url, client.patient_ref) == ("http://127.0.0.1:8000", WALTER)
    finally:
        client.close()
    record = json.loads((SCHEMA_DIR / "examples" / "company_record.valid.json").read_text())
    assert gate.field_names(record) == client_field_names(record)
    assert "symptoms[].term_code" in gate.field_names(record)


# ---------- build ----------

def test_build_has_exactly_the_schema_fields_and_the_enrollment_from_the_profile(db_path):
    record = make_record(db_path)
    assert set(record) == SCHEMA_FIELDS
    assert record == {
        "schema_version": "2.0", "record_id": "rec_0a1b2c3d", "patient_ref": WALTER, "program_id": "prog_demo_01",
        "cohort_id": "cohort_B", "drug_version": "v2", "iso_week": "2026-W45", "status": "completed",
        "symptoms": [{"term_code": "SE_RASH", "severity": "moderate", "onset": "1_3_days",
                      "known_side_effect": True, "possible_link_flag": False}],
        "unanswered_questions": 0, "consent": {"care_team": True, "caregiver": True}, "reporter": "self",
        "input_mode": "voice"}


def test_status_is_partial_when_any_question_is_unanswered(db_path):
    assert make_record(db_path, unanswered=0)["status"] == "completed"
    assert make_record(db_path, unanswered=2)["status"] == "partial"


@pytest.mark.parametrize("now, week", [
    (datetime(2026, 11, 8, 23, 59, tzinfo=timezone.utc), "2026-W45"),                   # Sunday
    (datetime(2026, 11, 8, 23, 30, tzinfo=timezone(timedelta(hours=-5))), "2026-W46"),  # Monday in UTC
    (datetime(2027, 1, 1, 12, 0, tzinfo=timezone.utc), "2026-W53"),                     # ISO year, not calendar year
    (datetime(2026, 11, 2, 0, 0), "2026-W45"),                                          # naive is taken as UTC
])
def test_iso_week_is_the_utc_iso_week(db_path, now, week):
    assert make_record(db_path, now=now)["iso_week"] == week


def test_iso_week_defaults_to_now(db_path):
    iso = datetime.now(timezone.utc).isocalendar()
    assert make_record(db_path, now=None)["iso_week"] == f"{iso.year}-W{iso.week:02d}"


@pytest.mark.parametrize("care_team, caregiver", [(1, 1), (1, 0), (0, 1), (0, 0)])
def test_consent_maps_share_flags_to_booleans(db_path, care_team, caregiver):
    consent = {"share_care_team": care_team, "share_caregiver": caregiver, "emergency_consent": 1,
               "caregiver_detail": "alerts_only"}
    assert make_record(db_path, consent=consent)["consent"] == {"care_team": bool(care_team),
                                                                "caregiver": bool(caregiver)}


@pytest.mark.parametrize("change", [{"severity": "terrible"}, {"term_code": "rash"}, {"onset": "last week"},
                                    {"known_side_effect": "yes"}, {"possible_link_flag": 2}])
def test_invalid_record_raises_contract_error_and_nothing_is_written_or_sent(db_path, change):
    with pytest.raises(ContractError) as exc:
        make_record(db_path, symptoms=[{**RASH, **change}])
    bad_value = str(next(iter(change.values())))
    assert bad_value not in str(exc.value)  # errors name the field, never the value
    assert exc.value.errors[0]["field"].startswith("/symptoms/0/")
    assert rows(db_path, "SELECT * FROM outbox") == [] and rows(db_path, "SELECT * FROM egress_log") == []


def test_record_never_carries_local_only_data(db_path):
    with closing(connect(db_path)) as conn, conn:  # a stored transcript and patient words on the device
        conn.execute("INSERT INTO survey_cache VALUES ('cfg_cohort_b_v1', 'cohort_B', 1, '{}', ?)", (utc_now(),))
        conn.execute("INSERT INTO checkin_session (session_id, config_id, started_at, status) "
                     "VALUES ('ses_1', 'cfg_cohort_b_v1', ?, 'completed')", (utc_now(),))
    symptom = {**RASH, "patient_words": "Walter says his rash is itchy", "transcript_text": "call 555-0142"}
    record = make_record(db_path, symptoms=[symptom])
    with closing(connect(db_path)) as conn, conn:
        gate.queue_payload(conn, outbox_id=record["record_id"], session_id="ses_1", destination="company_record",
                           payload=record)
    service = FakeService()
    gate.send_queued(db_path, record["record_id"], client=service.client())
    stored = rows(db_path, "SELECT payload FROM outbox")[0]["payload"]
    on_the_wire = service.sends()[0][2].decode()
    for text in (canonical(record).decode(), stored, on_the_wire):
        for value in LOCAL_ONLY + ("itchy", "display_name", "date_of_birth", "phone", "transcript_text",
                                   "patient_words"):
            assert value not in text


# ---------- outbox ----------

def test_queue_writes_canonical_payload_and_is_idempotent(db_path):
    record = make_record(db_path)
    queue(db_path, record)
    queue(db_path, record)  # same id, same payload: no-op
    [row] = rows(db_path, "SELECT * FROM outbox")
    assert row["outbox_id"] == "rec_0a1b2c3d" and row["destination"] == "company_record"
    assert row["status"] == "queued" and row["sent_at"] is None and row["session_id"] is None
    assert row["payload"] == canonical(record).decode() and row["payload_sha256"] == payload_sha256(record)
    assert row["created_at"].endswith("Z")


def test_queue_refuses_the_same_id_with_a_different_payload(db_path):
    record = make_record(db_path)
    queue(db_path, record)
    with pytest.raises(ValueError, match="different payload") as exc:
        queue(db_path, make_record(db_path, unanswered=1))
    assert "SE_RASH" not in str(exc.value)
    assert rows(db_path, "SELECT payload_sha256 FROM outbox") == [{"payload_sha256": payload_sha256(record)}]


def test_queue_validates_and_needs_the_record_id_as_outbox_id(db_path):
    record = make_record(db_path)
    with pytest.raises(ContractError):
        queue(db_path, {**record, "display_name": "Walter"})
    with pytest.raises(ValueError, match="record_id"):
        queue(db_path, record, outbox_id="rec_ffffffff")
    with pytest.raises(ValueError, match="destination"):
        queue(db_path, record, destination="doctor")
    assert rows(db_path, "SELECT * FROM outbox") == []


def test_queue_leaves_the_transaction_to_the_caller(db_path):
    with closing(connect(db_path)) as conn:
        gate.queue_payload(conn, outbox_id="rec_0a1b2c3d", session_id=None, destination="company_record",
                           payload=make_record(db_path))
        conn.rollback()
    assert rows(db_path, "SELECT * FROM outbox") == []


# ---------- send ----------

def test_send_success_marks_sent_logs_the_request_and_returns_the_receipt(db_path):
    record = make_record(db_path)
    queue(db_path, record)
    service = FakeService()
    receipt = gate.send_queued(db_path, "rec_0a1b2c3d", client=service.client())

    assert receipt.status == "sent" and receipt.response_code == 201
    assert receipt.payload_sha256 == payload_sha256(record)
    assert (receipt.outbox_id, receipt.destination, receipt.method, receipt.url) == (
        "rec_0a1b2c3d", "company_record", "POST", f"{BASE}/v1/records")
    assert receipt.fields_sent == client_field_names(record) and "symptoms[].term_code" in receipt.fields_sent
    assert "SE_RASH" not in json.dumps(receipt.to_dict())  # names only, never values
    assert service.sends() == [("POST", "/v1/records", canonical(record))]  # the stored payload, unchanged

    [outbox] = rows(db_path, "SELECT status, sent_at FROM outbox")
    assert outbox == {"status": "sent", "sent_at": receipt.sent_at} and receipt.sent_at.endswith("Z")
    [entry] = rows(db_path, "SELECT * FROM egress_log")
    assert {k: entry[k] for k in ("outbox_id", "method", "url", "payload_sha256", "response_code", "sent_at")} == {
        "outbox_id": "rec_0a1b2c3d", "method": "POST", "url": f"{BASE}/v1/records",
        "payload_sha256": receipt.payload_sha256, "response_code": 201, "sent_at": receipt.sent_at}
    assert json.loads(entry["fields_sent"]) == receipt.fields_sent
    assert gate.receipt_for(db_path, "rec_0a1b2c3d") == receipt
    assert json.loads(json.dumps(receipt.to_dict())) == receipt.to_dict()


def test_a_sent_payload_is_never_sent_twice(db_path):
    queue(db_path, make_record(db_path))
    service = FakeService()
    first = gate.send_queued(db_path, "rec_0a1b2c3d", client=service.client())
    second = gate.send_queued(db_path, "rec_0a1b2c3d", client=service.client())
    assert second == first and len(service.sends()) == 1
    assert len(rows(db_path, "SELECT * FROM egress_log")) == 1


def test_no_network_keeps_it_queued_with_no_log_row_then_sends_the_same_payload(db_path):
    record = make_record(db_path)
    queue(db_path, record)
    service = FakeService(down=True)
    receipt = gate.send_queued(db_path, "rec_0a1b2c3d", client=service.client())
    assert receipt == gate.Receipt("queued", "rec_0a1b2c3d", "company_record", "POST", f"{BASE}/v1/records",
                                   client_field_names(record), payload_sha256(record), None, None)
    assert rows(db_path, "SELECT status FROM outbox") == [{"status": "queued"}]
    assert rows(db_path, "SELECT * FROM egress_log") == []  # nothing reached the service
    assert gate.receipt_for(db_path, "rec_0a1b2c3d", base_url=BASE) == receipt

    service.down = False  # back online: same id, same bytes
    sent = gate.send_queued(db_path, "rec_0a1b2c3d", client=service.client())
    assert sent.status == "sent" and sent.payload_sha256 == receipt.payload_sha256
    assert service.sends() == [("POST", "/v1/records", canonical(record))]


def test_server_error_is_logged_and_stays_queued(db_path):
    queue(db_path, make_record(db_path))
    service = FakeService(status=503)
    receipt = gate.send_queued(db_path, "rec_0a1b2c3d", client=service.client())
    assert (receipt.status, receipt.response_code, receipt.sent_at) == ("queued", None, None)
    assert rows(db_path, "SELECT status FROM outbox") == [{"status": "queued"}]
    assert [r["response_code"] for r in rows(db_path, "SELECT * FROM egress_log")] == [503]  # it reached the service
    assert gate.receipt_for(db_path, "rec_0a1b2c3d") == receipt

    service.status = 201
    assert gate.send_queued(db_path, "rec_0a1b2c3d", client=service.client()).status == "sent"
    assert [r["response_code"] for r in rows(db_path, "SELECT * FROM egress_log ORDER BY log_id")] == [503, 201]


@pytest.mark.parametrize("status", [401, 403, 409, 422])
def test_rejected_is_failed_logged_and_never_retried(db_path, status):
    queue(db_path, make_record(db_path))
    service = FakeService(status=status)
    receipt = gate.send_queued(db_path, "rec_0a1b2c3d", client=service.client())
    assert (receipt.status, receipt.response_code, receipt.sent_at) == ("failed", status, None)
    assert rows(db_path, "SELECT status, sent_at FROM outbox") == [{"status": "failed", "sent_at": None}]
    assert [r["response_code"] for r in rows(db_path, "SELECT * FROM egress_log")] == [status]

    service.status = 201
    assert gate.send_queued(db_path, "rec_0a1b2c3d", client=service.client()) == receipt
    assert gate.receipt_for(db_path, "rec_0a1b2c3d") == receipt
    assert len(service.sends()) == 1


def test_other_destinations_are_not_sent_yet(db_path):
    alert = json.loads((SCHEMA_DIR / "examples" / "alert_event.valid.json").read_text())
    queue(db_path, alert, destination="alert", outbox_id=alert["alert_id"])
    service = FakeService()
    with pytest.raises(NotImplementedError):
        gate.send_queued(db_path, alert["alert_id"], client=service.client())
    assert service.requests == [] and rows(db_path, "SELECT status FROM outbox") == [{"status": "queued"}]


def test_unknown_outbox_ids(db_path):
    assert gate.receipt_for(db_path, "rec_ffffffff") is None
    with pytest.raises(KeyError):
        gate.send_queued(db_path, "rec_ffffffff", client=FakeService().client())


def test_logs_carry_no_payload_or_response_body(db_path, caplog):
    caplog.set_level(logging.DEBUG)
    queue(db_path, make_record(db_path))
    queue(db_path, make_record(db_path, record_id="rec_11111111"))
    gate.send_queued(db_path, "rec_0a1b2c3d", client=FakeService().client())
    gate.send_queued(db_path, "rec_11111111", client=FakeService(status=422).client())
    gate.refresh_config(db_path, WALTER, client=FakeService(get_status=403).client())
    assert "rec_0a1b2c3d" in caplog.text and "/v1/records" in caplog.text
    for secret in (BODY_MARKER, "SE_RASH", "moderate", "1_3_days") + LOCAL_ONLY:
        assert secret not in caplog.text


# ---------- configuration ----------

def test_refresh_config_upserts_survey_and_terms(db_path):
    service = FakeService()
    assert gate.refresh_config(db_path, WALTER, client=service.client()) == gate.ConfigRefresh("updated", "updated")
    assert [(m, p) for m, p, _ in service.requests] == [("GET", "/v1/survey"), ("GET", "/v1/terms")]
    [survey] = rows(db_path, "SELECT * FROM survey_cache")
    assert (survey["config_id"], survey["cohort_id"], survey["version"]) == ("cfg_cohort_b_v1", "cohort_B", 1)
    assert json.loads(survey["questions_json"]) == {"schedule": SURVEY["schedule"], "questions": SURVEY["questions"]}
    terms = {r["term_code"]: r for r in rows(db_path, "SELECT * FROM term_cache")}
    assert len(terms) == len(TERMS["terms"])  # follows schema/terms.json (12 in 2.0, 18 in 2.2)
    rash = next(t for t in TERMS["terms"] if t["term_code"] == "SE_RASH")
    assert terms["SE_RASH"] == {"term_code": "SE_RASH", "label_term": rash["label_term"],
                                "everyday_words": json.dumps(rash["everyday_words"]),
                                "severe_trigger": 0, "known_for_program": 1}
    assert terms["SE_DYSPNEA"]["severe_trigger"] == 1

    # a recorded symptom references term_cache; a second refresh updates in place and keeps it
    with closing(connect(db_path)) as conn, conn:
        conn.execute("INSERT INTO checkin_session (session_id, config_id, started_at, status) "
                     "VALUES ('ses_1', 'cfg_cohort_b_v1', ?, 'completed')", (utc_now(),))
        conn.execute("INSERT INTO symptom_event (event_id, session_id, term_code, severity, onset, known_side_effect, "
                     "possible_link_flag, created_at) VALUES ('sym_1', 'ses_1', 'SE_RASH', 'mild', 'today', 1, 0, ?)",
                     (utc_now(),))
    service.terms = {**TERMS, "terms": [{**t, "label_term": "Skin rash"} if t["term_code"] == "SE_RASH" else t
                                        for t in TERMS["terms"]]}
    assert gate.refresh_config(db_path, WALTER, client=service.client()) == gate.ConfigRefresh("updated", "updated")
    assert len(rows(db_path, "SELECT * FROM survey_cache")) == 1
    assert len(rows(db_path, "SELECT * FROM term_cache")) == len(TERMS["terms"])
    assert rows(db_path, "SELECT label_term FROM term_cache WHERE term_code = 'SE_RASH'") == [{"label_term": "Skin rash"}]
    assert len(rows(db_path, "SELECT * FROM symptom_event")) == 1


def test_refresh_config_offline_keeps_the_cache(db_path):
    service = FakeService()
    gate.refresh_config(db_path, WALTER, client=service.client())
    before = (rows(db_path, "SELECT * FROM survey_cache"), rows(db_path, "SELECT * FROM term_cache"))
    for broken in (FakeService(down=True), FakeService(get_status=503)):
        assert gate.refresh_config(db_path, WALTER, client=broken.client()) == gate.ConfigRefresh("offline", "offline")
    assert (rows(db_path, "SELECT * FROM survey_cache"), rows(db_path, "SELECT * FROM term_cache")) == before
    assert rows(db_path, "SELECT * FROM egress_log") == []  # configuration fetches carry no patient payload


def test_refresh_config_rejected(db_path):
    assert gate.refresh_config(db_path, WALTER, client=FakeService(get_status=403).client()) == gate.ConfigRefresh(
        "rejected", "rejected")
    assert rows(db_path, "SELECT * FROM survey_cache") == [] and rows(db_path, "SELECT * FROM term_cache") == []


def test_refresh_config_refuses_a_reply_that_breaks_the_contract(db_path):
    bad_survey = {**SURVEY, "questions": [{"question_id": "q1", "purpose": "wellbeing", "asks": ["only one"]}]}
    bad_terms = {**TERMS, "terms": [{**TERMS["terms"][0], "known_for_program": "yes"}] + TERMS["terms"][1:]}
    service = FakeService(survey=bad_survey, terms=bad_terms)
    assert gate.refresh_config(db_path, WALTER, client=service.client()) == gate.ConfigRefresh("rejected", "rejected")
    assert rows(db_path, "SELECT * FROM survey_cache") == [] and rows(db_path, "SELECT * FROM term_cache") == []

    other_cohort = FakeService(survey={**SURVEY, "cohort_id": "cohort_A"}, terms={**TERMS, "program_id": "prog_x"})
    assert gate.refresh_config(db_path, WALTER, client=other_cohort.client()) == gate.ConfigRefresh(
        "rejected", "rejected")


def test_refresh_config_without_a_profile(tmp_path):
    path = tmp_path / "patient.db"
    init_db(path, "pt_00000000")
    service = FakeService()
    assert gate.refresh_config(path, "pt_00000000", client=service.client()) == gate.ConfigRefresh(
        "no_profile", "no_profile")
    assert service.requests == []


# ---------- live: the local Sentinel service ----------

LIVE = "http://127.0.0.1:8000"


@pytest.fixture(scope="module")
def live():
    try:
        health = httpx.get(f"{LIVE}/healthz", timeout=2)
    except httpx.TransportError:
        pytest.skip("Sentinel service not running on 127.0.0.1:8000")
    if health.status_code != 200 or not health.json().get("seeded"):
        pytest.skip("Sentinel service is not seeded")
    return LIVE


@pytest.fixture()
def live_client(live, db_path):
    client = gate.make_client(Settings(db_path=db_path, patient_ref=WALTER, sentinel_base_url=live))
    yield client
    client.close()


def test_live_refresh_config_fills_the_caches(db_path, live_client):
    assert gate.refresh_config(db_path, WALTER, client=live_client) == gate.ConfigRefresh("updated", "updated")
    [survey] = rows(db_path, "SELECT * FROM survey_cache")
    assert (survey["config_id"], survey["cohort_id"]) == ("cfg_cohort_b_v1", "cohort_B")
    assert len(json.loads(survey["questions_json"])["questions"]) == 6
    assert len(rows(db_path, "SELECT * FROM term_cache")) == len(TERMS["terms"])  # service serves schema/terms.json
    assert rows(db_path, "SELECT known_for_program FROM term_cache WHERE term_code = 'SE_RASH'") == [
        {"known_for_program": 1}]


def test_live_send_walter_record(db_path, live, live_client):
    """Sends one real record for Walter for today (the service's history ends yesterday)."""
    record = make_record(db_path, record_id=gate.new_record_id(), now=None,
                         symptoms=[{**RASH, "severity": "mild", "onset": "today"}])
    queue(db_path, record)
    receipt = gate.send_queued(db_path, record["record_id"], client=live_client)
    assert (receipt.status, receipt.response_code) == ("sent", 201)
    assert receipt.url == f"{live}/v1/records" and receipt.payload_sha256 == payload_sha256(record)

    # the service's own hash for this record_id: same id + same payload -> 200 with its stored payload_sha256
    again = httpx.post(f"{live}/v1/records", content=canonical(record), timeout=5,
                       headers={"Content-Type": "application/json", "X-Role": "patient_device", "X-Actor-Id": WALTER})
    assert again.status_code == 200 and again.json()["payload_sha256"] == receipt.payload_sha256

    assert gate.send_queued(db_path, record["record_id"], client=live_client) == receipt  # not re-sent
    assert [r["response_code"] for r in rows(db_path, "SELECT * FROM egress_log")] == [201]
