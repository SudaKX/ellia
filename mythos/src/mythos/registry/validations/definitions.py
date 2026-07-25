from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, TypeAlias

from mythos.players.context import CommandContext

ValidationAttemptHandler: TypeAlias = Callable[
    [CommandContext, Mapping[str, Any]],
    Awaitable["ValidationOutcome"],
]


@dataclass(frozen=True)
class ValidationAttempt:
    stable_id: str
    validation_id: str
    handler: ValidationAttemptHandler


@dataclass(frozen=True)
class ValidationOutcome:
    accepted: bool
