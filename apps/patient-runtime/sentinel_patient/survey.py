"""Today's questions for this device (VC-01, VC-09 groundwork).

Source: the newest `survey_cache` row for the patient's cohort. Until the egress gate fetches the survey from
`GET /v1/survey` (task A4), the cache is empty and the contract's example survey is used instead.
"""

from __future__ import annotations

import json
from contextlib import closing
from functools import lru_cache
from pathlib import Path

from sentinel_contract import SCHEMA_DIR

from .db import connect

EXAMPLE_SURVEY = SCHEMA_DIR / "examples" / "survey_config.valid.json"


@lru_cache(maxsize=1)
def _example_questions() -> tuple[dict, ...]:
    return tuple(json.loads(EXAMPLE_SURVEY.read_text())["questions"])


@lru_cache(maxsize=1)
def term_labels() -> dict[str, str]:
    """term_code -> label_term from schema/terms.json, for plain-words display on the patient screen."""
    terms = json.loads((SCHEMA_DIR / "terms.json").read_text())["terms"]
    return {t["term_code"]: t["label_term"] for t in terms}


def current_questions(db_path: Path, patient_ref: str) -> tuple[list[dict], str]:
    """(questions, source) where source is "cache" or "example"."""
    with closing(connect(db_path)) as conn:
        row = conn.execute(
            "SELECT questions_json FROM survey_cache WHERE cohort_id = "
            "(SELECT cohort_id FROM patient_profile WHERE patient_ref = ?) "
            "ORDER BY version DESC, fetched_at DESC LIMIT 1", (patient_ref,)).fetchone()
    if row:
        data = json.loads(row["questions_json"])
        return list(data["questions"] if isinstance(data, dict) else data), "cache"
    return list(_example_questions()), "example"
