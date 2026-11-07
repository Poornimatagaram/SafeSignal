# Patient runtime (on-device)

- **Owner:** Patient side (see `CODEOWNERS`)
- **Package name:** `sentinel_patient`
- **Port:** 8001
- **Runtime data:** `var/patient/patient.db` from `schema/patient.sql`
- **Contract:** read `schema/`; never edit it. Hashing and types come from `packages/` (see the root README).
- **Agent brief:** Scoping Doc 26.14, Patient layer brief. Paths in that brief map to this repo as: `device_runtime/` → `apps/patient-runtime/`; `clients/sentinel_client.py` → `from sentinel_contract.client import SentinelClient`; `device_runtime/egress_gate.py` → `apps/patient-runtime/sentinel_patient/egress_gate.py`.

Structure inside this folder is up to its owner.
