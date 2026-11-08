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
