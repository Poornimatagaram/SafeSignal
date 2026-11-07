from __future__ import annotations


class ApiError(Exception):
    """Raised by the store or auth layer; rendered as models.ErrorBody with the given HTTP status."""

    def __init__(self, status: int, error: str, detail: str, errors: list[dict] | None = None):
        self.status = status
        self.error = error
        self.detail = detail
        self.errors = errors or []
        super().__init__(detail)


def forbidden(detail: str) -> ApiError:
    return ApiError(403, "forbidden", detail)


def not_found(detail: str) -> ApiError:
    return ApiError(404, "not_found", detail)


def conflict(detail: str) -> ApiError:
    return ApiError(409, "conflict", detail)


def unprocessable(detail: str, errors: list[dict]) -> ApiError:
    return ApiError(422, "schema_validation", detail, errors)
