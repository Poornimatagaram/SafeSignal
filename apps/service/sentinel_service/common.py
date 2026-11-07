"""Helpers shared by the store, the seed and the API."""

from __future__ import annotations

from datetime import datetime, timezone

from sentinel_contract import validation_errors

from .errors import ApiError, unprocessable

PAGE_SIZE = 100  # Scoping Doc 26.13: at most 100 items per `since` call
TS_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"  # D-054: microseconds so server timestamps sort and page correctly


def fmt_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(TS_FORMAT)


def now_iso() -> str:
    return fmt_ts(datetime.now(timezone.utc))


def normalize_since(since: str | None) -> str | None:
    """Accept any ISO 8601 UTC time ('...Z', with or without fraction) and return it in TS_FORMAT."""
    if since is None:
        return None
    try:
        dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
    except ValueError:
        raise ApiError(422, "schema_validation", "since must be an ISO 8601 UTC timestamp",
                       [{"field": "since", "message": "not an ISO 8601 timestamp"}])
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return fmt_ts(dt)


def iso_week(dt: datetime) -> str:
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


def require_valid(kind: str, payload) -> None:
    errors = validation_errors(kind, payload)
    if errors:
        raise unprocessable(f"{kind} failed schema validation", errors)
