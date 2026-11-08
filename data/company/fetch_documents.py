"""Download each trial's Study Protocol and Statistical Analysis Plan PDFs into a local, gitignored folder (D-080).

The PDFs are sponsor-authored, so they are fetched locally and never committed (docs/research/datasets.md section 7).
The URLs come from the committed ClinicalTrials.gov extracts (fetch_ctgov.py); the seed lists the same documents
in the company `document` table whether or not they have been downloaded.
Run from the repo root: uv run --project packages/contract-py python data/company/fetch_documents.py
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
OUT = HERE / "documents"  # gitignored
CDN = "https://cdn.clinicaltrials.gov/large-docs/{suffix}/{nct}/{filename}"


def trial_documents() -> list[dict]:
    """Protocol and SAP documents listed in each cached extract, with their public URL."""
    docs = []
    for path in sorted((HERE / "ctgov").glob("*.json")):
        study = json.loads(path.read_text())["study"]
        nct = study["protocolSection"]["identificationModule"]["nctId"]
        for d in study.get("documentSection", {}).get("largeDocumentModule", {}).get("largeDocs", []):
            docs.append({"trial": path.stem, "nct": nct, "kind": d["typeAbbrev"].lower(), "date": d.get("date"),
                         "filename": d["filename"], "size": d.get("size"),
                         "url": CDN.format(suffix=nct[-2:], nct=nct, filename=d["filename"])})
    return docs


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for d in trial_documents():
        dest = OUT / f"{d['trial']}_{d['filename']}"
        if dest.exists() and dest.stat().st_size == d["size"]:
            print(f"have {dest.name}")
            continue
        with httpx.stream("GET", d["url"], timeout=120, follow_redirects=True) as r:
            r.raise_for_status()
            with dest.open("wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        print(f"downloaded {dest.name} ({dest.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
