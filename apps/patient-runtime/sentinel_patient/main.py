"""Patient runtime API on localhost:8001. Only patient-web (localhost:5173) calls it.

Run: uv run uvicorn sentinel_patient.main:app --port 8001   (uvicorn binds 127.0.0.1 by default; keep it that way)

Logs carry method, path and status only, never request bodies, transcripts or patient words (26.12).
This module makes no outbound calls: every outbound byte goes through egress_gate.
"""

from __future__ import annotations

from contextlib import asynccontextmanager, closing

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sentinel_contract import SCHEMA_VERSION

from .config import Settings
from .db import connect, init_db


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        init_db(settings.db_path, settings.patient_ref)
        yield

    app = FastAPI(title="Sentinel patient runtime", version=SCHEMA_VERSION, lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins,
                       allow_methods=["GET", "POST", "PUT"], allow_headers=["Content-Type"])

    @app.get("/health")
    def health() -> dict:
        """Local checks only (no network): the database opens and holds this device's profile."""
        with closing(connect(settings.db_path)) as conn:
            meta = conn.execute("SELECT schema_version FROM schema_meta WHERE id = 1").fetchone()
            profile = conn.execute("SELECT 1 FROM patient_profile WHERE patient_ref = ?",
                                   (settings.patient_ref,)).fetchone()
        return {
            "status": "ok",
            "schema_version": meta["schema_version"] if meta else None,
            "patient_ref": settings.patient_ref,
            "profile_loaded": profile is not None,
        }

    return app


app = create_app()
