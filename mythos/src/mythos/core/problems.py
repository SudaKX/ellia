from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from http import HTTPStatus
from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from mythos.core.config import Settings

PROBLEM_MEDIA_TYPE = "application/problem+json"
PROBLEM_STATUS_CODES = (400, 401, 403, 404, 409, 412, 422, 500, 502, 503)
_STANDARD_MEMBERS = frozenset({"type", "title", "status", "detail", "instance"})
_logger = logging.getLogger(__name__)


class ProblemType(StrEnum):
    ACCESS_TOKEN_MISSING = "access-token-missing"
    ACCESS_TOKEN_INVALID = "access-token-invalid"
    PRIMARY_CREDENTIALS_INVALID = "primary-credentials-invalid"
    REFRESH_CREDENTIAL_INVALID = "refresh-credential-invalid"
    USERNAME_ALREADY_EXISTS = "username-already-exists"
    VIRTUAL_ACCOUNT_INVALID_CREDENTIALS = "virtual-account-invalid-credentials"
    INVALID_REQUEST = "invalid-request"
    INTERNAL_ERROR = "internal-error"


class ProblemDetails(BaseModel):
    """RFC 9457 problem detail response body."""

    model_config = ConfigDict(extra="allow", frozen=True)

    type: str
    title: str
    status: int = Field(ge=400, le=599)
    detail: str | None = None
    instance: str = Field(default_factory=lambda: f"urn:uuid:{uuid4()}")


@dataclass(eq=False)
class ApiProblem(Exception):
    problem_type: ProblemType
    status: int
    title: str
    detail: str | None = None
    extensions: Mapping[str, Any] = field(default_factory=dict)
    instance: str = field(default_factory=lambda: f"urn:uuid:{uuid4()}")

    def __post_init__(self) -> None:
        if not 400 <= self.status <= 599:
            raise ValueError("Problem status must be a 4xx or 5xx HTTP status code.")
        overlap = _STANDARD_MEMBERS & self.extensions.keys()
        if overlap:
            raise ValueError(f"Problem extensions cannot replace standard members: {sorted(overlap)!r}")
        Exception.__init__(self, self.detail or self.title)

    def details(self, settings: Settings) -> ProblemDetails:
        return ProblemDetails(
            type=settings.problem_type_url(self.problem_type),
            title=self.title,
            status=self.status,
            detail=self.detail,
            instance=self.instance,
            **self.extensions,
        )


def problem_response(problem: ApiProblem, settings: Settings) -> JSONResponse:
    return _problem_details_response(problem.details(settings))


async def api_problem_handler(request: Request, problem: ApiProblem) -> JSONResponse:
    return problem_response(problem, request.app.state.settings)


async def http_exception_handler(
    request: Request,
    error: StarletteHTTPException,
) -> JSONResponse:
    if error.status_code == 400 and error.detail == "There was an error parsing the body":
        return problem_response(
            ApiProblem(
                ProblemType.INVALID_REQUEST,
                status=422,
                title="Invalid request",
                detail="One or more request values are invalid.",
                extensions={"errors": [{"pointer": "/", "reason": "Request body must be valid JSON."}]},
            ),
            request.app.state.settings,
        )
    try:
        title = HTTPStatus(error.status_code).phrase
    except ValueError:
        title = f"HTTP {error.status_code} error"
    detail = error.detail if isinstance(error.detail, str) else None
    return _problem_details_response(
        ProblemDetails(
            type="about:blank",
            title=title,
            status=error.status_code,
            detail=detail,
        ),
        headers=error.headers,
    )


async def request_validation_exception_handler(
    request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    return problem_response(
        ApiProblem(
            ProblemType.INVALID_REQUEST,
            status=422,
            title="Invalid request",
            detail="One or more request values are invalid.",
            extensions={"errors": validation_errors(error.errors())},
        ),
        request.app.state.settings,
    )


async def unhandled_exception_handler(request: Request, error: Exception) -> JSONResponse:
    problem = ApiProblem(
        ProblemType.INTERNAL_ERROR,
        status=500,
        title="Internal server error",
        detail="The server could not complete the request.",
    )
    _logger.exception("Unhandled API error instance=%s", problem.instance, exc_info=error)
    return problem_response(problem, request.app.state.settings)


def _problem_details_response(
    details: ProblemDetails,
    *,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    response_headers = {
        key: value
        for key, value in (headers or {}).items()
        if key.lower() != "www-authenticate"
    }
    response_headers.setdefault("Cache-Control", "no-store")
    return JSONResponse(
        status_code=details.status,
        content=details.model_dump(mode="json", exclude_none=True),
        headers=response_headers,
        media_type=PROBLEM_MEDIA_TYPE,
    )


def validation_errors(errors: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    return [_validation_error(error) for error in errors]


def _validation_error(error: Mapping[str, Any]) -> dict[str, str]:
    if error.get("type") == "json_invalid":
        return {"pointer": "/", "reason": "Request body must be valid JSON."}
    location = tuple(str(part) for part in error.get("loc", ()))
    if location[:1] == ("body",):
        location = location[1:]
    pointer = "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in location)
    return {"pointer": pointer or "/", "reason": str(error.get("msg", "Invalid value."))}
