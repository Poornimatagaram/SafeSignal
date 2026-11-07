# Sentinel service

- **Owner:** Company side · **Package:** `sentinel_service` · **Port:** 8000
- **Runtime data:** `var/service/company.db`, `var/service/relay.db` (Step 2; the stub is in memory today)
- **Run:** `uv sync && uv run uvicorn sentinel_service.main:app --port 8000` · **Test:** `uv run pytest -q`
