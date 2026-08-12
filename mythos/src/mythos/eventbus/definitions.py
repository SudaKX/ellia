from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Literal, TypeAlias
from uuid import UUID

from mythos.core.followups import ContextScope
from mythos.players.player import Player


@dataclass(frozen=True, slots=True)
class Event:
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class PlayerEvent(Event):
    player_id: UUID


@dataclass(frozen=True, slots=True)
class PlayerConstructedEvent(PlayerEvent):
    trigger: Literal["registration", "first_login"]


@dataclass(frozen=True, slots=True)
class PlayerDeconstructingEvent(PlayerEvent):
    trigger: Literal["deletion"]


@dataclass(frozen=True, slots=True)
class VirtualAccountLoggedInEvent(PlayerEvent):
    account_id: str


class EventPriority(IntEnum):
    EARLY = 100
    DEFAULT = 200
    LATE = 300


@dataclass(frozen=True, slots=True)
class EventContext:
    player: Player | None
    event: Event
    scope: ContextScope


EventHandler: TypeAlias = Callable[[EventContext], Awaitable[None]]
