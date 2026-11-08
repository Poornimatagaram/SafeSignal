"""Fetch per-arm adverse events and trial-document metadata from ClinicalTrials.gov and cache them (D-057, D-078).

Public US government data (no login, no patient context in the request). The extracts are committed; the PDFs they
point to are not (see fetch_documents.py).
Run from the repo root: uv run --project packages/contract-py python data/company/fetch_ctgov.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parent / "ctgov"
API = "https://clinicaltrials.gov/api/v2/studies/{nct}"
FIELDS = ",".join([
    "protocolSection.identificationModule",
    "protocolSection.sponsorCollaboratorsModule.leadSponsor",
    "protocolSection.eligibilityModule.minimumAge",
    "protocolSection.eligibilityModule.maximumAge",
    "resultsSection.adverseEventsModule",
    "documentSection.largeDocumentModule",
])
TRIALS = {"flaura": "NCT02296125", "mariposa": "NCT04487080", "melody": "NCT03979313"}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, nct in TRIALS.items():
        r = httpx.get(API.format(nct=nct), params={"fields": FIELDS}, timeout=60)
        r.raise_for_status()
        doc = {
            "source": API.format(nct=nct),
            "query": {"fields": FIELDS},
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "terms": "https://clinicaltrials.gov/about-site/terms-conditions (public US government data)",
            "study": r.json(),
        }
        path = OUT / f"{name}.json"
        path.write_text(json.dumps(doc, indent=1) + "\n")
        groups = doc["study"]["resultsSection"]["adverseEventsModule"]["eventGroups"]
        print(f"wrote {path.name}: {nct}, {len(groups)} arms")


if __name__ == "__main__":
    main()
