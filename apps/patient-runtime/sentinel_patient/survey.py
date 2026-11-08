"""Today's questions for this device (VC-01, VC-09).

Source: the newest `survey_cache` row for the patient's cohort, filled by `egress_gate.refresh_config` from
`GET /v1/survey` at the start of each check-in. There is no stand-in: if the survey was never downloaded, the
check-in cannot start (NoSurvey). Once cached, check-ins keep working with the network off.
"""

from __future__ import annotations

import json
import sqlite3
from functools import lru_cache

from sentinel_contract import SCHEMA_DIR


class NoSurvey(LookupError):
    """No survey in the cache yet: the service has never been reached from this device."""


@lru_cache(maxsize=1)
def term_labels() -> dict[str, str]:
    """term_code -> label_term from schema/terms.json, for plain-words display on the patient screen."""
    terms = json.loads((SCHEMA_DIR / "terms.json").read_text())["terms"]
    return {t["term_code"]: t["label_term"] for t in terms}


def latest_survey(conn: sqlite3.Connection, patient_ref: str) -> tuple[str, list[dict]]:
    """(config_id, questions) of the newest cached survey for the patient's cohort; NoSurvey if none."""
    row = conn.execute(
        "SELECT config_id, questions_json FROM survey_cache WHERE cohort_id = "
        "(SELECT cohort_id FROM patient_profile WHERE patient_ref = ?) "
        "ORDER BY version DESC, fetched_at DESC LIMIT 1", (patient_ref,)).fetchone()
    if row is None:
        raise NoSurvey("today's questions have not been downloaded yet")
    return row["config_id"], _questions(row["questions_json"])


def survey_questions(conn: sqlite3.Connection, config_id: str) -> list[dict]:
    row = conn.execute("SELECT questions_json FROM survey_cache WHERE config_id = ?", (config_id,)).fetchone()
    if row is None:
        raise NoSurvey(f"survey {config_id} is not in the cache")
    return _questions(row["questions_json"])


def _questions(questions_json: str) -> list[dict]:
    data = json.loads(questions_json)
    return list(data["questions"] if isinstance(data, dict) else data)
