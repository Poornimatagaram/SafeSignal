"""Check-in sessions: answers in, a summary to approve, then one send through the egress gate (PV-04, PV-05).

- start: a `checkin_session` row tied to the cached survey (status 'partial' until approved).
- turn: an `answer_turn` row (transcript_text stays on the device) and the coded symptoms merged into a draft.
  Only questions that ask about symptoms (wellbeing, symptom screen, exposure) may add symptoms: the model invents
  one for answers like "it started two days ago", and the guard would turn that into SE_OTHER_REVIEW.
  Answers to the severity and onset questions fill in the symptoms from the latest answer that reported any
  (what "How bad is it?" refers to), using the rule-based helpers in extract.py; unclear stays empty.
- summary: plain words plus the exact record that would be shared. A symptom without a severity is never guessed:
  the patient picks one on the summary screen (VC-10).
- approve: only here does anything leave the device. symptom_event rows, the session's final status and the outbox
  row are written in one transaction; then egress_gate sends the stored payload and returns the receipt.
- care envelope (NF-05, A7): after the record, if the patient shares with the care team, egress_gate seals the doctor
  payload (name, exact date, drug, symptoms, trend) to the care-team organization's key and sends it. If the key
  can't be fetched yet (not registered, offline), the check-in waits and the retry worker seals and sends it later.

The draft lives in memory: if the runtime restarts mid check-in, the transcripts are kept but the coded symptoms of
earlier answers are lost (to be persisted with the network-off work in A6).
"""

from __future__ import annotations

import logging
import secrets
import threading
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

from . import egress_gate, extract, summary as spoken
from sentinel_contract import ContractError

from .db import connect, utc_now
from .survey import latest_survey, survey_questions, term_labels

SEVERITIES = ("mild", "moderate", "severe")
SYMPTOM_PURPOSES = frozenset({"wellbeing", "symptom_screen", "exposure"})  # schema/enums.json question_purpose
DESTINATION = "company_record"
ALERT = "alert"
DESTINATION_LABEL = "Drug company safety team (Sentinel service)"
CARE_ENVELOPE = "care_envelope"
CARE_LABEL = "Your care team (sealed: only your doctors can read it)"

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Shared:
    """What approval sent (or queued): the record, the severe alert and the care envelope.

    `envelope` is a Receipt, {"status": "waiting", "reason": "no_key" | "offline" | "refused"} while the sealed
    record waits for the organization's key, or None when the patient does not share with the care team.
    """
    record: "egress_gate.Receipt"
    alert: "egress_gate.Receipt | None"
    envelope: "egress_gate.Receipt | dict | None"
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


class CheckinStore:
    def __init__(self, db_path: Path, patient_ref: str):
        self.db_path, self.patient_ref = db_path, patient_ref
        self._drafts: dict[str, Draft] = {}
        self._lock = threading.Lock()
        self._envelope_wait: dict[str, str] = {}  # session_id -> why its care envelope is still waiting

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
                    extracted: list | None, rating: str | None = None) -> list | None:
        """Store the answer (with its rating) and update the draft. `answer_text` is the filtered part of the answer
        that answers the question (the relevant sentences of a rambling reply). Returns the symptoms taken from this
        answer (None if the model was unavailable)."""
        with self._lock, closing(connect(self.db_path)) as conn, conn:
            session = self._session(conn, session_id)
            if self._outbox(conn, session_id):
                raise AlreadyShared(session_id)
            question = self._question(conn, session, question_id)
            conn.execute("INSERT INTO answer_turn (session_id, question_id, attempt, prompt_text, transcript_text, "
                         "rating, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (session_id, question_id, ask, question["asks"][ask], transcript, rating, utc_now()))
            draft = self._drafts.setdefault(session_id, Draft())
            draft.record_id = None  # the record changes with every answer
            filtered_text = answer_text
            if rating in ("off_topic", "no_answer"):
                return []  # nothing in it answers the question: no symptoms, no severity, no onset
            accepted = extracted if question["purpose"] in SYMPTOM_PURPOSES else []
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
            draft = self._drafts.setdefault(session_id, Draft())
            items = self._items(conn, draft)
            needs = [i["term_code"] for i in items if i["severity"] is None]
            unanswered = self._unanswered(conn, session_id, session["config_id"])
            record = None
            if not needs:
                draft.record_id = draft.record_id or egress_gate.new_record_id()
                record = self._record(conn, draft.record_id, items, unanswered)
            # Field names only (no values) even while a severity is missing, so the screen can say what will go.
            fields = egress_gate.field_names(record or self._record(
                conn, "rec_00000000", [{**i, "severity": i["severity"] or "mild"} for i in items], unanswered,
                validate=False))
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
            return self._items(conn, self._drafts.setdefault(session_id, Draft()))

    def correct(self, session_id: str, term_code: str, *, severity: str | None = None, onset: str | None = None,
                remove: bool = False) -> None:
        """VC-08: one change to one item before sharing (new severity, new onset, or "I don't have that")."""
        with self._lock, closing(connect(self.db_path)) as conn:
            self._session(conn, session_id)
            if self._outbox(conn, session_id):
                raise AlreadyShared(session_id)
            draft = self._drafts.setdefault(session_id, Draft())
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

    def receipts(self, session_id: str, base_url: str) -> Shared | None:
        """The receipts as they stand now (the retry worker may have sent a queued one since); None if not shared."""
        with closing(connect(self.db_path)) as conn:
            self._session(conn, session_id)
            rec, alert = self._outbox(conn, session_id), self._outbox(conn, session_id, ALERT)
            env = self._outbox(conn, session_id, CARE_ENVELOPE)
        if rec is None:
            return None
        if env is not None:
            envelope = egress_gate.receipt_for(self.db_path, env["outbox_id"], base_url=base_url)
        elif session_id in egress_gate.pending_care_sessions(self.db_path):
            envelope = {"status": "waiting", "reason": self._envelope_wait.get(session_id, "no_key")}
        else:
            envelope = None
        return Shared(egress_gate.receipt_for(self.db_path, rec["outbox_id"], base_url=base_url),
                      egress_gate.receipt_for(self.db_path, alert["outbox_id"], base_url=base_url) if alert else None,
                      envelope)

    def _send_envelope(self, session_id: str, client) -> "egress_gate.Receipt | dict | None":
        """Seal and send the care envelope for an approved session (NF-05), or say why it is waiting.

        Sealed only while the patient shares with the care team (checked again here, so turning sharing off stops
        it, CN-03). A key that can't be fetched leaves nothing queued; the retry worker tries again later.
        """
        try:
            envelope_id = egress_gate.queue_care_envelope(self.db_path, session_id, self.patient_ref, client=client)
        except egress_gate.KeyUnavailable as e:
            self._envelope_wait[session_id] = e.reason
            log.info("care envelope for %s waiting: %s", session_id, e.reason)
            return {"status": "waiting", "reason": e.reason}
        except (ContractError, ValueError) as e:  # never the message: it could quote a value
            log.error("care envelope for %s not built: %s", session_id, type(e).__name__)
            self._envelope_wait[session_id] = "refused"
            return {"status": "waiting", "reason": "refused"}
        self._envelope_wait.pop(session_id, None)
        if envelope_id is None:
            return None
        return egress_gate.send_queued(self.db_path, envelope_id, client=client)

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
                return Shared(record, alert, self._send_envelope(session_id, client))

            draft = self._drafts.setdefault(session_id, Draft())
            for code, sev in severities.items():
                if code not in draft.symptoms or sev not in SEVERITIES:
                    raise ValueError("severities must name reported symptoms and use mild, moderate or severe")
                if draft.symptoms[code]["severity"] is None:
                    draft.symptoms[code]["severity"] = sev
                    draft.record_id = None
            with closing(connect(self.db_path)) as conn, conn:
                session = self._session(conn, session_id)
                items = self._items(conn, draft)
                needs = [i["term_code"] for i in items if i["severity"] is None]
                if needs:
                    raise NeedsSeverity(needs)
                record_id = draft.record_id or egress_gate.new_record_id()
                record = self._record(conn, record_id, items, self._unanswered(conn, session_id, session["config_id"]))
                now = utc_now()
                conn.executemany(
                    "INSERT INTO symptom_event (event_id, session_id, term_code, severity, onset, known_side_effect, "
                    "possible_link_flag, created_at) VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
                    [("sym_" + secrets.token_hex(4), session_id, i["term_code"], i["severity"], i["onset"],
                      int(i["known_side_effect"]), now) for i in items])
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
            # The alert goes first: it is the urgent one. Both are already safe in the outbox if the network is off.
            alert = egress_gate.send_queued(self.db_path, alert_id, client=client) if alert_id else None
            record = egress_gate.send_queued(self.db_path, record_id, client=client)
            # Then the doctor's copy, sealed on this device to the care-team organization's key (NF-05).
            return Shared(record, alert, self._send_envelope(session_id, client))

    # ---------- helpers ----------

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
        return {"destination": CARE_LABEL, "org_id": profile["care_org_id"], "method": "POST",
                "url": egress_gate.envelopes_url(base_url), "sealed": True, "fields": egress_gate.field_names(shape)}

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

    def _record(self, conn, record_id: str, items: list[dict], unanswered: int, *, validate: bool = True) -> dict:
        profile = conn.execute("SELECT * FROM patient_profile WHERE patient_ref = ?", (self.patient_ref,)).fetchone()
        consent = conn.execute("SELECT * FROM consent ORDER BY consent_id DESC LIMIT 1").fetchone()
        symptoms = [{"term_code": i["term_code"], "severity": i["severity"], "onset": i["onset"],
                     "known_side_effect": i["known_side_effect"], "possible_link_flag": False} for i in items]
        kwargs = dict(record_id=record_id, profile=dict(profile), consent=dict(consent), symptoms=symptoms,
                      unanswered_questions=unanswered, reporter=profile["reporter_default"], input_mode="voice")
        if validate:
            return egress_gate.build_company_record(**kwargs)
        try:
            return egress_gate.build_company_record(**kwargs)
        except Exception:  # field names only; the real record is validated before anything is shown or sent
            return {}


def _plain_words(items: list[dict], unanswered: int) -> str:
    if items:
        parts = [f"{i['label'].lower()}, {i['severity'] or 'how bad not said yet'}, {ONSET_WORDS[i['onset']]}"
                 for i in items]
        text = "You told me about: " + "; ".join(parts) + "."
    else:
        text = "You did not report any new problems."
    if unanswered:
        text += f" {unanswered} question{'s were' if unanswered > 1 else ' was'} not answered."
    return text
