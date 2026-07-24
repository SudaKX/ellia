from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

@dataclass(frozen=True)
class ActionExecutionResult:
    owner_player_id: UUID
    status_code: int
    body: dict[str, Any]
    headers: dict[str, str]
    followups: tuple[dict[str, Any], ...]
    state_revision: int
