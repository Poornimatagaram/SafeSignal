"""Check-in sessions: answers in, a summary to approve, then one send through the egress gate (PV-04, PV-05).

- start: a `checkin_session` row tied to the cached survey (status 'partial' until approved).
- turn: an `answer_turn` row (transcript_text stays on the device) and the coded symptoms merged into a draft.
  Each answer also sets the session's input_mode (voice, text or mixed; D-066), which the record carries.
  Only questions that ask about symptoms (wellbeing, symptom screen, exposure) may add symptoms: the model invents
  one for answers like "it started two days ago", and the guard would turn that into SE_OTHER_REVIEW.
  Answers to the severity and onset questions fill in the symptoms from the latest answer that reported any
  (what "How bad is it?" refers to), using the rule-based helpers in extract.py; unclear stays empty.
- summary: plain words plus the exact record that would be shared. A symptom without a severity is never guessed:
  the patient picks one on the summary screen (VC-10).
- approve: only here does anything leave the device. symptom_event rows, the session's final status and the outbox
  row are written in one transaction; then egress_gate sends the stored payload and returns the receipt.
- care envelopes (NF-05, A7): after the record, egress_gate seals the doctor payload (name, exact date, drug,
  symptoms, trend) once per organization: the care team if the patient shares with it, and each emergency hospital
  if emergency consent is on (D-064, D-065). An organization whose key can't be fetched yet (not registered, offline)
  waits on its own; the retry worker seals and sends it later.

The draft (coded symptoms, exposures, the one correction) is kept in memory and saved after every change to
var/patient/drafts/<session_id>.json (state_store), so a check-in survives a runtime restart; the file is deleted
once the check-in is approved.
"""

from __future__ import annotations

import json
import logging
import secrets
from datetime import date
import threading
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

from . import egress_gate, exposure as exposures, extract, summary as spoken

from .consent import options as consent_options
from .db import connect, utc_now
from .state_store import JsonFile
from .survey import latest_survey, survey_questions, term_labels

SEVERITIES = ("mild", "moderate", "severe")
INPUT_MODES = ("voice", "text")  # how one answer was given; a session can also be "mixed" (D-066)
SYMPTOM_PURPOSES = frozenset({"wellbeing", "symptom_screen", "exposure"})  # schema/enums.json question_purpose
DESTINATION = "company_record"
ALERT = "alert"
DESTINATION_LABEL = "Drug company safety team (Sentinel service)"
CARE_ENVELOPE = "care_envelope"
CARE_LABEL = "Your care team (sealed: only your doctors can read it)"
EMERGENCY_LABEL = "Your emergency hospital (sealed: opened only in an emergency, and that is logged)"

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Shared:
    """What approval sent (or queued): the record, the severe alert and the sealed envelopes.

    `envelopes`: one {"org_id", "link_type", "label", "receipt": Receipt | None, "waiting": reason | None} per
    organization, care team first. `envelope` is the care team's: its Receipt, {"status": "waiting", "reason":
    "no_key" | "offline" | "refused"}, or None when the patient does not share with the care team.
    """
    record: "egress_gate.Receipt"
    alert: "egress_gate.Receipt | None"
    envelopes: tuple = ()

    @property
    def envelope(self):
        care = next((e for e in self.envelopes if e["link_type"] == "care_team"), None)
        if care is None:
            return None
        return care["receipt"] or {"status": "waiting", "reason": care["waiting"]}
ONSET_WORDS = {"today": "started today", "1_3_days": "started 1 to 3 days ago",
               "4_7_days": "started 4 to 7 days ago", "over_7_days": "started more than a week ago",
               "unknown": "start not known"}


class UnknownSession(LookupError):
    pass


class AlreadyShared(RuntimeError):
    pass


class CorrectionUsed(RuntimeError):
    """VC-08 allows one correction per check-in."""


class UnknownQuestion(LookupError):
    pass


class NoTerms(LookupError):
    """The term list was never downloaded, so known_side_effect cannot be set."""


class NeedsSeverity(ValueError):
    def __init__(self, term_codes: list[str]):
        self.term_codes = term_codes
        super().__init__("a severity is missing for: " + ", ".join(term_codes))


@dataclass
class Draft:
    symptoms: dict[str, dict] = field(default_factory=dict)  # term_code -> {"severity": str | None, "onset": str}
    last_reported: list[str] = field(default_factory=list)   # codes from the latest answer that reported symptoms
    record_id: str | None = None
    correction_used: bool = False                            # VC-08: one correction before sharing
    exposures: dict = field(default_factory=dict)            # question_id -> (local description, Exposure) (SE-04)

    def to_dict(self) -> dict:
        return {"symptoms": self.symptoms, "last_reported": self.last_reported, "record_id": self.record_id,
                "correction_used": self.correction_used,
                "exposures": {q: [text, list(e.days_ago)] for q, (text, e) in self.exposures.items()}}

    @classmethod
    def from_dict(cls, d: dict) -> "Draft":
        return cls(symptoms={k: dict(v) for k, v in d.get("symptoms", {}).items()},
                   last_reported=list(d.get("last_reported", [])), record_id=d.get("record_id"),
                   correction_used=bool(d.get("correction_used")),
                   exposures={q: (text, exposures.Exposure(tuple(days)))
                              for q, (text, days) in d.get("exposures", {}).items()})


class CheckinStore:
    def __init__(self, db_path: Path, patient_ref: str):
        self.db_path, self.patient_ref = db_path, patient_ref
        self._drafts: dict[str, Draft] = {}
        self._draft_dir = Path(db_path).parent / "drafts"
        self._lock = threading.Lock()
        self._envelope_wait: dict[tuple[str, str], str] = {}  # (session_id, org_id) -> why it is still waiting

    # ---------- session ----------

    def start(self) -> tuple[str, int]:
        """New session on the newest cached survey; NoSurvey if questions were never downloaded."""
        session_id = "ses_" + secrets.token_hex(4)
        with self._lock, closing(connect(self.db_path)) as conn, conn:
            config_id, questions = latest_survey(conn, self.patient_ref)
            reporter = conn.execute("SELECT reporter_default FROM patient_profile WHERE patient_ref = ?",
                                    (self.patient_ref,)).fetchone()
            conn.execute("INSERT INTO checkin_session (session_id, config_id, started_at, status, reporter, input_mode) "
                         "VALUES (?, ?, ?, 'partial', ?, 'voice')",
                         (session_id, config_id, utc_now(), reporter["reporter_default"] if reporter else "self"))
            self._drafts[session_id] = Draft()
        self._save_draft(session_id)
        return session_id, len(questions)

    def check_open(self, session_id: str) -> None:
        with closing(connect(self.db_path)) as conn:
            self._session(conn, session_id)
            if self._outbox(conn, session_id):
                raise AlreadyShared(session_id)

    def question(self, session_id: str, question_id: str) -> dict:
        """The survey question {question_id, purpose, asks} this session is answering."""
        with closing(connect(self.db_path)) as conn:
            return self._question(conn, self._session(conn, session_id), question_id)

    @staticmethod
    def next_step(question: dict, ask: int, rating: str) -> dict:
        """VC-05: complete -> next question; otherwise re-ask with asks[1], then asks[2]; after 2 re-asks give up
        (the question counts as unanswered) and move on."""
        if rating == "complete":
            return {"action": "next"}
        if ask < 2:
            return {"action": "reask", "ask": ask + 1, "text": question["asks"][ask + 1]}
        return {"action": "next", "unanswered": True}

    def record_turn(self, session_id: str, question_id: str, ask: int, transcript: str, answer_text: str,
                    extracted: list | None, rating: str | None = None, mode: str = "voice") -> list | None:
        """Store the answer (with its rating) and update the draft. `answer_text` is the filtered part of the answer
        that answers the question (the relevant sentences of a rambling reply). `mode` is how it was given, "voice"
        or "text"; the session's input_mode follows it (D-066, see _input_mode). Returns the symptoms taken from this
        answer (None if the model was unavailable)."""
        if mode not in INPUT_MODES:
            raise ValueError("mode must be voice or text")
        with self._lock, closing(connect(self.db_path)) as conn, conn:
            session = self._session(conn, session_id)
            if self._outbox(conn, session_id):
                raise AlreadyShared(session_id)
            question = self._question(conn, session, question_id)
            conn.execute("UPDATE checkin_session SET input_mode = ? WHERE session_id = ?",
                         (self._input_mode(conn, session, mode), session_id))
            conn.execute("INSERT INTO answer_turn (session_id, question_id, attempt, prompt_text, transcript_text, "
                         "rating, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (session_id, question_id, ask, question["asks"][ask], transcript, rating, utc_now()))
            draft = self._draft(session_id)
            draft.record_id = None  # the record changes with every answer
            try:
                return self._apply_turn(draft, question, question_id, answer_text, extracted, rating)
            finally:
                self._save_draft(session_id)

    @staticmethod
    def _input_mode(conn, session, mode: str) -> str:
        """D-066: the first answer sets the session's mode; a later answer given the other way makes it "mixed",
        and mixed stays mixed. Commands ("repeat", "slower") are not answers and never get here."""
        prior = conn.execute("SELECT 1 FROM answer_turn WHERE session_id = ? LIMIT 1",
                             (session["session_id"],)).fetchone()
        if prior is None:
            return mode
        return session["input_mode"] if session["input_mode"] == mode else "mixed"

    @staticmethod
    def _apply_turn(draft: Draft, question: dict, question_id: str, answer_text: str, extracted: list | None,
                    rating: str | None) -> list | None:
        filtered_text = answer_text
        if rating in ("off_topic", "no_answer"):
            return []  # nothing in it answers the question: no symptoms, no severity, no onset
        accepted = extracted if question["purpose"] in SYMPTOM_PURPOSES else []
        if question["purpose"] == "exposure" and accepted:
            # "I started a new hand cream" is an exposure, not a symptom: the model invents one for it, and the
            # guard turns that into SE_OTHER_REVIEW. Keep only symptoms the answer names (a cue-backed code).
            accepted = [s for s in accepted if s.term_code != extract.OTHER_REVIEW]
        for s in accepted or []:
            d = draft.symptoms.setdefault(s.term_code, {"severity": None, "onset": "unknown"})
            if s.severity:
                d["severity"] = s.severity
            if s.onset and s.onset != "unknown":
                d["onset"] = s.onset
        if accepted:
            draft.last_reported = [s.term_code for s in accepted]
        latest = [draft.symptoms[c] for c in draft.last_reported if c in draft.symptoms]
        if question["purpose"] == "severity" and (sev := extract.severity_in_text(filtered_text)):
            for d in latest:
                d["severity"] = d["severity"] or sev
        if question["purpose"] == "exposure":  # SE-04: the latest answer to this question decides
            if exposures.is_new_exposure(filtered_text):
                draft.exposures[question_id] = (filtered_text, exposures.exposure_from_answer(
                    extract.onset_in_text(filtered_text)))
            else:
                draft.exposures.pop(question_id, None)
        if question["purpose"] == "onset" and (onset := extract.onset_in_text(filtered_text)):
            for d in latest:
                if d["onset"] == "unknown":
                    d["onset"] = onset
        return accepted

    # ---------- summary and approval ----------

    def summary(self, session_id: str, base_url: str) -> dict:
        with self._lock, closing(connect(self.db_path)) as conn:
            session = self._session(conn, session_id)
            shared = self._outbox(conn, session_id) is not None
            draft = self._draft(session_id)
            items = self._flag_links(conn, session_id, draft, self._items(conn, draft))
            needs = [i["term_code"] for i in items if i["severity"] is None]
            unanswered = self._unanswered(conn, session_id, session["config_id"])
            record = None
            if not needs:
                if draft.record_id is None:  # the id shown is the id sent, even after a restart
                    draft.record_id = egress_gate.new_record_id()
                    self._save_draft(session_id)
                record = self._record(conn, draft.record_id, items, unanswered, session["input_mode"])
            # Field names only (no values) even while a severity is missing, so the screen can say what will go.
            fields = egress_gate.field_names(record or self._record(
                conn, "rec_00000000", [{**i, "severity": i["severity"] or "mild"} for i in items], unanswered,
                session["input_mode"], validate=False))
            care = self._care_preview(conn, items, base_url)
        return {"session_id": session_id, "shared": shared, "items": items, "needs_severity": needs,
                "unanswered_questions": unanswered, "text": _plain_words(items, unanswered),
                "spoken": spoken.spoken_summary(items, unanswered), "correction_used": draft.correction_used,
                "share": {"destination": DESTINATION_LABEL, "method": "POST",
                          "url": egress_gate.records_url(base_url), "fields": fields, "record": record,
                          "care": care}}

    def correction_items(self, session_id: str) -> list[dict]:
        """Current items, for parsing a spoken correction against them."""
        with self._lock, closing(connect(self.db_path)) as conn:
            self._session(conn, session_id)
            draft = self._draft(session_id)
            return self._flag_links(conn, session_id, draft, self._items(conn, draft))

    def correct(self, session_id: str, term_code: str, *, severity: str | None = None, onset: str | None = None,
                remove: bool = False) -> None:
        """VC-08: one change to one item before sharing (new severity, new onset, or "I don't have that")."""
        with self._lock, closing(connect(self.db_path)) as conn:
            self._session(conn, session_id)
            if self._outbox(conn, session_id):
                raise AlreadyShared(session_id)
            draft = self._draft(session_id)
            if draft.correction_used:
                raise CorrectionUsed(session_id)
            changes = sum([severity is not None, onset is not None, bool(remove)])
            if term_code not in draft.symptoms or changes != 1:
                raise ValueError("a correction changes one thing about one reported symptom")
            if severity is not None and severity not in SEVERITIES:
                raise ValueError("severity must be mild, moderate or severe")
            if onset is not None and onset not in ONSET_WORDS:
                raise ValueError("unknown onset")
            if remove:
                del draft.symptoms[term_code]
                draft.last_reported = [c for c in draft.last_reported if c != term_code]
            elif severity is not None:
                draft.symptoms[term_code]["severity"] = severity
            else:
                draft.symptoms[term_code]["onset"] = onset
            draft.correction_used, draft.record_id = True, None
            self._save_draft(session_id)

    def receipts(self, session_id: str, base_url: str) -> Shared | None:
        """The receipts as they stand now (the retry worker may have sent a queued one since); None if not shared."""
        with closing(connect(self.db_path)) as conn:
            self._session(conn, session_id)
            rec, alert = self._outbox(conn, session_id), self._outbox(conn, session_id, ALERT)
            if rec is None:
                return None
            sealed = {json.loads(r["payload"])["org_id"]: r["outbox_id"] for r in conn.execute(
                "SELECT outbox_id, payload FROM outbox WHERE session_id = ? AND destination = ? ORDER BY created_at",
                (session_id, CARE_ENVELOPE))}
            links = dict((org, link) for org, link in egress_gate.care_recipients(conn, session_id, self.patient_ref))
            care_org = conn.execute("SELECT care_org_id FROM patient_profile WHERE patient_ref = ?",
                                    (self.patient_ref,)).fetchone()["care_org_id"]
        pending = {org for sid, org in egress_gate.pending_care_envelopes(self.db_path) if sid == session_id}
        envelopes = []
        for org in [*sealed, *(o for o in links if o not in sealed)]:
            link = links.get(org, "care_team" if org == care_org else "emergency")
            if org in sealed:
                receipt = egress_gate.receipt_for(self.db_path, sealed[org], base_url=base_url)
                envelopes.append(_target(org, link, receipt, None))
            elif org in pending:
                envelopes.append(_target(org, link, None, self._envelope_wait.get((session_id, org), "no_key")))
        envelopes.sort(key=lambda e: e["link_type"] != "care_team")
        return Shared(egress_gate.receipt_for(self.db_path, rec["outbox_id"], base_url=base_url),
                      egress_gate.receipt_for(self.db_path, alert["outbox_id"], base_url=base_url) if alert else None,
                      tuple(envelopes))

    def _send_envelopes(self, session_id: str, client) -> tuple:
        """Seal and send one envelope per organization for an approved session (NF-05), or say why each waits.

        Recipients follow consent now and at approval (egress_gate.care_recipients), so turning sharing off stops
        new envelopes (CN-03). An organization whose key can't be fetched has nothing queued; the worker retries it.
        """
        out = []
        for t in egress_gate.queue_care_envelopes(self.db_path, session_id, self.patient_ref, client=client):
            if t.envelope_id is None:
                self._envelope_wait[(session_id, t.org_id)] = t.waiting
                log.info("care envelope for %s to %s waiting: %s", session_id, t.org_id, t.waiting)
                out.append(_target(t.org_id, t.link_type, None, t.waiting))
            else:
                self._envelope_wait.pop((session_id, t.org_id), None)
                receipt = egress_gate.send_queued(self.db_path, t.envelope_id, client=client)
                out.append(_target(t.org_id, t.link_type, receipt, None))
        return tuple(out)

    def approve(self, session_id: str, severities: dict[str, str], *, client) -> Shared:
        with self._lock:
            with closing(connect(self.db_path)) as conn:
                self._session(conn, session_id)
                existing = self._outbox(conn, session_id)
                alert_row = self._outbox(conn, session_id, ALERT)
            if existing:  # approved before: never build or send a second record or alert
                alert = (egress_gate.send_queued(self.db_path, alert_row["outbox_id"], client=client)
                         if alert_row else None)
                if existing["status"] == "queued":
                    record = egress_gate.send_queued(self.db_path, existing["outbox_id"], client=client)
                else:
                    record = egress_gate.receipt_for(self.db_path, existing["outbox_id"])
                return Shared(record, alert, self._send_envelopes(session_id, client))

            draft = self._draft(session_id)
            for code, sev in severities.items():
                if code not in draft.symptoms or sev not in SEVERITIES:
                    raise ValueError("severities must name reported symptoms and use mild, moderate or severe")
                if draft.symptoms[code]["severity"] is None:
                    draft.symptoms[code]["severity"] = sev
                    draft.record_id = None
            self._save_draft(session_id)
            with closing(connect(self.db_path)) as conn, conn:
                session = self._session(conn, session_id)
                items = self._flag_links(conn, session_id, draft, self._items(conn, draft))
                needs = [i["term_code"] for i in items if i["severity"] is None]
                if needs:
                    raise NeedsSeverity(needs)
                record_id = draft.record_id or egress_gate.new_record_id()
                record = self._record(conn, record_id, items, self._unanswered(conn, session_id, session["config_id"]),
                                     session["input_mode"])
                now = utc_now()
                conn.executemany(
                    "INSERT INTO symptom_event (event_id, session_id, term_code, severity, onset, known_side_effect, "
                    "possible_link_flag, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [("sym_" + secrets.token_hex(4), session_id, i["term_code"], i["severity"], i["onset"],
                      int(i["known_side_effect"]), int(i["possible_link"]), now) for i in items])
                today = date.today()
                conn.executemany(  # SE-04: kept for later check-ins; the description never leaves this device
                    "INSERT INTO exposure_event (exposure_id, description, started_on) VALUES (?, ?, ?)",
                    [("exp_" + secrets.token_hex(4), text or "(not described)",
                      exposures.started_on(e, today).isoformat()) for text, e in draft.exposures.values()])
                conn.execute("UPDATE checkin_session SET ended_at = ?, status = ? WHERE session_id = ?",
                             (now, record["status"], session_id))
                egress_gate.queue_payload(conn, outbox_id=record_id, session_id=session_id,
                                          destination=DESTINATION, payload=record)
                alert_id = None
                if self._severe(conn, items) and self._alert_consent(conn):  # AL-02, SE-03
                    alert_id = egress_gate.new_alert_id()
                    egress_gate.queue_payload(conn, outbox_id=alert_id, session_id=session_id, destination=ALERT,
                                              payload=egress_gate.build_alert(alert_id=alert_id,
                                                                              patient_ref=self.patient_ref))
            self._draft_file(session_id).delete()  # approved: everything needed is in the database now
            # The alert goes first: it is the urgent one. Both are already safe in the outbox if the network is off.
            alert = egress_gate.send_queued(self.db_path, alert_id, client=client) if alert_id else None
            record = egress_gate.send_queued(self.db_path, record_id, client=client)
            # Then the doctor's copy, sealed on this device to the care-team organization's key (NF-05).
            return Shared(record, alert, self._send_envelopes(session_id, client))

    # ---------- helpers ----------

    def _draft_file(self, session_id: str) -> JsonFile:
        return JsonFile(self._draft_dir / f"{session_id}.json")

    def _draft(self, session_id: str) -> Draft:
        """The session's draft: in memory, else from its file (after a restart), else empty."""
        draft = self._drafts.get(session_id)
        if draft is None:
            saved = self._draft_file(session_id).load()
            try:
                draft = Draft.from_dict(saved) if isinstance(saved, dict) else Draft()
            except (KeyError, TypeError, ValueError):
                log.error("check-in draft for %s unreadable; starting it empty", session_id)
                draft = Draft()
            self._drafts[session_id] = draft
        return draft

    def _save_draft(self, session_id: str) -> None:
        self._draft_file(session_id).save(self._draft(session_id).to_dict())

    def _session(self, conn, session_id: str):
        row = conn.execute("SELECT * FROM checkin_session WHERE session_id = ?", (session_id,)).fetchone()
        if row is None:
            raise UnknownSession(session_id)
        return row

    @staticmethod
    def _question(conn, session, question_id: str) -> dict:
        question = next((q for q in survey_questions(conn, session["config_id"])
                         if q["question_id"] == question_id), None)
        if question is None:
            raise UnknownQuestion(question_id)
        return question

    @staticmethod
    def _outbox(conn, session_id: str, destination: str = "company_record"):
        return conn.execute("SELECT outbox_id, status FROM outbox WHERE session_id = ? AND destination = ? "
                            "ORDER BY created_at LIMIT 1", (session_id, destination)).fetchone()

    def _care_preview(self, conn, items: list[dict], base_url: str) -> dict | None:
        """What the care team would get, sealed (field names only), or None when not sharing with the care team."""
        profile = conn.execute("SELECT care_org_id FROM patient_profile WHERE patient_ref = ?",
                               (self.patient_ref,)).fetchone()
        consent = conn.execute("SELECT share_care_team FROM consent ORDER BY consent_id DESC LIMIT 1").fetchone()
        if not (profile and profile["care_org_id"] and consent and consent["share_care_team"]):
            return None
        shape = {k: None for k in ("schema_version", "patient_ref", "display_name", "drug_name", "drug_version",
                                   "checkin_date", "status", "trend", "reporter", "age_years")}
        shape["symptoms"] = [{k: None for k in ("term_code", "severity", "onset", "known_side_effect",
                                                "possible_link_flag")}] if items else []
        names = {o["org_id"]: o["display_name"] for o in consent_options(self.patient_ref)["organizations"]}
        current = conn.execute("SELECT emergency_consent FROM consent ORDER BY consent_id DESC LIMIT 1").fetchone()
        emergency = [{"org_id": r["org_id"], "display_name": names.get(r["org_id"], r["org_id"])}
                     for r in conn.execute("SELECT org_id FROM emergency_org WHERE org_id != ? ORDER BY org_id",
                                           (profile["care_org_id"],))] if current["emergency_consent"] else []
        return {"destination": CARE_LABEL, "org_id": profile["care_org_id"], "method": "POST",
                "url": egress_gate.envelopes_url(base_url), "sealed": True, "fields": egress_gate.field_names(shape),
                "emergency": emergency}

    @staticmethod
    def _severe(conn, items: list[dict]) -> bool:
        """A severe symptom, or any symptom whose term is a severe trigger (schema/terms.json via term_cache)."""
        triggers = {r["term_code"] for r in conn.execute("SELECT term_code FROM term_cache WHERE severe_trigger = 1")}
        return any(i["severity"] == "severe" or i["term_code"] in triggers for i in items)

    @staticmethod
    def _alert_consent(conn) -> bool:
        """AL-02 within consent: alerts go to the care team and the caregiver, so at least one must be shared with."""
        c = conn.execute("SELECT share_care_team, share_caregiver FROM consent ORDER BY consent_id DESC LIMIT 1").fetchone()
        return bool(c and (c["share_care_team"] or c["share_caregiver"]))

    @staticmethod
    def _flag_links(conn, session_id: str, draft: Draft, items: list[dict]) -> list[dict]:
        """SE-04: mark each item `possible_link` (for review, never a cause). New = not in the previous approved
        check-in; exposures = the ones reported in this check-in plus those stored in the last 30 days."""
        today = date.today()
        previous = conn.execute("SELECT session_id FROM checkin_session WHERE ended_at IS NOT NULL AND session_id != ? "
                                "ORDER BY ended_at DESC, rowid DESC LIMIT 1", (session_id,)).fetchone()
        previous_codes = {r["term_code"] for r in conn.execute(
            "SELECT term_code FROM symptom_event WHERE session_id = ?", (previous["session_id"],))} if previous else set()
        found = [e for _, e in draft.exposures.values()]
        for r in conn.execute("SELECT started_on FROM exposure_event"):
            try:
                stored = exposures.stored_exposure(date.fromisoformat(r["started_on"]), today)
            except ValueError:
                continue
            if stored:
                found.append(stored)
        flagged = exposures.possible_links(items, found, previous_codes)
        return [{**i, "possible_link": i["term_code"] in flagged} for i in items]

    @staticmethod
    def _items(conn, draft: Draft) -> list[dict]:
        known = {r["term_code"]: (r["label_term"], bool(r["known_for_program"]))
                 for r in conn.execute("SELECT term_code, label_term, known_for_program FROM term_cache")}
        items = []
        for code, d in draft.symptoms.items():
            if code not in known:
                raise NoTerms(code)
            label, known_side_effect = known[code]
            items.append({"term_code": code, "label": label or term_labels().get(code, code),
                          "severity": d["severity"], "onset": d["onset"], "known_side_effect": known_side_effect})
        return items

    @staticmethod
    def _unanswered(conn, session_id: str, config_id: str) -> int:
        # Answered = some turn was rated complete (unrated turns with words count, for turns stored before A5).
        answered = {r["question_id"] for r in conn.execute(
            "SELECT question_id FROM answer_turn WHERE session_id = ? AND (rating = 'complete' OR "
            "(rating IS NULL AND trim(coalesce(transcript_text, '')) != ''))", (session_id,))}
        return sum(1 for q in survey_questions(conn, config_id) if q["question_id"] not in answered)

    def _record(self, conn, record_id: str, items: list[dict], unanswered: int, input_mode: str, *,
                validate: bool = True) -> dict:
        profile = conn.execute("SELECT * FROM patient_profile WHERE patient_ref = ?", (self.patient_ref,)).fetchone()
        consent = conn.execute("SELECT * FROM consent ORDER BY consent_id DESC LIMIT 1").fetchone()
        symptoms = [{"term_code": i["term_code"], "severity": i["severity"], "onset": i["onset"],
                     "known_side_effect": i["known_side_effect"],
                     "possible_link_flag": bool(i.get("possible_link", False))} for i in items]
        kwargs = dict(record_id=record_id, profile=dict(profile), consent=dict(consent), symptoms=symptoms,
                      unanswered_questions=unanswered, reporter=profile["reporter_default"], input_mode=input_mode)
        if validate:
            return egress_gate.build_company_record(**kwargs)
        try:
            return egress_gate.build_company_record(**kwargs)
        except Exception:  # field names only; the real record is validated before anything is shown or sent
            return {}


def _target(org_id: str, link_type: str, receipt, waiting: str | None) -> dict:
    """One organization's sealed copy for the receipt: a sent or queued receipt, or why it is still waiting."""
    label = CARE_LABEL if link_type == "care_team" else EMERGENCY_LABEL
    return {"org_id": org_id, "link_type": link_type, "label": label, "waiting": waiting,
            "receipt": None if receipt is None else {**receipt.to_dict(), "envelope_id": receipt.outbox_id,
                                                     "label": label}}


def _plain_words(items: list[dict], unanswered: int) -> str:
    if items:
        parts = [f"{i['label'].lower()}, {i['severity'] or 'how bad not said yet'}, {ONSET_WORDS[i['onset']]}"
                 for i in items]
        text = "You told me about: " + "; ".join(parts) + "."
        linked = [i["label"].lower() for i in items if i.get("possible_link")]
        if linked:  # SE-04: for review, never a cause
            text += (f" Marked for review: the {' and the '.join(linked)} started within a week of something new "
                     "you began. That does not mean one caused the other.")
    else:
        text = "You did not report any new problems."
    if unanswered:
        text += f" {unanswered} question{'s were' if unanswered > 1 else ' was'} not answered."
    return text
