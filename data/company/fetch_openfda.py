"""Fetch openFDA adverse-event reaction counts for the demo drug and cache them (Scoping Doc 16; risk R12).

Public, aggregate counts only; no patient context is attached to the request.
Run from the repo root: uv run --project packages/contract-py python data/company/fetch_openfda.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parent / "openfda"
URL = "https://api.fda.gov/drug/event.json"
# brand_name/generic_name return no matches for this drug in openFDA's harmonized fields; medicinalproduct does.
QUERY = 'patient.drug.medicinalproduct:"TAGRISSO"'


def main() -> None:
    r = httpx.get(URL, params={"search": QUERY, "count": "patient.reaction.reactionmeddrapt.exact", "limit": 100},
                  timeout=30)
    r.raise_for_status()
    body = r.json()
    OUT.mkdir(parents=True, exist_ok=True)
    doc = {
        "source": URL,
        "query": {"search": QUERY, "count": "patient.reaction.reactionmeddrapt.exact", "limit": 100},
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "openfda_last_updated": body.get("meta", {}).get("last_updated"),
        "disclaimer": body.get("meta", {}).get("disclaimer"),
        "results": body["results"],
    }
    path = OUT / "tagrisso_reaction_counts.json"
    path.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"wrote {len(doc['results'])} reaction terms to {path}")


if __name__ == "__main__":
    main()
