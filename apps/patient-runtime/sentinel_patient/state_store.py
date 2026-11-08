"""Small local state files that must survive a runtime restart, next to the database under var/patient/.

The schema is the contract and has no table for a check-in in progress or for retry timing, so they live in JSON
files beside `patient.db`, in the same local-only class of storage: owner-read/write only, written atomically
(temporary file, fsync, rename), never logged, never sent. A missing or unreadable file reads as None.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class JsonFile:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> Any | None:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as e:  # never the content: it may hold local-only words
            log.error("state file %s unreadable (%s); starting without it", self.path.name, type(e).__name__)
            return None

    def save(self, data: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=f".{self.path.name}.")
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def delete(self) -> None:
        self.path.unlink(missing_ok=True)
