from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, TypeAlias

from mythos.endpoints.actions import Action
from mythos.players.context import PlayerRequestContext

ViewCallback: TypeAlias = Callable[[PlayerRequestContext], Awaitable[tuple[Action, ...]]]
CommandCallback: TypeAlias = Callable[[PlayerRequestContext, Mapping[str, Any]], Awaitable[tuple[Action, ...]]]


@dataclass(frozen=True)
class ViewCallbackRegistration:
    endpoint_id: str
    stable_id: str
    priority: int
    registration_order: int
    callback: ViewCallback


@dataclass(frozen=True)
class CommandCallbackRegistration:
    endpoint_id: str
    stable_id: str
    callback: CommandCallback
