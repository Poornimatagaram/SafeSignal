# Dataset research: authentic data for SafeSignal

**Date:** 2026-11-07 · **Owner:** company side · **Status:** research complete; adoption decisions in `docs/DECISIONS.md` (D-057 onward)

The demo currently runs on synthetic data. Real-world data is messy, and a demo built on it is more convincing. This document lists public datasets that match our use case, what each one covers, how messy it is, and whether we may use and publish it.

**Bottom line:** no public dataset contains what SafeSignal itself would collect (daily check-ins from individual patients on a trial drug). That data is private by nature, which is the problem SafeSignal solves. So the demo still generates per-patient daily records, but **every rate, cohort, document and test sentence can come from real public sources**, and the dashboard can say so.

## 1. The use case these datasets must serve

| Area | Requirement (from the product owner) |
| --- | --- |
| Patients | Any age from 0 to 100. Patients answer for themselves or a **proxy answers for them**: a parent for an infant, a caregiver for an older adult. |
| Check-ins | On the schedule the trial sets (daily or another interval), the patient gets a questionnaire about side effects **and how they are feeling in general**, answered by voice, typing or another input method. |
| Missed check-ins | 1 missed day: alert. 2 consecutive days: escalate, something is wrong. 3rd day: inform the concerned parties **and public-service medical experts**. |
| Company | Several drugs. Per drug, about 1,000 enrolled patients in **4 control groups of 250**. The company holds trial documents (about 500 in reality); the proof of concept shows **1–2 documents per trial or drug**. The demo patient belongs to one group and gets that group's questions. |
| Doctor | Sees only the patient's medical history and continues the conversation from there at the visit. Missed check-in alerts reach the **doctor and the hospital or clinic**, because doctors change and the record must stay with the institution. |

## 2. Data needs and the best source for each

| Need | Best source | Verified |
| --- | --- | --- |
| Real side-effect rates per control group, per drug | ClinicalTrials.gov results API (per-arm adverse events) | Yes, live API calls |
| Real trial documents for the company (1–2 per trial) | ClinicalTrials.gov Study Protocol and Statistical Analysis Plan PDFs | Yes, live API calls |
| Real report-level mess (dates, ages 0–100, reporter type, duplicates) | FDA FAERS quarterly files; openFDA API | Yes (openFDA cached in `data/company/`) |
| Which side effects are on each drug's label | OnSIDES | Release notes checked |
| How patients and caregivers actually describe side effects | PsyTAR, CADEC, WebMD and Drugs.com/Druglib reviews | Pages checked |
| Spoken symptom descriptions and varied voices for speech-to-text | Medical Speech, Transcription & Intent; Mozilla Common Voice | Pages checked |
| Lay words mapped to medical terms | Consumer Health Vocabulary; OnSIDES/MedDRA terms | Pages checked |
| Questionnaire design for self-report and caregiver report | NCI PRO-CTCAE and Ped-PRO-CTCAE (design reference only) | Terms of use checked |

## 3. Company side

### 3.1 ClinicalTrials.gov results: real rates per control group

Public US government data, JSON API, no login: `https://clinicaltrials.gov/api/v2/studies/<NCT>?fields=resultsSection.adverseEventsModule`. Each trial reports adverse events per arm as "patients affected / patients at risk".

| Trial | Drug (demo program) | Patients | Ages | Arms with AE results | Example (any grade, from the API) |
| --- | --- | --- | --- | --- | --- |
| FLAURA `NCT02296125` | Tagrisso (osimertinib) vs older EGFR drugs | 674 | 18–100 | **4**: osimertinib global, standard care global, osimertinib China, standard care China | Diarrhoea 167/279 vs 162/277; acne-like rash 73/279 vs 136/277; shortness of breath 42/279 vs 22/277 |
| MARIPOSA `NCT04487080` | Rybrevant (amivantamab) + lazertinib vs osimertinib vs lazertinib | 1,074 | 18+ | **3** | Rash 260/421 vs 131/428 vs 95/213; nail infection 288/421 vs 121/428 vs 61/213; diarrhoea 123/421 vs 189/428 |
| AURA3 `NCT02151981` | Osimertinib vs chemotherapy | 421 | 18–130 | 2 | (not yet extracted) |
| FLAURA2 `NCT04035486` | Osimertinib with or without chemotherapy | 587 | 18–110 | 4 | (not yet extracted) |
| MELODY `NCT03979313` | Nirsevimab (RSV antibody) vs placebo, **infants** | 3,012 | **0–1 year** | 2 | (not yet extracted); covers the parent-reports-for-baby case |

Why it fits: arms map directly to our control groups, so cohort differences on the dashboard come from real trials instead of an invented story. FLAURA alone has exactly 4 groups.

Realistic messiness: one symptom split across several medical terms (rash vs acne-like rash vs maculo-papular rash), a 5% reporting threshold for non-serious events, uneven arm sizes, and regional sub-cohorts.

### 3.2 ClinicalTrials.gov documents: the company's trial documents

Every trial above has its **Study Protocol** and **Statistical Analysis Plan** as PDFs, 0.7–9 MB each, listed under `documentSection.largeDocumentModule`:

| Trial | Protocol | Statistical Analysis Plan |
| --- | --- | --- |
| FLAURA | `cdn.clinicaltrials.gov/large-docs/25/NCT02296125/Prot_000.pdf` (3.4 MB) | `.../SAP_001.pdf` (1.4 MB) |
| MARIPOSA | `cdn.clinicaltrials.gov/large-docs/80/NCT04487080/Prot_000.pdf` (9.1 MB) | `.../SAP_001.pdf` (3.2 MB) |
| AURA3 | `cdn.clinicaltrials.gov/large-docs/81/NCT02151981/Prot_000.pdf` (1.5 MB) | `.../SAP_001.pdf` (1.6 MB) |
| FLAURA2 | `cdn.clinicaltrials.gov/large-docs/86/NCT04035486/Prot_000.pdf` (1.7 MB) | `.../SAP_002.pdf` (1.2 MB) |
| MELODY | `cdn.clinicaltrials.gov/large-docs/13/NCT03979313/Prot_000.pdf` (1.9 MB) | `.../SAP_001.pdf` (0.8 MB) |

Together with each drug's FDA label (DailyMed), this gives the company **2–3 real documents per drug** for the dashboard and the document assistant (Scoping Doc CO-05). The documents are sponsor-authored; we link to them and fetch them locally rather than committing them (section 7).

### 3.3 FAERS and openFDA: real report-level mess

| Source | What it is | Access |
| --- | --- | --- |
| FAERS quarterly data files (FDA) | Raw individual reports, as related tables: demographics, drugs, reactions, outcomes, report sources, therapy dates, indications. Latest: July–September 2026, posted 28 Oct 2026 (~60 MB zip) | Public; `fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html`; CSV mirror at NBER |
| openFDA drug event API | Query layer over FAERS; already used for `data/company/openfda/tagrisso_reaction_counts.json` | Public |

Why it fits: real dates (weekly time series), **patient age and age group across the whole range from newborn to elderly**, sex, outcome seriousness, and **who reported** (consumer, physician, pharmacist, lawyer), which mirrors our self vs proxy reporting.

Realistic messiness: duplicate and follow-up versions of the same case, missing ages, free-text drug names, mixed age units, reports listing several suspect drugs.

### 3.4 Other regulators (second opinion)

| Source | What it is | Access |
| --- | --- | --- |
| Canada Vigilance data extract (Health Canada) | Full case-level download of suspected reactions, now including indications; consumer and professional reporters | Open Government Portal, public zip |
| MHRA Yellow Card interactive drug profiles (UK) | Suspected reactions by drug | Public, interactive |
| EMA adrreports.eu line listings (EU) | Suspected reactions by product or substance | Public, interactive; bulk download is awkward |

### 3.5 Label side effects: OnSIDES

OnSIDES v3.1.1 (April 2026): about 6.9 million drug–side-effect pairs extracted from US, EU, UK and Japanese labels, mapped to MedDRA terms and RxNorm drugs. **CC BY 4.0.** Use it to correct `schema/terms.json` (`drug_scope`, which drives `known_for_program`). Example of why: FLAURA reports shortness of breath and cough on osimertinib, while our term list marks them Rybrevant-only.

## 4. Patient side

### 4.1 How patients and caregivers describe side effects (text)

| Dataset | What it is | Fit | Licence and caveats |
| --- | --- | --- | --- |
| **PsyTAR** | 891 patient reviews, 6,009 sentences; 4,813 side-effect mentions mapped to UMLS and SNOMED CT, with severity and persistence qualifiers | Real patient wording with labels: ready-made scoring for extraction (SE-01) | **CC BY 4.0** (safe to commit). Psychiatric drugs, not oncology |
| **CADEC / CADECv2** (CSIRO) | Patient forum posts (AskaPatient) with side effects mapped to SNOMED CT and MedDRA | The standard benchmark for patient-reported side effects | CSIRO Data Licence; "research purposes only"; must cite; do not commit |
| **WebMD drug reviews** (Kaggle) | ~362,000 reviews (2007–2020) with condition, side-effects field, ratings, **age band** and sex | Covers reviewers across age bands, including people writing about others; filter by age band rather than to older adults only | Scraped; terms unclear; do not commit. Which age bands and drugs it contains: verify on download |
| **Drugs.com / Druglib** (UCI) | 215,000 reviews (Drugs.com); Druglib separates side-effect text and gives a 5-step severity rating | Severity in patients' own words | Research only, **no commercial use, no redistribution** (the Hugging Face copy was taken down). UCI download link has moved; fetch from UCI or Kaggle |

How we would use them: take real sentences and rewrite them as spoken answers to our questions, keeping the wording messy (rambling, off-topic, unclear). They become the 50 test transcripts and 20 re-ask cases (Scoping Doc 7.5), including proxy answers ("my daughter had a rash on her arms").

### 4.2 Voices for speech-to-text (all ages)

| Dataset | What it is | Fit | Licence and caveats |
| --- | --- | --- | --- |
| **Medical Speech, Transcription & Intent** (Kaggle, from Figure Eight) | 8.5 hours, about 6,600 spoken symptom descriptions ("I break out on my face very frequently") in 25 categories | Real people describing symptoms aloud | Labels and audio quality are knowingly imperfect (realistic). Licence through Appen's terms; do not commit |
| **Mozilla Common Voice** | Thousands of hours of read English speech with age bands from teens to 90s, plus sex and accent | Varied adult voices: the person speaking may be the patient, a parent or a caregiver | **CC0**, but Mozilla asks that it not be re-shared; download through Mozilla Data Collective; do not commit |
| **elderLUCID** (UCL) | Conversational speech from adults aged 19–84, older speakers with and without mild hearing loss | Slow and clarified speech | Audio available on request only |

Infants and young children do not speak in the check-in: their parent or caregiver does, so adult voices of all ages cover the 0–100 range.

### 4.3 Lay words and medical terms

| Resource | What it is | Use |
| --- | --- | --- |
| **Consumer Health Vocabulary** (open-access, collaborative) | About 158,000 lay terms, including misspellings, mapped to UMLS concepts | Grow `everyday_words` in `schema/terms.json`. Last updated 2011; download needs a guestbook sign-up |
| **OnSIDES / MedDRA terms** | Medical side-effect terms per drug | Map lay words to label terms |

### 4.4 Questionnaire design reference

**NCI PRO-CTCAE** (adults) and **Ped-PRO-CTCAE** (children, including **caregiver report**) are the standard way cancer trials collect side effects from patients: for example, "In the last 7 days, what was the SEVERITY of your DRY SKIN at its WORST?" (None, Mild, Moderate, Severe, Very severe).

Its terms **prohibit altering the wording and including it in anything sold**, and require registering the study. Our re-ask flow rephrases questions and the product is commercial, so **we do not copy the items**. We follow the structure: a 7-day recall window, and frequency, severity and interference with daily life as separate dimensions.

### 4.5 Signal-to-Dose package (track data)

Within3's public items about Tagrisso and Rybrevant, provided through the HACK1984 track. Real public text for the sentiment and signal work (Scoping Doc 8.4).

## 5. Mapping to the company portfolio (proposal)

| Program (drug) | Real source for cohort rates | Real documents | What it shows |
| --- | --- | --- | --- |
| Tagrisso | FLAURA's 4 arms (exactly 4 groups) | FLAURA protocol and SAP; FDA label | The main demo: Walter's cohort |
| Rybrevant | MARIPOSA's 3 arms | MARIPOSA protocol and SAP; FDA label | A drug version with clearly different skin side effects |
| Nirsevimab (infant) | MELODY's 2 arms | MELODY protocol and SAP; FDA label | A parent answering for a baby (proxy reporting, age 0) |

Each program keeps the company's design of 1,000 patients in 4 groups of 250. Where a trial has fewer than 4 arms, groups are assigned to arms (for example, two groups per arm). The daily records are generated by sampling from the real per-arm rates, with timing and reporting patterns taken from FAERS.

## 6. Excluded for now (credentials or approvals required)

Scoping Doc 16.1 rules out credentialed datasets for the weekend: MIMIC, n2c2 ADE, DementiaBank, mPower, and patient-level trial data from Project Data Sphere, Vivli or YODA. They are options for v1 pilots under data use agreements.

## 7. Rules for using these in this repository

The repository is **public**. Commit only data whose licence allows redistribution:

| Commit to the repo | Fetch locally only (gitignored), commit the fetch script |
| --- | --- |
| ClinicalTrials.gov API extracts, FAERS/openFDA extracts, Canada Vigilance extracts, OnSIDES (CC BY), PsyTAR (CC BY) | Trial protocol and SAP PDFs, CADEC, WebMD, Drugs.com/Druglib, Medical Speech audio, Common Voice audio |

Every dataset used gets a row in `data/README.md` with its source, licence and refresh command. No dataset is ever sent to a cloud AI tool (Scoping Doc 26.12).

## 8. Open questions

1. **"Public-service medical experts" on day 3:** who exactly (a public health authority, a nurse line, emergency services)? Sending identifiable data to them goes against the privacy promise unless the patient consents at enrollment. Needs a decision before it is built.
2. **Hospital-level records:** doctor envelopes are encrypted to one doctor's key, so a successor doctor cannot read them. Hospital continuity needs a care-team or hospital key. This is a contract change.
3. **Real drugs, fictional company:** the demo company should be fictional ("Demo Pharma"), with every real figure and document credited to its public source, so it is never presented as the real sponsor.

## Sources

- ClinicalTrials.gov API: https://clinicaltrials.gov/data-api/api · FLAURA https://clinicaltrials.gov/study/NCT02296125 · MARIPOSA https://clinicaltrials.gov/study/NCT04487080 · AURA3 https://clinicaltrials.gov/study/NCT02151981 · FLAURA2 https://clinicaltrials.gov/study/NCT04035486 · MELODY https://clinicaltrials.gov/study/NCT03979313
- FAERS quarterly files: https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html · NBER mirror: https://www.nber.org/research/data/fda-adverse-event-reporting-system · openFDA: https://open.fda.gov/apis/drug/event/
- Canada Vigilance extract: https://open.canada.ca/data/en/dataset/9cbaef00-b52c-4a70-9fed-d9aa8263ab74 · MHRA Yellow Card: https://yellowcard.mhra.gov.uk/idaps · EMA: https://www.adrreports.eu/
- OnSIDES: https://github.com/tatonetti-lab/onsides
- PsyTAR: https://pmc.ncbi.nlm.nih.gov/articles/PMC6495095/ · CADEC: https://data.csiro.au/collection/csiro:10948 · CADECv2: https://data.csiro.au/collection/csiro:62387
- WebMD reviews: https://www.kaggle.com/datasets/rohanharode07/webmd-drug-reviews-dataset · Druglib: https://archive.ics.uci.edu/dataset/461/drug+review+dataset+druglib+com · Drugs.com (Kaggle): https://www.kaggle.com/datasets/jessicali9530/kuc-hackathon-winter-2018
- Medical Speech, Transcription & Intent: https://www.kaggle.com/datasets/paultimothymooney/medical-speech-transcription-and-intent · Common Voice: https://commonvoice.mozilla.org/en/datasets and terms https://commonvoice.mozilla.org/terms · elderLUCID: https://reshare.ukdataservice.ac.uk/852906/
- Consumer Health Vocabulary: https://biomedinfo.smhs.gwu.edu/chv-files
- PRO-CTCAE: https://healthcaredelivery.cancer.gov/pro-ctcae/ · terms of use: https://healthcaredelivery.cancer.gov/pro-ctcae/terms_of_use.html
