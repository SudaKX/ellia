from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeAlias

if TYPE_CHECKING:
    from mythos.players.context import ValidationContext

ValidationAttemptHandler: TypeAlias = Callable[
    ["ValidationContext", Mapping[str, Any]],
    Awaitable["ValidationResult"],
]


@dataclass(frozen=True)
class ValidationAttempt:
    stable_id: str
    validation_id: str
    handler: ValidationAttemptHandler


@dataclass(frozen=True)
class ValidationResult:
    accepted: bool
