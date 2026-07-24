from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, TypeAlias

from mythos.endpoints.actions import Action
from mythos.players.context import PlayerRequestContext

ValidationAttemptHandler: TypeAlias = Callable[
    [PlayerRequestContext, Mapping[str, Any]],
    Awaitable[tuple[Action, ...]],
]


@dataclass(frozen=True)
class ValidationAttempt:
    stable_id: str
    validation_id: str
    handler: ValidationAttemptHandler
