from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi.encoders import jsonable_encoder

_HEADER_NAME_PATTERN = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")


class ResponseFormatError(Exception):
    pass


class CommandRejected(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class ResponseSpec:
    status_code: int
    body: Mapping[str, Any]
    headers: Mapping[str, str]

    def __post_init__(self) -> None:
        if not 100 <= self.status_code <= 599:
            raise ResponseFormatError("Response status codes must be valid HTTP status codes.")
        object.__setattr__(self, "body", _encode_body(self.body))
        object.__setattr__(self, "headers", _encode_headers(self.headers))


@dataclass(frozen=True)
class CachedResponse:
    owner_player_id: UUID
    response: ResponseSpec


def _encode_body(body: Mapping[str, Any]) -> dict[str, Any]:
    try:
        encoded = jsonable_encoder(dict(body))
        json.dumps(encoded, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ResponseFormatError("Response bodies must be JSON serializable.") from error
    if not isinstance(encoded, dict):
        raise ResponseFormatError("Response bodies must encode to JSON objects.")
    return encoded


def _encode_headers(headers: Mapping[str, str]) -> dict[str, str]:
    encoded: dict[str, str] = {}
    for key, value in headers.items():
        name = str(key)
        header_value = str(value)
        if not _HEADER_NAME_PATTERN.fullmatch(name):
            raise ResponseFormatError("Response headers contain an invalid name.")
        if any(ord(character) < 32 or ord(character) == 127 for character in header_value):
            raise ResponseFormatError("Response headers contain control characters.")
        encoded[name] = header_value
    return encoded
