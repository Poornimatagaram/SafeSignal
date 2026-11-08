"""Fetch the FDA label sections that list side effects for each program's drug and cache them (task C2; D-079).

openFDA drug label API (public; https://open.fda.gov/terms/). Only the side-effect sections are kept; they are used
to check `schema/terms.json` drug_scope (apps/service/tests/test_terms_labels.py).
Run from the repo root: uv run --project packages/contract-py python data/company/fetch_labels.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parent / "labels"
URL = "https://api.fda.gov/drug/label.json"
# Tagrisso's label has no harmonized openfda fields, so it is matched on the product data elements instead.
DRUGS = {"tagrisso": "spl_product_data_elements:TAGRISSO", "rybrevant": 'openfda.brand_name:"RYBREVANT"',
         "beyfortus": 'openfda.brand_name:"BEYFORTUS"'}
SECTIONS = ["boxed_warning", "warnings_and_cautions", "adverse_reactions", "information_for_patients",
            "spl_patient_package_insert"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, query in DRUGS.items():
        r = httpx.get(URL, params={"search": query, "limit": 1}, timeout=30)
        r.raise_for_status()
        label = r.json()["results"][0]
        doc = {
            "source": URL,
            "query": {"search": query, "limit": 1},
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "set_id": label["set_id"],
            "effective_time": label["effective_time"],
            "dailymed_url": f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={label['set_id']}",
            "product": label.get("spl_product_data_elements", [""])[0][:80],
            "sections": {s: label[s] for s in SECTIONS if s in label},
        }
        path = OUT / f"{name}.json"
        path.write_text(json.dumps(doc, indent=1) + "\n")
        print(f"wrote {path.name}: set_id {doc['set_id']}, effective {doc['effective_time']}")


if __name__ == "__main__":
    main()
