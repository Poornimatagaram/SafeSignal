"""Regenerate schema/examples/ (valid + invalid payloads) and hash_vectors.json.

Run from the repo root: uv run --project packages/contract-py python scripts/build_examples.py
Owner-only: examples are part of the contract; regenerate and commit after any schema change.
"""

from __future__ import annotations

import base64
import copy
import json

from sentinel_contract import SCHEMA_DIR, canonical, payload_sha256, validation_errors

OUT = SCHEMA_DIR / "examples"

WALTER = "pt_4b82d0c6"
DR_SHAH = "dr_3a7f10b2"
ANNA = "cg_7e21c9a4"

company_record = {
    "schema_version": "1.0",
    "record_id": "rec_7f3c9a1e",
    "patient_ref": WALTER,
    "program_id": "prog_demo_01",
    "cohort_id": "cohort_B",
    "drug_version": "v2",
    "iso_week": "2026-W45",
    "status": "completed",
    "symptoms": [
        {"term_code": "SE_RASH", "severity": "moderate", "onset": "1_3_days",
         "known_side_effect": True, "possible_link_flag": True},
        {"term_code": "SE_PARONYCHIA", "severity": "mild", "onset": "4_7_days",
         "known_side_effect": True, "possible_link_flag": False},
    ],
    "unanswered_questions": 0,
    "consent": {"doctor": True, "caregiver": True},
}

doctor_payload = {
    "schema_version": "1.0",
    "patient_ref": WALTER,
    "display_name": "Walter",
    "drug_name": "Tagrisso",
    "drug_version": "v2",
    "checkin_date": "2026-11-07",
    "status": "completed",
    "trend": "worse",
    "symptoms": [
        {"term_code": "SE_RASH", "severity": "moderate", "onset": "1_3_days",
         "known_side_effect": True, "possible_link_flag": True},
    ],
}

# Placeholder ciphertext: real envelopes carry a libsodium sealed box. Shape-valid only.
fake_ciphertext = base64.b64encode(b"SEALED-BOX-PLACEHOLDER-" + canonical(doctor_payload)[:80]).decode()

doctor_envelope = {
    "schema_version": "1.0",
    "envelope_id": "env_91c2a7d4",
    "doctor_id": DR_SHAH,
    "patient_ref": WALTER,
    "ciphertext": fake_ciphertext,
    "payload_sha256": payload_sha256(doctor_payload),
}

alert_event = {
    "schema_version": "1.0",
    "alert_id": "alt_5d0e8c11",
    "patient_ref": WALTER,
    "alert_type": "severe",
    "created_at": "2026-11-07T14:05:00Z",
}

consent_update = {
    "schema_version": "1.0",
    "patient_ref": WALTER,
    "doctor_id": DR_SHAH,
    "caregiver_id": ANNA,
    "share_doctor": True,
    "share_caregiver": True,
    "caregiver_detail": "alerts_only",
}

survey_config = {
    "questions": [
        {"question_id": "q1", "purpose": "wellbeing", "asks": [
            "How have you been feeling since yesterday?",
            "Have you felt any different in your body since yesterday?",
            "Did you feel unwell yesterday, yes or no?"]},
        {"question_id": "q2", "purpose": "symptom_screen", "asks": [
            "Have you noticed anything new on your skin or nails?",
            "Any new rash, spots or nail changes?",
            "Is it a rash, a nail problem, or nothing new?"]},
        {"question_id": "q3", "purpose": "severity", "asks": [
            "How bad is it?",
            "Is it mild, moderate or severe?",
            "Is it bad enough to stop you doing things, yes or no?"]},
        {"question_id": "q4", "purpose": "onset", "asks": [
            "When did it start?",
            "Did it start today, in the last few days, or earlier?",
            "Did it start this week, yes or no?"]},
        {"question_id": "q5", "purpose": "adherence", "asks": [
            "Did you take your medicine today?",
            "Have you had your tablets or treatment today?",
            "Yes or no?"]},
        {"question_id": "q6", "purpose": "exposure", "asks": [
            "Anything new you started using, eating or doing?",
            "Any new soap, cream, food or activity?",
            "Yes or no?"]},
    ]
}


def mutate(base: dict, fn) -> dict:
    d = copy.deepcopy(base)
    fn(d)
    return d


VALID = {
    "company_record": company_record,
    "doctor_payload": doctor_payload,
    "doctor_envelope": doctor_envelope,
    "alert_event": alert_event,
    "consent_update": consent_update,
    "survey_config": survey_config,
}

# Each invalid example breaks exactly one rule and names the field the service must report.
INVALID = {
    "company_record": (
        mutate(company_record, lambda d: d.update(notes="my grandson visited and I got a rash")),
        "/notes",
        "Free-text field: the egress-gate refusal shown in the demo",
    ),
    "doctor_payload": (
        mutate(doctor_payload, lambda d: d.update(transcript_text="Well, my grandson...")),
        "/transcript_text",
        "Transcript must never leave the device, even encrypted",
    ),
    "doctor_envelope": (
        mutate(doctor_envelope, lambda d: d.update(ciphertext="not base64 !!")),
        "/ciphertext",
        "Ciphertext must be standard base64",
    ),
    "alert_event": (
        mutate(alert_event, lambda d: d.update(alert_type="missed")),
        "/alert_type",
        "Devices may only send 'severe'; 'missed' is created by the service scheduler",
    ),
    "consent_update": (
        mutate(consent_update, lambda d: d.pop("caregiver_detail")),
        "/caregiver_detail",
        "Required field missing",
    ),
    "survey_config": (
        mutate(survey_config, lambda d: d["questions"][0]["asks"].pop()),
        "/questions/0/asks",
        "Every question needs exactly 3 asks (first ask + 2 re-asks)",
    ),
}

HASH_VECTORS = [
    ("flat_sorted_keys", {"b": 1, "a": 2}),
    ("nested_objects_and_arrays", {"z": [3, 1, {"y": True, "x": None}], "a": {"d": False, "c": "s"}}),
    ("unicode_kept_raw", {"name": "Zoë", "city": "Malmö", "emoji": "💊"}),
    ("escapes", {"q": "quote\" back\\ slash", "nl": "line1\nline2", "tab": "a\tb"}),
    ("empty_containers", {"arr": [], "obj": {}}),
    ("integers", {"n": 0, "neg": -7, "big": 1000000}),
    ("company_record_example", company_record),
    ("doctor_payload_example", doctor_payload),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for kind, payload in VALID.items():
        errs = validation_errors(kind, payload)
        assert not errs, f"valid example for {kind} fails: {errs}"
        (OUT / f"{kind}.valid.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    for kind, (payload, field, why) in INVALID.items():
        errs = validation_errors(kind, payload)
        fields = [e["field"] for e in errs]
        assert field in fields, f"invalid example for {kind} should fail on {field}, got {errs}"
        doc = {"_expect": {"status": 422, "field": field, "why": why}, "payload": payload}
        (OUT / f"{kind}.invalid.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    vectors = [
        {"name": name, "input": obj, "canonical": canonical(obj).decode("utf-8"), "sha256": payload_sha256(obj)}
        for name, obj in HASH_VECTORS
    ]
    (OUT / "hash_vectors.json").write_text(json.dumps(
        {"rule": "SHA-256 over JSON with keys sorted recursively, separators ',' and ':', no whitespace, "
                 "UTF-8, non-ASCII not escaped; lowercase hex", "vectors": vectors},
        indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {len(VALID)} valid, {len(INVALID)} invalid examples and {len(vectors)} hash vectors to {OUT}")


if __name__ == "__main__":
    main()
