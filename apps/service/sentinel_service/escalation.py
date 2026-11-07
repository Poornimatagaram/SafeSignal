"""Who is notified for each alert (contract 2.0; D-060, D-068). One implementation for the API, the seed and the
missed check-in scheduler, so the recipients never differ between them.

| Alert | Recipients |
| --- | --- |
| missed, level 1 | patient, caregiver, care team |
| missed, level 2 | same (urgent) |
| missed, level 3 | same + every consented emergency contact |
| severe | caregiver, care team |
| emergency_access | caregiver, care team (someone opened the record in an emergency) |

Only active links count. Emergency contacts exist only with emergency consent (D-067).
"""

from __future__ import annotations

import sqlite3


def recipients(relay: sqlite3.Connection, patient_ref: str, alert_type: str,
               level: int | None = None) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if alert_type == "missed":
        out.append(("patient", patient_ref))
    out += [("caregiver", r[0]) for r in relay.execute(
        "SELECT caregiver_id FROM caregiver_link WHERE patient_ref = ? AND status = 'active' ORDER BY caregiver_id",
        (patient_ref,))]
    out += [("care_team", r[0]) for r in relay.execute(
        "SELECT org_id FROM care_link WHERE patient_ref = ? AND link_type = 'care_team' AND status = 'active' "
        "ORDER BY org_id", (patient_ref,))]
    if alert_type == "missed" and level is not None and level >= 3:
        out += [("emergency_contact", r[0]) for r in relay.execute(
            "SELECT contact_id FROM emergency_contact WHERE patient_ref = ? ORDER BY priority, contact_id",
            (patient_ref,))]
    return out


def record_deliveries(relay: sqlite3.Connection, alert_id: str, targets: list[tuple[str, str]], at: str) -> None:
    relay.executemany(
        "INSERT OR IGNORE INTO alert_delivery (alert_id, recipient_type, recipient_id, channel, delivered_at) "
        "VALUES (?, ?, ?, 'in_app', ?)", [(alert_id, t, rid, at) for t, rid in targets])
