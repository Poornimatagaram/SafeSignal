"""Task A4 egress gate (PV-04, PV-05, PV-06, PV-08): build, outbox, send, receipt, egress_log and config refresh.

Offline tests drive the real SentinelClient against an in-memory stand-in for the service (httpx.MockTransport).
Live tests run against the local Sentinel service and skip when it is not reachable.
"""

import base64
import json
import logging
import threading
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from nacl.exceptions import CryptoError
from nacl.public import PrivateKey, SealedBox

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
                 failures: int = 0, delay: float = 0.0, org_key: str | dict | None = None, key_status: int = 200):
        self.status, self.get_status, self.down = status, get_status, down
        self.survey, self.terms = survey or SURVEY, terms or TERMS
        self.failures, self.delay = failures, delay  # the first `failures` POSTs get a 503
        self.org_key, self.key_status = org_key, key_status  # GET /v1/orgs/{id}/public-key: 404 without a key
        self.consent_status = 200
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
        if path.endswith("/public-key"):
            org_id = path.split("/")[3]
            key = self.org_key.get(org_id) if isinstance(self.org_key, dict) else self.org_key
            if self.key_status != 200 or key is None:
                return httpx.Response(self.key_status if self.key_status != 200 else 404, json={"error": BODY_MARKER})
            return httpx.Response(200, json={"org_id": org_id, "public_key": key})
        if path.startswith("/v1/consent/"):
            if self.consent_status != 200:
                return httpx.Response(self.consent_status, json={"error": BODY_MARKER})
            return httpx.Response(200, json={"patient_ref": path.rsplit("/", 1)[1]})  # no payload_sha256 echoed
        if path == "/v1/care-envelopes":
            if self.status >= 400:
                return httpx.Response(self.status, json={"error": BODY_MARKER})
            body = json.loads(request.content)
            return httpx.Response(self.status, json={"envelope_id": body["envelope_id"],
                                                     "payload_sha256": body["payload_sha256"]})
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
        return [r for r in self.requests if r[0] in ("POST", "PUT")]


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


def test_every_outbox_destination_has_a_sender():
    assert set(gate.SENDERS) == set(gate.PAYLOAD_KINDS)
    assert gate.SENDERS["care_envelope"] == "send_envelope" and gate.SENDERS["consent"] == "send_consent"


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


def test_retry_sends_a_queued_envelope_unchanged(db_path):
    envelope = json.loads((SCHEMA_DIR / "examples" / "care_envelope.valid.json").read_text())
    queue(db_path, envelope, destination="care_envelope", outbox_id=envelope["envelope_id"])
    service = FakeService()
    worker = worker_for(db_path, service)
    assert worker.status(envelope["envelope_id"]) == {"attempts": 0, "next_attempt_in": 0.0}
    [receipt] = worker.run_once()
    assert (receipt.status, receipt.payload_sha256) == ("sent", envelope["payload_sha256"])
    assert service.sends() == [("POST", "/v1/care-envelopes", canonical(envelope))]


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


# ---------- hash vectors (26.13) ----------

HASH_VECTORS = json.loads((SCHEMA_DIR / "examples" / "hash_vectors.json").read_text())["vectors"]


@pytest.mark.parametrize("vector", HASH_VECTORS, ids=[v["name"] for v in HASH_VECTORS])
def test_hash_vectors(vector):
    assert canonical(vector["input"]) == vector["canonical"].encode("utf-8")
    assert payload_sha256(vector["input"]) == vector["sha256"]


# ---------- care envelopes (NF-05; task A7) ----------

NORTHGATE, LAKESIDE = "org_5e1a2b3c", "org_8f4d6a2e"  # Walter's care team and consented emergency hospital
ORG_SK = PrivateKey.generate()  # test-only care-team key pair
ORG_PK = base64.b64encode(bytes(ORG_SK.public_key)).decode()
ER_SK = PrivateKey.generate()   # test-only emergency hospital key pair
ER_PK = base64.b64encode(bytes(ER_SK.public_key)).decode()
BOTH_KEYS = {NORTHGATE: ORG_PK, LAKESIDE: ER_PK}


def seed_session(db_path, session_id="ses_00000007", day=7, symptoms=(RASH,), *, care_team=True,
                 record_status="queued", started_at=None):
    """An approved session as checkin.approve leaves it: session ended, symptom_event rows, company record queued."""
    started = started_at or f"2026-11-{day:02d}T15:00:00Z"
    with closing(connect(db_path)) as conn, conn:
        conn.execute("INSERT OR IGNORE INTO survey_cache VALUES ('cfg_cohort_b_v1', 'cohort_B', 1, '{}', ?)",
                     (utc_now(),))
        conn.execute("INSERT OR IGNORE INTO term_cache VALUES ('SE_RASH', 'Rash', '[]', 0, 1)")
        conn.execute("INSERT INTO checkin_session (session_id, config_id, started_at, ended_at, status) "
                     "VALUES (?, 'cfg_cohort_b_v1', ?, ?, 'completed')", (session_id, started, started))
        for i, s in enumerate(symptoms):
            conn.execute("INSERT INTO symptom_event (event_id, session_id, term_code, severity, onset, "
                         "known_side_effect, possible_link_flag, patient_words, created_at) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?, 'Walter says it itches', ?)",
                         (f"sym_{session_id[4:]}{i}", session_id, s["term_code"], s["severity"], s["onset"],
                          s["known_side_effect"], s["possible_link_flag"], started))
        record = make_record(db_path, record_id="rec_" + session_id[4:], symptoms=symptoms,
                             consent={"share_care_team": int(care_team), "share_caregiver": 1})
        gate.queue_payload(conn, outbox_id=record["record_id"], session_id=session_id,
                           destination="company_record", payload=record)
        if record_status != "queued":
            conn.execute("UPDATE outbox SET status = ? WHERE outbox_id = ?", (record_status, record["record_id"]))
    return session_id


def set_consent(db_path, *, care_team=1, emergency=1, caregiver=1, at=None):
    with closing(connect(db_path)) as conn, conn:
        conn.execute("INSERT INTO consent (share_care_team, emergency_consent, share_caregiver, caregiver_detail, "
                     "updated_at) VALUES (?, ?, ?, 'alerts_only', ?)", (care_team, emergency, caregiver,
                                                                       at or utc_now()))


def plaintext_for(db_path, session_id):
    from sentinel_patient import care_payload
    with closing(connect(db_path)) as conn:
        return care_payload.doctor_payload_for_session(conn, session_id, WALTER)


def recipients(db_path, session_id):
    with closing(connect(db_path)) as conn:
        return gate.care_recipients(conn, session_id, WALTER)


def envelope_rows(db_path):
    return {json.loads(r["payload"])["org_id"]: r
            for r in rows(db_path, "SELECT * FROM outbox WHERE destination = 'care_envelope'")}


def T(org_id, link, envelope_id=None, waiting=None):
    return gate.EnvelopeTarget(org_id, link, envelope_id, waiting)


def test_envelope_and_consent_ids_and_urls():
    for make, prefix in ((gate.new_envelope_id, "env_"), (gate.new_consent_id, "con_")):
        ids = {make() for _ in range(20)}
        assert len(ids) == 20
        assert all(i.startswith(prefix) and len(i) == 12 and set(i[4:]) <= set("0123456789abcdef") for i in ids)
    assert gate.envelopes_url("http://127.0.0.1:8000/") == "http://127.0.0.1:8000/v1/care-envelopes"
    assert gate.consent_url("http://127.0.0.1:8000/", WALTER) == f"http://127.0.0.1:8000/v1/consent/{WALTER}"
    target = T(NORTHGATE, "care_team", "env_0a1b2c3d")
    assert target.to_dict() == {"org_id": NORTHGATE, "link_type": "care_team", "envelope_id": "env_0a1b2c3d",
                                "waiting": None}


def test_fetch_org_key_stores_the_key_and_maps_errors(db_path, caplog):
    caplog.set_level(logging.DEBUG)
    assert gate.fetch_org_key(db_path, NORTHGATE, client=FakeService(org_key=ORG_PK).client()) == ORG_PK
    assert rows(db_path, "SELECT care_org_public_key FROM patient_profile") == [{"care_org_public_key": ORG_PK}]
    assert rows(db_path, "SELECT public_key FROM emergency_org") == [{"public_key": None}]
    gate.fetch_org_key(db_path, LAKESIDE, client=FakeService(org_key=ER_PK).client())  # an emergency org
    assert rows(db_path, "SELECT care_org_public_key FROM patient_profile") == [{"care_org_public_key": ORG_PK}]
    assert rows(db_path, "SELECT org_id, public_key FROM emergency_org") == [{"org_id": LAKESIDE,
                                                                              "public_key": ER_PK}]

    for service, reason in ((FakeService(), "no_key"), (FakeService(org_key=ORG_PK, key_status=403), "refused"),
                            (FakeService(org_key=ORG_PK, key_status=503), "offline"),
                            (FakeService(org_key=ORG_PK, down=True), "offline"),
                            (FakeService(org_key=base64.b64encode(b"short").decode()), "refused"),
                            (FakeService(org_key="not base64 !!"), "refused")):
        with pytest.raises(gate.KeyUnavailable) as exc:
            gate.fetch_org_key(db_path, NORTHGATE, client=service.client())
        assert exc.value.reason == reason
    assert f"/v1/orgs/{NORTHGATE}/public-key" in caplog.text and "404" in caplog.text
    assert BODY_MARKER not in caplog.text and ORG_PK not in caplog.text
    assert rows(db_path, "SELECT * FROM egress_log") == []  # a key fetch carries no patient payload


def test_one_envelope_per_organization_round_trip(db_path, caplog):
    caplog.set_level(logging.DEBUG)
    session_id = seed_session(db_path)
    assert recipients(db_path, session_id) == [(NORTHGATE, "care_team"), (LAKESIDE, "emergency")]
    service = FakeService(org_key=BOTH_KEYS)
    targets = gate.queue_care_envelopes(db_path, session_id, WALTER, client=service.client())
    assert [(t.org_id, t.link_type, t.waiting) for t in targets] == [(NORTHGATE, "care_team", None),
                                                                     (LAKESIDE, "emergency", None)]
    ids = [t.envelope_id for t in targets]
    assert all(i.startswith("env_") for i in ids) and ids[0] != ids[1]
    plaintext = plaintext_for(db_path, session_id)
    digest = payload_sha256(plaintext)

    stored = envelope_rows(db_path)
    assert set(stored) == {NORTHGATE, LAKESIDE}
    for target, sk, other in ((targets[0], ORG_SK, ER_SK), (targets[1], ER_SK, ORG_SK)):
        row = stored[target.org_id]
        assert (row["outbox_id"], row["session_id"], row["status"]) == (target.envelope_id, session_id, "queued")
        assert row["payload_sha256"] == digest  # the plaintext hash, never a hash of the sealed JSON
        envelope = json.loads(row["payload"])
        assert (envelope["envelope_id"], envelope["org_id"], envelope["patient_ref"]) == (
            target.envelope_id, target.org_id, WALTER)
        for secret in ("Tagrisso", "SE_RASH", "itches", "display_name") + LOCAL_ONLY:  # sealed: no plaintext
            assert secret not in row["payload"]

        receipt = gate.send_queued(db_path, target.envelope_id, client=service.client())
        assert (receipt.status, receipt.response_code, receipt.destination) == ("sent", 201, "care_envelope")
        assert (receipt.method, receipt.url) == ("POST", f"{BASE}/v1/care-envelopes")
        assert receipt.payload_sha256 == digest and receipt.fields_sent == client_field_names(envelope)
        [body] = [b for _, p, b in service.sends() if p == "/v1/care-envelopes" and
                  json.loads(b)["envelope_id"] == target.envelope_id]
        assert body == row["payload"].encode()  # the stored envelope, unchanged
        sealed = base64.b64decode(envelope["ciphertext"])
        opened = SealedBox(sk).decrypt(sealed)
        assert opened == canonical(plaintext) and json.loads(opened)["display_name"] == "Walter"
        with pytest.raises(CryptoError):  # only that organization's key opens it
            SealedBox(other).decrypt(sealed)
        [entry] = rows(db_path, "SELECT * FROM egress_log WHERE outbox_id = ?", target.envelope_id)
        assert (entry["payload_sha256"], entry["response_code"]) == (digest, 201)
        assert gate.receipt_for(db_path, target.envelope_id) == receipt

    # once queued, each organization keeps its one envelope: no second key fetch, no second seal
    fetches = len(service.requests)
    assert gate.queue_care_envelopes(db_path, session_id, WALTER, client=service.client()) == targets
    assert len(service.requests) == fetches and gate.pending_care_envelopes(db_path) == []
    for secret in ("Walter", "Tagrisso", "SE_RASH", BODY_MARKER, json.loads(stored[NORTHGATE]["payload"])[
            "ciphertext"][:24]):
        assert secret not in caplog.text


def test_envelope_is_resent_unchanged_after_offline_and_a_server_error(db_path):
    session_id = seed_session(db_path)
    service = FakeService(org_key=BOTH_KEYS)
    envelope_id = gate.queue_care_envelopes(db_path, session_id, WALTER, client=service.client())[0].envelope_id
    stored = rows(db_path, "SELECT payload, payload_sha256 FROM outbox WHERE outbox_id = ?", envelope_id)[0]
    service.down = True
    queued = gate.send_queued(db_path, envelope_id, client=service.client())
    assert (queued.status, queued.payload_sha256) == ("queued", stored["payload_sha256"])
    assert gate.receipt_for(db_path, envelope_id, base_url=BASE) == queued
    service.down, service.failures = False, 1
    assert gate.send_queued(db_path, envelope_id, client=service.client()).status == "queued"
    assert gate.send_queued(db_path, envelope_id, client=service.client()).status == "sent"
    bodies = [b for _, p, b in service.sends() if p == "/v1/care-envelopes"]
    assert bodies == [stored["payload"].encode()] * 2  # the 503 attempt and the 201 one: same bytes
    assert [r["response_code"] for r in rows(db_path, "SELECT * FROM egress_log ORDER BY log_id")] == [503, 201]
    assert rows(db_path, "SELECT payload FROM outbox WHERE outbox_id = ?", envelope_id)[0] == {
        "payload": stored["payload"]}


def test_envelope_queue_is_idempotent_and_the_integrity_check_holds(db_path):
    envelope = json.loads((SCHEMA_DIR / "examples" / "care_envelope.valid.json").read_text())
    queue(db_path, envelope, destination="care_envelope", outbox_id=envelope["envelope_id"])
    queue(db_path, envelope, destination="care_envelope", outbox_id=envelope["envelope_id"])  # no-op
    with pytest.raises(ValueError, match="different payload"):  # same plaintext hash, new ciphertext
        queue(db_path, {**envelope, "ciphertext": "V" + envelope["ciphertext"][1:]}, destination="care_envelope",
              outbox_id=envelope["envelope_id"])
    assert rows(db_path, "SELECT payload_sha256 FROM outbox") == [{"payload_sha256": envelope["payload_sha256"]}]

    with closing(connect(db_path)) as conn, conn:  # someone edits the stored hash: never sent
        conn.execute("UPDATE outbox SET payload_sha256 = ?", ("0" * 64,))
    service = FakeService()
    with pytest.raises(RuntimeError, match="hash"):
        gate.send_queued(db_path, envelope["envelope_id"], client=service.client())
    with closing(connect(db_path)) as conn, conn:  # or re-writes the stored text
        conn.execute("UPDATE outbox SET payload_sha256 = ?, payload = ?",
                     (envelope["payload_sha256"], json.dumps(envelope, indent=1)))
    with pytest.raises(RuntimeError, match="hash"):
        gate.send_queued(db_path, envelope["envelope_id"], client=service.client())
    assert service.requests == []


def test_no_key_queues_nothing_and_the_worker_sends_once_a_key_exists(db_path):
    session_id = seed_session(db_path)
    service = FakeService()  # neither admin has registered a key yet: 404
    assert gate.queue_care_envelopes(db_path, session_id, WALTER, client=service.client()) == [
        T(NORTHGATE, "care_team", waiting="no_key"), T(LAKESIDE, "emergency", waiting="no_key")]
    assert envelope_rows(db_path) == {}
    assert gate.pending_care_envelopes(db_path) == [(session_id, NORTHGATE), (session_id, LAKESIDE)]
    assert gate.pending_care_sessions(db_path) == [session_id]

    clock = FakeClock()
    worker = gate.RetryWorker(db_path, service.client, clock=clock, patient_ref=WALTER)
    receipts = worker.run_once()  # sends the queued record; the envelopes wait for keys
    assert [r.destination for r in receipts] == ["company_record"]
    assert worker._state[f"care:{session_id}:{NORTHGATE}"][0] == 1
    assert worker._state[f"care:{session_id}:{LAKESIDE}"][0] == 1
    service.org_key = {NORTHGATE: ORG_PK}  # Northgate registers; Lakeside still has none
    clock.now += 1
    assert worker.run_once() == []  # not due yet (2 s)
    clock.now += 1
    [receipt] = worker.run_once()
    assert (receipt.destination, receipt.status, receipt.response_code) == ("care_envelope", "sent", 201)
    assert receipt.payload_sha256 == payload_sha256(plaintext_for(db_path, session_id))
    assert gate.pending_care_envelopes(db_path) == [(session_id, LAKESIDE)]
    assert f"care:{session_id}:{NORTHGATE}" not in worker._state
    assert worker._state[f"care:{session_id}:{LAKESIDE}"][0] == 2  # backs off on its own: 4 s now
    service.org_key = BOTH_KEYS
    clock.now += 3
    assert worker.run_once() == []
    clock.now += 1
    [receipt] = worker.run_once()
    assert (receipt.destination, receipt.status) == ("care_envelope", "sent")
    assert gate.pending_care_envelopes(db_path) == [] and gate.pending_care_sessions(db_path) == []
    clock.now += 1000
    assert worker.run_once() == []
    sent = [json.loads(b)["org_id"] for _, p, b in service.sends() if p == "/v1/care-envelopes"]
    assert sent == [NORTHGATE, LAKESIDE]


def test_an_emergency_org_without_a_key_never_blocks_the_care_team(db_path):
    session_id = seed_session(db_path)
    service = FakeService(org_key={NORTHGATE: ORG_PK})
    targets = gate.queue_care_envelopes(db_path, session_id, WALTER, client=service.client())
    assert targets[1] == T(LAKESIDE, "emergency", waiting="no_key")
    assert targets[0].org_id == NORTHGATE and targets[0].envelope_id and targets[0].waiting is None
    assert gate.send_queued(db_path, targets[0].envelope_id, client=service.client()).status == "sent"
    # the next attempt seals Lakeside only, with the same plaintext hash and its own envelope_id
    service.org_key = BOTH_KEYS
    again = gate.queue_care_envelopes(db_path, session_id, WALTER, client=service.client())
    assert again[0] == targets[0] and again[1].envelope_id not in (None, targets[0].envelope_id)
    stored = envelope_rows(db_path)
    assert stored[NORTHGATE]["payload_sha256"] == stored[LAKESIDE]["payload_sha256"]


@pytest.mark.parametrize("error, waiting", [(gate.KeyUnavailable("offline", LAKESIDE), "offline"),
                                            (ValueError("bad"), "refused")])
def test_per_org_errors_do_not_raise(db_path, monkeypatch, error, waiting):
    session_id = seed_session(db_path)
    real = gate.fetch_org_key

    def fetch(db, org_id, *, client):
        if org_id == LAKESIDE:
            raise error
        return real(db, org_id, client=client)

    monkeypatch.setattr(gate, "fetch_org_key", fetch)
    targets = gate.queue_care_envelopes(db_path, session_id, WALTER,
                                        client=FakeService(org_key=BOTH_KEYS).client())
    assert targets[0].envelope_id and targets[1] == T(LAKESIDE, "emergency", waiting=waiting)


def test_a_payload_that_cannot_be_built_waits_as_refused(db_path):
    session_id = seed_session(db_path)
    with closing(connect(db_path)) as conn, conn:
        conn.execute("UPDATE patient_profile SET date_of_birth = NULL")
    service = FakeService(org_key=BOTH_KEYS)
    assert gate.queue_care_envelopes(db_path, session_id, WALTER, client=service.client()) == [
        T(NORTHGATE, "care_team", waiting="refused"), T(LAKESIDE, "emergency", waiting="refused")]
    assert service.requests == []


def test_worker_reads_the_patient_ref_from_the_profile(db_path):
    session_id = seed_session(db_path, record_status="sent")
    service = FakeService(org_key=BOTH_KEYS)
    receipts = gate.RetryWorker(db_path, service.client, clock=FakeClock()).run_once()
    assert [(r.destination, r.status) for r in receipts] == [("care_envelope", "sent")] * 2
    assert {r["session_id"] for r in envelope_rows(db_path).values()} == {session_id}


def test_consent_off_means_no_envelope_and_nothing_pending(db_path):
    session_id = seed_session(db_path)
    set_consent(db_path, care_team=0, emergency=0)  # CN-03: turning it off stops future sharing
    service = FakeService(org_key=BOTH_KEYS)
    assert gate.pending_care_envelopes(db_path) == [] and recipients(db_path, session_id) == []
    assert gate.queue_care_envelopes(db_path, session_id, WALTER, client=service.client()) == []
    worker = gate.RetryWorker(db_path, service.client, clock=FakeClock(), patient_ref=WALTER)
    assert [r.destination for r in worker.run_once()] == ["company_record"]
    assert [p for _, p, _ in service.requests] == ["/v1/records"]  # never a key fetch or envelope
    assert envelope_rows(db_path) == {}

    set_consent(db_path, care_team=1, emergency=1)  # back on: approved while sharing, so it may go now
    assert gate.pending_care_envelopes(db_path) == [(session_id, NORTHGATE), (session_id, LAKESIDE)]


def test_emergency_consent_off_means_no_emergency_envelope(db_path):
    session_id = seed_session(db_path)
    set_consent(db_path, care_team=1, emergency=0)
    assert recipients(db_path, session_id) == [(NORTHGATE, "care_team")]
    service = FakeService(org_key=BOTH_KEYS)
    [target] = gate.queue_care_envelopes(db_path, session_id, WALTER, client=service.client())
    assert target.org_id == NORTHGATE and target.envelope_id
    assert set(envelope_rows(db_path)) == {NORTHGATE}
    assert all(LAKESIDE not in p for _, p, _ in service.requests)  # its key is not even fetched


def test_emergency_consent_turned_on_later_does_not_seal_earlier_checkins(db_path):
    with closing(connect(db_path)) as conn, conn:
        conn.execute("UPDATE consent SET updated_at = '2026-11-01T00:00:00Z'")  # seeded: emergency on
    set_consent(db_path, emergency=0, at="2026-11-06T00:00:00Z")
    before = seed_session(db_path, "ses_00000007", day=7)               # approved with emergency consent off
    set_consent(db_path, emergency=1, at="2026-11-08T00:00:00Z")
    after = seed_session(db_path, "ses_00000009", day=9)                # approved with it on
    assert recipients(db_path, before) == [(NORTHGATE, "care_team")]
    assert recipients(db_path, after) == [(NORTHGATE, "care_team"), (LAKESIDE, "emergency")]
    assert gate.pending_care_envelopes(db_path) == [(before, NORTHGATE), (after, NORTHGATE), (after, LAKESIDE)]

    set_consent(db_path, emergency=0)  # off again now: no emergency envelope for anyone
    assert recipients(db_path, after) == [(NORTHGATE, "care_team")]


def test_the_care_org_is_never_also_an_emergency_recipient(db_path):
    session_id = seed_session(db_path)
    with closing(connect(db_path)) as conn, conn:
        conn.execute("INSERT INTO emergency_org (org_id) VALUES (?)", (NORTHGATE,))
    assert recipients(db_path, session_id) == [(NORTHGATE, "care_team"), (LAKESIDE, "emergency")]


@pytest.mark.parametrize("kwargs", [{"care_team": False}, {"record_status": "failed"}])
def test_care_team_needs_a_record_approved_while_sharing(db_path, kwargs):
    session_id = seed_session(db_path, **kwargs)
    expected = [] if kwargs.get("record_status") == "failed" else [(LAKESIDE, "emergency")]
    assert recipients(db_path, session_id) == expected
    service = FakeService(org_key=BOTH_KEYS)
    targets = gate.queue_care_envelopes(db_path, session_id, WALTER, client=service.client())
    assert [t.org_id for t in targets] == [org for org, _ in expected]
    assert NORTHGATE not in envelope_rows(db_path)


def test_no_envelope_without_a_care_org_or_before_approval(db_path):
    with closing(connect(db_path)) as conn, conn:
        conn.execute("INSERT INTO survey_cache VALUES ('cfg_cohort_b_v1', 'cohort_B', 1, '{}', ?)", (utc_now(),))
        conn.execute("INSERT INTO checkin_session (session_id, config_id, started_at, status) "
                     "VALUES ('ses_0000000a', 'cfg_cohort_b_v1', ?, 'partial')", (utc_now(),))
    service = FakeService(org_key=BOTH_KEYS)
    assert recipients(db_path, "ses_0000000a") == [] and recipients(db_path, "ses_missing") == []
    assert gate.queue_care_envelopes(db_path, "ses_0000000a", WALTER, client=service.client()) == []
    session_id = seed_session(db_path)
    with closing(connect(db_path)) as conn, conn:
        conn.execute("UPDATE patient_profile SET care_org_id = NULL")
    assert gate.pending_care_envelopes(db_path) == [(session_id, LAKESIDE)]
    assert [t.org_id for t in gate.queue_care_envelopes(db_path, session_id, WALTER, client=service.client())] == [
        LAKESIDE]


def test_an_already_sealed_org_is_still_reported_after_consent_is_withdrawn(db_path):
    session_id = seed_session(db_path)
    service = FakeService(org_key=BOTH_KEYS)
    targets = gate.queue_care_envelopes(db_path, session_id, WALTER, client=service.client())
    set_consent(db_path, care_team=0, emergency=0)
    assert gate.queue_care_envelopes(db_path, session_id, WALTER, client=service.client()) == targets
    assert gate.pending_care_envelopes(db_path) == []


# ---------- consent updates (CN-01) ----------

CONSENT_LABELS = ("Emergency services", "Lakeside Emergency Hospital", "display_label")


def test_consent_update_from_the_seeded_state_matches_the_example(db_path):
    with closing(connect(db_path)) as conn:
        update = gate.build_consent_update(conn, WALTER)
    assert update == json.loads((SCHEMA_DIR / "examples" / "consent_update.valid.json").read_text())
    for value in CONSENT_LABELS + LOCAL_ONLY:
        assert value not in json.dumps(update)


def test_consent_update_without_emergency_consent_has_empty_lists(db_path):
    set_consent(db_path, care_team=0, emergency=0, caregiver=0)
    with closing(connect(db_path)) as conn:
        update = gate.build_consent_update(conn, WALTER)
    assert (update["share_care_team"], update["share_caregiver"], update["emergency_consent"]) == (False, False, False)
    assert update["emergency_org_ids"] == [] and update["emergency_contacts"] == []
    assert "911" not in json.dumps(update) and "+1617" not in json.dumps(update)
    with closing(connect(db_path)) as conn, pytest.raises(LookupError):
        gate.build_consent_update(conn, "pt_00000000")


def test_queue_consent_update_supersedes_older_queued_ones_and_sends_with_put(db_path):
    with closing(connect(db_path)) as conn:  # the caller owns the transaction
        gate.queue_consent_update(conn, WALTER)
        conn.rollback()
    assert rows(db_path, "SELECT * FROM outbox") == []
    assert gate.latest_consent_receipt(db_path) is None

    with closing(connect(db_path)) as conn, conn:
        first = gate.queue_consent_update(conn, WALTER)
    with closing(connect(db_path)) as conn, conn:
        conn.execute("INSERT INTO consent (share_care_team, emergency_consent, share_caregiver, caregiver_detail, "
                     "updated_at) VALUES (0, 0, 1, 'summary', ?)", (utc_now(),))
        second = gate.queue_consent_update(conn, WALTER)
    assert first.startswith("con_") and second.startswith("con_") and first != second
    statuses = {r["outbox_id"]: (r["status"], r["session_id"], r["destination"])
                for r in rows(db_path, "SELECT * FROM outbox")}
    assert statuses == {first: ("failed", None, "consent"), second: ("queued", None, "consent")}
    assert rows(db_path, "SELECT * FROM egress_log") == []  # superseded, never sent

    service = FakeService()
    receipt = gate.send_queued(db_path, second, client=service.client())
    assert (receipt.status, receipt.response_code, receipt.method) == ("sent", 200, "PUT")
    assert receipt.url == gate.consent_url(BASE, WALTER)
    [(method, path, body)] = service.sends()
    assert (method, path) == ("PUT", f"/v1/consent/{WALTER}")
    sent = json.loads(body)
    assert (sent["share_care_team"], sent["caregiver_detail"], sent["emergency_contacts"]) == (False, "summary", [])
    assert receipt.payload_sha256 == payload_sha256(sent)
    assert gate.latest_consent_receipt(db_path) == receipt
    assert gate.send_queued(db_path, first, client=service.client()).status == "failed"  # never sent
    assert len(service.sends()) == 1


def test_worker_sends_consent_then_alert_then_record_then_envelope(db_path):
    envelope = json.loads((SCHEMA_DIR / "examples" / "care_envelope.valid.json").read_text())
    queue(db_path, envelope, destination="care_envelope", outbox_id=envelope["envelope_id"])
    queue(db_path, make_record(db_path))
    queue_alert(db_path, make_alert())
    with closing(connect(db_path)) as conn, conn:
        consent_id = gate.queue_consent_update(conn, WALTER)
    service = FakeService()
    worker = worker_for(db_path, service)
    assert all(worker.status(i)["attempts"] == 0
               for i in (consent_id, "alt_0a1b2c3d", "rec_0a1b2c3d", envelope["envelope_id"]))
    receipts = worker.run_once()
    assert [r.outbox_id for r in receipts] == [consent_id, "alt_0a1b2c3d", "rec_0a1b2c3d", envelope["envelope_id"]]
    assert [p for _, p, _ in service.sends()] == [f"/v1/consent/{WALTER}", "/v1/alerts", "/v1/records",
                                                  "/v1/care-envelopes"]
    assert all(r.status == "sent" for r in receipts)


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


PATEL, OKAFOR = "dr_b29c4e71", "dr_d4a8e2b6"  # Northgate and Lakeside admins (schema/demo_fixtures.json)


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


class LiveDoctor:
    """What doctor-web does in the browser (as scripts/e2e_check.py): personal key, org key, self key grant."""

    def __init__(self, base: str, doctor_id: str):
        self.id, self.personal = doctor_id, PrivateKey.generate()
        self.http = httpx.Client(base_url=base, timeout=10, headers={"X-Role": "doctor", "X-Actor-Id": doctor_id})

    def register_org_key(self, org_id: str) -> None:
        assert self.http.put(f"/v1/doctors/{self.id}/public-key",
                             json={"public_key": b64(bytes(self.personal.public_key))}).status_code == 200
        org = PrivateKey.generate()
        assert self.http.put(f"/v1/orgs/{org_id}/public-key",
                             json={"public_key": b64(bytes(org.public_key))}).status_code == 200
        wrapped = SealedBox(self.personal.public_key).encrypt(bytes(org))
        assert self.http.post(f"/v1/orgs/{org_id}/key-grants",
                              json={"doctor_id": self.id, "wrapped_key": b64(wrapped)}).status_code == 201

    def org_key(self, org_id: str) -> PrivateKey:
        r = self.http.get(f"/v1/orgs/{org_id}/key-grants/{self.id}")
        assert r.status_code == 200
        return PrivateKey(SealedBox(self.personal).decrypt(base64.b64decode(r.json()["wrapped_key"])))


@pytest.fixture(scope="module")
def live_doctors(live):
    """Registers throwaway Northgate (Dr. Patel) and Lakeside (Dr. Okafor) keys with self grants.
    This replaces both organizations' keys in the local dev service (synthetic data, reseeded before the demo)."""
    patel, okafor = LiveDoctor(live, PATEL), LiveDoctor(live, OKAFOR)
    patel.register_org_key(NORTHGATE)
    okafor.register_org_key(LAKESIDE)
    yield patel, okafor
    patel.http.close()
    okafor.http.close()


def test_live_envelopes_reach_northgate_and_lakeside_and_decrypt(db_path, live, live_client, live_doctors):
    patel, okafor = live_doctors
    session_id = seed_session(db_path, started_at=utc_now())
    targets = gate.queue_care_envelopes(db_path, session_id, WALTER, client=live_client)
    assert [(t.org_id, t.link_type, t.waiting) for t in targets] == [(NORTHGATE, "care_team", None),
                                                                     (LAKESIDE, "emergency", None)]
    plaintext = plaintext_for(db_path, session_id)
    digest = payload_sha256(plaintext)
    receipts = {t.org_id: gate.send_queued(db_path, t.envelope_id, client=live_client) for t in targets}
    for org_id, receipt in receipts.items():
        assert (receipt.status, receipt.response_code) == ("sent", 201)
        assert receipt.url == f"{live}/v1/care-envelopes" and receipt.payload_sha256 == digest

    # the service's own hash: the stored envelope again -> 200 with its payload_sha256
    stored = envelope_rows(db_path)[NORTHGATE]["payload"]
    again = httpx.post(f"{live}/v1/care-envelopes", content=stored.encode(), timeout=5,
                       headers={"Content-Type": "application/json", "X-Role": "patient_device", "X-Actor-Id": WALTER})
    assert again.status_code == 200 and again.json()["payload_sha256"] == digest

    # Northgate: the routine inbox, opened with the org key unwrapped from Dr. Patel's grant
    inbox = patel.http.get(f"/v1/orgs/{NORTHGATE}/envelopes").json()
    mine = next(e for e in inbox if e["envelope_id"] == targets[0].envelope_id)
    opened = json.loads(SealedBox(patel.org_key(NORTHGATE)).decrypt(base64.b64decode(mine["ciphertext"])))
    assert opened == plaintext and payload_sha256(opened) == mine["payload_sha256"] == digest
    assert all(e["envelope_id"] != targets[1].envelope_id for e in inbox)

    # Lakeside: not in its routine inbox; only through audited emergency access
    routine = okafor.http.get(f"/v1/orgs/{LAKESIDE}/envelopes").json()
    assert all(e["envelope_id"] != targets[1].envelope_id for e in routine)
    r = okafor.http.post(f"/v1/orgs/{LAKESIDE}/emergency-access",
                         json={"patient_ref": WALTER, "reason": "emergency_admission"})
    assert r.status_code == 200
    em = next(e for e in r.json()["envelopes"] if e["envelope_id"] == targets[1].envelope_id)
    opened = json.loads(SealedBox(okafor.org_key(LAKESIDE)).decrypt(base64.b64decode(em["ciphertext"])))
    assert opened == plaintext and em["payload_sha256"] == digest
    for t in targets:
        assert gate.send_queued(db_path, t.envelope_id, client=live_client) == receipts[t.org_id]  # not re-sent


def test_live_consent_update(db_path, live, live_client):
    """Sends Walter's seeded consent (the same state the service was seeded with)."""
    with closing(connect(db_path)) as conn, conn:
        outbox_id = gate.queue_consent_update(conn, WALTER)
    receipt = gate.send_queued(db_path, outbox_id, client=live_client)
    assert (receipt.status, receipt.response_code, receipt.method) == ("sent", 200, "PUT")
    assert receipt.url == gate.consent_url(live, WALTER)
    assert gate.latest_consent_receipt(db_path) == receipt


# ---------- configuration fetches in the network log (PV-06, D-088) ----------

def _service(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://127.0.0.1:8000")


def test_make_client_logs_every_config_fetch(db_path):
    client = gate.make_client(Settings(db_path=db_path, patient_ref=WALTER))
    assert client._on_fetch is not None
    client.close()


def test_config_fetches_are_logged_with_their_parameters_only(db_path):
    survey = json.loads((SCHEMA_DIR / "examples" / "survey_config.valid.json").read_text())

    def handler(request):
        if request.url.path == "/v1/survey":
            return httpx.Response(200, json={"config_id": "cfg_b_v1", "cohort_id": "cohort_B", "version": 1,
                                             "published_at": "2026-09-27T12:00:00Z", **survey})
        return httpx.Response(503, json={"error": "down"})

    client = SentinelClient("http://127.0.0.1:8000", WALTER, http=_service(handler),
                            on_fetch=lambda r: gate.log_fetch(db_path, r))
    gate.refresh_config(db_path, WALTER, client=client)
    logged = rows(db_path, "SELECT outbox_id, kind, method, url, fields_sent, payload_sha256, response_code "
                           "FROM egress_log ORDER BY log_id")
    assert [(r["kind"], r["method"], r["response_code"]) for r in logged] == \
        [("config_fetch", "GET", 200), ("config_fetch", "GET", 503)]
    assert all(r["outbox_id"] is None for r in logged)
    assert logged[0]["url"].endswith("/v1/survey?cohort_id=cohort_B")
    assert json.loads(logged[0]["fields_sent"]) == ["cohort_id"]
    assert logged[0]["payload_sha256"] == payload_sha256({"cohort_id": "cohort_B"})
    assert "Walter" not in json.dumps(logged)


def test_no_network_logs_nothing_and_a_log_failure_never_blocks_a_fetch(db_path, tmp_path):
    def offline(request):
        raise httpx.ConnectError("no network")

    client = SentinelClient("http://127.0.0.1:8000", WALTER, http=_service(offline),
                            on_fetch=lambda r: gate.log_fetch(db_path, r))
    assert gate.refresh_config(db_path, WALTER, client=client).survey == "offline"
    assert rows(db_path, "SELECT * FROM egress_log") == []
    result = type("R", (), {"method": "GET", "url": "u", "fields_sent": [], "payload_sha256": "x",
                            "status_code": 200})()
    gate.log_fetch(tmp_path / "missing" / "nowhere.db", result)  # logs an error, never raises


def test_network_log_lists_sends_and_fetches_newest_first(db_path):
    record = make_record(db_path)
    queue(db_path, record)
    gate.send_queued(db_path, record["record_id"], client=FakeService().client())
    result = type("R", (), {"method": "GET", "url": "http://127.0.0.1:8000/v1/terms?program_id=prog_demo_01",
                            "fields_sent": ["program_id"], "payload_sha256": "f" * 64, "status_code": 200})()
    gate.log_fetch(db_path, result)
    entries = gate.network_log(db_path)
    assert [(e["kind"], e["destination"]) for e in entries] == [("config_fetch", None), ("send", "company_record")]
    assert entries[1]["outbox_id"] == record["record_id"] and entries[1]["response_code"] == 201
    assert set(entries[0]) == {"log_id", "kind", "outbox_id", "destination", "org_id", "method", "url",
                               "fields_sent", "payload_sha256", "response_code", "sent_at"}
    assert "SE_RASH" not in json.dumps(entries) and "\"payload\"" not in json.dumps(entries)  # no payload content
