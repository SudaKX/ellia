from __future__ import annotations

import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CredentialsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value.strip())
        if len(normalized) < 3:
            raise ValueError("Username must contain at least three characters.")
        if any(character.isspace() or ord(character) < 32 for character in normalized):
            raise ValueError("Username cannot contain whitespace or control characters.")
        return normalized


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
