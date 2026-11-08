"""Demo controls for the Sentinel service (Scoping Doc 21.3; D-076). Operates on the service's company.db directly;
safe to run while the service is up (SQLite WAL).

    python -m sentinel_service.demo close-window pt_9c1d2e3f --in 60   # today's window closes in ~60 s
    python -m sentinel_service.demo run-scheduler                      # run one scheduler pass now
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .scheduler import due_days, run_missed_checks
from .store import SqliteStore


def close_window(store: SqliteStore, patient_ref: str, seconds: int, now: datetime | None = None) -> str:
    """Set the patient's window to [now - 60 min, now + seconds], rounded to whole minutes (UTC)."""
    now = now or datetime.now(timezone.utc)
    start = (now - timedelta(minutes=60)).replace(second=0, microsecond=0)
    end = (now + timedelta(seconds=seconds + 59)).replace(second=0, microsecond=0)
    window = f"{start:%H:%M}-{end:%H:%M}"
    c = store.db.company
    row = c.execute("SELECT e.start_date, e.cohort_id FROM enrollment e WHERE e.patient_ref = ?",
                    (patient_ref,)).fetchone()
    if row is None:
        raise SystemExit(f"unknown patient {patient_ref}")
    with store.db.tx(c):
        c.execute("UPDATE enrollment SET checkin_window = ? WHERE patient_ref = ?", (window, patient_ref))
    return window


def main() -> None:
    ap = argparse.ArgumentParser(description="Demo controls for the Sentinel service")
    ap.add_argument("--data-dir", type=Path, default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    cw = sub.add_parser("close-window", help="make today's check-in window for a patient close soon")
    cw.add_argument("patient_ref")
    cw.add_argument("--in", dest="seconds", type=int, default=60)
    sub.add_parser("run-scheduler", help="run one missed check-in scheduler pass now")
    args = ap.parse_args()

    store = SqliteStore.open(args.data_dir)
    try:
        if args.cmd == "close-window":
            window = close_window(store, args.patient_ref, args.seconds)
            today = datetime.now(timezone.utc).date()
            start = store.db.company.execute("SELECT start_date FROM enrollment WHERE patient_ref = ?",
                                             (args.patient_ref,)).fetchone()[0]
            print(f"{args.patient_ref}: window set to {window} UTC; if no check-in arrives, the scheduler raises the "
                  f"missed alert within one interval after it closes.")
            if not due_days(datetime.fromisoformat(start).date(), 1, today, today):
                print("warning: today is before the patient's start date")
        else:
            for item in run_missed_checks(store):
                print(f"missed {item['patient_ref']} {item['day']} level {item['escalation_level']} "
                      f"-> {', '.join(item['notified'])}")
    finally:
        store.close()


if __name__ == "__main__":
    main()
