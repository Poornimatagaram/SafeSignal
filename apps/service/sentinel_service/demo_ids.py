"""Demo IDs, loaded from schema/demo_fixtures.json (the single source shared with all apps; D-033)."""

import json

from sentinel_contract import SCHEMA_DIR

_F = json.loads((SCHEMA_DIR / "demo_fixtures.json").read_text())

PROGRAM_ID = _F["program"]["program_id"]
COMPANY_ID = _F["program"]["company_id"]
DRUG_NAME = _F["program"]["drug_name"]

COHORTS = {c["cohort_id"]: c["drug_version"] for c in _F["cohorts"]}  # D-006: records must match

_profiles = {p["display_name"]: p["patient_ref"] for p in _F["device_profiles"]}
WALTER = _profiles["Walter"]   # demo patient, cohort_B / v2
PRIYA = _profiles["Priya"]     # second patient; her missed check-in fires during the role-switcher segment
ANNA = _F["caregivers"][0]["caregiver_id"]

_orgs = {o["display_name"]: o["org_id"] for o in _F["organizations"]}
NORTHGATE = _orgs["Northgate Medical Center"]      # care team for Walter and Priya
LAKESIDE = _orgs["Lakeside Emergency Hospital"]    # Walter's emergency hospital

_doctors = {d["display_name"]: d["doctor_id"] for d in _F["doctors"]}
DR_SHAH = _doctors["Dr. Shah"]      # Northgate attending
DR_PATEL = _doctors["Dr. Patel"]    # Northgate admin
DR_RIVERA = _doctors["Dr. Rivera"]  # not a member yet: joins during the doctor-change demo
DR_OKAFOR = _doctors["Dr. Okafor"]  # Lakeside admin (emergency access)

_users = {u["role"]: u["user_id"] for u in _F["company_users"]}
DR_LEE = _users["company_safety"]
MARCO = _users["company_reader"]
ADMIN = _users["company_admin"]

ENROLLMENTS = _F["enrollments"]
ORGANIZATIONS = _F["organizations"]
DOCTORS = _F["doctors"]
ORG_MEMBERS = _F["org_members"]
CARE_LINKS = _F["care_links"]
CAREGIVER_LINKS = _F["caregiver_links"]
EMERGENCY_CONTACTS = _F["emergency_contacts"]
DEVICE_PROFILES = _F["device_profiles"]
