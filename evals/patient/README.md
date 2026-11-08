# Patient evaluations

## Leakage (PV-01): `leakage_eval.py`

Checks that no personal identifier reaches the coded output the patient runtime builds its outbound record from (Scoping Doc 12.2 PV-01, 17.3). Dataset: `data/patient/leakage_transcripts.json` (10 synthetic, identifier-heavy check-in answers; see `data/patient/README.md`).

For each case the harness runs the real pipeline:
1. `redact(transcript)` from `sentinel_patient.filter` gives the filtered text.
2. `extract_symptoms(filtered_text)` from `sentinel_patient.extract` gives the coded symptoms; the output is `json.dumps` of them.
3. Every labelled identifier of the case is looked for in the output and, separately, in the filtered text.

An identifier counts as found when:
- its whole value appears, ignoring case (all types);
- NAME: any part of 3 or more letters appears as a whole word ("Delacroix-Meyer" checks "Delacroix" and "Meyer");
- PHONE: its last 7 digits appear in a run of 7 or more digits, whatever the separators ("218-555-0142" matches "2185550142" and "555 0142").

The output is enum-only today, so the check mainly guards against a future free-text field.

### Metrics
| Metric | Role |
| --- | --- |
| Output leaks: identifiers found in the extraction output | **Pass/fail.** PASS = 0 across all cases and every case produced output. |
| Filter residuals: identifiers still in the filtered text, by type | Reported only. The stronger check of the filter itself. |
| Term match: extracted vs expected term codes, micro precision, recall and F1 over distinct codes per case | Reported only (SE-01 target F1 0.75). |

A case where the extractor raises `ExtractionError` produced no output, so its leak check did not really run: it is counted under `extraction_errors` and the run fails.

### Run
From the repository root, with Ollama running and the model pulled:

```bash
uv run --project apps/patient-runtime python evals/patient/leakage_eval.py            # writes evals/patient/results/leakage_results.json
uv run --project apps/patient-runtime python evals/patient/leakage_eval.py --out /tmp/x.json --data path/to/cases.json
uv run --project apps/patient-runtime pytest -q evals/patient                          # harness and dataset tests, no model needed
```

The model name recorded in the results comes from `PATIENT_OLLAMA_MODEL` (default `llama3.2:3b`).

| Exit code | Meaning |
| --- | --- |
| 0 | Pass |
| 1 | Fail: an identifier reached the output, or a case raised `ExtractionError` |
| 2 | The runtime could not be imported or the model is unavailable (`ExtractionUnavailable`). Nothing was evaluated and no results file is written, so a pass is never reported for a run where the model did not run. |

### Results file
`evals/patient/results/leakage_results.json` (or `--out`):
- `run_at_utc`, `model`, `dataset` and its `dataset_sha256`, `pass_rule`, `pass`;
- `totals`: case and identifier counts (by type), `output_leaks` and `filter_residuals` (total and by type), `extraction_errors`, and `term_match` (tp, fp, fn, precision, recall, F1, target);
- `cases[]`: `id`, `reporter`, `status`, `identifiers` (count), `output_leaks` and `filter_residuals` as `{count, types}` (one type entry per identifier found), `expected_terms`, `extracted_terms`, `term_match`.

The file and the printed summary contain only case ids, identifier types, counts and term codes: never transcript text or identifier values (project rule: never log patient words, kept even for synthetic data). An extracted term code that is not in `schema/enums.json` is written as `INVALID`.

Results from real runs are committed here, failures included (`evals/README.md`, Scoping Doc 17.4).
