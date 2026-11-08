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

The draft lives in memory: if the runtime restarts mid check-in, the transcripts are kept but the coded symptoms of
earlier answers are lost (to be persisted with the network-off work in A6).
"""

from __future__ import annotations

import secrets
import threading
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

from . import egress_gate, extract
from .db import connect, utc_now
from .survey import latest_survey, survey_questions, term_labels

SEVERITIES = ("mild", "moderate", "severe")
SYMPTOM_PURPOSES = frozenset({"wellbeing", "symptom_screen", "exposure"})  # schema/enums.json question_purpose
DESTINATION = "company_record"
DESTINATION_LABEL = "Drug company safety team (Sentinel service)"
ONSET_WORDS = {"today": "started today", "1_3_days": "started 1 to 3 days ago",
               "4_7_days": "started 4 to 7 days ago", "over_7_days": "started more than a week ago",
               "unknown": "start not known"}


class UnknownSession(LookupError):
    pass


class AlreadyShared(RuntimeError):
    pass


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


class CheckinStore:
    def __init__(self, db_path: Path, patient_ref: str):
        self.db_path, self.patient_ref = db_path, patient_ref
        self._drafts: dict[str, Draft] = {}
        self._lock = threading.Lock()

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
        return {"session_id": session_id, "shared": shared, "items": items, "needs_severity": needs,
                "unanswered_questions": unanswered, "text": _plain_words(items, unanswered),
                "share": {"destination": DESTINATION_LABEL, "method": "POST",
                          "url": egress_gate.records_url(base_url), "fields": fields, "record": record}}

    def approve(self, session_id: str, severities: dict[str, str], *, client) -> egress_gate.Receipt:
        with self._lock:
            with closing(connect(self.db_path)) as conn:
                self._session(conn, session_id)
                existing = self._outbox(conn, session_id)
            if existing:  # approved before: never build or send a second record
                if existing["status"] == "queued":
                    return egress_gate.send_queued(self.db_path, existing["outbox_id"], client=client)
                return egress_gate.receipt_for(self.db_path, existing["outbox_id"])

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
            return egress_gate.send_queued(self.db_path, record_id, client=client)

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
    def _outbox(conn, session_id: str):
        return conn.execute("SELECT outbox_id, status FROM outbox WHERE session_id = ? AND destination = ? "
                            "ORDER BY created_at LIMIT 1", (session_id, DESTINATION)).fetchone()

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
