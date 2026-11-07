"""Fixed IDs for the demo personas (Scoping Doc 3, 21.3). Shared by the stub, the seed script and tests."""

PROGRAM_ID = "prog_demo_01"
COMPANY_ID = "co_demo"
DRUG_NAME = "Tagrisso"

COHORTS = {  # cohort_id -> drug_version (D-006: records must match)
    "cohort_A": "v1",
    "cohort_B": "v2",
    "cohort_C": "v3",
    "cohort_D": "v4",
}

WALTER = "pt_4b82d0c6"   # demo patient, cohort_B / v2
PRIYA = "pt_9c1d2e3f"    # second patient; her missed check-in fires during the role-switcher segment
DR_SHAH = "dr_3a7f10b2"
ANNA = "cg_7e21c9a4"     # Walter's caregiver

DR_LEE = "usr_dr_lee"    # company_safety
MARCO = "usr_marco"      # company_reader
ADMIN = "usr_admin"      # company_admin
