# Doctor evals

Doctor-side checks from Scoping Doc 26.15 on contract 2.x, run against a live service over HTTP. No database files are read; only check names, status codes, IDs and timings are printed or saved.

```bash
# from the repo root, service running and seeded (docs/INTEGRATION_STATUS.md)
uv run --project packages/contract-py python evals/doctor/access_checks.py          # print results
uv run --project packages/contract-py python evals/doctor/access_checks.py --write  # also save to results/
```

| Section | Checks |
|---|---|
| Access control | Company role gets 403 on all 11 doctor, org and caregiver endpoints · doctors outside an org can't read it · members can't fetch each other's key grants · non-admins can't set the org key or add members · no link means no envelope · missing headers get 401 · revoking consent stops the next envelope · doctor change (add, grant, read, revoke → 403, grant gone) · the emergency hospital has no routine access · emergency access needs a coded reason and an emergency link |
| Privacy | The relay returns ciphertext only · caregiver alerts carry no symptom details (AL-03) |
| End to end | Envelope reaches the care team within 1 minute · ack · severe alert reaches care team and caregiver · emergency access releases the history and notifies caregiver and care team · decrypt + hash match (only with throwaway org keys) |

- If Northgate and Lakeside already have keys from the doctor web app, the script seals to them and skips the decrypt checks. Otherwise it registers throwaway org keys: reseed before a demo.
- The revoke check restores Walter's consent; the doctor-change check uses Dr. Rivera and leaves her revoked, as in the seed.
- The missed check-in check is not written yet (the scheduler exists since D-074).

Results are committed in `results/`, failures included.
