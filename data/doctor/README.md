# Doctor data

Synthetic generators only (Scoping Doc 16.1). Nothing here is real patient data.

| File | What | Run |
| --- | --- | --- |
| `send_demo_history.py` | A fixed synthetic 3-week check-in history for Walter (rash starting mild and worsening, diarrhea, nail changes, some days answered by his caregiver, one item for review) and Priya (fatigue easing, a cough). Acts as each patient's device and seals envelopes to the care-team key, plus Walter's emergency hospital if its key exists. | After Dr. Patel creates the Northgate key in the doctor web app: `uv run --project packages/contract-py python data/doctor/send_demo_history.py` |

- Safe to re-run: envelope IDs come from patient, organization and date; an already-sent day returns 409 and is skipped.
- For emergency access, create Lakeside's key (Dr. Okafor) before running, so Walter's history is also sealed to Lakeside.
- Prints only counts and status codes.
