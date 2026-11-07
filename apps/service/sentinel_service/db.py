"""SQLite files for the service: company.db and relay.db, kept separate (Scoping Doc 26.1, 26.9).

Location: $SERVICE_DATA_DIR, default <repo>/var/service (D-031). Schema files are applied on every open
(they are idempotent) and the contract version is recorded in schema_meta.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from sentinel_contract import CONTRACT_VERSION, SCHEMA_DIR

from .common import now_iso

REPO_ROOT = Path(__file__).resolve().parents[3]


def default_data_dir() -> Path:
    return Path(os.environ.get("SERVICE_DATA_DIR") or REPO_ROOT / "var" / "service")


def connect(path: Path, schema_file: str) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)  # explicit transactions only
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript((SCHEMA_DIR / schema_file).read_text())
    conn.execute(
        "INSERT INTO schema_meta (id, schema_version, applied_at) VALUES (1, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET schema_version = excluded.schema_version, applied_at = excluded.applied_at",
        (CONTRACT_VERSION, now_iso()),
    )
    return conn


class Databases:
    """The two connections plus one lock: requests run in a thread pool and SQLite connections are shared."""

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.company = connect(self.data_dir / "company.db", "company.sql")
        self.relay = connect(self.data_dir / "relay.db", "relay.sql")
        self.lock = threading.RLock()

    @contextmanager
    def tx(self, *conns: sqlite3.Connection):
        """One transaction across the given connections. Each is committed or rolled back with the others."""
        with self.lock:
            for c in conns:
                c.execute("BEGIN IMMEDIATE")
            try:
                yield
            except BaseException:
                for c in conns:
                    c.execute("ROLLBACK")
                raise
            for c in conns:
                c.execute("COMMIT")

    def close(self) -> None:
        self.company.close()
        self.relay.close()
