"""Shared fixtures: every test gets its own SQLite files in a temp directory."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from sentinel_service.main import app
from sentinel_service.seed import seed
from sentinel_service.store import SqliteStore

TODAY = date(2026, 11, 7)  # Saturday of 2026-W45, the demo day


@pytest.fixture()
def store(tmp_path):
    """Demo people only (schema/demo_fixtures.json), no synthetic patients or history."""
    s = SqliteStore.open(tmp_path)
    seed(s.db, patients_per_cohort=0, weeks=0, today=TODAY)
    yield s
    s.close()


@pytest.fixture()
def c(store):
    app.state.store = store
    with TestClient(app) as client:
        yield client
    app.state.store = None


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    """Small but realistic history: 40 patients per cohort over 2 weeks."""
    s = SqliteStore.open(tmp_path_factory.mktemp("seeded"))
    summary = seed(s.db, patients_per_cohort=40, weeks=2, today=TODAY)
    yield s, summary
    s.close()
