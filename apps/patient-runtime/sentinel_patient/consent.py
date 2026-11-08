"""Consent switches (CN-01, CN-03): "Share with my doctor" and "Share with my caregiver".

A change is saved on this device first, as a new `consent` row, in the same transaction that queues the full consent
update for the service. From that moment the device acts on it, even offline: approval reads the latest row, so
turning the care team off means no new care envelope, no pending one is sealed, and the company record says
`consent.care_team: false`. The update itself then goes out through the egress gate (`PUT /v1/consent/{ref}`), which
revokes or restores the links on the service; the retry worker resends it if the network is off.

Setup (CN-01): `setup` replaces the whole choice at once: the care-team organization, the caregiver and the detail
they get, and (only with emergency consent) emergency hospitals and up to 3 emergency contacts. The choices come from
`options()`, the synthetic demo directory in schema/demo_fixtures.json: the service has no organization directory a
patient device can read. Contact labels ("Anna (daughter)") stay on this device; phones leave only inside the consent
update, and only with emergency consent.

Nothing here sends: `egress_gate.send_queued` does, called by the PUT /consent and PUT /consent/setup routes.
"""

from __future__ import annotations

import json
import re
import secrets
from contextlib import closing
from pathlib import Path

from . import egress_gate
from .db import DEMO_FIXTURES, connect, utc_now

SWITCHES = ("share_care_team", "share_caregiver")
CONTACT_TYPES = ("emergency_service", "hospital", "person")
DETAILS = ("alerts_only", "summary")
PHONE = re.compile(r"^(\+[1-9][0-9]{6,14}|[0-9]{3})$")  # schema/consent_update.json
MAX_LABEL = 40


class NoRecipient(ValueError):
    """Sharing can't be turned on: no care team (or caregiver) is set up on this device."""


def _current(conn, patient_ref: str):
    profile = conn.execute("SELECT care_org_id, caregiver_id FROM patient_profile WHERE patient_ref = ?",
                           (patient_ref,)).fetchone()
    consent = conn.execute("SELECT * FROM consent ORDER BY consent_id DESC LIMIT 1").fetchone()
    if profile is None or consent is None:
        raise LookupError("no profile or consent on this device")
    return profile, consent


def state(db_path: Path, patient_ref: str, *, base_url: str = "") -> dict:
    """The two switches, whether each can be on, and the receipt of the latest consent update (or None)."""
    with closing(connect(db_path)) as conn:
        profile, consent = _current(conn, patient_ref)
        orgs = [r["org_id"] for r in conn.execute("SELECT org_id FROM emergency_org ORDER BY org_id")]
        contacts = [{"contact_id": r["contact_id"], "contact_type": r["contact_type"], "phone": r["phone"],
                     "org_id": r["org_id"], "priority": r["priority"], "label": r["display_label"]}
                    for r in conn.execute("SELECT * FROM emergency_contact ORDER BY priority, contact_id")]
    receipt = egress_gate.latest_consent_receipt(db_path, base_url=base_url)
    emergency = bool(consent["emergency_consent"])
    return {"share_care_team": bool(consent["share_care_team"]), "share_caregiver": bool(consent["share_caregiver"]),
            "has_care_team": profile["care_org_id"] is not None, "has_caregiver": profile["caregiver_id"] is not None,
            "receipt": None if receipt is None else receipt.to_dict(),
            "setup": {"care_org_id": profile["care_org_id"], "caregiver_id": profile["caregiver_id"],
                      "caregiver_detail": consent["caregiver_detail"], "emergency_consent": emergency,
                      "emergency_org_ids": orgs if emergency else [], "emergency_contacts": contacts if emergency else []},
            "options": options(patient_ref)}


def options(patient_ref: str) -> dict:
    """Organizations and this patient's caregivers to choose from (synthetic demo directory)."""
    fixtures = json.loads(DEMO_FIXTURES.read_text())
    return {"organizations": [{k: o[k] for k in ("org_id", "display_name", "org_type")}
                              for o in fixtures.get("organizations", [])],
            "caregivers": [{"caregiver_id": c["caregiver_id"], "display_name": c["display_name"]}
                           for c in fixtures.get("caregivers", []) if c.get("patient_ref") == patient_ref]}


def setup(db_path: Path, patient_ref: str, choice: dict) -> str:
    """Replace the whole consent choice and queue the consent update; returns its outbox_id.

    Raises ValueError with a plain message (never quoting a phone or label) when the choice is not allowed.
    """
    opts = options(patient_ref)
    org_ids = {o["org_id"] for o in opts["organizations"]}
    caregiver_ids = {c["caregiver_id"] for c in opts["caregivers"]}
    care_org, caregiver = choice.get("care_org_id"), choice.get("caregiver_id")
    share_care, share_cg = choice.get("share_care_team"), choice.get("share_caregiver")
    detail, emergency = choice.get("caregiver_detail", "alerts_only"), choice.get("emergency_consent")
    if not all(isinstance(v, bool) for v in (share_care, share_cg, emergency)):
        raise ValueError("each sharing choice is yes or no")
    if care_org is not None and care_org not in org_ids:
        raise ValueError("unknown care team")
    if caregiver is not None and caregiver not in caregiver_ids:
        raise ValueError("unknown caregiver")
    if share_care and care_org is None:
        raise NoRecipient("choose a care team before sharing with it")
    if share_cg and caregiver is None:
        raise NoRecipient("choose a caregiver before sharing with them")
    if detail not in DETAILS:
        raise ValueError("caregiver detail is alerts only or a summary")
    hospitals = list(choice.get("emergency_org_ids") or []) if emergency else []
    contacts = list(choice.get("emergency_contacts") or []) if emergency else []
    if len(hospitals) > 3 or len(set(hospitals)) != len(hospitals) or not set(hospitals) <= org_ids:
        raise ValueError("choose up to 3 different emergency hospitals")
    if care_org is not None and care_org in hospitals:
        raise ValueError("your care team can't also be your emergency hospital")
    if len(contacts) > 3:
        raise ValueError("up to 3 emergency contacts")
    rows = []
    for c in contacts:
        if not isinstance(c, dict) or c.get("contact_type") not in CONTACT_TYPES:
            raise ValueError("each contact is an emergency service, a hospital or a person")
        if not isinstance(c.get("phone"), str) or not PHONE.fullmatch(c["phone"]):
            raise ValueError("a phone number must start with + and have 7 to 15 digits, or be a 3-digit "
                             "emergency number like 911")
        if c.get("org_id") is not None and c["org_id"] not in org_ids:
            raise ValueError("unknown hospital for a contact")
        if type(c.get("priority")) is not int or not 1 <= c["priority"] <= 3:
            raise ValueError("contact order is 1, 2 or 3")
        label = c.get("label")
        if label is not None and (not isinstance(label, str) or len(label) > MAX_LABEL):
            raise ValueError(f"a contact name is at most {MAX_LABEL} characters")
        rows.append(("ec_" + secrets.token_hex(4), c["contact_type"], c["phone"], c.get("org_id"), c["priority"],
                     (label or "").strip() or None))
    if len({r[4] for r in rows}) != len(rows):
        raise ValueError("each contact needs its own place in the order")

    with closing(connect(db_path)) as conn, conn:
        profile, _ = _current(conn, patient_ref)
        if profile["care_org_id"] != care_org:  # a new care team: its key is fetched fresh before sealing
            conn.execute("UPDATE patient_profile SET care_org_id = ?, care_org_public_key = NULL "
                         "WHERE patient_ref = ?", (care_org, patient_ref))
        conn.execute("UPDATE patient_profile SET caregiver_id = ? WHERE patient_ref = ?", (caregiver, patient_ref))
        conn.execute("INSERT INTO consent (share_care_team, emergency_consent, share_caregiver, caregiver_detail, "
                     "updated_at) VALUES (?, ?, ?, ?, ?)",
                     (int(share_care), int(emergency), int(share_cg), detail, utc_now()))
        conn.execute("DELETE FROM emergency_contact")  # replaced as a set, like the service (D-067)
        kept = {r["org_id"]: r["public_key"] for r in conn.execute("SELECT org_id, public_key FROM emergency_org")}
        conn.execute("DELETE FROM emergency_org")
        conn.executemany("INSERT INTO emergency_org (org_id, public_key) VALUES (?, ?)",
                         [(o, kept.get(o)) for o in hospitals])
        conn.executemany("INSERT INTO emergency_contact (contact_id, contact_type, phone, org_id, priority, "
                         "display_label) VALUES (?, ?, ?, ?, ?, ?)", rows)
        return egress_gate.queue_consent_update(conn, patient_ref)


def change(db_path: Path, patient_ref: str, *, share_care_team: bool | None = None,
           share_caregiver: bool | None = None) -> str | None:
    """Save the change and queue the consent update; returns its outbox_id, or None if nothing changed."""
    wanted = {"share_care_team": share_care_team, "share_caregiver": share_caregiver}
    wanted = {k: v for k, v in wanted.items() if v is not None}
    if not wanted:
        raise ValueError("say which sharing to change")
    if not all(isinstance(v, bool) for v in wanted.values()):
        raise ValueError("sharing is on or off")
    with closing(connect(db_path)) as conn, conn:
        profile, consent = _current(conn, patient_ref)
        if wanted.get("share_care_team") and profile["care_org_id"] is None:
            raise NoRecipient("no care team is set up on this device")
        if wanted.get("share_caregiver") and profile["caregiver_id"] is None:
            raise NoRecipient("no caregiver is set up on this device")
        if all(bool(consent[k]) == v for k, v in wanted.items()):
            return None
        new = {k: int(wanted.get(k, consent[k])) for k in SWITCHES}
        conn.execute("INSERT INTO consent (share_care_team, emergency_consent, share_caregiver, caregiver_detail, "
                     "updated_at) VALUES (?, ?, ?, ?, ?)",
                     (new["share_care_team"], consent["emergency_consent"], new["share_caregiver"],
                      consent["caregiver_detail"], utc_now()))
        return egress_gate.queue_consent_update(conn, patient_ref)
