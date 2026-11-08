"""Task A4 egress gate (PV-04, PV-05, PV-06, PV-08): build, outbox, send, receipt, egress_log and config refresh.

Offline tests drive the real SentinelClient against an in-memory stand-in for the service (httpx.MockTransport).
Live tests run against the local Sentinel service and skip when it is not reachable.
"""

import json
import logging
import threading
import time
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

    def __init__(self, *, status: int = 201, get_status: int = 200, down: bool = False, survey=None, terms=None,
                 failures: int = 0, delay: float = 0.0):
        self.status, self.get_status, self.down = status, get_status, down
        self.survey, self.terms = survey or SURVEY, terms or TERMS
        self.failures, self.delay = failures, delay  # the first `failures` POSTs get a 503
        self.requests: list[tuple[str, str, bytes]] = []
        self._lock = threading.Lock()

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("connection refused", request=request)
        with self._lock:
            self.requests.append((request.method, request.url.path, request.content))
            flaky = request.method == "POST" and self.failures > 0
            self.failures -= flaky
        if self.delay:
            time.sleep(self.delay)
        if flaky:
            return httpx.Response(503, json={"error": BODY_MARKER})
        path = request.url.path
        if path in ("/v1/records", "/v1/alerts"):
            if self.status >= 400:
                return httpx.Response(self.status, json={"error": BODY_MARKER})
            body = json.loads(request.content)
            if path == "/v1/alerts":  # the service answers alerts without a payload_sha256
                return httpx.Response(self.status, json={"alert_id": body["alert_id"], "routed_care_team": True,
                                                         "routed_caregiver": True})
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
    envelope = json.loads((SCHEMA_DIR / "examples" / "care_envelope.valid.json").read_text())
    queue(db_path, envelope, destination="care_envelope", outbox_id=envelope["envelope_id"])
    service = FakeService()
    with pytest.raises(NotImplementedError):
        gate.send_queued(db_path, envelope["envelope_id"], client=service.client())
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


# ---------- severe alerts (AL-02, SE-03) ----------

ALERT_FIELDS = set(json.loads((SCHEMA_DIR / "alert_event.json").read_text())["properties"])


def make_alert(alert_id="alt_0a1b2c3d", now=DEMO_DAY):
    return gate.build_alert(alert_id=alert_id, patient_ref=WALTER, now=now)


def queue_alert(db_path, alert):
    queue(db_path, alert, destination="alert", outbox_id=alert["alert_id"])


def test_alert_ids_and_url():
    ids = {gate.new_alert_id() for _ in range(20)}
    assert len(ids) == 20
    assert all(i.startswith("alt_") and len(i) == 12 and set(i[4:]) <= set("0123456789abcdef") for i in ids)
    assert gate.alerts_url("http://127.0.0.1:8000/") == "http://127.0.0.1:8000/v1/alerts"


def test_build_alert_has_exactly_the_schema_fields_and_no_symptom_details():
    alert = make_alert()
    assert set(alert) == ALERT_FIELDS
    assert alert == {"schema_version": "2.0", "alert_id": "alt_0a1b2c3d", "patient_ref": WALTER,
                     "alert_type": "severe", "created_at": "2026-11-07T15:00:00Z"}
    assert make_alert(now=datetime(2026, 11, 7, 10, 0, tzinfo=timezone(timedelta(hours=-5))))["created_at"] == \
        "2026-11-07T15:00:00Z"
    assert make_alert(now=datetime(2026, 11, 7, 15, 0))["created_at"] == "2026-11-07T15:00:00Z"  # naive is UTC
    assert make_alert(now=None)["created_at"].endswith("Z")
    for word in ("SE_", "severity", "term", "symptom", "words") + LOCAL_ONLY:
        assert word not in json.dumps(alert).replace('"severe"', "")


@pytest.mark.parametrize("kwargs", [{"alert_id": "rec_0a1b2c3d"}, {"alert_id": "alt_XYZ"},
                                    {"patient_ref": "Walter"}])
def test_build_alert_refuses_bad_ids(kwargs):
    args = {"alert_id": "alt_0a1b2c3d", "patient_ref": WALTER, **kwargs}
    with pytest.raises(ContractError) as exc:
        gate.build_alert(**args, now=DEMO_DAY)
    assert next(iter(kwargs.values())) not in str(exc.value)


def test_alert_is_queued_sent_logged_and_receipted(db_path):
    alert = make_alert()
    queue_alert(db_path, alert)
    [row] = rows(db_path, "SELECT * FROM outbox")
    assert (row["outbox_id"], row["destination"], row["status"]) == ("alt_0a1b2c3d", "alert", "queued")
    assert row["payload"] == canonical(alert).decode() and row["payload_sha256"] == payload_sha256(alert)

    service = FakeService()
    receipt = gate.send_queued(db_path, "alt_0a1b2c3d", client=service.client())
    assert (receipt.status, receipt.response_code, receipt.destination) == ("sent", 201, "alert")
    assert (receipt.method, receipt.url) == ("POST", f"{BASE}/v1/alerts")
    assert receipt.payload_sha256 == payload_sha256(alert)
    assert receipt.fields_sent == client_field_names(alert)
    assert service.sends() == [("POST", "/v1/alerts", canonical(alert))]
    [entry] = rows(db_path, "SELECT * FROM egress_log")
    assert (entry["outbox_id"], entry["url"], entry["response_code"]) == ("alt_0a1b2c3d", f"{BASE}/v1/alerts", 201)
    assert gate.receipt_for(db_path, "alt_0a1b2c3d") == receipt
    assert gate.send_queued(db_path, "alt_0a1b2c3d", client=service.client()) == receipt  # never twice
    assert len(service.sends()) == 1


def test_alert_retry_and_reject_semantics(db_path):
    queue_alert(db_path, make_alert())
    service = FakeService(down=True)
    assert gate.send_queued(db_path, "alt_0a1b2c3d", client=service.client()).status == "queued"
    service.down, service.failures = False, 1
    assert gate.send_queued(db_path, "alt_0a1b2c3d", client=service.client()).status == "queued"
    assert gate.send_queued(db_path, "alt_0a1b2c3d", client=service.client()).status == "sent"
    assert [r["response_code"] for r in rows(db_path, "SELECT * FROM egress_log ORDER BY log_id")] == [503, 201]

    queue_alert(db_path, make_alert("alt_11111111"))
    refused = gate.send_queued(db_path, "alt_11111111", client=FakeService(status=403).client())
    assert (refused.status, refused.response_code) == ("failed", 403)
    assert gate.send_queued(db_path, "alt_11111111", client=service.client()) == refused


def test_queue_alert_needs_the_alert_id_as_outbox_id(db_path):
    with pytest.raises(ValueError, match="alert_id"):
        queue(db_path, make_alert(), destination="alert", outbox_id="alt_ffffffff")
    with pytest.raises(ContractError):
        queue_alert(db_path, {**make_alert(), "alert_type": "missed"})  # devices send only severe (D-016)


# ---------- retry worker (PV-07) ----------

class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def worker_for(db_path, service, clock=None):
    return gate.RetryWorker(db_path, service.client, clock=clock or FakeClock())


def test_retry_backs_off_2_4_8_16_32_60_60_and_stops_after_201(db_path):
    queue(db_path, make_record(db_path))
    clock, service = FakeClock(), FakeService(failures=7)
    worker = worker_for(db_path, service, clock)
    assert worker.status("rec_0a1b2c3d") == {"attempts": 0, "next_attempt_in": 0.0}  # due at once
    delays = []
    for attempt in range(1, 8):
        [receipt] = worker.run_once()
        assert receipt.status == "queued"
        state = worker.status("rec_0a1b2c3d")
        assert state["attempts"] == attempt
        delays.append(state["next_attempt_in"])
        clock.now += state["next_attempt_in"] - 0.5
        assert worker.run_once() == []  # not due yet
        clock.now += 0.5
    assert delays == [2, 4, 8, 16, 32, 60, 60]

    [receipt] = worker.run_once()
    assert (receipt.status, receipt.response_code) == ("sent", 201)
    assert worker.status("rec_0a1b2c3d") is None
    clock.now += 1000
    assert worker.run_once() == [] and len(service.sends()) == 8
    assert [r["response_code"] for r in rows(db_path, "SELECT * FROM egress_log ORDER BY log_id")] == [503] * 7 + [201]


def test_retry_with_no_network_then_back_online(db_path):
    queue(db_path, make_record(db_path))
    clock, service = FakeClock(), FakeService(down=True)
    worker = worker_for(db_path, service, clock)
    assert [r.status for r in worker.run_once()] == ["queued"]
    assert rows(db_path, "SELECT * FROM egress_log") == []
    service.down = False
    clock.now += 2
    assert [r.status for r in worker.run_once()] == ["sent"]


def test_retry_never_touches_failed_or_sent_rows(db_path):
    queue(db_path, make_record(db_path))
    queue(db_path, make_record(db_path, record_id="rec_11111111"))
    gate.send_queued(db_path, "rec_0a1b2c3d", client=FakeService(status=422).client())   # refused
    gate.send_queued(db_path, "rec_11111111", client=FakeService().client())             # sent
    service = FakeService()
    worker = worker_for(db_path, service)
    assert worker.run_once() == [] and service.requests == []
    assert worker.status("rec_0a1b2c3d") is None and worker.status("rec_11111111") is None

    # refused by the service during a retry: failed, then never again
    queue(db_path, make_record(db_path, record_id="rec_22222222"))
    clock, refusing = FakeClock(), FakeService(status=409)
    worker = worker_for(db_path, refusing, clock)
    assert [r.status for r in worker.run_once()] == ["failed"]
    clock.now += 1000
    assert worker.run_once() == [] and len(refusing.sends()) == 1


def test_retry_sends_alerts_before_records(db_path):
    queue(db_path, make_record(db_path))
    queue(db_path, make_record(db_path, record_id="rec_11111111"))
    queue_alert(db_path, make_alert())
    service = FakeService()
    receipts = worker_for(db_path, service).run_once()
    assert [r.outbox_id for r in receipts] == ["alt_0a1b2c3d", "rec_0a1b2c3d", "rec_11111111"]
    assert [p for _, p, _ in service.sends()] == ["/v1/alerts", "/v1/records", "/v1/records"]
    assert all(r.status == "sent" for r in receipts)


def test_retry_skips_destinations_it_cannot_send(db_path):
    envelope = json.loads((SCHEMA_DIR / "examples" / "care_envelope.valid.json").read_text())
    queue(db_path, envelope, destination="care_envelope", outbox_id=envelope["envelope_id"])
    service = FakeService()
    worker = worker_for(db_path, service)
    assert worker.run_once() == [] and service.requests == []
    assert worker.status(envelope["envelope_id"]) is None


def test_concurrent_run_once_never_double_sends(db_path):
    for i in range(3):
        queue(db_path, make_record(db_path, record_id=f"rec_{i}{i}{i}{i}{i}{i}{i}{i}"))
    queue_alert(db_path, make_alert())
    service = FakeService(delay=0.05)
    worker = worker_for(db_path, service)
    other = worker_for(db_path, service)  # a second worker as well: the per-outbox lock still holds
    results, start = [], threading.Barrier(4)

    def run(w):
        start.wait()
        results.extend(w.run_once())

    threads = [threading.Thread(target=run, args=(w,)) for w in (worker, worker, other, other)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    paths = [p for _, p, _ in service.sends()]
    assert sorted(paths) == ["/v1/alerts"] + ["/v1/records"] * 3
    assert len(rows(db_path, "SELECT * FROM egress_log")) == 4
    assert rows(db_path, "SELECT DISTINCT status FROM outbox") == [{"status": "sent"}]


def test_retry_survives_a_client_factory_error_and_backs_off(db_path):
    queue(db_path, make_record(db_path))
    clock = FakeClock()

    def broken():
        raise RuntimeError("no client")

    worker = gate.RetryWorker(db_path, broken, clock=clock)
    with pytest.raises(RuntimeError):
        worker.run_once()
    assert worker.status("rec_0a1b2c3d") == {"attempts": 1, "next_attempt_in": 2}


def test_retry_logs_carry_no_payload(db_path, caplog):
    caplog.set_level(logging.DEBUG)
    queue(db_path, make_record(db_path))
    queue_alert(db_path, make_alert())
    worker_for(db_path, FakeService(failures=1)).run_once()
    assert "alt_0a1b2c3d" in caplog.text and "/v1/alerts" in caplog.text
    for secret in (BODY_MARKER, "SE_RASH", "moderate", "2026-11-07T15:00:00Z") + LOCAL_ONLY:
        assert secret not in caplog.text


def test_start_and_stop_the_retry_thread(db_path):
    service = FakeService(failures=1)
    worker = gate.RetryWorker(db_path, service.client, backoff=[0])
    worker.start(interval=0.01)
    try:
        queue(db_path, make_record(db_path))  # queued after start: picked up on the next tick
        deadline = time.monotonic() + 5
        while rows(db_path, "SELECT status FROM outbox") != [{"status": "sent"}] and time.monotonic() < deadline:
            time.sleep(0.01)
        assert rows(db_path, "SELECT status FROM outbox") == [{"status": "sent"}]
    finally:
        worker.stop()
    assert worker._thread is None
    assert not any(t.name == "egress-retry" and t.is_alive() for t in threading.enumerate())
    assert len(service.sends()) == 2


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


def test_live_send_walter_severe_alert(db_path, live, live_client):
    """Sends one real severe alert for Walter. The service answers alerts without a payload_sha256, so the
    receipt hash is checked against the contract's canonical hash and the service's idempotent replay (200)."""
    alert = gate.build_alert(alert_id=gate.new_alert_id(), patient_ref=WALTER)
    queue_alert(db_path, alert)
    receipt = gate.send_queued(db_path, alert["alert_id"], client=live_client)
    assert (receipt.status, receipt.response_code) == ("sent", 201)
    assert receipt.url == f"{live}/v1/alerts" and receipt.payload_sha256 == payload_sha256(alert)

    again = httpx.post(f"{live}/v1/alerts", content=canonical(alert), timeout=5,
                       headers={"Content-Type": "application/json", "X-Role": "patient_device", "X-Actor-Id": WALTER})
    assert again.status_code == 200 and again.json()["alert_id"] == alert["alert_id"]
    assert again.json().get("payload_sha256", receipt.payload_sha256) == receipt.payload_sha256

    assert gate.send_queued(db_path, alert["alert_id"], client=live_client) == receipt  # not re-sent
    assert [r["response_code"] for r in rows(db_path, "SELECT * FROM egress_log")] == [201]


def test_live_retry_worker_sends_a_queued_alert(db_path, live):
    alert = gate.build_alert(alert_id=gate.new_alert_id(), patient_ref=WALTER)
    queue_alert(db_path, alert)
    worker = gate.RetryWorker(db_path, lambda: gate.make_client(
        Settings(db_path=db_path, patient_ref=WALTER, sentinel_base_url=live)))
    [receipt] = worker.run_once()
    assert (receipt.status, receipt.response_code, receipt.outbox_id) == ("sent", 201, alert["alert_id"])
