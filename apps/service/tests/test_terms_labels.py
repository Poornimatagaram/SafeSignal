"""Task C2 (D-079): every term's drug_scope in schema/terms.json matches the cached FDA label text.

A drug is in scope when the term appears in its label's adverse-reactions section (data/company/labels/,
fetched by data/company/fetch_labels.py). Patterns use the label's own wording.
"""

import json
import re

from sentinel_contract import SCHEMA_DIR, enums
from sentinel_service.db import REPO_ROOT

LABELS = {"Tagrisso": "tagrisso", "Rybrevant": "rybrevant", "Beyfortus": "beyfortus"}
PATTERNS = {
    "SE_RASH": r"\brash",
    "SE_DRY_SKIN": r"dry skin",
    "SE_PARONYCHIA": r"paronychia|nail toxicity",
    "SE_DIARRHEA": r"diarrhea",
    "SE_STOMATITIS": r"stomatitis",
    "SE_FATIGUE": r"fatigue",
    "SE_DECREASED_APPETITE": r"decreased appetite",
    "SE_INFUSION_REACTION": r"infusion-related reaction",
    "SE_DYSPNEA": r"dyspnea",
    "SE_COUGH": r"\bcough",
    "SE_EDEMA": r"(?<!pulmonary )(?<!site )\bedema\b",
    "SE_NAUSEA": r"nausea",
    "SE_VOMITING": r"vomiting",
    "SE_FEVER": r"pyrexia",
    "SE_NASAL": r"rhinorrh|nasal congestion",
    "SE_IRRITABILITY": r"irritability",
    "SE_INJECTION_SITE": r"injection site",
}


def adverse_reactions(drug: str) -> str:
    label = json.loads((REPO_ROOT / "data" / "company" / "labels" / f"{LABELS[drug]}.json").read_text())
    return " ".join(label["sections"]["adverse_reactions"]).lower()


def test_every_term_has_a_label_pattern():
    assert set(enums()["term_code"]) - {"SE_OTHER_REVIEW"} == set(PATTERNS)


def test_drug_scope_matches_the_labels():
    terms = json.loads((SCHEMA_DIR / "terms.json").read_text())["terms"]
    assert [t["term_code"] for t in terms] == enums()["term_code"]
    for t in terms:
        if t["term_code"] == "SE_OTHER_REVIEW":
            assert t["drug_scope"] == []
            continue
        on_label = {d for d in LABELS if re.search(PATTERNS[t["term_code"]], adverse_reactions(d))}
        assert set(t["drug_scope"]) == on_label, t["term_code"]
