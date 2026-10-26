"""Maps domain errors to RFC 7807 Problem Details (application/problem+json). The only place that knows the format.

RFC 7807 has been superseded by RFC 9457, which keeps the same format.
"""

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain import errors as domain

PROBLEM_JSON = "application/problem+json"

# Domain error -> (HTTP status, machine-readable code, title)
_MAPPING: dict[type[domain.DomainError], tuple[int, str, str]] = {
    domain.ValidationError: (400, "validation_error", "Invalid request"),
    domain.Unauthorized: (401, "unauthorized", "Missing or empty X-User-Id header"),
    domain.Forbidden: (403, "forbidden", "Not allowed"),
    domain.EventNotFound: (404, "event_not_found", "Event not found"),
    domain.SoldOut: (409, "sold_out", "Not enough tickets left"),
    domain.EventAlreadyTookPlace: (409, "event_already_took_place", "Event already took place"),
}


def problem_body(status: int, code: str, title: str, detail: str, instance: str) -> dict:
    # TODO: `type` is a relative URI that is not served. A real service would host docs per problem type.
    return {
        "type": f"/problems/{code.replace('_', '-')}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": instance,
        "code": code,
    }


def problem(status: int, code: str, title: str, detail: str, instance: str, **extra) -> JSONResponse:
    """Build one Problem Details response; `extra` adds extension members."""
    body = {**problem_body(status, code, title, detail, instance), **extra}
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON)


def problem_example(status: int, code: str, title: str, detail: str, instance: str) -> dict:
    """An entry for a route's `responses=`, so /docs shows the error body."""
    return {
        "description": title,
        "content": {PROBLEM_JSON: {"example": problem_body(status, code, title, detail, instance)}},
    }


def register_error_handlers(app: FastAPI) -> None:
    """Domain errors -> 400/401/403/404/409, request validation (422) -> 400 with `errors`, catch-all -> 500."""

    @app.exception_handler(domain.DomainError)
    async def on_domain_error(request: Request, exc: domain.DomainError) -> JSONResponse:
        status, code, title = _MAPPING.get(type(exc), (500, "internal_error", "Internal server error"))
        return problem(status, code, title, str(exc), request.url.path)

    @app.exception_handler(RequestValidationError)
    async def on_invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"field": _field_name(e), "message": e["msg"]}
            for e in exc.errors()
        ]
        return problem(
            400, "validation_error", "Invalid request",
            f"The request is invalid ({len(errors)} error(s)).", request.url.path, errors=errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def on_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Errors raised by the framework itself, e.g. unknown route (404) or wrong method (405).
        phrase = HTTPStatus(exc.status_code).phrase
        code = phrase.lower().replace(" ", "_")
        return problem(exc.status_code, code, phrase, str(exc.detail), request.url.path)

    @app.exception_handler(Exception)
    async def on_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Nothing about the exception is returned. uvicorn still logs the traceback.
        # TODO: structured logging with a request id.
        return problem(
            500, "internal_error", "Internal server error",
            "An unexpected error occurred.", request.url.path,
        )

    _hide_default_422_from_docs(app)


def _field_name(error: dict) -> str:
    """'body.eventDate' -> 'eventDate'. Unparsable JSON has the error position as its loc, so call it 'body'."""
    if error["type"] == "json_invalid":
        return "body"
    return ".".join(str(part) for part in error["loc"][1:]) or "body"


def _hide_default_422_from_docs(app: FastAPI) -> None:
    """FastAPI documents a 422 on every route, but this API answers invalid requests with 400."""
    generate = app.openapi

    def openapi() -> dict:
        if app.openapi_schema is None:
            schema = generate()  # also caches itself in app.openapi_schema
            for path in schema["paths"].values():
                for operation in path.values():
                    operation["responses"].pop("422", None)
            for name in ("HTTPValidationError", "ValidationError"):
                schema.get("components", {}).get("schemas", {}).pop(name, None)
        return app.openapi_schema

    app.openapi = openapi
