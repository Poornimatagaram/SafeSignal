# Data

Public drug data (openFDA cache) and synthetic generators only; no real patient data (Scoping Doc 16.1). Each area writes only in its own subfolder (`data/<area>/`). Every dataset lists its source and licence here.

| Path | Contents | Source | Licence / terms | Refresh |
| --- | --- | --- | --- | --- |
| `company/openfda/tagrisso_reaction_counts.json` | Top 100 reaction terms (MedDRA preferred terms) in FDA adverse-event reports naming Tagrisso, with counts | openFDA drug adverse event API (`api.fda.gov/drug/event.json`, `patient.drug.medicinalproduct:"TAGRISSO"`) | Public data; see https://open.fda.gov/terms/. openFDA results are unvalidated and not for medical decisions | `uv run --project packages/contract-py python data/company/fetch_openfda.py` |

Notes on the openFDA cache:
- Counts are spontaneous-report frequencies, not incidence. The seed uses them only as relative weights for the synthetic side-effect mix (`apps/service/sentinel_service/seed.py`).
- The search matches reports where Tagrisso appears in any drug role (suspect or concomitant).
