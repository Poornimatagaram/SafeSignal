# Side-Effect Sentinel — Scoping Document

Nov 7, 2026 · @nandu

## 0. Document Control

Version 0.1 is a working draft for the HACK1984 build weekend (Nov 7–8, 2026, Boston); each section moves to Approved only after the team signs off on it.

| Field | Value |
| --- | --- |
| Product | Side-Effect Sentinel (working name) |
| Document type | Product scoping document |
| Version | 0.1 (draft) |
| Event | HACK1984, Sat Nov 7 – Sun Nov 8, 2026; hacking ends Sun 11:00 ET, judging 12:00 ET |
| Team | 3 members (names and roles to be added by the team) |
| Primary track | Privacy-First (main track) |
| Secondary tracks | Most Startup-able; Signal-to-Dose (Within3) |
| Judging lens | Problem · Target user · What's different · Flagship · Who pays (problem and flagship weighted highest) |

### Change log

| Version | Date | Change |
| --- | --- | --- |
| 0.1 | Nov 7, 2026 | Outline created; sections reordered so the judges' five questions (Problem, Target user, What's different, Flagship, Who pays) lead the document |

### Section approval tracker

| Section | Status |
| --- | --- |
| 0. Document Control | Approved |
| 1. Executive Summary | Approved |
| 2. Problem Statement | Approved |
| 3. Target Users & Personas | Approved |
| 4. What's Different | Approved |
| 5. Flagship & Prioritization | Approved |
| 6. Who Pays | Approved |
| 7. Goals, Non-Goals & Success Metrics | Approved |
| 8. Hackathon Track Alignment | Approved |
| 9. Solution Overview | Approved |
| 10. In Scope | Approved |
| 11. Out of Scope | Approved |
| 12. Functional Requirements | Approved |
| 13. Non-Functional Requirements | Approved |
| 14. Privacy & Data-Flow Architecture | Approved |
| 15. System Architecture & Tech Stack | Approved |
| 16. Data Sources & Datasets | Approved |
| 17. AI/Model Design & Evaluation | Approved |
| 18. Regulatory & Compliance | Approved |
| 19. Risks, Assumptions, Dependencies, Open Questions | Approved |
| 20. Work Breakdown & Timeline | Approved |
| 21. Demo Plan | Approved |
| 22. Market & Competitive Landscape | Approved |
| 23. Go-to-Market & Pitch Narrative | Approved |
| 24. Scaling Roadmap | Approved |
| 25. Appendix | Approved |
| 26. Database Schema & Data Contracts | In review |

## 1. Executive Summary

Side-Effect Sentinel is a voice-first side-effect monitoring platform. Patients report how they feel by talking. Everything they say is processed on their own device, and the drug company receives only a minimal, structured JSON record of the fields its safety team actually needs.

It serves three parties from one daily check-in. The patient gets a simple, safe way to be looked after. The drug company gets a steady, structured side-effect signal per drug and cohort. The doctor gets a ready-made symptom history before the visit. The drug company pays.

### The judges' five questions, answered

| Question | Our answer |
| --- | --- |
| Problem | Three sides, one gap. Patient: side effects go unreported (only about 6% of adverse drug reactions are reported, per a 2022 review), forms fail elderly users with tremors, and patients fear losing control of their health data. Drug company: it must monitor side effects but gets a thin, late, unstructured signal, and its drug documents are scattered across product versions. Doctor: sees the patient for minutes every few months and has no reliable record of what happened in between. |
| Target user | Patients on a monitored drug (first wedge: older adults); the drug company's drug-safety and medical-affairs teams (the buyer); prescribing doctors (the third user). |
| What's different | Voice-first for elderly users, and private by architecture. Raw audio and transcripts never leave the patient's device; only a schema-defined minimal JSON record leaves, and every outbound field is logged on screen. |
| Flagship | The daily voice check-in that turns speech into a minimal, privacy-filtered side-effect record. It is the highest-impact feature, every other module depends on it, and its effort is contained. Prioritization is detailed in Section 5. |
| Who pays | The drug company, per drug program and per enrolled patient. The patient never pays and the doctor never pays. Pricing is detailed in Section 6. |

### Privacy stance (one line)

Nothing the patient says leaves the device as raw audio or text. Only fields the patient approved, defined in a fixed JSON schema, are sent; Section 14 defines exactly what leaves, who can read it, and how we prove it.

### Hackathon tracks

- **Privacy-First (primary):** answers the judges' test directly: what leaves the device, who can read it, and proof of both.
- **Most Startup-able:** a buyer with a legal obligation and budget (drug-safety monitoring) and a recurring daily-use product.
- **Signal-to-Dose (Within3):** the same on-device pipeline flags side-effect signals and sentiment on a small model we host ourselves.

### Open decisions carried into later sections

- Whether missed check-ins alert the insurer (privacy risk; Sections 4, 14, 18).
- How much identified data the doctor view needs, and how "no token leaves" is defined for it (Section 14).
- Whether cough and tremor detection is built or staged for the demo (Sections 5, 10, 11).

## 2. Problem Statement

Patients, drug companies and doctors all lack the same thing: a timely, trusted record of how a patient is doing on a drug between visits. Each side feels that gap differently, so we state three problems.

### 2.1 Patient problem

**Problem statement:** An older patient on a long-term drug needs an easy, safe way to say how they feel every day. Today, reporting means forms, portals or phone lines, and sharing health data means losing control of it.

- **Side effects go unreported.** Patients notice symptoms but rarely report them; only about 6% of adverse drug reactions reach reporting systems.
- **Forms fail the people who need them most.** A 92-year-old with trembling hands, weak eyesight or little comfort with apps gives wrong answers or gives up.
- **Sharing feels unsafe.** Patients do not know who reads their health data, where it goes, or whether it is sold.
- **No one is checking in.** Between visits, a patient can get worse, or skip doses, and nobody notices.

**Consequence:** Harm goes unnoticed, and some patients stop an effective drug because of a symptom that may not even be caused by it.

### 2.2 Drug company problem

**Problem statement:** A drug company's drug-safety team must monitor side effects for every marketed drug. Today, it receives a thin, late, unstructured signal and spends its time searching scattered documents.

- **The signal is thin and late.** Spontaneous reporting misses most events, and the reports that arrive lack detail and timing.
- **No cohort view.** With, for example, 1,000 patients split across 4 drug versions (250 each), the team cannot easily see which version is causing which side effects.
- **Surveys are generic.** Patient questionnaires are not tailored to the drug version, the cohort or the side effects the team is watching.
- **Documents are scattered.** Around 500 documents across 4 versions of one drug (labels, protocols, safety reports) are hard to search and keep consistent.
- **Holding patient data is a liability.** Every identifiable record the company stores adds privacy risk and compliance cost.

**Consequence:** Safety signals surface late, regulatory exposure grows, and the company cannot tell which product version is performing well.

### 2.3 Doctor problem

**Problem statement:** A prescribing doctor needs to know what happened to the patient between visits. Today, they see the patient briefly and rely on what the patient remembers on the day.

- **Recall is unreliable.** Patients remember the last few days, not the last few months, and forget mild or intermittent symptoms.
- **History is fragmented.** Drug, dose changes and symptoms sit in different notes and systems.
- **Time goes to reconstruction.** The first part of a visit is spent piecing the story together instead of deciding.
- **No early warning.** A patient who worsens or stops responding between visits does not trigger anything.

**Consequence:** The doctor works with tunnel vision on today's visit, trends are missed, and decisions come later than they could.

### 2.4 The three problems side by side

| Side | Today | What breaks | What they need |
| --- | --- | --- | --- |
| Patient | Forms, portals, memory | Unreported symptoms, fear of data misuse, no one checking in | A simple voice check-in that keeps their data private |
| Drug company | Spontaneous reports, generic surveys, scattered documents | Late signal, no cohort comparison, data liability | Structured, minimal side-effect data by drug version and cohort |
| Doctor | Short visits, patient recall | Missed trends, time lost rebuilding history | A ready symptom timeline and alerts before the visit |

### 2.5 Evidence

| Claim | Source | Status |
| --- | --- | --- |
| Only about 6% of adverse drug reactions are reported | [Parracha et al., 2022, scoping review](https://doi.org/10.1002/pds.5542) | Sourced |
| Spontaneous reporting to FDA shows substantial underreporting | [Nature Medicine, 2015](https://doi.org/10.1038/nm0215-104) | Sourced |
| Patients stop effective drugs over perceived side effects that may be unrelated | [Nature Medicine, 2015](https://doi.org/10.1038/nm0215-104) (osteoporosis example) | Sourced |
| 1,000 patients, 4 drug versions, \~500 documents | Team's illustrative scenario | Example, not data |
| Elderly patients struggle with app and form input | Team observation | To verify before the pitch |

## 3. Target Users & Personas

The demo is built for three primary personas: the elderly patient who uses it, the drug-safety lead who pays for it, and the doctor who reads it. The other personas shape requirements but are secondary for the hackathon. All names are illustrative.

### 3.1 Who uses, who pays, who benefits

| Persona | Side | Role | Pays? | Hackathon priority |
| --- | --- | --- | --- | --- |
| Walter, 92, retired | Patient | Primary user, daily voice check-in | No | Primary |
| Priya, 58, on a lung cancer drug | Patient | Primary user, tech-comfortable | No | Secondary |
| Anna, Walter's daughter | Caregiver | Receives missed check-in alerts | No | Secondary |
| Dr. Lee, drug-safety lead | Drug company | Buyer; monitors side-effect signal | Yes | Primary |
| Marco, medical affairs | Drug company | Compares drug versions and cohorts | Yes (same budget) | Secondary |
| Dr. Shah, prescribing doctor | Doctor | Reads symptom timeline and alerts | No | Primary |
| Insurer | Payer | Not a user in v1; open decision | No | Out of scope (see Section 18) |

### 3.2 Walter, 92: the elderly patient (primary user)

- **Context:** On a long-term drug, lives alone, hand tremor, weak eyesight, mild hearing loss.
- **Goals:** Feel that someone is looking after him; avoid apps and forms; keep his health details private.
- **Pain points:** Cannot tap small buttons; drifts off topic or tells long stories when asked a question; forgets symptoms by the next doctor visit.
- **What Sentinel gives him:** A short daily voice conversation. If he rambles or does not answer, the agent re-asks the question more simply or in a different way. Nothing he says leaves his device.

### 3.3 Priya, 58: the working patient (secondary user)

- **Context:** On an oncology drug such as Tagrisso; uses a phone daily; busy.
- **Goals:** Report symptoms in under two minutes; know whether a symptom is a known side effect.
- **Pain points:** Portals are slow; worries her diagnosis could reach an employer or insurer.
- **What Sentinel gives her:** A fast check-in, plain-language feedback on known side effects, and a clear view of exactly what was shared.

### 3.4 Anna: the caregiver (secondary user)

- **Context:** Walter's daughter, lives in another city, is his emergency contact.
- **Goals:** Know quickly if her father misses a check-in or reports something serious.
- **Pain points:** Finds out about problems days later.
- **What Sentinel gives her:** An alert when a check-in is missed or a severe symptom is flagged. She sees the alert, not his full health record, unless Walter allows it.

### 3.5 Dr. Lee: the drug-safety lead (buyer)

- **Context:** Runs drug-safety monitoring (pharmacovigilance) for a drug with several versions and cohorts.
- **Goals:** Detect side-effect signals early; meet reporting obligations; avoid holding unnecessary patient data.
- **Pain points:** Thin, late reports; generic surveys; about 500 documents to search across 4 drug versions.
- **What Sentinel gives her:** Structured, minimal side-effect records by drug version and cohort; survey customization per cohort; a document assistant over the company's own files.
- **Buying criteria:** Data quality, regulatory fit, privacy liability reduced, cost per enrolled patient.

### 3.6 Marco: medical affairs (secondary company user)

- **Context:** Needs to know which drug version performs best and for whom.
- **Goals:** Compare cohorts (for example, 4 groups of 250 patients) on side effects and adherence over time.
- **What Sentinel gives him:** Cohort dashboards and week-over-week trends.

### 3.7 Dr. Shah: the prescribing doctor (primary reader)

- **Context:** Sees each patient briefly every few months.
- **Goals:** Walk into the visit already knowing the symptom history and current drug.
- **Pain points:** Relies on patient memory; spends the first minutes rebuilding the story; no warning when a patient worsens.
- **What Sentinel gives him:** A one-screen symptom timeline, flagged trends and alerts, shared with the patient's consent.

### 3.8 Persona decisions for the build

- The demo follows Walter end to end, then shows Dr. Lee's dashboard and Dr. Shah's timeline.
- The insurer is not a persona in v1. Sending missed check-in alerts to an insurer conflicts with the privacy-first promise and is decided in Section 18.

## 4. What's Different

Sentinel is the only option we found that combines voice-first check-ins for elderly patients, on-device processing where raw speech never leaves the phone, and one check-in that serves patient, drug company and doctor, each seeing only what they need.

### 4.1 How people solve this today

| Alternative | Example | How it works | Where it falls short |
| --- | --- | --- | --- |
| Regulator reporting apps | FDA MedWatcher (launched 2010s), national side-effect apps such as Yellow Card | Patient fills in a form after noticing a side effect | Manual, one-off, form-based; underused; no follow-up; no doctor or cohort view |
| Cloud patient apps | NowPatient | Patient logs side effects in an account; reminders every three months | Typed input, data stored on the vendor's cloud, infrequent |
| Social listening | Within3 and similar vendors | Reads public posts from patients, doctors and media | Sees only what people post publicly; not tied to a known drug version or cohort |
| Pharma patient-support and survey apps | Drug-company or vendor apps (category) | Questionnaires sent to enrolled patients | Usually typed, cloud-stored, generic questions; company holds identifiable data |
| Doctor visit and patient recall | Standard care | Patient tells the doctor what they remember | Recall bias, short visits, no warning between visits |

### 4.2 What Sentinel does differently

1. **Private by architecture, not by policy.** Speech-to-text, understanding and personal-data filtering run on the patient's device. Only a fixed-schema JSON record of approved fields leaves, and every outbound field is shown in an egress log the patient (and the judges) can inspect.
2. **Voice-first for people who cannot use forms.** A short spoken conversation replaces buttons and text boxes. If the patient rambles, drifts off topic or gives an incomplete answer, the agent re-asks the question more simply or in a different way.
3. **One check-in, three views.** The same daily check-in feeds the patient's own history, the company's cohort data and the doctor's timeline. Each view is scoped: the company sees de-identified structured fields, the doctor sees the history only with the patient's consent.
4. **Built around drug versions and cohorts.** Records are tagged by drug version and cohort, so the company can compare, for example, 4 groups of 250 patients week over week.
5. **The company tailors the questions, not the data access.** The company configures the survey per cohort; the questions are pushed to the device, and answers come back only as minimal structured fields.
6. **Connects symptoms over time.** On-device analysis links symptoms across days (for example, a rash appearing after a new nail product) and against the drug's known side effects, before anything is shared.
7. **A safety net, not just a form.** A missed check-in or a severe symptom triggers an alert to the caregiver and the doctor, so the patient is never silently lost.

### 4.3 Feature comparison

| Capability | Regulator apps | Cloud patient apps | Social listening | Sentinel |
| --- | --- | --- | --- | --- |
| Voice input for elderly users | No | No | No | Yes |
| Re-asks unclear answers | No | No | No | Yes |
| Raw data stays on device | No | No | Not applicable | Yes |
| Daily, continuous signal | No | Partial | Yes (public only) | Yes |
| Tied to drug version and cohort | No | No | No | Yes |
| Doctor timeline | No | Partial | No | Yes |
| Missed check-in alerts | No | No | No | Yes |

### 4.4 Why this is hard to copy

- Cloud-first vendors would have to rebuild their architecture to stop storing raw patient data.
- Each new drug program adds labelled, structured side-effect data by cohort, which improves detection for the next one.
- Trust is the moat with elderly patients and caregivers: a product that provably keeps data on the device is easier to recommend than one that asks for trust.

Competitor descriptions come from public product pages reviewed on Nov 7, 2026; the pharma survey-app row is a category, not a named product.

## 5. Flagship & Prioritization

The flagship is the **Private Check-in**: the patient speaks, the agent re-asks anything unclear, personal data is filtered on the device, and a minimal JSON record leaves with a receipt showing exactly what was sent. It scores high impact and low effort, so it is built first; everything else attaches to it.

### 5.1 Method (the judges' framework)

- **Impact:** High or Low, judged by how much the feature moves the problem statement, the Privacy-First test and the demo.
- **Effort:** High or Low, sized with three questions: Have we done it before? How many unknowns does it have? Does it wait on something outside our control?
- **Rule:** High impact + Low effort = build first. High impact + High effort = plan and chunk into small pieces. Low impact + Low effort = quick wins if time allows. Low impact + High effort = stage or cut.
- **Waits go first:** anything that depends on a download, an outside dataset or another person starts in the first hour, in parallel with coding.

### 5.2 Impact x effort map

&#91;embedded content: impact x effort · 16 features, 4 quadrants\]

Eight features sit in Build first, four of them the flagship chain; cough and tremor detection are staged, not built.

### 5.3 Effort sizing per feature

"Done before" reflects the team lead's past projects (RAG assistants, document extraction, evaluation suites, a voice pipeline demo); teammates should confirm or correct their rows.

| # | Feature | Impact | Done before? | Unknowns | Waits on | Effort | Quadrant |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Voice check-in (local speech-to-text, spoken questions) | High | Partly (voice pipeline demo) | 2: accuracy on elderly speech, browser audio latency | Speech model download | Low | Build first (flagship) |
| 2 | Re-ask unclear or rambling answers | High | No | 2: can a 3B model judge answer quality, how many retries | Language model download | Low | Build first (flagship) |
| 3 | On-device personal-data filter + minimal JSON | High | Yes (document extraction) | 2: personal-data recall, schema accuracy | None | Low | Build first (flagship) |
| 4 | Egress receipt (what left, to whom) | High | Yes | 0 | None | Low | Build first (flagship) |
| 5 | Match symptom to the drug's known side effects | High | Partly | 1: lay words vs label terms | openFDA label download | Low | Build first |
| 7 | Missed check-in alert to caregiver and doctor | High | Yes | 1: how alerts are delivered in the demo | None | Low | Build first |
| 11 | Doctor symptom timeline | High | Yes (dashboards) | 0 | None | Low | Build first |
| 15 | Consent controls (patient approves fields and doctor access) | High | Yes | 0 | None | Low | Build first |
| 6 | Link symptoms over time (for example, rash after a new nail product) | High | No | 3: rules vs model, false links, data | None | High | Plan and chunk |
| 8 | Company cohort dashboard by drug version | High | Yes (analytics) | 1: realistic synthetic cohort data | Synthetic data | High | Plan and chunk |
| 9 | Company survey customization pushed to device | High | No | 1: config format | None | High | Plan and chunk |
| 14 | Signal-to-Dose pipeline (insight cards, sentiment trends) | High | Partly | 3: hidden test set, track spec details, 3B model quality | Within3 starter repo and data | High | Plan and chunk |
| 10 | Company document assistant over drug documents | Low | Yes (RAG projects) | 1: which public documents to load | Public label documents | Low | Quick win if time |
| 16 | Draft FDA side-effect report from a record | Low | No | 1: required fields | None | Low | Quick win if time |
| 12 | Cough detection from audio | Low | No | 3: model, training data, on-device speed | Audio model | High | Stage or cut |
| 13 | Tremor detection from voice or phone motion | Low | No | 4: method, data, accuracy, device access | None | High | Stage or cut |

### 5.4 Build order

1. **Hour 0, start the waits:** download the speech and language models, pull the openFDA labels for the demo drugs, get the Within3 starter repo, and generate synthetic patients and cohorts.
2. **Flagship chain (features 1 → 2 → 3 → 4):** working end to end on one patient before anything else is touched.
3. **Remaining build-first features (5, 7, 11, 15):** each plugs into the flagship's JSON record.
4. **Plan-and-chunk features, smallest chunk first:** cohort dashboard as one chart before many; survey customization as a JSON file before an editor; symptom linking as one rule before a model; Signal-to-Dose only if a teammate owns it from hour 0.
5. **Quick wins (10, 16)** only after the demo runs end to end.
6. **Cough and tremor detection** are shown as a roadmap slide or a staged recording, not built live.

### 5.5 Cut-lines if time runs short

- At hour 6 of coding, if the flagship chain is not working end to end, stop all other features and fix it.
- At hour 9, freeze new features; only integration and demo polish after that.
- Never cut: features 1–4 and 15. They are the Privacy-First answer.

## 6. Who Pays

The drug company pays, through an annual platform fee per drug program plus a fee per enrolled patient per month. Patients and doctors use Sentinel free, and patient data is never sold: that rule is part of the privacy promise, not a pricing choice.

### 6.1 Value and payment by side

| Side | What they get | Pays? | Why they would pay |
| --- | --- | --- | --- |
| Drug company (drug-safety, medical affairs) | Structured side-effect records by drug version and cohort; survey customization; cohort analytics; document assistant | Yes, the buyer | Legal duty to monitor side effects; earlier signals; comparison across drug versions; less identifiable patient data to hold |
| Patient | Daily voice check-in, safety net, own history, control over sharing | No | Free use drives enrollment and daily completion, which is what the company pays for |
| Caregiver | Missed check-in and severe-symptom alerts | No | Raises completion rates and trust |
| Doctor | Symptom timeline and alerts before the visit | No | Free access drives consent and adoption; a paid clinic tier is a later option |

### 6.2 Pricing model (illustrative, to validate with buyers)

| Component | Unit | Illustrative price | Covers |
| --- | --- | --- | --- |
| Platform fee | Per drug program per year | $100,000 | Setup, survey configuration, cohort dashboards, document assistant, compliance package |
| Enrolled patient fee | Per active patient per month | $25 | Daily voice check-ins, on-device processing, structured records, alerts |
| Add-on: Signal-to-Dose analytics | Per drug program per year | To be set | Insight cards and sentiment trends across public and program data |

Worked example: one drug program with 1,000 enrolled patients for a year = $100,000 + (1,000 x $25 x 12) = **$400,000 per program per year**. The figures are placeholders to show the model, not market-tested prices.

### 6.3 Why the margins hold

- Speech-to-text, the language model and personal-data filtering run on the patient's device, so we do not pay per-patient cloud inference.
- Our servers store only small JSON records, not audio or transcripts, which keeps storage and security costs low.
- Each new drug program reuses the same app; only the survey and drug-label configuration change.

### 6.4 Other payers to explore later

- **Contract research organizations (CROs)** running post-marketing studies, which need the same structured side-effect data.
- **Patient-support program vendors** that run adherence and support services for drug companies.
- **Health systems or clinics** that want the doctor timeline for their own patients (a paid clinic tier).

### 6.5 What we will not do

- Sell, rent or share patient data with advertisers, data brokers or insurers.
- Charge patients.
- Price per data record sold; we price for the service, so we have no incentive to collect more data than needed.

### 6.6 Open questions for pricing

- Do drug companies budget this from drug safety, medical affairs or the brand team? This decides who signs.
- Is per-patient pricing or a flat per-program price easier to buy?
- How does receiving more side-effect reports change the company's reporting workload, and can we price the triage we save them? (Linked to Section 18.)

## 7. Goals, Non-Goals & Success Metrics

The weekend is a success if one patient's check-in runs end to end on a laptop, the egress receipt shows that only the minimal JSON record left the device, and the company and doctor views update from it live. Every target below is a team-set target, not a measured result.

### 7.1 Hackathon goals (due Sun Nov 8, 11:00 ET)

1. **Flagship works end to end:** voice check-in → re-ask → on-device filter → JSON record → egress receipt, live, on one machine.
2. **Privacy is provable on stage:** a network view or log shows zero audio and zero transcript text leaving; only the schema fields go out.
3. **Re-asking is visible:** a rambling or off-topic answer triggers a simpler re-asked question, shown in the demo.
4. **Three views update from one check-in:** patient history, company cohort dashboard (4 drug versions) and doctor timeline.
5. **Safety net fires:** a missed check-in produces an alert to the caregiver and doctor.
6. **Pitch answers the judges' five questions:** problem, target user, what's different, flagship, who pays.
7. **Optional:** a Signal-to-Dose submission from the same on-device pipeline, if a teammate owns it from hour 0.

### 7.2 Product goals (v1, first 6–12 months)

1. Run one paid pilot with one drug program and one cohort of enrolled patients.
2. Prove that voice check-ins get higher daily completion than typed surveys for older patients.
3. Deliver structured side-effect records the drug-safety team can use without re-entering data.
4. Pass a privacy and security review by the pilot company, including an external audit of what leaves the device.

### 7.3 Non-goals

- **No diagnosis or medical advice.** Sentinel records and flags; doctors decide.
- **No replacement of the company's regulatory systems.** We feed structured records into their existing drug-safety database; we do not file reports to regulators on their behalf.
- **No raw audio or transcripts on our servers,** ever.
- **No insurer integration** in the hackathon or v1 (decision pending in Section 18).
- **No native mobile app this weekend.** A web app on a laptop stands in for the patient's device.
- **No real patient data in the hackathon.** Synthetic patients, voices and records only.
- **No selling or sharing of patient data** with third parties.

### 7.4 Success metrics

| Metric | Definition | Hackathon target | v1 target |
| --- | --- | --- | --- |
| Raw data egress | Audio or transcript bytes leaving the device | 0 | 0 |
| Fields per record | Fields in each outbound JSON record | Only fields in the published schema | Only fields in the published schema |
| Personal-data leakage | Names, addresses, phone numbers, dates of birth or other identifiers found in outbound JSON | 0 on a 50-transcript synthetic test set | 0 in audited samples |
| Side-effect detection | F1 score for flagging the correct side effect against labels | ≥ 0.75 on our labeled test set | ≥ 0.85, reviewed by a drug-safety expert |
| Re-ask success | Rambling or incomplete answers resolved within 2 re-asks | ≥ 80% of 20 scripted cases | ≥ 80% of real check-ins |
| Check-in length | Time to finish one daily check-in | ≤ 3 minutes | Median ≤ 3 minutes |
| Response time | Delay between the patient finishing speaking and the agent replying | ≤ 3 seconds on a laptop | ≤ 3 seconds on a mid-range phone |
| Daily completion | Share of enrolled patients completing that day's check-in | Not measured | ≥ 70% (to validate in pilot) |
| Missed check-in alert | Time from missed window to alert | ≤ 1 minute in the demo | Within the window the program sets |
| Doctor prep time | Minutes a doctor spends reviewing history before a visit | Not measured | Baseline to measure in pilot, then reduce |

### 7.5 How we measure during the hackathon

- A synthetic test set of 50 check-in transcripts, including rambling, off-topic and identifier-heavy answers, with expected JSON outputs.
- 20 scripted re-ask cases with pass or fail per case.
- An egress log captured during the demo run, shown on screen and exported for judges.

## 8. Hackathon Track Alignment

We enter Privacy-First as the main track and Most Startup-able as the second; Signal-to-Dose is a stretch entry because it requires its own deliverables on Within3's data, and Surge is not targeted. Track criteria below are quoted from the [HACK1984 tracks page](https://claudeneu.com/hackathon/#tracks), read on Nov 7, 2026.

### 8.1 Track fit at a glance

| Track | What the judges ask | Our answer | Fit |
| --- | --- | --- | --- |
| Privacy-First (main) | "What leaves the device, who can read it, and can you prove it? Then: would anyone use it?" | Only a fixed-schema JSON record leaves; the company reads de-identified fields, the doctor reads history only with consent; an on-screen egress receipt proves it; elderly patients and a paying buyer will use it | Primary entry |
| Most Startup-able | "How fundable is it? Who is it for, would they pay, and why is this team the one to build it?" | Drug companies pay per program and per patient (Section 6); a legal duty to monitor side effects creates the budget | Secondary entry |
| Signal-to-Dose (Within3) | Catch the right signals and sentiment on a hidden set; citations support claims; trends at the demo; a network-off run on private transcripts; "Would a launch-intelligence expert act on it?" | Our on-device pipeline and 3B self-hosted model fit the network-off requirement; patient check-ins are a private, cited data source | Stretch entry, only if a teammate owns it from hour 0 |
| Surge (Tavily, Exa) | How central Tavily or Exa is to the project, and how well it works | Web search would add outbound calls and weaken the privacy story | Not targeted |

### 8.2 Privacy-First: our answer to each judging question

| Judge's question | Our answer | How we prove it in the demo |
| --- | --- | --- |
| What leaves the device? | One JSON record per check-in, limited to the fields in a published schema (symptom, severity, onset, drug version, cohort, check-in status). No audio, no transcript, no name. | Egress receipt shown after each check-in, field by field |
| Who can read it? | The company reads de-identified structured fields for its cohort. The doctor reads the patient's timeline only after the patient consents. The caregiver sees alerts only. | A role switcher showing each view side by side |
| Can you prove it? | Every outbound request is logged with its exact payload; the app works with the network off for everything except sending the record. | A live network log, then a network-off run where the check-in still completes |
| Would anyone use it? | Voice-first design for elderly patients; drug companies have a legal duty and a budget for this signal. | Walter's check-in in the demo, then the pricing slide |

### 8.3 Most Startup-able: the four things the track asks to see

- **A first customer in mind:** the drug-safety team for a specialty drug with several versions or cohorts, such as an oncology drug.
- **A working demo:** the flagship Private Check-in, end to end.
- **A one-line pitch:** "Your patients talk, their data stays on their phone, and you get the side-effect signal you are legally required to monitor."
- **Why it has to exist now:** on-device speech and small language models now run on ordinary hardware, which makes private-by-architecture monitoring practical for the first time.

### 8.4 Signal-to-Dose: what entering would require

- The track's own deliverables on Within3's \~2,000 public items about Tagrisso and Rybrevant: insight cards (headline, signal type, why it matters, citations, confidence) and a sentiment trend report scored -2 to +2 by aspect and speaker, week over week.
- A 3B open model we host ourselves, and a run with the network off on private transcripts.
- Reuse from Sentinel: the on-device model setup, side-effect extraction and the egress log. The insight cards and sentiment report are extra work and sit in the Plan-and-chunk quadrant (feature 14, Section 5).

### 8.5 Mapping to the judging panel's five questions

| Panel question | Where it is answered |
| --- | --- |
| Problem | Section 2 (three-sided problem) |
| Target user | Section 3 |
| What's different | Section 4 |
| Flagship | Section 5 |
| Who pays | Section 6 |

### 8.6 Answers from the organizers

- **Multiple tracks: allowed.** We enter several tracks but focus the build and pitch on Privacy-First.
- **Submission format:** a code repository plus a demo video.
- **Signal-to-Dose output format:** none specified, so we use the track's described deliverables (insight cards, sentiment trend report).

## 9. Solution Overview

One daily voice check-in on the patient's device produces one minimal JSON record. A thin Sentinel service stores only that record and routes it by role and consent to the drug company, the doctor and the caregiver. Raw audio and transcripts never leave the device.

### 9.1 How it fits together

&#91;embedded content: system overview · device, service, three views\]

Everything inside the dashed box runs on the patient's device; the only things that cross it are survey questions coming in and one JSON record going out.

### 9.2 Patient journey (Walter, daily)

1. At the scheduled time, the device greets Walter by voice and asks the first question of today's survey.
2. Walter answers out loud. Speech is turned into text on the device.
3. If the answer rambles, drifts off topic or misses the question, the agent re-asks it more simply or in a different way (up to 2 times).
4. The device removes names, places, phone numbers and other personal details, and extracts only the fields the survey needs.
5. The device checks the reported symptoms against the drug's known side effects and against Walter's own recent history.
6. Walter hears a short summary and approves what will be shared.
7. One JSON record is sent, and the egress receipt shows Walter (and the judges) exactly which fields left.

### 9.3 Drug company journey (Dr. Lee)

1. **Setup:** the company configures the survey for each drug version and cohort; only the questions are pushed to patients' devices.
2. **Daily:** de-identified records arrive, tagged by drug version and cohort.
3. **Weekly:** the cohort dashboard compares side effects and completion across, for example, 4 cohorts of 250 patients.
4. **On demand:** the document assistant answers questions over the company's own drug documents.

### 9.4 Doctor journey (Dr. Shah)

1. Walter consents to share his history with Dr. Shah.
2. Before the visit, Dr. Shah opens a one-screen symptom timeline with the current drug and flagged trends.
3. Between visits, Dr. Shah receives alerts for severe symptoms or missed check-ins.

### 9.5 Caregiver journey (Anna)

1. If Walter misses a check-in window or reports a severe symptom, Anna receives an alert.
2. The alert says what happened, not Walter's full health details, unless he has allowed more.

### 9.6 Who sees what

| Data | Patient device | Drug company | Doctor | Caregiver |
| --- | --- | --- | --- | --- |
| Raw audio | Yes, deleted after processing | No | No | No |
| Transcript | Yes, kept on device only | No | No | No |
| Name and contact details | Yes | No | Yes, with consent | Yes (already known) |
| Symptoms, severity, onset | Yes | Yes, de-identified | Yes, with consent | Severe flags only |
| Drug version and cohort | Yes | Yes | Yes, with consent | No |
| Check-in status (done or missed) | Yes | Yes, as completion rates | Yes, with consent | Yes |
| Survey questions | Yes | Yes (company writes them) | No | No |

## 10. In Scope

The hackathon MVP is the flagship Private Check-in plus the four other build-first features, running as a web app on a laptop that stands in for the patient's phone, with synthetic data only. Product v1 turns the same flow into a phone app and a pilot-ready service for one drug program.

### 10.1 Hackathon MVP (built by Sun Nov 8, 11:00 ET)

Feature numbers match Section 5.

| # | Feature | What we build this weekend | Priority |
| --- | --- | --- | --- |
| 1 | Voice check-in | Browser microphone, local speech-to-text, spoken questions, a 4–6 question daily survey | Must |
| 2 | Re-ask unclear answers | The local model rates each answer as complete or not; up to 2 rephrased re-asks, then moves on and flags it | Must |
| 3 | Personal-data filter + minimal JSON | Identifier removal plus extraction into a fixed JSON schema, all on the device | Must |
| 4 | Egress receipt | A panel listing every field sent, the destination and the time; plus a raw log of outbound requests | Must |
| 5 | Match to known side effects | Lookup against cached openFDA label text for the demo drugs | Must |
| 7 | Missed check-in alert | A timer that marks a check-in as missed and shows an in-app alert for caregiver and doctor | Must |
| 11 | Doctor timeline | One screen: current drug, symptoms by date, severity trend, flags | Must |
| 15 | Consent controls | Patient toggles for sharing with the doctor and the caregiver; consent stored with the record | Must |
| 8 | Cohort dashboard | One or two charts comparing 4 synthetic cohorts of 250 patients by drug version | Should |
| 9 | Survey customization | Company edits a survey JSON file per cohort; the device loads it | Should |
| 6 | Link symptoms over time | One rule: a new symptom within a set number of days of a new exposure is flagged for review | Should |
| 14 | Signal-to-Dose pipeline | Insight cards and a sentiment trend on Within3's data, only if a teammate owns it from hour 0 | Could |
| 10 | Document assistant | Question answering over a small set of public drug-label documents | Could |
| 16 | Draft FDA side-effect report | A pre-filled report draft from one JSON record | Could |

**Hackathon deliverables:** the code repository, a demo video, the 50-transcript synthetic test set and its results, and the egress log from the demo run.

### 10.2 Product v1 (first 6–12 months)

- **Patient app:** native iOS and Android apps running speech-to-text and the language model on the phone; large-text, voice-first interface.
- **Check-in engine:** scheduled daily or weekly surveys, re-asking, multiple languages, offline capture with send-when-online.
- **Privacy layer:** the published JSON schema, on-device filtering, signed egress receipts the patient can review, and an external audit of what leaves the device.
- **Company portal:** cohort analytics by drug version, survey builder, document assistant over the company's own documents, and export of side-effect records in the industry exchange format the company's drug-safety database accepts.
- **Doctor portal:** consent-gated web timeline and alerts.
- **Caregiver alerts:** text message or push notification for missed check-ins and severe symptoms.
- **Operations:** a HIPAA-ready hosting setup, business associate agreements, role-based access and audit logs, ready for one paid pilot.

## 11. Out of Scope

Anything that sends raw patient data off the device, makes a medical decision, or cannot be finished in 12 hours of coding is out of scope for the hackathon. Items marked "later" are deferred, not rejected.

### 11.1 Out of scope for the hackathon

| Item | Why it is out | When it returns |
| --- | --- | --- |
| Native iOS or Android app | A browser web app shows the same flow in the time we have | v1 |
| Real patients or real health data | Legal, ethical and consent requirements; synthetic data only | v1 pilot, under agreements |
| Cough detection from audio | Low impact for the demo, three unknowns, high effort (Section 5) | Roadmap slide or staged recording; later |
| Tremor detection from voice or phone motion | Low impact for the demo, four unknowns, high effort | Roadmap slide; later |
| Real text messages, calls or emails for alerts | Alerts are shown in the app; real delivery adds accounts and setup | v1 |
| Insurer notifications | Conflicts with the privacy-first promise; decision pending (Section 18) | Decision in Section 18 |
| Filing reports with the FDA or other regulators | The company's drug-safety team files reports; we supply structured records | Not planned |
| Integration with hospital record systems | Requires partner access and certification | Later |
| Production login, single sign-on and multi-tenant accounts | A role switcher stands in for logins in the demo | v1 |
| Multiple languages | English only for the demo | v1 |
| Production hosting, security certification and business associate agreements | Not needed for a demo on synthetic data | v1 pilot |

### 11.2 Out of scope for the product (not planned)

- **Diagnosis, treatment advice or dosing changes.** Sentinel records, flags and routes; clinicians decide.
- **Processing raw audio or transcripts in the cloud.** All speech handling stays on the patient's device.
- **Selling, renting or sharing patient data** with advertisers, data brokers or insurers.
- **Replacing the company's drug-safety database.** We export structured records into it.
- **Consumer sign-up outside a drug program.** Patients join through a program run by their drug company or clinic.
- **Wearables and continuous vital-sign monitoring.** Different product category with different regulation.

### 11.3 Boundary rules for scope changes during the weekend

- Any new idea must name the Section 5 quadrant it falls in before anyone works on it.
- Nothing new starts after hour 9 of coding.
- If an item would send anything other than the schema JSON off the device, it is out, whatever its impact.

## 12. Functional Requirements

44 requirements across 8 modules; 26 are Must for the hackathon, and every Must has a pass or fail check we can run before the demo. Priorities use the same Must, Should, Could scale as Section 10 and can be changed in place.

### 12.1 Voice check-in agent

| ID | Requirement | Acceptance check | Priority |
| --- | --- | --- | --- |
| VC-01 | Speak each survey question aloud and show it in large text | Every question is played and shown on screen | Must |
| VC-02 | Capture the spoken answer and turn it into text on the device | No network request appears in the log during transcription | Must |
| VC-03 | Tolerate slow speech and long pauses before ending the answer | A 3-second pause does not cut the answer off | Should |
| VC-04 | Rate each answer as complete, partial, off-topic, rambling or no answer | Correct rating on at least 16 of 20 scripted cases | Must |
| VC-05 | Re-ask any answer that is not complete, in a simpler or different way (for example, a yes or no question, or a short list of choices); at most 2 re-asks, then mark it unanswered and move on | Demo case shows a re-ask; never more than 2 re-asks per question | Must |
| VC-06 | Pull the relevant answer out of a long or rambling reply and ignore the rest | Symptom captured correctly from the rambling test cases | Must |
| VC-07 | Let the patient say "repeat" or "slower" at any time | Both commands work in the demo | Should |
| VC-08 | Read back a short spoken summary at the end and allow one correction | Patient hears the summary and can change one answer | Must |
| VC-09 | Load the day's questions from the company's survey configuration for the patient's cohort | Changing the configuration file changes the questions | Should |
| VC-10 | Ask severity in plain words (mild, moderate, severe) | Severity stored for every reported symptom | Must |

### 12.2 Privacy and data minimization

| ID | Requirement | Acceptance check | Priority |
| --- | --- | --- | --- |
| PV-01 | Remove names, addresses, phone numbers, emails, dates of birth and place names before extracting fields | 0 identifiers in outbound JSON across the 50 test transcripts | Must |
| PV-02 | Extract only the fields defined in the published JSON schema; drop everything else | Every outbound record validates against the schema; extra fields are rejected | Must |
| PV-03 | Delete raw audio after transcription; keep the transcript on the device only | No audio file remains after a check-in; no transcript in any outbound request | Must |
| PV-04 | Ask the patient to approve what will be shared before sending | Nothing is sent until the patient confirms | Must |
| PV-05 | Show an egress receipt after sending: fields, destination, time and a fingerprint (hash) of the payload | Receipt matches the logged request exactly | Must |
| PV-06 | Log every network request the app makes, with its full payload | Log shows only the record send and approved configuration fetches | Must |
| PV-07 | Complete a check-in with the network off and send the record when back online | Check-in succeeds with the network off | Should |
| PV-08 | Identify patients in records by a random ID, not by name | No name or contact detail in any company-side record | Must |

### 12.3 Side-effect detection and analysis

| ID | Requirement | Acceptance check | Priority |
| --- | --- | --- | --- |
| SE-01 | Map the patient's own words to standard side-effect terms | F1 score of at least 0.75 on the labeled test set | Must |
| SE-02 | Mark each symptom as a known or unlisted side effect of the patient's drug, using its label | Known side effects of the demo drugs are matched correctly | Must |
| SE-03 | Flag severe symptoms for immediate alerting | Every severe test case raises a flag | Must |
| SE-04 | Flag a possible link when a new symptom starts within a set number of days of a new exposure (for example, a rash after a new nail product); show it as "for review", never as a cause | Demo case shows the link with the "for review" wording | Should |
| SE-05 | Show each patient's trend (better, same, worse) over the last 7 check-ins | Trend shown on the doctor timeline | Should |

### 12.4 Alerts and escalation

| ID | Requirement | Acceptance check | Priority |
| --- | --- | --- | --- |
| AL-01 | Mark a check-in as missed when its window closes and alert the caregiver and the doctor | Alert appears within 1 minute in the demo | Must |
| AL-02 | Alert the doctor and the caregiver immediately on a severe symptom, within the patient's consent settings | Severe test case triggers both alerts | Must |
| AL-03 | Keep alert content minimal (what happened and when) unless the patient allowed more detail | Caregiver alert shows no symptom details by default | Must |
| AL-04 | Give the patient one spoken reminder before marking a check-in as missed | Reminder plays before the missed alert | Should |

### 12.5 Consent

| ID | Requirement | Acceptance check | Priority |
| --- | --- | --- | --- |
| CN-01 | Let the patient turn sharing on or off for the doctor and the caregiver, and choose the detail level | Toggles change what each role can see | Must |
| CN-02 | Store consent with each record and enforce it in the Sentinel service by role | A doctor without consent sees nothing for that patient | Must |
| CN-03 | Stop future sharing immediately when consent is withdrawn | Next record is not visible to the withdrawn role | Should |

### 12.6 Drug company portal

| ID | Requirement | Acceptance check | Priority |
| --- | --- | --- | --- |
| CO-01 | Show side-effect counts by drug version and cohort, week over week | Dashboard compares 4 synthetic cohorts of 250 patients | Should |
| CO-02 | Show check-in completion rates by cohort | Rates shown per cohort | Should |
| CO-03 | Let the company edit the survey per cohort and publish it to devices | Edited question appears on the next check-in | Should |
| CO-04 | Give the company de-identified structured records only, never transcripts or audio | Company views contain no transcript text or identifiers | Must |
| CO-05 | Answer questions over the company's drug documents with cited sources | Each answer links to the document passage it used | Could |
| CO-06 | Pre-fill a draft FDA side-effect report from a record | Draft generated for one demo record | Could |
| CO-07 | Export records as JSON or CSV | Export downloads and opens | Could |

### 12.7 Doctor view

| ID | Requirement | Acceptance check | Priority |
| --- | --- | --- | --- |
| DR-01 | Show a one-screen timeline: current drug, symptoms by date, severity, flags | Timeline renders for the demo patient | Must |
| DR-02 | Show only patients who consented to share with this doctor | Non-consenting patient is not listed | Must |
| DR-03 | List alerts for missed check-ins and severe symptoms | Alerts from AL-01 and AL-02 appear | Must |
| DR-04 | Generate a short pre-visit summary from the structured records | Summary generated for the demo patient | Could |

### 12.8 Signal-to-Dose (stretch)

| ID | Requirement | Acceptance check | Priority |
| --- | --- | --- | --- |
| SD-01 | Produce insight cards (headline, signal type, why it matters, citations, confidence) from Within3's data | Cards generated for both drugs | Could |
| SD-02 | Produce a sentiment trend report (-2 to +2 by aspect and speaker, week over week, with quotes) | Report generated with quotes behind each score | Could |
| SD-03 | Run the pipeline with the network off on the 3B self-hosted model | Run completes with the network disabled | Could |

## 13. Non-Functional Requirements

Privacy and accessibility outrank speed and polish: if a requirement in this section conflicts with a feature, the feature changes. Hackathon targets are what we test this weekend; v1 targets are for the pilot.

| ID | Category | Requirement | Hackathon target | v1 target |
| --- | --- | --- | --- | --- |
| NF-01 | Privacy | Raw audio, transcripts and free text never leave the device | 0 bytes in the egress log | 0 bytes, confirmed by external audit |
| NF-02 | Privacy | All network traffic passes through one egress gate that validates against the JSON schema | 1 code path for outbound data | Same, covered by automated tests |
| NF-03 | Privacy | Company dashboards hide any count below 5 patients, so small groups cannot be singled out | Applied to all cohort charts | Applied to all views and exports |
| NF-04 | Security | Data stored on the device is encrypted | Browser storage, synthetic data (not encrypted this weekend) | Phone's encrypted storage |
| NF-05 | Security | Data in transit uses TLS; doctor-bound data is encrypted so only the doctor can read it | TLS on localhost not required; doctor encryption is a Should | TLS 1.2+ and end-to-end encryption to the doctor |
| NF-06 | Performance | Agent replies after the patient stops speaking | ≤ 3 seconds on a laptop | ≤ 3 seconds on a mid-range phone |
| NF-07 | Performance | One full daily check-in | ≤ 3 minutes | Median ≤ 3 minutes |
| NF-08 | Accessibility | Voice-first; large text (at least 24 px); high contrast; no small tap targets | Met on the patient screen | Meets WCAG 2.2 AA |
| NF-09 | Accessibility | Works for slow speech, pauses, hearing loss (repeat and slower commands) | Met in demo cases | Tested with older adults |
| NF-10 | Reliability | Check-in works offline and sends when back online | Network-off demo run passes | Queue survives app restarts |
| NF-11 | Reliability | Missed check-in and severe-symptom alerts are never silently dropped | Alerts appear within 1 minute | Delivery confirmed and retried |
| NF-12 | Auditability | Every outbound request and every record read is logged | Egress log exported | Tamper-evident logs (each entry chained to the previous one) |
| NF-13 | Transparency | The JSON schema and egress rules are published | In the repository README | Public page for patients and companies |
| NF-14 | Maintainability | Models, survey and drug labels are swappable by configuration | Config files | Admin tools |

## 14. Privacy & Data-Flow Architecture

"Not one token leaves" means this: no audio, no transcript and no free text the patient said ever leaves the device. What leaves is a record built only from coded values (picked from fixed lists), numbers and IDs, so there is no field in which a sentence, a name or a stray identifier could travel.

### 14.1 Design rules

1. **No free-text fields in any outbound record.** Every field is a code from a fixed list, a number, a boolean or a random ID. This is what makes the guarantee checkable.
2. **One egress gate.** A single function is the only code path allowed to send data off the device. It validates every payload against the schema and refuses anything else.
3. **Two payloads, two readers.** The company receives a de-identified record. The doctor receives a separate record, encrypted so that only the doctor can read it, and only when the patient has consented. The Sentinel service stores both but can read only the company record.
4. **Coarse time for the company, exact dates for the doctor.** The company sees the ISO week; the doctor, with consent, sees the exact date.
5. **Small groups stay hidden.** Company views suppress any count below 5 patients.
6. **The patient approves every send** and gets a receipt for it.

### 14.2 Data classes

| Class | Examples | Where it lives | Leaves the device? | Who can read it |
| --- | --- | --- | --- | --- |
| Raw | Audio of the answer | Device memory, deleted after transcription | Never | Nobody after deletion |
| Private | Transcript, name, contact details, the patient's own words | Device storage only | Never | The patient |
| Doctor-shared | Exact dates, symptom timeline, severity, flags | Encrypted copy on the Sentinel service | Yes, encrypted to the doctor, with consent | The consented doctor only |
| Company-shared | Coded symptoms, severity, onset range, week, cohort, drug version, random patient ID | Sentinel service | Yes, de-identified | The company's authorized users |
| Alert | Check-in missed or severe flag, with time | Sentinel service | Yes | Caregiver and doctor, per consent |

### 14.3 Outbound record format (company payload)

Every value is from a fixed list, a number, a boolean or an ID. The draft is below; final codes are fixed in the Appendix.

```json
{
  "schema_version": "1.0",
  "record_id": "rec_7f3c9a1e",
  "patient_ref": "pt_4b82d0c6",
  "program_id": "prog_demo_01",
  "cohort_id": "cohort_B",
  "drug_version": "v2",
  "iso_week": "2026-W45",
  "status": "completed",
  "symptoms": [
    {
      "term_code": "SE_RASH",
      "severity": "moderate",
      "onset": "1_3_days",
      "known_side_effect": true,
      "possible_link_flag": false
    }
  ],
  "unanswered_questions": 0,
  "consent": { "doctor": true, "caregiver": true }
}
```

The doctor payload adds the exact date and the patient's trend and is encrypted with the doctor's key before it leaves the device. The caregiver alert carries only the event type and time.

### 14.4 How data flows in one check-in

1. The survey configuration arrives on the device (questions only, no patient data).
2. Audio is captured and turned into text on the device; the audio is deleted.
3. The local model rates the answer, re-asks if needed, and extracts coded fields.
4. The personal-data filter runs on the transcript before extraction; the transcript stays on the device.
5. The patient hears a summary and approves sharing.
6. The egress gate validates the company payload against the schema, encrypts the doctor payload if consent is on, and sends.
7. The receipt is shown: fields, destination, time and a fingerprint (hash) of each payload.
8. The Sentinel service stores the records, applies role and consent rules, and triggers any alerts.

### 14.5 How we prove it to the judges

| Proof | What the judges see |
| --- | --- |
| Egress receipt | After the check-in, the exact fields that left, field by field |
| Network log | Every outbound request with its full payload; nothing else appears |
| Schema check | A test that tries to send a free-text field and is refused by the egress gate |
| Network-off run | The check-in completes with the network disabled; the record waits and sends when back online |
| Role switcher | Company, doctor and caregiver views side by side, each showing only what it is allowed |
| Leakage test | 50 synthetic transcripts full of names and addresses produce 0 identifiers in outbound records |

### 14.6 Known limits (stated openly)

- **Re-identification from combinations.** A rare symptom, in a small cohort, in one week, could point to one person. The under-5 suppression rule reduces this; v1 adds a formal re-identification test.
- **On-device model errors.** The local model can miss or mis-code a symptom. The patient summary and approval step is the first check; doctor review is the second.
- **A compromised device** is outside what the app can protect against.
- **Hackathon shortcuts:** browser storage is not encrypted this weekend and the doctor-payload encryption is a Should; both are required for v1.

## 15. System Architecture & Tech Stack

The hackathon build is a React web app talking to a local Python "device runtime" that runs speech-to-text, a 3B open model and the personal-data filter on the laptop, plus a small Sentinel service that receives only schema-valid records. Every component runs offline except the egress gate's one send.

### 15.1 Components

&#91;embedded content: components · two laptops, one egress path\]

The browser talks only to the local runtime; the egress gate is the single path from laptop A to the Sentinel service, and the company and doctor screens read through its role and consent gate.

### 15.2 Tech stack

| Layer | Choice | Why | Fallback |
| --- | --- | --- | --- |
| Patient, company and doctor screens | React + Vite + TypeScript, Tailwind CSS, Recharts for charts | Fast to build; one app with a role switcher | Plain React without Tailwind |
| Microphone capture | Browser MediaRecorder API, audio sent only to the local runtime (localhost) | Stays on the machine | Upload of a recorded file |
| Speech-to-text | faster-whisper (small or base English model) in the device runtime | Runs offline on a laptop CPU or Apple Silicon | whisper.cpp |
| Spoken questions | Local system voices or Piper text-to-speech | Offline | Pre-recorded question audio |
| Language model | Llama 3.2 3B Instruct (or Qwen2.5 3B) served by Ollama, with JSON-schema constrained output | 3B fits a laptop and matches the Signal-to-Dose model size | A smaller 1B model for speed |
| Answer rating and re-asking | Prompted classification by the local model, plus simple rules (length, missing keywords) | Covers VC-04 to VC-06 | Rules only |
| Personal-data filter | Microsoft Presidio with spaCy, plus regular expressions, before the model extracts fields | Proven, local identifier detection | Regular expressions plus the model |
| Side-effect matching | openFDA drug-label text for the demo drugs, cached locally before the demo; a small term list mapping everyday words to label terms | No patient data involved in fetching labels | Hand-built term list |
| Egress gate | Python module with JSON Schema validation (pydantic), SHA-256 fingerprints, SQLite log | One auditable send path | Same, without the log UI |
| Doctor payload encryption | PyNaCl sealed box with the doctor's public key | Only the doctor can decrypt | Marked as a Should; skip if time runs out |
| Device runtime API | FastAPI on localhost | Simple, async, typed | Flask |
| Device storage | SQLite file on the laptop | Local, zero setup | JSON files |
| Sentinel service | FastAPI + SQLite, role and consent gate, APScheduler for missed check-in alerts | Small and fast to build | Same app, separate port |
| Document assistant (Could) | Local embeddings (nomic-embed-text via Ollama) + a small vector store over public label documents | Company documents only, cited answers | Keyword search |
| Signal-to-Dose (Could) | Within3's starter repo on the same Ollama model | Reuses the model setup | Skip |
| Synthetic data | Python script generating patients, 4 cohorts of 250, check-in history and 50 test transcripts | Realistic demo without real data | Hand-written samples |

### 15.3 Demo setup

- **Two laptops, if possible:** laptop A is the patient's device (web app + device runtime); laptop B hosts the Sentinel service and the company and doctor screens. A real network hop makes the egress log meaningful.
- **One laptop fallback:** the Sentinel service runs on a separate port; the egress log still shows every request.
- **Hardware assumption:** a recent laptop with 16 GB of memory; a 3B model in 4-bit form needs about 2 to 3 GB.

### 15.4 Privacy traps to avoid

- **Do not use the browser's built-in speech recognition** (the Web Speech API's SpeechRecognition in Chrome). In Chrome it sends audio to Google's servers, which would break the privacy promise.
- **Avoid online text-to-speech voices.** Some browser voices are generated in the cloud; use local system voices or Piper.
- **No cloud AI APIs on the patient path.** Cloud models may only be used for company-side work on public documents, and only if the team decides so.
- **No analytics or tracking scripts** in the web app.

### 15.5 Repository layout

```text
sentinel/
  web/              React app: patient, company, doctor screens
  device_runtime/   FastAPI: speech-to-text, model, filter, egress gate
  sentinel_service/ FastAPI: records, consent gate, alerts
  schema/           Published JSON schema and term lists
  data/             Synthetic patients, cohorts, test transcripts, labels
  evals/            Leakage, re-ask and side-effect tests
  docs/             README, privacy proof, demo script
```

## 16. Data Sources & Datasets

The hackathon uses only public drug data and synthetic patients; no real patient data is used anywhere. Two sources must be fetched in hour 0 because the build waits on them: the openFDA labels for the demo drugs and the Within3 starter repo.

| Dataset | Used for | Source | Real patient data? | Fetch timing |
| --- | --- | --- | --- | --- |
| Drug labels for Tagrisso (osimertinib) and Rybrevant (amivantamab) | Known side-effect lists (SE-02); company document assistant | openFDA drug label API (api.fda.gov/drug/label.json); DailyMed for full label documents | No | Hour 0, cached locally |
| FDA adverse event reports for the same drugs | Realistic side-effect mix for synthetic cohorts; building the everyday-words-to-label-terms list | openFDA adverse event API (api.fda.gov/drug/event.json) | De-identified public reports; used only in aggregate | Hour 0, cached locally |
| Within3 Signal-to-Dose package (about 2,000 unlabeled public items, labeled dev set, starter repo) | Signal-to-Dose stretch entry (SD-01 to SD-03); extra test text for side-effect extraction | Within3, via the track | No (public items) | Hour 0, only if a teammate owns the track |
| Synthetic patients | Demo personas (Walter, Priya) and the 1,000-patient cohort | Python script with generated names, ages, drugs and contacts | No | Hours 0–1 |
| Synthetic cohorts | Company dashboard: 4 drug versions x 250 patients, several weeks of check-ins | Generated from the synthetic patients and the side-effect mix | No | Hours 1–2 |
| Test transcripts (50) | Leakage, side-effect and re-ask evaluations; includes rambling, off-topic and identifier-heavy answers, each with the expected JSON | Written by the team, optionally drafted with an AI model and then checked | No | Hours 0–2 |
| Re-ask cases (20) | VC-04 to VC-06 evaluation | Written by the team | No | Hours 0–2 |
| Voice samples | Demo and speech-to-text testing, including slow speech with pauses | Team recordings and local text-to-speech | No (team voices, with consent) | Hours 1–3 |
| Everyday-words-to-label-terms list | Mapping "my nails are cracking" to a label term (SE-01) | Built by the team from label adverse-reaction sections | No | Hours 1–3 |

### 16.1 Data rules for the weekend

- No real patient records, recordings or credentialed research datasets.
- Every dataset in the repository lists its source and license in the data folder's README.
- Fetching public drug data happens before any patient flow runs, so no patient context is ever attached to an outbound request.

### 16.2 Notes for v1

- Industry side-effect terminology (MedDRA) requires a license; the hackathon uses our own term list, and v1 budgets for the license.
- Pilot data will come only from consented, enrolled patients under the drug company's program and agreements.

## 17. AI/Model Design & Evaluation

The 3B model is used only where judgment is needed (rating answers, rephrasing, extracting fields), and every output is forced into a fixed JSON shape or a fixed list of terms, so it cannot invent a symptom outside the list. Everything a patient or doctor hears or reads as a summary is built from the structured fields by templates, not written freely by the model.

### 17.1 Tasks and methods

| Task | Method | Input → output | Guardrail |
| --- | --- | --- | --- |
| Speech to text | faster-whisper, small or base English model | Audio → text | Audio deleted after; low-confidence words flagged |
| Rate the answer | Local 3B model with a JSON-schema output, plus simple rules (very short answer, no symptom words, very long answer) | Question + answer → one of complete, partial, off-topic, rambling, no answer | Temperature 0; rules can override the model |
| Re-ask | Local 3B model choosing one of three strategies: simpler words, a short list of choices, or a yes or no question | Question + rating → rephrased question | At most 2 re-asks; output must be one short question; then marked unanswered |
| Pull out the relevant part | Local 3B model | Rambling answer → the sentence or phrase that answers the question | Must quote words the patient actually said |
| Remove personal data | Presidio with spaCy, plus regular expressions; the model only sees filtered text | Transcript → transcript with identifiers replaced by placeholders | Runs before any extraction |
| Code the symptom | Local 3B model constrained to the term list (a JSON enum) | Filtered answer → symptom term codes | Cannot output a term outside the list; unknown → "other, needs review" |
| Severity and onset | Local 3B model constrained to fixed values | Answer → mild, moderate or severe; onset range | Fixed values only |
| Known side effect check | Lookup against the cached label term list | Term code → known or unlisted | Deterministic, no model |
| Possible link over time | Rule: new symptom within a set number of days of a new exposure | History → "possible link, for review" | Deterministic; never worded as a cause |
| Spoken summary for the patient | Template filled from the structured fields | Fields → short spoken summary | No free model text read to the patient |
| Doctor pre-visit summary (Could) | Template, optionally polished by the local model | Structured history → one paragraph | Every sentence traceable to a record |
| Document assistant (Could) | Retrieval over public label documents with the local model | Question → answer with cited passages | Answers only from retrieved text; says when it does not know |

### 17.2 Prompting approach

- Few-shot examples in each prompt, taken from the re-ask and transcript sets (never the test cases themselves).
- Ollama's JSON-schema output mode on every call, so responses always parse.
- Temperature 0 for rating and extraction; slightly higher only for rephrasing.
- A shared safety instruction: never give medical advice, never say a drug caused a symptom, and suggest contacting the doctor when a severe symptom is reported.

### 17.3 Evaluation plan

| Evaluation | Dataset | Metric | Target | When |
| --- | --- | --- | --- | --- |
| Personal-data leakage | 50 test transcripts, identifier-heavy | Identifiers found in outbound JSON | 0 | Every build; final run before the demo |
| Side-effect coding | 50 test transcripts with expected terms | F1 score | ≥ 0.75 | Hours 6, 9 and final |
| Answer rating | 20 re-ask cases | Correct ratings | ≥ 16 of 20 | Hours 6, 9 and final |
| Re-ask success | 20 re-ask cases, replayed with scripted follow-up answers | Resolved within 2 re-asks | ≥ 16 of 20 | Hour 9 and final |
| Schema validity | All test outputs | Records that pass the egress gate | 100% | Every build |
| Speed | 10 demo check-ins | Seconds from end of speech to reply | ≤ 3 | Final |
| Signal-to-Dose (stretch) | Within3 labeled dev set | Signal and sentiment accuracy on the dev set | Report the number; no target set | If entered |

### 17.4 When the model is unsure

- Low confidence or an "other" term marks the record "needs review" rather than guessing.
- An unanswered question is recorded as unanswered, never filled in.
- Every evaluation result, including failures, goes into the repository's evals folder and the demo video.

## 18. Regulatory & Compliance

Recommendation: **no insurer notifications** in the hackathon, v1 or by default ever; only a patient-initiated share could reach an insurer later. Sentinel positions itself as a record-and-route tool that minimizes data, not a medical device and not the company's regulatory reporting system. Its biggest compliance effect is on the buyer: records from a company-run program become side-effect reports the company must assess. This section is a planning summary from the team's general knowledge, not legal advice; every row needs confirmation by regulatory counsel before a pilot.

### 18.1 Decision: insurer notifications

| Option | Effect on patients | Effect on the pitch | Recommendation |
| --- | --- | --- | --- |
| Alert the insurer on missed check-ins | Patients fear their adherence or symptoms affect coverage or price; trust and enrollment drop | Contradicts "who can read it?" in the Privacy-First test | Reject |
| Patient-initiated share with an insurer (later) | Patient chooses, for example to support a claim | Consistent with consent-first design | Consider after v1 |
| No insurer involvement | Clear promise: insurers never see your data | Simplest, strongest privacy story | Adopt for hackathon and v1 |

### 18.2 Regulation map

| Rule | Applies when | What it asks of us | How the design responds | Hackathon status |
| --- | --- | --- | --- | --- |
| HIPAA (US health privacy law) | When Sentinel works on behalf of doctors, clinics or health plans | Business associate agreements, safeguards, minimum necessary use | On-device processing, minimal records, role and consent gate, audit logs | Synthetic data only; not applicable this weekend |
| FDA postmarketing safety reporting (21 CFR 314.80 for drugs, 21 CFR 600.80 for biologics) | Applies to the drug company once it receives side-effect information | The company must assess reports and send serious, unexpected ones to FDA on deadline | Records arrive structured and triage-ready; we never file for them | Explained in the pitch; no filing built |
| ICH E2B(R3) (international format for individual side-effect reports) | When the company loads our records into its drug-safety database | Data in a standard exchange format | Export to this format is a v1 feature | Out of scope |
| FTC Health Breach Notification Rule | Health apps outside HIPAA that hold identifiable health data | Notify users and the FTC after a breach | Identifiable data stays on the device; the server holds pseudonymous records | Noted |
| State consumer health data laws (for example, Washington's My Health My Data Act) and California privacy law | Consumer health data of residents | Consent before collection and sharing; right to delete | Consent controls (CN-01 to CN-03); deletion on the device | Consent built; deletion is v1 |
| Biometric privacy laws (for example, Illinois BIPA) | If voiceprints or other biometric identifiers are created | Written consent, retention limits | We transcribe and delete audio and create no voiceprints; future cough and tremor features need a review first | Compliant by design this weekend |
| FDA rules for software as a medical device and clinical decision support | If software diagnoses or recommends treatment | Device clearance in some cases | No diagnosis or advice; flags are marked "for review" by a clinician | Wording enforced in prompts and templates |
| GDPR (if expanding to the EU) | EU patients | Explicit consent for health data, impact assessment, data protection officer | Same minimal design; EU hosting | Not applicable |

### 18.3 What changes for the drug company

- Reports from a company-run program count as "solicited" reports. The company must review them, and serious ones related to the drug must be reported. Exact rules must be confirmed with the company's safety team.
- A valid side-effect report needs four minimum elements: an identifiable patient, an identifiable reporter, a suspect drug and a side effect. A stable pseudonymous patient ID can satisfy "identifiable" without a name.
- The company will need to ask follow-up questions. v1 adds a **follow-up relay**: the company sends a question through Sentinel, the patient answers on their device, and the company still never learns who the patient is.
- Selling point: structured, coded, triage-ready records reduce the company's processing work instead of adding to it.

### 18.4 A correction on "de-identified"

Under HIPAA's Safe Harbor method, all date elements except the year count as identifiers, so a record with an ISO week is **pseudonymized, not de-identified** in the legal sense. For v1 we either share year-level dates only, use a limited data set under a data use agreement, or obtain an expert determination. Earlier sections that say "de-identified" mean "no direct identifiers"; the Appendix glossary records this distinction.

### 18.5 Guidelines for the company document assistant

1. Answers only from the company's approved documents, with a citation to the passage used.
2. No patient data in the assistant, ever; it sees documents, not records.
3. Answers stay consistent with the approved label; it does not suggest unapproved uses.
4. It says "not found in the documents" instead of guessing.
5. Access is role-based, and every question and answer is logged.
6. A named person at the company reviews and approves the document set it uses.

### 18.6 Open questions for counsel

- Is Sentinel a business associate of the prescribing doctor, a vendor of the drug company, or both?
- Do doctor alerts on severe symptoms count as clinical decision support that needs review?
- Which date precision satisfies both the company's reporting needs and de-identification rules?

## 19. Risks, Assumptions, Dependencies, Open Questions

The two risks most likely to sink the demo are late integration between the three parallel workstreams and slow or inaccurate speech-to-text on the venue laptops. Both are handled by freezing the JSON schema in hour 1 and keeping a recorded backup run. Likelihood and impact can be changed in place as the weekend goes on.

### 19.1 Build and demo risks

| ID | Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- | --- |
| R1 | Speech-to-text is inaccurate on slow or elderly-style speech | Medium | High | Push-to-talk, a good microphone, test with the team's slow-speech recordings, fallback to recorded audio files |
| R2 | The 3B model rates answers unreliably, so re-asking misfires | Medium | High | Rules can override the model; few-shot examples; tune on the 20 re-ask cases by hour 6 |
| R3 | Replies take longer than 3 seconds on the laptop | Medium | Medium | Smaller speech model, warm up the model before the demo, keep prompts short, 1B model fallback |
| R4 | Model downloads are slow on venue Wi-Fi | Medium | High | Start downloads in hour 0; share model files between laptops by USB drive |
| R5 | The three workstreams do not fit together late in the build | High | High | JSON schema and API contracts frozen in hour 1; integration checkpoint at hour 6 of coding |
| R6 | The live demo fails on stage | Medium | High | Recorded end-to-end run as backup (the submission needs a video anyway); rehearse twice |
| R7 | Personal data slips into an outbound record | Low | High | No free-text fields in the schema; egress gate rejects non-schema payloads; leakage test on every build |
| R8 | Scope creep into the document assistant or cough detection | High | Medium | Section 11 rules: name the quadrant first, nothing new after hour 9 |
| R9 | Judges challenge medical or regulatory claims | Medium | Medium | "For review" wording, no diagnosis, Section 18 summary ready as a backup slide |
| R10 | Someone uses the browser's built-in speech recognition and audio goes to Google | Low | High | Listed in Section 15 traps; check the network log before every rehearsal |
| R11 | Signal-to-Dose pulls effort away from the flagship | Medium | Medium | Only with a dedicated owner from hour 0; dropped first at any cut-line |
| R12 | Synthetic data looks unrealistic to judges | Medium | Medium | Side-effect mix based on openFDA reports for the real demo drugs |

### 19.2 Business risks (for the startup pitch)

| ID | Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- | --- |
| B1 | Long drug-company sales cycles | High | High | Start with one paid pilot in a specialty drug program; sell through patient-support program vendors |
| B2 | Extra side-effect reports look like extra workload to the buyer | Medium | High | Structured, triage-ready records and the follow-up relay (Section 18.3) |
| B3 | Elderly patients do not keep up daily check-ins | Medium | High | Voice-first design, short check-ins, caregiver alerts; measure completion in the pilot |
| B4 | Regulatory classification changes (for example, flags treated as medical-device software) | Medium | Medium | Keep "record and route" positioning; counsel review before the pilot |

### 19.3 Assumptions

- Each laptop has about 16 GB of memory and can run a 3B model and speech-to-text together.
- A 3B model is good enough for answer rating and constrained extraction.
- Voice input works better than forms for older patients (to validate in the pilot).
- Drug companies will pay for privacy-preserving side-effect data (to validate with buyers).
- Patients in v1 have a smartphone or a caregiver who sets it up.

### 19.4 Dependencies

| Dependency | Needed for | Fallback |
| --- | --- | --- |
| Ollama and the 3B model files | Rating, re-asking, extraction | Smaller model, pre-copied files |
| faster-whisper model files | Speech-to-text | whisper.cpp, recorded transcripts |
| Presidio and spaCy language model | Personal-data filter | Regular expressions |
| openFDA API availability in hour 0 | Drug labels and side-effect mix | DailyMed label downloads |
| Within3 starter repo and data | Signal-to-Dose entry | Skip the track |
| A second laptop | Two-laptop demo with a real network hop | One laptop, separate ports |

### 19.5 Open questions (collected from earlier sections)

- Which drug-company budget owns this: drug safety, medical affairs or the brand team? (Section 6)
- Per-patient or flat per-program pricing? (Section 6)
- Is the doctor-payload encryption built this weekend or shown as a design? (Section 14)
- Business associate status, clinical decision support status and date precision. (Section 18, for counsel)
- Who presents, and who records and edits the demo video? (Section 20)

## 20. Work Breakdown & Timeline

Three parallel streams split the build by architecture: A owns the patient device and the flagship chain, B owns the Sentinel service and the company and doctor screens, and C owns data, models, side-effect logic and evaluations. Hours are counted from the start of coding (H0): hours 0–12 are coding, hours 12–24 are demo, pitch and submission. The team assigns people to streams and fills in the Owner column.

### 20.1 Timeline and gates

&#91;embedded content: 24-hour plan · 3 streams, 6 gates\]

Highlighted bars are the flagship chain (A2 to A5); every stream lands its first deliverable at H1 so the schema can freeze, and all three converge on submission by H21.

| Gate | Hour | Pass condition |
| --- | --- | --- |
| Schema frozen | H1 | JSON record format and the device-to-service API agreed and committed |
| Flagship end to end | H6 | Speak → filter → JSON → egress receipt works for one patient |
| Feature freeze | H9 | No new features start (Section 11 rule) |
| Code freeze | H12 | Only bug fixes after this point |
| Video done | H19 | Demo video recorded and edited |
| Submitted | H21 | Repository and video submitted; 3 hours of buffer before the deadline |

### 20.2 Coding tasks (H0–H12)

| Task | Stream | Hours | Work | Requirements | Done when | Owner |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | A | 0–1 | Repository skeleton, device runtime running Ollama and faster-whisper | Section 15 | A test call returns text and a model reply |  |
| A2 | A | 1–3 | Voice loop: spoken question, microphone capture, local transcription, large-text screen | VC-01, VC-02, VC-03, VC-10 | One full question-and-answer turn works offline |  |
| A3 | A | 3–5 | Personal-data filter and constrained extraction into the schema | PV-01, PV-02, PV-03 | Test transcript produces a valid record with no identifiers |  |
| A4 | A | 5–6 | Egress gate, patient approval, receipt, request log | PV-04, PV-05, PV-06, PV-08 | Gate H6 passes |  |
| A5 | A | 6–8 | Integrate answer rating, re-asking and relevant-part extraction | VC-04, VC-05, VC-06 | Rambling demo case triggers a re-ask |  |
| A6 | A | 8–10 | Spoken summary and correction, "repeat" and "slower", network-off queue | VC-07, VC-08, PV-07 | Network-off run completes |  |
| A7 | A | 10–12 | Doctor-payload encryption (Should), patient-screen accessibility polish | NF-05, NF-08 | Doctor record unreadable on the service |  |
| B1 | B | 0–1 | Sentinel service skeleton; agree the schema and API with A | Section 14 | Gate H1 passes |  |
| B2 | B | 1–3 | Records API, synthetic cohort loading, role switcher | CO-04 | Company view lists synthetic records |  |
| B3 | B | 3–5 | Consent and role gate, missed check-in scheduler, severe-symptom alerts | CN-01 to CN-03, AL-01 to AL-04 | Missed check-in alert appears within 1 minute |  |
| B4 | B | 5–8 | Doctor timeline and alert list; caregiver alert view | DR-01, DR-02, DR-03 | Timeline renders for the demo patient |  |
| B5 | B | 8–10 | Company cohort dashboard with the under-5 rule | CO-01, CO-02, NF-03 | 4 cohorts compared by drug version |  |
| B6 | B | 10–12 | Survey configuration published to devices; record export (Could) | CO-03, VC-09, CO-07 | Edited question appears on the next check-in |  |
| C1 | C | 0–1 | Fetch and cache openFDA labels and adverse event data; Within3 repo if entering | Section 16 | Files cached locally |  |
| C2 | C | 1–3 | Everyday-words-to-label-terms list; known side-effect matching; severe flags | SE-01, SE-02, SE-03 | Demo symptoms map to the right terms |  |
| C3 | C | 3–4 | Test sets: 50 transcripts, 20 re-ask cases; voice recordings | Section 16 | Test files committed |  |
| C4 | C | 4–6 | Prompts and examples for rating, re-asking and extraction; evaluation harness | Section 17 | Harness reports leakage, F1 and rating scores |  |
| C5 | C | 6–9 | Possible-link rule and patient trend; evaluation runs at H6 and H9 | SE-04, SE-05 | Link demo case shows "for review" |  |
| C6 | C | 9–12 | One Could item: document assistant, FDA report draft, or Signal-to-Dose | CO-05, CO-06, SD-01 to SD-03 | Chosen item demo-ready, or dropped at H9 |  |

### 20.3 Demo, pitch and submission tasks (H12–H24)

| Task | Stream | Hours | Work | Done when | Owner |
| --- | --- | --- | --- | --- | --- |
| A8 | A | 12–14 | Integration bug fixing; full end-to-end runs | Three clean runs in a row |  |
| A9 | A | 14–16 | Two-laptop setup, network log view, network-off proof | Proof steps work on demand |  |
| A10 | A | 16–19 | Record the demo video runs (plus a backup run) | Raw footage of a clean run |  |
| A11 | A | 19–21 | Rehearse the live demo | Two full rehearsals |  |
| B7 | B | 12–14 | Integration bug fixing on the service and screens | No open blocking bugs |  |
| B8 | B | 14–17 | Slides built on the judges' five questions, plus pricing | Slides reviewed by the team |  |
| B9 | B | 17–19 | Pitch script and timing | Script fits the time limit |  |
| B10 | B | 19–21 | Rehearse the pitch | Two full rehearsals |  |
| C7 | C | 12–14 | Final evaluation runs; results table | Results committed |  |
| C8 | C | 14–17 | README, privacy proof write-up, published schema | Repository readable by a judge in 5 minutes |  |
| C9 | C | 17–19 | Edit the demo video | Final video exported |  |
| C10 | C | 19–21 | Submit repository and video | Gate H21 passes |  |

Hours 21–24 are buffer for fixes, rest and the judging setup before hacking ends Sunday at 11:00 ET.

## 21. Demo Plan

The demo follows one story: Walter rambles, the agent re-asks, his record leaves as a handful of coded fields, and the company, doctor and caregiver each see only their part. The three wow moments are the re-ask, the egress receipt and the network-off run. The same script drives the submitted video and the live demo at judging.

### 21.1 Demo script (about 3 minutes; adjust to the time limit once known)

| Time | On screen | What we say | Proves |
| --- | --- | --- | --- |
| 0:00–0:20 | Walter's photo and a one-line problem | "Walter is 92, his hands shake, and the side effects he feels this week will never be reported." | Problem |
| 0:20–0:40 | Three panels: patient, drug company, doctor | One sentence per side: unreported symptoms, a thin and late signal, a doctor working from memory | Three-sided problem |
| 0:40–1:30 | Patient screen, live voice check-in | Walter answers the first question with a story about his grandson, then mentions a rash and cracked nails. The agent re-asks: "Is the rash mild, moderate or severe?" | Voice-first and re-ask (flagship) |
| 1:30–1:50 | Spoken summary, approval, egress receipt | "This is everything that left Walter's device: six coded fields. No audio, no words he said, no name." | What leaves |
| 1:50–2:05 | Network log, then a refused free-text payload | The gate rejects a test payload with free text | Can you prove it |
| 2:05–2:20 | Network off, check-in still completes | Record waits and sends when back online | Privacy by architecture |
| 2:20–2:45 | Role switcher: company cohort dashboard, doctor timeline, caregiver alert from a missed check-in | Each role sees only its own view | Who can read it |
| 2:45–3:00 | Pricing and close | "Drug companies pay per program and per patient. Patients talk, their data stays home." | Who pays |

### 21.2 Wow moments

1. **The re-ask:** a rambling answer becomes a clean, simple follow-up question, live.
2. **The receipt:** six coded fields on screen, next to the 40-second spoken answer they came from.
3. **The network-off run:** the check-in completes with Wi-Fi off.

### 21.3 Demo data and setup

- Persona: Walter, on a drug from cohort B (drug version v2), with 3 weeks of prior synthetic check-ins.
- Scripted spoken answers, including one rambling answer and one off-topic answer, recorded as backups.
- The company dashboard shows 4 cohorts of 250 synthetic patients; the doctor timeline shows Walter's history.
- A missed check-in for a second synthetic patient is timed to fire during the role-switcher segment.

### 21.4 Fallbacks

| If this fails | We do this |
| --- | --- |
| Microphone or speech-to-text | Play the recorded answer file into the same pipeline |
| Model too slow | Switch to the warmed-up smaller model; narrate over the pause |
| Second laptop or network | One-laptop mode on separate ports |
| Everything | Play the matching segment of the recorded video |

### 21.5 Likely judge questions

| Question | Short answer |
| --- | --- |
| Isn't this just a chatbot? | No: it is a structured check-in whose output is a fixed-schema record; the model only rates, rephrases and codes answers into a fixed list. |
| What if the model codes the wrong symptom? | The patient hears and approves the summary; unclear answers become "needs review"; doctor review follows. |
| Is the company record truly anonymous? | It has no direct identifiers; with week-level dates it is pseudonymized, and v1 uses year-level dates or a data use agreement (Section 18.4). |
| Why would a drug company pay? | It has a legal duty to monitor side effects, and today's signal is thin and late; we deliver structured, cohort-tagged records. |
| How is this different from social listening? | Social listening sees public posts; we see enrolled patients on known drug versions, privately. |
| Who is liable for alerts? | Alerts inform the caregiver and doctor; no diagnosis or advice is given; counsel review is planned. |
| What about patients without smartphones? | A caregiver can set it up; a phone-call version is on the roadmap. |
| Why do you need the doctor's view at all? | It turns the same check-in into value for care, with the patient's consent, at no extra data cost. |

## 22. Market & Competitive Landscape

Sentinel sells into pharmacovigilance (drug-safety monitoring), which research firms size at $8.6–9.35 billion in 2025, with growth forecasts from 5.6% to 14.7% a year. Our wedge is a slice incumbents do not serve well: private, continuous, patient-reported side-effect data from enrolled patients on known drug versions.

### 22.1 Market size estimates

| Research firm | 2025 size | Forecast | Annual growth |
| --- | --- | --- | --- |
| [Grand View Research](https://www.grandviewresearch.com/industry-analysis/pharmacovigilance-industry) | $8.6B | $13.5B by 2033 | 5.6% (2026–2033) |
| [Mordor Intelligence](https://www.mordorintelligence.com/industry-reports/pharmacovigilance-pv-market) | $9.35B | $18.26B by 2031 | 11.78% (2026–2031) |
| [Fortune Business Insights](https://www.fortunebusinessinsights.com/pharmacovigilance-pv-market-102746) | $9.35B | $31.56B by 2034 | 14.69% (2026–2034) |

Fortune Business Insights puts services at about 91% of the market and drug and biotech companies at about 63% of buyers in 2026, which supports billing the drug company. Estimates differ by firm; the pitch should quote the range, not one number.

### 22.2 Bottom-up view (illustrative)

At the Section 6 example of $400,000 per drug program per year, every 25 programs is about $10 million in annual revenue. The number of specialty drug programs we can reach is an open question to research before any investor conversation.

### 22.3 Where competitors sit

&#91;embedded content: positioning · data source x processing location\]

Placement is by zone, not exact position. Drug-safety databases and service providers are not shown: they process reports downstream rather than collect them from patients.

### 22.4 Competitors, partners and channels

| Category | Examples | Relationship to Sentinel |
| --- | --- | --- |
| Drug-safety databases | Oracle Argus, ArisGlobal LifeSphere | Partners: we export structured records into them |
| Drug-safety service providers | IQVIA, ICON, Accenture, Cognizant | Channel or competitor: they run case processing for drug companies and could resell Sentinel |
| Social listening | Within3 and similar vendors | Complementary: public conversation versus private enrolled-patient data; Within3 is also a track sponsor |
| Regulator reporting apps | FDA MedWatcher, Yellow Card | Not commercial competitors; show the gap in usability |
| Cloud patient apps | NowPatient | Direct alternative for patients; typed, cloud-stored, infrequent |
| Patient-support and adherence programs | Drug-company and vendor apps (category) | Channel: Sentinel can be embedded in existing programs |

Examples in the first two rows come from industry knowledge and a research-firm player list, not from a fresh review of each company's product.

### 22.5 Why now

- Small language and speech models now run offline on ordinary laptops and phones, which makes on-device processing practical.
- State consumer health data laws and the FTC's health breach rule raise the cost of holding identifiable health data in the cloud.
- Drug-safety teams are adopting AI to handle growing case volumes, so structured, machine-ready input has a buyer.
- An aging patient population needs interfaces that do not depend on fine motor control or small screens.

## 23. Go-to-Market & Pitch Narrative

The first customer is the drug-safety team of a mid-size specialty drug company, such as an oncology company with several drug versions, that already runs a patient-support program. We land with one paid pilot on one drug program and expand program by program. Patients never come from consumer marketing; they are invited through the program.

### 23.1 First customer profile

- Specialty or oncology drug with long-term use and known, trackable side effects.
- Several drug versions, doses or cohorts to compare.
- An existing patient-support program, so enrollment already happens.
- An older patient population, where voice-first matters most.
- A drug-safety or medical-affairs leader who owns a budget for real-world safety data.

### 23.2 Sales motion

1. **Find the buyer:** drug-safety and medical-affairs leaders, through advisors, the hackathon's sponsor network and patient-support program vendors.
2. **Run a paid pilot:** one drug program, a few hundred enrolled patients, 3–6 months, at a reduced pilot price.
3. **Agree success criteria up front:** daily completion of at least 70%, records usable without re-entry, and earlier signals than spontaneous reports.
4. **Expand:** more drug versions and cohorts in the same company, then a second program.
5. **Add channels:** patient-support vendors and drug-safety service providers resell or embed Sentinel.

### 23.3 How patients join

- The drug company or clinic invites enrolled patients; the doctor or a caregiver can help with setup.
- No consumer advertising and no app-store growth strategy; trust comes through the program and the doctor.
- The privacy promise is explained in one sentence at enrollment: "Your voice and words stay on your phone."

### 23.4 Pitch outline (built on the judges' five questions)

| Slide | Judge question | Message | Visual |
| --- | --- | --- | --- |
| 1 | Hook | Walter, 92, and the side effects no one hears about | Photo and one sentence |
| 2 | Problem | Three sides, one gap: unreported symptoms, a thin signal, a doctor working from memory | Section 2.4 table as three panels |
| 3 | Target user | Older patients use it, drug-safety teams pay, doctors read it | Persona strip |
| 4 | What's different | Voice-first, re-asks unclear answers, private by architecture, one check-in for three views | Section 22.3 positioning chart |
| 5 | Flagship | Live demo of the Private Check-in | Demo (Section 21) |
| 6 | Privacy proof | What leaves, who reads it, how we prove it | Egress receipt and network-off run |
| 7 | Who pays | Drug company, per program and per patient | Pricing example from Section 6 |
| 8 | Market and why now | $8.6–9.35B drug-safety market; on-device models make it possible now | Market range and why-now bullets |
| 9 | Close | Patients talk, their data stays home, and companies get the signal they must monitor | One line |

### 23.5 One-liner and 30-second pitch

**One-liner:** "Your patients talk, their data stays on their phone, and you get the side-effect signal you are legally required to monitor."

**30 seconds:** "Most side effects are never reported, and the patients who feel them, like Walter at 92, can't use forms. Sentinel is a daily voice check-in that runs entirely on the patient's device. It re-asks when an answer rambles, strips out everything personal, and sends the drug company only a handful of coded fields, with a receipt the patient can see. The doctor gets a timeline, the caregiver gets an alert, and the drug company pays per program."

### 23.6 Why this team

To be filled in by the team: each member's relevant experience (voice, on-device AI, healthcare, data privacy) in one line each.

## 24. Scaling Roadmap

Sentinel scales by adding drug programs, not servers: speech and AI run on patients' phones, so each new patient adds almost no cloud cost, and each new program is mostly configuration. The roadmap has four phases after the hackathon, each unlocked by a measurable gate. Timings are planning estimates in months from the hackathon.

### 24.1 Roadmap

&#91;embedded content: roadmap · 4 phases, 3 gates (not to scale)\]

The first paid pilot is the phase that matters most: it proves both that older patients keep up voice check-ins and that a drug company will renew.

### 24.2 What scales and what limits it

| Dimension | How it scales | What limits it | Response |
| --- | --- | --- | --- |
| Patients | Processing runs on each patient's phone; the server stores small JSON records | Older phones may be too slow for on-device models | Smaller models; a phone-call channel for patients without capable phones |
| Drug programs | Survey, label terms and cohorts are configuration | Each drug needs its side-effect term list checked | Licensed industry terminology (MedDRA) and a review workflow |
| Drug companies | Multi-tenant service with separate keys and data per company | Security reviews and procurement per company | Reusable compliance package and external audit |
| Languages | Speech and language models support many languages | Accuracy varies by language and accent | Add languages pilot by pilot, with evaluation sets per language |
| Countries | Same privacy design everywhere | Different privacy and reporting rules (GDPR, EU drug-safety rules) | Regional hosting and local regulatory review |
| Doctors | Web timeline, no installation | Hospital record-system integration | Start with a standalone view; integrate later |

### 24.3 Features added along the way

- **Phase 1:** native apps, encrypted storage, HIPAA-ready hosting, published schema, external privacy audit.
- **Phase 2:** survey builder, real text-message and push alerts, follow-up relay (Section 18.3), pilot analytics.
- **Phase 3:** export to the international side-effect report format, licensed terminology, multiple languages, clinic tier for doctors.
- **Phase 4:** EU expansion, phone-call check-ins, CRO channel, and research into cough and tremor detection after a biometric-privacy review.

## 25. Appendix

Reference material the build uses directly: plain-language definitions, the formal record schema the egress gate enforces, the starting term list for the demo drugs, a sample daily survey with re-ask wording, and the sources cited in this document.

### 25.1 Glossary

| Term | Meaning in this document |
| --- | --- |
| Side effect (adverse drug reaction) | An unwanted effect a patient experiences while taking a drug |
| Pharmacovigilance | Drug-safety monitoring: collecting, assessing and reporting side effects |
| Egress | Data leaving the patient's device |
| Egress gate | The single code path allowed to send data off the device; it enforces the schema |
| Egress receipt | What the patient sees after a send: fields, destination, time and a payload fingerprint |
| Schema | The fixed format every outbound record must match |
| Pseudonymized | Direct identifiers removed and replaced by a random ID; still personal data in law |
| De-identified (HIPAA sense) | Meets HIPAA Safe Harbor or expert determination; week-level dates do not meet Safe Harbor |
| Cohort | A group of patients on the same drug version in the same program |
| Re-ask | Asking a question again, more simply or differently, after an unclear answer |
| Flagship | The Private Check-in: voice → re-ask → filter → JSON → receipt |
| Solicited report | A side-effect report from a company-run program, which the company must assess |
| F1 score | A single accuracy number combining missed and wrong detections (1.0 is perfect) |

### 25.2 Record schema (company payload, v1.0 draft)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SentinelCompanyRecord",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "record_id", "patient_ref", "program_id", "cohort_id", "drug_version", "iso_week", "status", "symptoms", "unanswered_questions", "consent"],
  "properties": {
    "schema_version": { "const": "1.0" },
    "record_id": { "type": "string", "pattern": "^rec_[a-f0-9]{8}$" },
    "patient_ref": { "type": "string", "pattern": "^pt_[a-f0-9]{8}$" },
    "program_id": { "type": "string", "pattern": "^prog_[a-z0-9_]{1,24}$" },
    "cohort_id": { "enum": ["cohort_A", "cohort_B", "cohort_C", "cohort_D"] },
    "drug_version": { "enum": ["v1", "v2", "v3", "v4"] },
    "iso_week": { "type": "string", "pattern": "^20[0-9]{2}-W[0-5][0-9]$" },
    "status": { "enum": ["completed", "partial", "missed"] },
    "symptoms": {
      "type": "array",
      "maxItems": 10,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["term_code", "severity", "onset", "known_side_effect", "possible_link_flag"],
        "properties": {
          "term_code": { "type": "string", "pattern": "^SE_[A-Z_]{2,30}$" },
          "severity": { "enum": ["mild", "moderate", "severe"] },
          "onset": { "enum": ["today", "1_3_days", "4_7_days", "over_7_days", "unknown"] },
          "known_side_effect": { "type": "boolean" },
          "possible_link_flag": { "type": "boolean" }
        }
      }
    },
    "unanswered_questions": { "type": "integer", "minimum": 0, "maximum": 10 },
    "consent": {
      "type": "object",
      "additionalProperties": false,
      "required": ["doctor", "caregiver"],
      "properties": { "doctor": { "type": "boolean" }, "caregiver": { "type": "boolean" } }
    }
  }
}
```

The egress gate also checks every term\_code against the published term list, so the pattern above cannot carry words outside that list.

### 25.3 Starting term list for the demo drugs

Drawn from the team's knowledge of the labels; every row must be checked against the cached openFDA label text in task C2 before the demo.

| Code | Label term | Everyday words that map to it | Demo drugs |
| --- | --- | --- | --- |
| SE\_RASH | Rash | rash, spots, red skin, itchy bumps | Tagrisso, Rybrevant |
| SE\_DRY\_SKIN | Dry skin | dry, flaky, cracked skin | Tagrisso |
| SE\_PARONYCHIA | Nail infection or nail changes | sore nails, cracked nails, swollen fingertips | Tagrisso, Rybrevant |
| SE\_DIARRHEA | Diarrhea | loose stools, runny tummy | Tagrisso |
| SE\_STOMATITIS | Mouth sores | mouth ulcers, sore mouth | Tagrisso, Rybrevant |
| SE\_FATIGUE | Fatigue | tired, worn out, no energy | Tagrisso, Rybrevant |
| SE\_DECREASED\_APPETITE | Decreased appetite | not hungry, off my food | Tagrisso |
| SE\_INFUSION\_REACTION | Infusion-related reaction | felt sick during the drip, chills at infusion | Rybrevant |
| SE\_DYSPNEA | Shortness of breath | out of breath, can't catch my breath | Rybrevant; also a severe-flag trigger |
| SE\_COUGH | Cough | coughing, chesty | Rybrevant |
| SE\_EDEMA | Swelling | swollen ankles, puffy legs | Rybrevant |
| SE\_OTHER\_REVIEW | Other, needs review | anything that does not map | Both |

### 25.4 Sample daily survey with re-ask wording

| # | First ask | Re-ask 1 (simpler) | Re-ask 2 (choices or yes/no) |
| --- | --- | --- | --- |
| 1 | How have you been feeling since yesterday? | Have you felt any different in your body since yesterday? | Did you feel unwell yesterday, yes or no? |
| 2 | Have you noticed anything new on your skin or nails? | Any new rash, spots or nail changes? | Is it a rash, a nail problem, or nothing new? |
| 3 | How bad is it? | Is it mild, moderate or severe? | Is it bad enough to stop you doing things, yes or no? |
| 4 | When did it start? | Did it start today, in the last few days, or earlier? | Did it start this week, yes or no? |
| 5 | Did you take your medicine today? | Have you had your tablets or treatment today? | Yes or no? |
| 6 | Anything new you started using, eating or doing? | Any new soap, cream, food or activity? | Yes or no? |

### 25.5 Sources

- [HACK1984 tracks page](https://claudeneu.com/hackathon/#tracks), read Nov 7, 2026
- [Parracha et al., 2022, mobile apps for adverse drug reaction reporting (scoping review)](https://doi.org/10.1002/pds.5542)
- [Nature Medicine, 2015, regulators and adverse event reporting via mobile apps](https://doi.org/10.1038/nm0215-104)
- [HHS guidance on HIPAA de-identification](https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html)
- [Grand View Research, pharmacovigilance market](https://www.grandviewresearch.com/industry-analysis/pharmacovigilance-industry)
- [Mordor Intelligence, pharmacovigilance market](https://www.mordorintelligence.com/industry-reports/pharmacovigilance-pv-market)
- [Fortune Business Insights, pharmacovigilance market](https://www.fortunebusinessinsights.com/pharmacovigilance-pv-market-102746)
- [NowPatient, side-effect reporting](https://nowpatient.com/how-report-side-effects-works)

## 26. Database Schema & Data Contracts

The company-side lead owns every data definition in Sentinel: three separate databases, one per persona, plus the API contract between them. The patient and doctor layers build against this contract. No layer reads another persona's database directly; data moves only through the API, and only in the shapes defined here.

### 26.1 Ownership and ground rules

- **Owner:** the company-side lead defines and versions all schemas in the repository's `schema/` folder (SQL table definitions, JSON Schemas, `enums.json`). After the H1 freeze, any change needs the owner's approval and a version bump.
- **Shared conventions:** IDs use prefixes (`pt_` patient, `rec_` record, `prog_` program, `cohort_`, `dr_` doctor, `cg_` caregiver, `alt_` alert, `env_` envelope); times are UTC ISO 8601; every enum comes from `schema/enums.json`; every outbound payload carries `schema_version`.
- **Separation:** the company role can never read the doctor relay store; the doctor role can never read the company database; nothing outside the device can read the patient database.

| Database | Persona | Where it lives | Hackathon file | v1 | Holds direct identifiers? |
| --- | --- | --- | --- | --- | --- |
| Patient DB | Patient | Patient's device | `device_runtime/patient.db` (SQLite) | Encrypted SQLite on the phone | Yes, and they never leave the device |
| Company DB | Drug company | Sentinel service | `sentinel_service/company.db` (SQLite) | PostgreSQL, one database per company | No (pseudonymized records only) |
| Doctor DB | Doctor | Relay store on the service (encrypted only) + the doctor's browser (decrypted) | `sentinel_service/relay.db` + browser IndexedDB | Same, per clinic | Only after decryption on the doctor's machine |

### 26.2 How data moves between the three databases

&#91;embedded content: data flow · patient DB, company DB, relay store, doctor DB\]

The patient's device writes records to the company DB and encrypted envelopes to the relay store; the company reads only its views, and the doctor's browser is the only place an envelope is ever decrypted.

### 26.3 Patient DB (on the device)

Built and used by the patient layer; defined by the owner. Columns marked "local only" can never appear in the outbox.

```sql
CREATE TABLE patient_profile (
  patient_ref       TEXT PRIMARY KEY,          -- pt_xxxxxxxx, the only ID shared off-device
  display_name      TEXT NOT NULL,             -- local only
  date_of_birth     TEXT,                      -- local only
  phone             TEXT,                      -- local only
  program_id        TEXT NOT NULL,
  cohort_id         TEXT NOT NULL,
  drug_version      TEXT NOT NULL,
  doctor_id         TEXT,                      -- dr_xxxxxxxx
  doctor_public_key TEXT,                      -- used to encrypt doctor envelopes
  caregiver_id      TEXT,                      -- cg_xxxxxxxx
  enrolled_at       TEXT NOT NULL
);

CREATE TABLE consent (
  consent_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  share_doctor      INTEGER NOT NULL CHECK (share_doctor IN (0,1)),
  share_caregiver   INTEGER NOT NULL CHECK (share_caregiver IN (0,1)),
  caregiver_detail  TEXT NOT NULL CHECK (caregiver_detail IN ('alerts_only','summary')),
  updated_at        TEXT NOT NULL
);

CREATE TABLE survey_cache (
  config_id         TEXT PRIMARY KEY,
  cohort_id         TEXT NOT NULL,
  version           INTEGER NOT NULL,
  questions_json    TEXT NOT NULL,             -- questions plus re-ask wordings
  fetched_at        TEXT NOT NULL
);

CREATE TABLE term_cache (
  term_code         TEXT PRIMARY KEY,          -- SE_RASH, ...
  label_term        TEXT NOT NULL,
  everyday_words    TEXT NOT NULL,             -- JSON array
  severe_trigger    INTEGER NOT NULL CHECK (severe_trigger IN (0,1))
);

CREATE TABLE checkin_session (
  session_id        TEXT PRIMARY KEY,
  config_id         TEXT NOT NULL REFERENCES survey_cache(config_id),
  started_at        TEXT NOT NULL,
  ended_at          TEXT,
  status            TEXT NOT NULL CHECK (status IN ('completed','partial','missed'))
);

CREATE TABLE answer_turn (
  turn_id           INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id        TEXT NOT NULL REFERENCES checkin_session(session_id),
  question_id       TEXT NOT NULL,
  attempt           INTEGER NOT NULL CHECK (attempt BETWEEN 0 AND 2),  -- 0 = first ask, 1-2 = re-asks
  prompt_text       TEXT NOT NULL,
  transcript_text   TEXT,                      -- local only
  rating            TEXT CHECK (rating IN ('complete','partial','off_topic','rambling','no_answer')),
  created_at        TEXT NOT NULL
);

CREATE TABLE symptom_event (
  event_id          TEXT PRIMARY KEY,
  session_id        TEXT NOT NULL REFERENCES checkin_session(session_id),
  term_code         TEXT NOT NULL REFERENCES term_cache(term_code),
  severity          TEXT NOT NULL CHECK (severity IN ('mild','moderate','severe')),
  onset             TEXT NOT NULL CHECK (onset IN ('today','1_3_days','4_7_days','over_7_days','unknown')),
  known_side_effect INTEGER NOT NULL CHECK (known_side_effect IN (0,1)),
  possible_link_flag INTEGER NOT NULL CHECK (possible_link_flag IN (0,1)),
  patient_words     TEXT,                      -- local only
  created_at        TEXT NOT NULL
);

CREATE TABLE exposure_event (
  exposure_id       TEXT PRIMARY KEY,
  description       TEXT NOT NULL,             -- local only, e.g. new nail product
  started_on        TEXT NOT NULL
);

CREATE TABLE outbox (
  outbox_id         TEXT PRIMARY KEY,
  session_id        TEXT REFERENCES checkin_session(session_id),
  destination       TEXT NOT NULL CHECK (destination IN ('company_record','doctor_envelope','alert','consent')),
  payload           TEXT NOT NULL,             -- schema-valid JSON or encrypted envelope
  payload_sha256    TEXT NOT NULL,
  status            TEXT NOT NULL CHECK (status IN ('queued','sent','failed')),
  created_at        TEXT NOT NULL,
  sent_at           TEXT
);

CREATE TABLE egress_log (
  log_id            INTEGER PRIMARY KEY AUTOINCREMENT,
  outbox_id         TEXT NOT NULL REFERENCES outbox(outbox_id),
  method            TEXT NOT NULL,
  url               TEXT NOT NULL,
  fields_sent       TEXT NOT NULL,             -- JSON list of field names, shown on the receipt
  payload_sha256    TEXT NOT NULL,
  response_code     INTEGER,
  sent_at           TEXT NOT NULL
);
```

### 26.4 Company DB (Sentinel service, company tenant)

Built and owned by the company-side lead. Holds pseudonymized records only; dashboards read the two views, which drop any group under 5 patients.

```sql
CREATE TABLE program (
  program_id      TEXT PRIMARY KEY,
  company_id      TEXT NOT NULL,
  drug_name       TEXT NOT NULL,
  created_at      TEXT NOT NULL
);

CREATE TABLE cohort (
  cohort_id       TEXT PRIMARY KEY,
  program_id      TEXT NOT NULL REFERENCES program(program_id),
  drug_version    TEXT NOT NULL,
  label           TEXT NOT NULL,
  target_size     INTEGER
);

CREATE TABLE survey_config (
  config_id       TEXT PRIMARY KEY,
  cohort_id       TEXT NOT NULL REFERENCES cohort(cohort_id),
  version         INTEGER NOT NULL,
  questions_json  TEXT NOT NULL,
  published_at    TEXT NOT NULL,
  published_by    TEXT NOT NULL,
  UNIQUE (cohort_id, version)
);

CREATE TABLE term_code (
  term_code       TEXT PRIMARY KEY,
  label_term      TEXT NOT NULL,
  everyday_words  TEXT NOT NULL,               -- JSON array
  drug_scope      TEXT NOT NULL,               -- JSON array of drug names
  severe_trigger  INTEGER NOT NULL CHECK (severe_trigger IN (0,1))
);

CREATE TABLE enrollment (
  patient_ref     TEXT PRIMARY KEY,            -- pt_xxxxxxxx, no name or contact
  program_id      TEXT NOT NULL REFERENCES program(program_id),
  cohort_id       TEXT NOT NULL REFERENCES cohort(cohort_id),
  checkin_window  TEXT NOT NULL,               -- e.g. 09:00-12:00 local, for missed check-in detection
  active          INTEGER NOT NULL CHECK (active IN (0,1))
);

CREATE TABLE checkin_record (
  record_id            TEXT PRIMARY KEY,       -- rec_xxxxxxxx
  schema_version       TEXT NOT NULL,
  patient_ref          TEXT NOT NULL REFERENCES enrollment(patient_ref),
  program_id           TEXT NOT NULL,
  cohort_id            TEXT NOT NULL,
  drug_version         TEXT NOT NULL,
  iso_week             TEXT NOT NULL,          -- 2026-W45
  status               TEXT NOT NULL CHECK (status IN ('completed','partial','missed')),
  unanswered_questions INTEGER NOT NULL,
  consent_doctor       INTEGER NOT NULL,
  consent_caregiver    INTEGER NOT NULL,
  payload_sha256       TEXT NOT NULL,          -- matches the patient's egress receipt
  received_at          TEXT NOT NULL
);

CREATE TABLE symptom_record (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  record_id          TEXT NOT NULL REFERENCES checkin_record(record_id),
  term_code          TEXT NOT NULL REFERENCES term_code(term_code),
  severity           TEXT NOT NULL,
  onset              TEXT NOT NULL,
  known_side_effect  INTEGER NOT NULL,
  possible_link_flag INTEGER NOT NULL
);

CREATE TABLE document (                        -- document assistant (Could)
  doc_id          TEXT PRIMARY KEY,
  title           TEXT NOT NULL,
  source_url      TEXT NOT NULL,
  version         TEXT NOT NULL,
  approved_by     TEXT NOT NULL,
  approved_at     TEXT NOT NULL
);

CREATE TABLE access_log (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_role      TEXT NOT NULL,
  actor_id        TEXT NOT NULL,
  action          TEXT NOT NULL,
  object          TEXT NOT NULL,
  at              TEXT NOT NULL
);

CREATE VIEW v_cohort_weekly AS
SELECT c.program_id, c.cohort_id, c.drug_version, c.iso_week, s.term_code,
       COUNT(DISTINCT c.patient_ref) AS patients
FROM checkin_record c
JOIN symptom_record s ON s.record_id = c.record_id
GROUP BY c.program_id, c.cohort_id, c.drug_version, c.iso_week, s.term_code
HAVING COUNT(DISTINCT c.patient_ref) >= 5;     -- under-5 suppression (NF-03)

CREATE VIEW v_completion_weekly AS
SELECT program_id, cohort_id, iso_week,
       COUNT(*) AS records,
       ROUND(1.0 * SUM(status = 'completed') / COUNT(*), 3) AS completion_rate
FROM checkin_record
GROUP BY program_id, cohort_id, iso_week
HAVING COUNT(*) >= 5;
```

### 26.5 Doctor DB (relay store + doctor's browser)

The relay store on the service holds only encrypted envelopes, consent links and alerts; the company role has no access to it. The readable copy exists only in the doctor's browser after decryption. Built by the doctor layer against these definitions.

```sql
-- relay.db on the Sentinel service (doctor and caregiver roles only)
CREATE TABLE doctor (
  doctor_id       TEXT PRIMARY KEY,            -- dr_xxxxxxxx
  display_name    TEXT NOT NULL,
  clinic          TEXT,
  public_key      TEXT NOT NULL                -- patients encrypt envelopes to this key
);

CREATE TABLE care_link (
  doctor_id       TEXT NOT NULL REFERENCES doctor(doctor_id),
  patient_ref     TEXT NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('active','revoked')),
  granted_at      TEXT NOT NULL,
  revoked_at      TEXT,
  PRIMARY KEY (doctor_id, patient_ref)
);

CREATE TABLE caregiver_link (
  caregiver_id    TEXT NOT NULL,               -- cg_xxxxxxxx
  patient_ref     TEXT NOT NULL,
  detail_level    TEXT NOT NULL CHECK (detail_level IN ('alerts_only','summary')),
  status          TEXT NOT NULL CHECK (status IN ('active','revoked')),
  PRIMARY KEY (caregiver_id, patient_ref)
);

CREATE TABLE doctor_inbox (
  envelope_id     TEXT PRIMARY KEY,            -- env_xxxxxxxx
  doctor_id       TEXT NOT NULL REFERENCES doctor(doctor_id),
  patient_ref     TEXT NOT NULL,
  ciphertext      TEXT NOT NULL,               -- base64 sealed box; the service cannot decrypt it
  payload_sha256  TEXT NOT NULL,
  received_at     TEXT NOT NULL,
  fetched_at      TEXT
);

CREATE TABLE alert (
  alert_id        TEXT PRIMARY KEY,            -- alt_xxxxxxxx
  patient_ref     TEXT NOT NULL,
  alert_type      TEXT NOT NULL CHECK (alert_type IN ('missed','severe')),
  created_at      TEXT NOT NULL,
  routed_doctor   INTEGER NOT NULL,
  routed_caregiver INTEGER NOT NULL,
  acknowledged_at TEXT
);

-- doctor_view in the doctor's browser (decrypted, never sent back)
CREATE TABLE dr_patient (
  patient_ref     TEXT PRIMARY KEY,
  display_name    TEXT NOT NULL,
  drug_name       TEXT NOT NULL,
  drug_version    TEXT NOT NULL,
  last_checkin    TEXT
);

CREATE TABLE dr_timeline_entry (
  entry_id           TEXT PRIMARY KEY,
  patient_ref        TEXT NOT NULL REFERENCES dr_patient(patient_ref),
  checkin_date       TEXT NOT NULL,            -- exact date, doctor only
  term_code          TEXT NOT NULL,
  severity           TEXT NOT NULL,
  onset              TEXT NOT NULL,
  known_side_effect  INTEGER NOT NULL,
  possible_link_flag INTEGER NOT NULL,
  trend              TEXT NOT NULL CHECK (trend IN ('better','same','worse','unknown'))
);

CREATE TABLE dr_alert (
  alert_id        TEXT PRIMARY KEY,
  patient_ref     TEXT NOT NULL,
  alert_type      TEXT NOT NULL,
  created_at      TEXT NOT NULL,
  seen_at         TEXT
);
```

### 26.6 Payloads other than the company record

The company record is defined in Section 25.2. The other three payloads the patient layer sends:

```json
{
  "doctor_envelope": {
    "envelope_version": "1.0",
    "envelope_id": "env_91c2a7d4",
    "doctor_id": "dr_3a7f10b2",
    "patient_ref": "pt_4b82d0c6",
    "ciphertext": "<base64 sealed box>",
    "payload_sha256": "<hash of the plaintext>"
  },
  "doctor_plaintext_inside_the_envelope": {
    "schema_version": "1.0",
    "patient_ref": "pt_4b82d0c6",
    "display_name": "Walter",
    "drug_name": "Tagrisso",
    "drug_version": "v2",
    "checkin_date": "2026-11-07",
    "status": "completed",
    "trend": "worse",
    "symptoms": [
      { "term_code": "SE_RASH", "severity": "moderate", "onset": "1_3_days",
        "known_side_effect": true, "possible_link_flag": true }
    ]
  },
  "alert_event": {
    "alert_version": "1.0",
    "alert_id": "alt_5d0e8c11",
    "patient_ref": "pt_4b82d0c6",
    "alert_type": "severe",
    "created_at": "2026-11-07T14:05:00Z"
  },
  "consent_update": {
    "patient_ref": "pt_4b82d0c6",
    "share_doctor": true,
    "share_caregiver": true,
    "caregiver_detail": "alerts_only"
  }
}
```

### 26.7 API contract (Sentinel service)

Hackathon authentication is demo-grade: each request carries `X-Role` and `X-Actor-Id` headers. v1 replaces this with device keys for patients and single sign-on for doctors and companies.

| Endpoint | Method | Called by | Body or response | Reads or writes | Role |
| --- | --- | --- | --- | --- | --- |
| `/v1/survey?cohort_id=` | GET | Patient layer | Latest survey config for the cohort | Reads company `survey_config` | `patient_device` |
| `/v1/terms?program_id=` | GET | Patient layer | Term list | Reads company `term_code` | `patient_device` |
| `/v1/records` | POST | Patient layer (egress gate) | Company record (25.2) → `201 {record_id, payload_sha256}` | Writes `checkin_record`, `symptom_record` | `patient_device` |
| `/v1/doctor-envelopes` | POST | Patient layer (egress gate) | Doctor envelope → `201`; `403` if no active care link | Writes relay `doctor_inbox` | `patient_device` |
| `/v1/alerts` | POST | Patient layer (egress gate) | Alert event (severe) → `201` | Writes relay `alert` | `patient_device` |
| `/v1/consent/{patient_ref}` | PUT | Patient layer | Consent update → `200` | Writes relay `care_link`, `caregiver_link` | `patient_device` |
| `/v1/doctors/{doctor_id}/patients` | GET | Doctor layer | Patients with an active care link | Reads relay `care_link` | `doctor` |
| `/v1/doctors/{doctor_id}/envelopes?since=` | GET | Doctor layer | Encrypted envelopes since a time | Reads relay `doctor_inbox` | `doctor` |
| `/v1/doctors/{doctor_id}/envelopes/{envelope_id}/ack` | POST | Doctor layer | Marks an envelope fetched | Writes relay `doctor_inbox.fetched_at` | `doctor` |
| `/v1/doctors/{doctor_id}/alerts?since=` | GET | Doctor layer | Alerts for linked patients | Reads relay `alert` | `doctor` |
| `/v1/caregivers/{caregiver_id}/alerts` | GET | Caregiver view | Alerts at the allowed detail level | Reads relay `alert`, `caregiver_link` | `caregiver` |
| `/v1/company/cohorts/weekly?program_id=` | GET | Company layer | Rows of `v_cohort_weekly` | Reads company view | `company_reader` |
| `/v1/company/completion?program_id=` | GET | Company layer | Rows of `v_completion_weekly` | Reads company view | `company_reader` |
| `/v1/company/cohorts/{cohort_id}/survey` | PUT | Company layer | New survey version → `201 {config_id, version}` | Writes `survey_config` | `company_admin` |
| `/v1/company/records/export?program_id=&format=` | GET | Company layer | Pseudonymized records as JSON or CSV | Reads `checkin_record`, `symptom_record` | `company_safety` |
| /v1/doctors/{doctor\_id}/public-key | PUT | Doctor layer | Registers the doctor's public key (base64) → 200 | Writes relay doctor.public\_key | doctor |
| /v1/doctors/{doctor\_id}/public-key | GET | Patient layer | Doctor's public key; 403 without an active care link | Reads relay doctor, care\_link | patient\_device |

A scheduler inside the service is the only component that touches both stores: it reads `enrollment.checkin_window` and record arrival times from the company DB and writes `missed` alerts to the relay store. It reads patient IDs and timestamps only.

### 26.8 How each layer's agent accesses data

| Layer and agent | Reads | Writes | Never touches | How |
| --- | --- | --- | --- | --- |
| Patient layer: voice agent, filter, extractor (device runtime) | All Patient DB tables; survey and terms from the API | All Patient DB tables; outbound payloads only through the outbox and egress gate | Company DB, relay store, doctor's browser | A local repository module over `patient.db`; the egress gate is the only code with network access |
| Doctor layer: timeline and pre-visit summary | Decrypted `dr_*` tables; envelopes, alerts and patient list from the API | `dr_*` tables in the browser; envelope acknowledgements | Company DB, Patient DB, transcripts (they never leave the device) | Fetch envelopes, decrypt with the doctor's private key in the browser, store in `doctor_view` |
| Company layer: dashboards, export, document assistant | The two views, exports (safety role), `document` | `survey_config`, `document` | Relay store, Patient DB, Doctor DB | Through the company endpoints only; the document assistant sees documents, never records |

### 26.9 Access by persona

| Persona | Patient DB | Company DB | Relay store | Doctor's browser DB |
| --- | --- | --- | --- | --- |
| Patient (own device) | Read and write | Writes records only, through the API | Writes envelopes, alerts and consent, through the API | No access |
| Drug company | No access | Reads views and exports; writes survey and documents | No access | No access |
| Doctor | No access | No access | Reads own envelopes, alerts and links | Read and write (own data only) |
| Caregiver | No access | No access | Reads own alerts | No access |

### 26.10 Handover to the patient and doctor layers

- At H1 the owner commits `schema/` (this section's SQL, the JSON Schemas for all four payloads, `enums.json`) and a seed script that loads the synthetic program, 4 cohorts, 1,000 enrollments, term list and survey configs.
- The patient layer builds `patient.db` from `schema/patient.sql` and sends only the four payloads above.
- The doctor layer builds `doctor_view` from `schema/doctor_view.sql` and reads only the doctor endpoints.
- The service rejects any payload that fails its JSON Schema with `422` and logs it, so contract drift shows up immediately during integration.

### 26.11 Integration and environment setup

The owner creates the two databases on the service and publishes the contract; each teammate creates their own persona's database from the owner's schema files. Layers reach each other only through the Sentinel service's HTTP API, never through a database connection or a shared database file.

**Who creates each database**

| Database | Created by | How | When |
| --- | --- | --- | --- |
| Company DB (`company.db`) | Owner (company side) | The service applies `schema/company.sql` at startup, then the seed script loads synthetic data | H1 |
| Relay store (`relay.db`) | Owner (company side) | Same service, from `schema/relay.sql` | H1 |
| Patient DB (`patient.db`) | Patient-layer teammate | The device runtime applies `schema/patient.sql` on first launch; the owner writes the file | H1–H2 |
| Doctor DB (browser) | Doctor-layer teammate | The doctor web app creates IndexedDB stores matching `schema/doctor_view.sql` | H1–H2 |

Schema files in the repository use `CREATE TABLE IF NOT EXISTS` and record the applied version in a one-row `schema_meta` table, so running them twice is safe.

**Handover package (committed by the owner at H1)**

1. `schema/`: `company.sql`, `relay.sql`, `patient.sql`, `doctor_view.sql`, `enums.json`, JSON Schemas for the four payloads (`company_record.json`, `doctor_payload.json`, `doctor_envelope.json`, `alert_event.json`, `consent_update.json`) and `CHANGELOG.md`.
2. A stub service: every endpoint in 26.7 exists and returns realistic fake data, so both layers can build immediately. FastAPI's interactive documentation at `/docs` is the reference.
3. `schema/examples/`: one valid and one invalid example of every payload, for teammates' tests.
4. Client helpers: `clients/sentinel_client.py` for the patient runtime (`fetch_survey`, `fetch_terms`, `fetch_doctor_key`, `send_record`, `send_envelope`, `send_alert`, `send_consent`) and TypeScript types generated from the API documentation for the doctor web app.
5. Seed data: the synthetic program, 4 cohorts, 1,000 enrollments, the term list, survey configurations, the demo doctor and caregiver, and an active care link for Walter.

**Environments**

| Environment | Where the service runs | Base URL | Used for |
| --- | --- | --- | --- |
| Local | Each teammate's own laptop, from the repository | `http://127.0.0.1:8000` | Day-to-day building against the stub, then the real service |
| Integration | The owner's laptop, reached over a phone hotspot | `http://<owner-hotspot-IP>:8000` | Joint runs, the H6 checkpoint |
| Demo | Laptop B (Section 15.3) | Set on the day | Video recording and judging |

Start command for any teammate: `python -m sentinel_service.seed && uvicorn sentinel_service.main:app --port 8000`. Venue Wi-Fi often blocks traffic between laptops, so the hotspot is tested in hour 1.

**Configuration (environment variables, never committed)**

| Variable | Layer | Example |
| --- | --- | --- |
| `SENTINEL_BASE_URL` | Patient, doctor | `http://127.0.0.1:8000` |
| `SENTINEL_ROLE` | Patient, doctor | `patient_device` or `doctor` |
| `SENTINEL_ACTOR_ID` | Patient, doctor | `pt_4b82d0c6` or `dr_3a7f10b2` |
| `PATIENT_DB_PATH` | Patient | `device_runtime/patient.db` |
| `SENTINEL_BIND_HOST` | Service | `127.0.0.1` locally; `0.0.0.0` only on the hotspot |
| `SENTINEL_ALLOWED_ORIGINS` | Service | The patient and doctor web app origins only |

**Integration timeline**

| Hour | Owner delivers | Teammates do |
| --- | --- | --- |
| H1 | Handover package and stub service | Build against the stub; apply their schema files |
| H3 | Real `/v1/records`, `/v1/survey`, `/v1/terms` | Patient layer switches from stub to real for records |
| H5 | Real relay endpoints and the missed check-in scheduler | Doctor layer switches to real envelopes and alerts |
| H6 | Integration run on the hotspot | Run the 26.15 checklist together |

**Schema change protocol (after the H1 freeze)**

1. The teammate requests the change from the owner with the reason; no one edits `schema/` except the owner.
2. The owner decides, bumps `schema_version` (1.0 → 1.1 for an added optional field; 2.0 for anything that breaks existing payloads), updates `CHANGELOG.md` and the examples.
3. The owner tells both teammates in the team chat with the commit link; the service accepts both versions until the next integration run.
4. No schema changes after H9 (feature freeze).

### 26.12 Data security protocols (every layer)

These rules are mandatory for all three layers and for every coding agent working on them; breaking any rule in the "Never" column is a blocking bug, fixed before any other work.

| Area | Always | Never |
| --- | --- | --- |
| Data | Use synthetic patients and team-recorded voices only | Load real patient data, or paste any patient-like data into a cloud AI tool, including coding assistants |
| Repository | Ignore `*.db`, `*.sqlite`, `.env`, `keys/` and recordings in `.gitignore` | Commit database files, keys, `.env` files or audio |
| Secrets | Keep keys and settings in environment variables or local key files | Hard-code keys, base URLs with credentials, or tokens in code |
| Network | Send patient-side data only through the egress gate and only to the endpoints in 26.7 | Call any other host from the patient side; add analytics, tracking or error-reporting services |
| Speech | Use the local speech-to-text model | Use the browser's SpeechRecognition API or any cloud speech service |
| Payloads | Validate against the JSON Schema before sending (client) and on receipt (service) | Add fields, send free text, or let the service "repair" an invalid payload |
| Logging | Log IDs, roles, status codes, field names and hashes | Log transcripts, patient words, names, decrypted doctor payloads or full request bodies on the service |
| Keys | Generate the doctor key pair in the doctor's browser; send only the public key | Send, export or store the doctor's private key anywhere else |
| Access | Check role and actor on every service endpoint; actor IDs must match the IDs in the URL | Trust a client's claim about who it is beyond the demo headers; open a direct database connection across layers |
| Exposure | Bind the service to `127.0.0.1` except during hotspot integration; restrict CORS to the two web apps | Expose the service on venue Wi-Fi or the public internet |
| Transport | Use plain HTTP only on localhost and the team hotspot (demo-grade) | Present HTTP as production-ready; v1 requires TLS 1.2+ |
| Reset | Wipe all databases with `scripts/reset_all.sh` before the demo and after the event | Keep demo databases on personal laptops after the event |

If any layer finds a way for personal data to leave a device, stop, tell the owner, and add a test case to the leakage evaluation before fixing it.

### 26.13 Shared contract rules

All three layers implement these rules identically; a mismatch here (especially in hashing) breaks the egress receipt and the privacy proof.

**Canonical JSON and hashing.** Every `payload_sha256` is SHA-256 over the canonical JSON of the payload, hex-encoded in lowercase. For the doctor envelope, the hash is over the plaintext before encryption.

```python
import hashlib, json

def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def payload_sha256(payload: dict) -> str:
    return hashlib.sha256(canonical(payload)).hexdigest()
```

The TypeScript side must produce byte-identical output; the owner ships a shared test vector in `schema/examples/hash_vectors.json` that both sides must pass.

**Encryption.** Doctor payloads use a libsodium sealed box (PyNaCl `SealedBox` on the patient side, `libsodium-wrappers` `crypto_box_seal_open` in the doctor's browser) with the doctor's X25519 public key; ciphertext and keys are base64 (standard alphabet).

**Headers.** Every request carries `X-Role` and `X-Actor-Id` (patient: the `pt_` ID; doctor: the `dr_` ID; company: a user ID). Every response carries `X-Schema-Version`.

**Idempotency.** Clients create IDs (`rec_`, `env_`, `alt_`) before sending and reuse them on retry. Re-sending the same ID with the same hash returns `200` with the original result; the same ID with a different hash returns `409`.

**Error codes**

| Code | Meaning | Client action |
| --- | --- | --- |
| 201 | Created | Mark the outbox item sent; write the receipt |
| 200 | Already received (same ID, same hash) | Treat as sent |
| 401 | Missing role or actor headers | Fix configuration; do not retry blindly |
| 403 | Role not allowed, actor does not match the URL, or no active care link or consent | Do not retry; surface to the user or developer |
| 409 | Same ID with a different payload | Stop; this is a bug, report it to the owner |
| 422 | Payload failed schema validation; the body names the failing field | Do not retry; fix the code that built the payload |
| 5xx or no network | Service or network problem | Keep it in the outbox; retry with backoff (2, 4, 8, up to 60 seconds) |

**Time and paging.** All timestamps are UTC ISO 8601 with a `Z`. `?since=` takes a timestamp and returns items received strictly after it, oldest first, at most 100 per call; clients keep the newest timestamp they have seen.

### 26.14 Instructions for each teammate's coding agent

Each brief below is ready to paste into the agent instruction file at the root of that layer's folder (for example `AGENTS.md` or `CLAUDE.md`). Every brief points to `schema/` as the single source of truth, so agents never invent fields, tables or endpoints.

**Patient layer brief** (`device_runtime/` and `web/patient/`)

```markdown
# Sentinel patient layer: agent instructions

## Your job
Build the patient's on-device check-in: voice questions, local speech-to-text, answer rating and re-asking,
personal-data filtering, extraction into coded fields, and sending ONLY schema-valid payloads through the egress gate.

## Source of truth
- `schema/` is owned by the company-side lead. Read it; never edit it. Request changes from the owner.
- Create `patient.db` by applying `schema/patient.sql` on first launch. Do not add, rename or drop tables or columns.
- Payload shapes: `schema/company_record.json`, `doctor_payload.json`, `doctor_envelope.json`,
  `alert_event.json`, `consent_update.json`. Enums: `schema/enums.json`.

## How to connect
- Base URL from `SENTINEL_BASE_URL`; send headers `X-Role: patient_device` and `X-Actor-Id: <patient_ref>`.
- Use `clients/sentinel_client.py`. Allowed calls only:
  GET /v1/survey, GET /v1/terms, GET /v1/doctors/{id}/public-key,
  POST /v1/records, POST /v1/doctor-envelopes, POST /v1/alerts, PUT /v1/consent/{patient_ref}.

## Always
- Route every outbound byte through `device_runtime/egress_gate.py`. It is the ONLY module allowed to import an HTTP library.
- Validate each payload against its JSON Schema, write it to `outbox`, compute `payload_sha256` with the canonical
  JSON rule in Section 26.13, send, then write `egress_log` (field names + hash) and show the receipt.
- Encrypt doctor payloads with a sealed box to the doctor's public key, and only when consent and a care link are active.
- Create record, envelope and alert IDs before sending; reuse them on retry. Keep failed sends in the outbox and retry with backoff.
- Make the check-in work with the network off.
- Run the leakage evaluation before every commit.

## Never
- Never send `transcript_text`, `patient_words`, `display_name`, `date_of_birth`, `phone`, exposure descriptions or audio
  anywhere. They are local only.
- Never add free-text fields to a payload, or any field not in the schema.
- Never use the browser's SpeechRecognition API, cloud speech, cloud AI APIs, analytics or error-reporting services.
- Never read or write `company.db`, `relay.db` or the doctor's browser storage.
- Never log transcripts or patient words outside `patient.db`.

## Done when
- A check-in produces a record that passes `/v1/records` with 201, the receipt hash matches the service's, and the
  network log shows only the allowed calls.
```

**Doctor layer brief** (`web/doctor/`)

```markdown
# Sentinel doctor layer: agent instructions

## Your job
Build the doctor's view: consented patient list, symptom timeline, alerts and an optional pre-visit summary,
from encrypted envelopes that only the doctor's browser can decrypt.

## Source of truth
- `schema/` is owned by the company-side lead. Read it; never edit it. Request changes from the owner.
- Create IndexedDB stores `dr_patient`, `dr_timeline_entry`, `dr_alert` matching `schema/doctor_view.sql` exactly.
- Decrypted payloads must validate against `schema/doctor_payload.json`.

## How to connect
- Base URL from configuration; send headers `X-Role: doctor` and `X-Actor-Id: <doctor_id>`.
- Use the generated TypeScript types. Allowed calls only:
  PUT /v1/doctors/{id}/public-key, GET /v1/doctors/{id}/patients, GET /v1/doctors/{id}/envelopes?since=,
  POST /v1/doctors/{id}/envelopes/{envelope_id}/ack, GET /v1/doctors/{id}/alerts?since=.

## Always
- On first launch, generate an X25519 key pair in the browser with libsodium-wrappers; keep the private key in
  IndexedDB; register only the public key.
- For each envelope: decrypt with crypto_box_seal_open, recompute the SHA-256 of the canonical JSON
  (sorted keys, no spaces, UTF-8; pass `schema/examples/hash_vectors.json`), reject it if the hash or schema check
  fails, upsert into the dr_* stores, then POST the ack.
- Show only patients with an active care link; show "possible link" flags as "for review".

## Never
- Never send decrypted data, or anything derived from it, back to the service or to any other host.
- Never export, log or transmit the private key.
- Never call `/v1/company/*` endpoints or read `company.db`, `relay.db` or `patient.db`.
- Never use cloud AI APIs on decrypted data; the pre-visit summary uses templates or the local model only.
- Never log decrypted payload contents to the console or any service.

## Done when
- Walter's envelopes decrypt, pass hash and schema checks, render on the timeline, and alerts appear within 1 minute.
```

**Service layer brief** (`sentinel_service/`, owner)

```markdown
# Sentinel service: agent instructions

## Your job
Run the company DB, the relay store, the API in Section 26.7 and the missed check-in scheduler.

## Always
- Apply `schema/company.sql` and `schema/relay.sql` at startup; keep them in separate SQLite files.
- Validate every incoming payload against its JSON Schema (`additionalProperties: false`); return 422 naming the field.
- Recompute `payload_sha256` on receipt and store it; enforce idempotency (same ID + same hash = 200; different hash = 409).
- Enforce role and actor on every endpoint; actor IDs must match path IDs; refuse doctor envelopes without an active care link.
- Company endpoints read only `v_cohort_weekly`, `v_completion_weekly`, exports for `company_safety`, and `document`.
- Write an `access_log` row for every company read and export.
- Bind to 127.0.0.1 unless `SENTINEL_BIND_HOST` says otherwise; restrict CORS to `SENTINEL_ALLOWED_ORIGINS`.

## Never
- Never give a company role any path to `relay.db`.
- Never decrypt doctor envelopes or store doctor private keys.
- Never log request bodies; log IDs, roles, status codes and hashes only.
- Never auto-correct an invalid payload, and never accept unknown fields.
```

### 26.15 Integration verification checklist

Run together at the H6 integration checkpoint and again before the H12 code freeze; every item must pass before the demo is recorded. Tick items as they pass.

**Contract**

- [ ] Patient and doctor layers both pass `schema/examples/hash_vectors.json` (identical SHA-256 output)
- [ ] Every valid example in `schema/examples/` is accepted (201); every invalid example is rejected (422) with the failing field named
- [ ] Re-sending the same record ID with the same payload returns 200; with a changed payload returns 409
- [ ] The receipt hash on the patient screen equals `payload_sha256` stored in `checkin_record`

**Access control**

- [ ] A company role cannot reach any relay endpoint (403)
- [ ] A doctor cannot read another doctor's envelopes, or any patient without an active care link (403)
- [ ] A patient cannot send an envelope to a doctor without an active care link (403)
- [ ] Revoking consent stops the next envelope from being accepted

**Privacy**

- [ ] Leakage evaluation: 0 identifiers across the 50 test transcripts in every outbound payload
- [ ] Network log during a full check-in shows only the allowed patient-side calls
- [ ] The service log contains no request bodies, transcripts or names
- [ ] The relay store holds only ciphertext in `doctor_inbox`; the service cannot decrypt it
- [ ] Cohort views return no group smaller than 5 patients
- [ ] Network-off check-in completes and sends when back online

**End to end**

- [ ] Walter's check-in appears in the company dashboard (aggregated) and the doctor timeline (decrypted) within 1 minute
- [ ] A missed check-in produces an alert for the doctor and the caregiver within 1 minute
- [ ] A severe symptom produces an immediate alert
- [ ] `scripts/reset_all.sh` wipes all four databases and the seed script restores the demo state
