# Sentinel service

- **Owner:** Company side · **Package:** `sentinel_service` · **Port:** 8000
- **Runtime data:** `var/service/company.db`, `var/service/relay.db` (or `$SERVICE_DATA_DIR`)
- **Run:** `uv sync && uv run python -m sentinel_service.seed && uv run uvicorn sentinel_service.main:app --port 8000` · **Test:** `uv run pytest -q`
