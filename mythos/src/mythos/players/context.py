from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping, NoReturn
from uuid import UUID

from mythos.auth.tokens import PlayerIdentity
from mythos.core.commands.exceptions import CommandRejected
from mythos.core.followups import FollowupBody, FollowupCollector
from mythos.players.player import Player
from mythos.registry.lifecycle.definitions import PlayerLifecycleEvent


@dataclass(frozen=True, slots=True, eq=False)
class PlayerContext:
    player: Player


@dataclass(frozen=True, slots=True, eq=False)
class RequestContext(PlayerContext):
    identity: PlayerIdentity
    _followups: FollowupCollector = field(default_factory=FollowupCollector, init=False, repr=False, compare=False)

    def follow(self, body: FollowupBody) -> None:
        self._followups.add(body)

    def _freeze_followups(self) -> tuple[dict[str, Any], ...]:
        return self._followups.freeze()


@dataclass(frozen=True, slots=True, eq=False)
class CommandContext(RequestContext):
    request_id: UUID

    def reject(self, status_code: int, detail: str) -> NoReturn:
        raise CommandRejected(status_code, detail)


class TaskContext:
    """Mutable, request-local task state passed to an asynchronous Handler."""

    def __init__(
        self,
        *,
        player: Player,
        task_id: str,
        time_1: datetime | None,
        time_2: datetime | None,
        exception: int,
        meta: Mapping[str, object],
        now: datetime,
    ) -> None:
        self.player = player
        self.task_id = task_id
        self._time_1 = time_1
        self._extra_time = time_2
        self._exception = exception
        self._meta = deepcopy(dict(meta))
        self.now = now
        self._deferred = False

    @property
    def time_1(self) -> datetime | None:
        return self._time_1

    @property
    def time_2(self) -> datetime | None:
        return self._extra_time

    @property
    def extra_time(self) -> datetime | None:
        return self._extra_time

    @property
    def exception(self) -> int:
        return self._exception

    @property
    def meta(self) -> Mapping[str, object]:
        return MappingProxyType(self._meta)

    @property
    def deferred(self) -> bool:
        return self._deferred

    def set_extra_time(self, value: datetime | None) -> None:
        self._extra_time = value

    def replace_meta(self, value: Mapping[str, object]) -> None:
        self._meta = deepcopy(dict(value))

    def update_meta(self, values: Mapping[str, object]) -> None:
        self._meta.update(deepcopy(dict(values)))

    def delete_meta(self, key: str) -> None:
        self._meta.pop(key, None)

    def defer(self) -> None:
        self._deferred = True

    def _meta_value(self) -> dict[str, object]:
        return deepcopy(self._meta)


@dataclass(frozen=True, slots=True, eq=False)
class PlayerLifecycleContext(PlayerContext):
    event: PlayerLifecycleEvent
