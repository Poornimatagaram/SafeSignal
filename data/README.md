# Data

Public drug data (openFDA cache) and synthetic generators only; no real patient data (Scoping Doc 16.1). Each area writes only in its own subfolder (`data/<area>/`). Every dataset lists its source and licence here.

| Path | Contents | Source | Licence / terms | Refresh |
| --- | --- | --- | --- | --- |
| `company/openfda/tagrisso_reaction_counts.json` | Top 100 reaction terms (MedDRA preferred terms) in FDA adverse-event reports naming Tagrisso, with counts | openFDA drug adverse event API (`api.fda.gov/drug/event.json`, `patient.drug.medicinalproduct:"TAGRISSO"`) | Public data; see https://open.fda.gov/terms/. openFDA results are unvalidated and not for medical decisions | `uv run --project packages/contract-py python data/company/fetch_openfda.py` |
| `company/ctgov/{flaura,mariposa,melody}.json` | Per-arm adverse events (serious and non-serious tables), arm titles, sponsor, age range and trial-document metadata for FLAURA `NCT02296125`, MARIPOSA `NCT04487080`, MELODY `NCT03979313` | ClinicalTrials.gov API v2 (`clinicaltrials.gov/api/v2/studies/<NCT>`) | Public US government data; https://clinicaltrials.gov/about-site/terms-conditions | `uv run --project packages/contract-py python data/company/fetch_ctgov.py` |
| `company/labels/{tagrisso,rybrevant,beyfortus}.json` | FDA label sections that list side effects (boxed warning, warnings, adverse reactions, patient information), set ID and DailyMed link | openFDA drug label API (`api.fda.gov/drug/label.json`) | Public data; https://open.fda.gov/terms/ | `uv run --project packages/contract-py python data/company/fetch_labels.py` |
| `company/trial_map.json` | Our mapping: program → trial, cohort → trial arm, MedDRA terms → our term codes | Written by the company owner (D-081) | Ours | Edit by hand |
| `company/surveys/infant_v1.json` | Parent-facing survey for the infant program | Written by the company owner | Ours | Edit by hand |
| `company/documents/` (**gitignored**) | Study Protocol and Statistical Analysis Plan PDFs for the three trials (about 19 MB) | `cdn.clinicaltrials.gov/large-docs/...` (URLs from the ctgov extracts) | Sponsor-authored; fetched locally, never committed (D-080) | `uv run --project packages/contract-py python data/company/fetch_documents.py` |

How the seed uses this data (`apps/service/sentinel_service/seed.py`, D-081):
- Every patient and record is synthetic. Each cohort samples its side effects from one real trial arm: a patient is affected with the arm's trial share (patients affected ÷ patients at risk, MedDRA variants combined as 1 − Π(1 − pᵢ)) and has an episode in 60% of weeks.
- Trial shares cover the whole treatment period (months to years), not a single week, and both serious and non-serious tables are used. ClinicalTrials.gov lists non-serious events only above a 5% threshold for FLAURA and MARIPOSA, so rarer terms are 0 in those arms; MELODY lists every event.
- The messiness is real and kept: FLAURA's China arms code mouth sores as "Mouth ulceration" rather than "Stomatitis", rash is split over several MedDRA terms, and arms are uneven in size (65 to 1,997 patients).
- The openFDA reaction counts are no longer used by the seed (they weighted the 2.1 seed, D-053). Counts are spontaneous-report frequencies, not incidence, and the search matches reports naming Tagrisso in any drug role.
