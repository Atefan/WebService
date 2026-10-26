"""Maps domain errors to RFC 7807 Problem Details (application/problem+json). The only place that knows the format."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse


def problem(status: int, code: str, title: str, detail: str, instance: str) -> JSONResponse:
    """Build one Problem Details response; type is /problems/<code with dashes>."""
    raise NotImplementedError


def register_error_handlers(app: FastAPI) -> None:
    """Domain errors -> 400/401/403/404/409, request validation (422) -> 400 with `errors`, catch-all -> 500."""
    # TODO: implement; mapping table is in CLAUDE.md.
    raise NotImplementedError
