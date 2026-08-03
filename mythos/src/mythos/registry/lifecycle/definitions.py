from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import TYPE_CHECKING, Literal, TypeAlias
from uuid import UUID

if TYPE_CHECKING:
    from mythos.players.context import PlayerLifecycleContext


class LifecycleEventKind(IntEnum):
    CONSTRUCT = 1
    DECONSTRUCT = 2


class LifecyclePriority(IntEnum):
    EARLY = 100
    DEFAULT = 200
    LATE = 300


@dataclass(frozen=True)
class PlayerLifecycleEvent(ABC):
    player_id: UUID
    occurred_at: datetime

    @property
    @abstractmethod
    def kind(self) -> LifecycleEventKind: ...


@dataclass(frozen=True)
class PlayerConstructEvent(PlayerLifecycleEvent):
    trigger: Literal["registration", "first_login"]

    @property
    def kind(self) -> LifecycleEventKind:
        return LifecycleEventKind.CONSTRUCT


@dataclass(frozen=True)
class PlayerDeconstructEvent(PlayerLifecycleEvent):
    trigger: Literal["deletion"]

    @property
    def kind(self) -> LifecycleEventKind:
        return LifecycleEventKind.DECONSTRUCT


LifecycleHandler: TypeAlias = Callable[["PlayerLifecycleContext"], Awaitable[None]]
