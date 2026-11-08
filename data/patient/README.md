# Patient data

Synthetic test data for the patient runtime. No real patient data (Scoping Doc 16.1).

## `leakage_transcripts.json`

Ten spoken check-in answers, written to be heavy with personal identifiers, each labelled with the identifiers it contains and the symptoms a correct extraction should return. Used by the leakage evaluation (`evals/patient/leakage_eval.py`, PV-01) and as extra term-coding cases (SE-01).

| | |
| --- | --- |
| Source | Hand-written for this project. No real people: names, streets, towns, hospitals, clinics and pharmacies are invented; a few real city names appear as place names with nobody attached. Phone numbers use the fictional 555-01xx range; emails use the reserved `example.com` and `example.org` domains. |
| Licence | MIT, the repository licence (`LICENSE`). |
| Contract | `schema_version` 2.0; `reporter`, `term_code`, `severity` and `onset` come from `schema/enums.json`. |

### Format

```json
{"schema_version": "2.0", "source": "...", "transcripts": [
  {"id": "lk_01", "reporter": "self", "transcript": "...",
   "identifiers": [{"type": "NAME", "value": "..."}],
   "expected": {"symptoms": [{"term_code": "SE_RASH", "severity": "moderate", "onset": "1_3_days"}]}}
]}
```

| Field | Meaning |
| --- | --- |
| `id` | `lk_` plus two digits, unique |
| `reporter` | who is speaking: `self`, `parent`, `caregiver` or `other` (enum `reporter`) |
| `transcript` | the answer as speech-to-text would write it |
| `identifiers` | every identifier in the transcript; `type` is one of `NAME`, `ADDRESS`, `PHONE`, `EMAIL`, `DATE_OF_BIRTH`, `PLACE` (cities, towns, hospitals, clinics, pharmacies); `value` is copied verbatim from the transcript |
| `expected.symptoms` | one entry per distinct symptom the patient has: `term_code` (enum `term_code`), `severity` (`mild`, `moderate`, `severe`, or `null` when not stated), `onset` (enum `onset`) |

### Labelling rules
- A negated symptom ("no rash") is not expected. A symptom off the term list is `SE_OTHER_REVIEW` (D-015).
- Severity is labelled only when the speaker states it; otherwise `null`.
- Onset: "this morning" `today`; "yesterday", "two days ago", "a couple of days ago", "the last three days" `1_3_days`; "four days ago", "five days", "for about a week", "since last week" `4_7_days`; "three weeks" `over_7_days`; not remembered `unknown`.
- Each form of an identifier that appears is listed separately (for example a full name and a nickname).

### Cases

| id | reporter | identifier types | expected terms |
| --- | --- | --- | --- |
| lk_01 | self | NAME, ADDRESS, PHONE, PLACE x2 | SE_RASH |
| lk_02 | parent (baby) | NAME x2, DATE_OF_BIRTH, EMAIL, PLACE x2 | SE_DIARRHEA, SE_DECREASED_APPETITE |
| lk_03 | caregiver (older patient) | NAME x2, DATE_OF_BIRTH, ADDRESS, PHONE, PLACE x2 | SE_EDEMA, SE_DYSPNEA |
| lk_04 | self | NAME, DATE_OF_BIRTH, ADDRESS, EMAIL, PLACE x2 | none |
| lk_05 | self | NAME x2, DATE_OF_BIRTH, ADDRESS, PHONE, PLACE | SE_OTHER_REVIEW (headaches) |
| lk_06 | self | NAME, PHONE, EMAIL, PLACE x2 | SE_DRY_SKIN, SE_PARONYCHIA ("no rash") |
| lk_07 | parent (child) | NAME, DATE_OF_BIRTH, ADDRESS, PHONE, PLACE | SE_STOMATITIS, SE_FATIGUE |
| lk_08 | self | NAME x2, DATE_OF_BIRTH, EMAIL, PLACE x2 | SE_INFUSION_REACTION, SE_COUGH |
| lk_09 | other (neighbour) | NAME x2, ADDRESS, PHONE, PLACE | SE_DIARRHEA |
| lk_10 | self | NAME x2, DATE_OF_BIRTH, ADDRESS, PHONE, EMAIL, PLACE x2 | SE_FATIGUE, SE_DECREASED_APPETITE |

59 identifiers in all (NAME 16, PLACE 17, ADDRESS 7, PHONE 7, DATE_OF_BIRTH 7, EMAIL 5); 15 expected symptoms covering all 12 term codes.

### Adding a case
1. Write a new entry with the next `lk_` id. Invent everything: no real person, a 555-01xx phone, an `example.com` or `example.org` email, made-up streets and facilities.
2. List every identifier with its exact text from the transcript, and label the expected symptoms with the rules above.
3. Run `uv run --project apps/patient-runtime pytest -q evals/patient` from the repository root. The dataset tests check ids, enums, that every value appears in its transcript and that all six identifier types are covered. They also pin the case count at 10, so update `test_dataset_shape` in `evals/patient/test_leakage_eval.py` when adding cases.

## `reask_cases.json`

Twenty spoken answers to the example survey's questions (`schema/examples/survey_config.valid.json`, q1 to q6), each labelled with the rating a correct rater gives it. Used by the answer-rating evaluation (`evals/patient/reask_eval.py`, VC-04, with VC-06 extraction reported). Scoping Doc 17.3 "Re-ask cases (20)".

| | |
| --- | --- |
| Source | Hand-written for this project, without running the rater. No real people: the few names are invented (the filter redacts them before rating). |
| Licence | MIT, the repository licence (`LICENSE`). |
| Contract | `expected_rating` from enum `answer_rating`; `question_id` and `ask` index into the example survey, whose `purpose` values cover enum `question_purpose`. |

### Format

```json
{"schema_version": "2.0", "source": "...", "survey": "schema/examples/survey_config.valid.json", "cases": [
  {"id": "rq_02", "question_id": "q2", "ask": 0, "style": "slow", "answer": "...",
   "expected_rating": "rambling", "expected_relevant": ["..."], "expected_not_relevant": ["..."]}
]}
```

| Field | Meaning |
| --- | --- |
| `id` | `rq_` plus two digits, unique |
| `question_id`, `ask` | the question and which of its three wordings (`asks[0..2]`, D-017) was spoken; ask 1 and 2 are the re-asks |
| `style` | `slow` for Walter-style halting speech (pauses written as "...", fillers), else `plain` |
| `answer` | the answer as speech-to-text would write it; `""` is silence |
| `expected_rating` | `complete`, `partial`, `off_topic`, `rambling` or `no_answer` |
| `expected_relevant` | phrases, copied verbatim from the answer, that answer the question; empty for `off_topic` and `no_answer`. Scored only for `rambling` cases: each must be in the rater's `relevant_text` |
| `expected_not_relevant` | `rambling` cases only: off-topic phrases that must not be in `relevant_text` |

### Labelling rules
- `complete`: answers what this wording asks, however short ("Yes." to "Yes or no?").
- `partial`: on the question but too vague or incomplete to fill the field (no severity word, "some of them", "not today, before that").
- `off_topic`: short and about something else entirely.
- `rambling`: long, mostly about something else, with the answer buried inside.
- `no_answer`: silence, fillers only, or asking to hear the question again.
- Phrases never contain a name or place, so redaction cannot remove them.

### Cases

| id | question (purpose) | ask | style | expected |
| --- | --- | --- | --- | --- |
| rq_01 | q1 wellbeing | 0 | plain | complete |
| rq_02 | q2 symptom_screen | 0 | slow | rambling (demo: grandson story, then rash and cracked nails) |
| rq_03 | q3 severity | 1 | slow | partial |
| rq_04 | q4 onset | 0 | slow | complete |
| rq_05 | q5 adherence | 1 | plain | partial |
| rq_06 | q6 exposure | 2 | plain | off_topic |
| rq_07 | q1 wellbeing | 1 | slow | off_topic |
| rq_08 | q1 wellbeing | 2 | slow | no_answer |
| rq_09 | q4 onset | 2 | plain | no_answer (silence) |
| rq_10 | q6 exposure | 1 | plain | no_answer |
| rq_11 | q3 severity | 0 | slow | rambling |
| rq_12 | q4 onset | 1 | slow | rambling |
| rq_13 | q5 adherence | 0 | slow | rambling |
| rq_14 | q6 exposure | 0 | plain | rambling |
| rq_15 | q2 symptom_screen | 2 | plain | complete |
| rq_16 | q3 severity | 2 | plain | complete |
| rq_17 | q5 adherence | 2 | plain | complete |
| rq_18 | q2 symptom_screen | 1 | plain | partial |
| rq_19 | q4 onset | 1 | plain | partial |
| rq_20 | q5 adherence | 2 | slow | off_topic |

Ratings: complete 5, rambling 5, partial 4, off_topic 3, no_answer 3. Asks: 0 x6, 1 x7, 2 x7. Nine `slow` cases.

### Adding a case
Use the next `rq_` id and the labelling rules above, then run `uv run --project apps/patient-runtime pytest -q evals/patient`. The dataset tests pin the count at 20 (the VC-04 target is 16 of 20), so change `test_dataset_shape` in `evals/patient/test_reask_eval.py` and `VC04_CASES` if the set grows.
