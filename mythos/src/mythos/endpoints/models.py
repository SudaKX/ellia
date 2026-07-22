from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stable_id: str = Field(min_length=1, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class ActionExecutionResult:
    owner_player_id: UUID
    status_code: int
    body: dict[str, Any]
    headers: dict[str, str]
    followups: tuple[dict[str, Any], ...]
    state_revision: int
