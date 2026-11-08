"""Consent switches (CN-01, CN-03): "Share with my doctor" and "Share with my caregiver".

A change is saved on this device first, as a new `consent` row, in the same transaction that queues the full consent
update for the service. From that moment the device acts on it, even offline: approval reads the latest row, so
turning the care team off means no new care envelope, no pending one is sealed, and the company record says
`consent.care_team: false`. The update itself then goes out through the egress gate (`PUT /v1/consent/{ref}`), which
revokes or restores the links on the service; the retry worker resends it if the network is off.

Nothing here sends: `egress_gate.send_queued` does, called by the PUT /consent route.
"""

from __future__ import annotations

from contextlib import closing
from pathlib import Path

from . import egress_gate
from .db import connect, utc_now

SWITCHES = ("share_care_team", "share_caregiver")


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
    receipt = egress_gate.latest_consent_receipt(db_path, base_url=base_url)
    return {"share_care_team": bool(consent["share_care_team"]), "share_caregiver": bool(consent["share_caregiver"]),
            "has_care_team": profile["care_org_id"] is not None, "has_caregiver": profile["caregiver_id"] is not None,
            "receipt": None if receipt is None else receipt.to_dict()}


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
