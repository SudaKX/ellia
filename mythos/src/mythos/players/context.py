from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping, NoReturn
from uuid import UUID

from mythos.auth.tokens import PlayerIdentity
from mythos.core.exceptions import CommandRejected, ValidationRejected
from mythos.core.followups import ContextScope, Followup
from mythos.players.player import Player
from mythos.registry.lifecycle.definitions import PlayerLifecycleEvent


@dataclass(frozen=True, slots=True, eq=False)
class Context:
    player: Player
    scope: ContextScope = field(default_factory=ContextScope.silent, kw_only=True)

    def follow(self, followup: Followup) -> None:
        self.scope.follow(followup)

    def followup_checkpoint(self) -> None:
        self.scope.followup_checkpoint()

    def followup_rollback(self) -> None:
        self.scope.followup_rollback()


@dataclass(frozen=True, slots=True, eq=False)
class RequestContext(Context):
    identity: PlayerIdentity

    @classmethod
    def from_context(cls, context: Context, *, identity: PlayerIdentity) -> RequestContext:
        return cls(player=context.player, identity=identity, scope=context.scope)


@dataclass(frozen=True, slots=True, eq=False)
class CommandContext(RequestContext):
    request_id: UUID

    @classmethod
    def from_context(
        cls,
        context: RequestContext,
        *,
        request_id: UUID,
    ) -> CommandContext:
        return cls(
            player=context.player,
            identity=context.identity,
            request_id=request_id,
            scope=context.scope,
        )

    def reject(self, status_code: int, detail: str) -> NoReturn:
        raise CommandRejected(status_code, detail)


class TaskContext(Context):
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
        scope: ContextScope | None = None,
    ) -> None:
        super().__init__(player=player, scope=scope or ContextScope.silent())
        self.task_id = task_id
        self._time_1 = time_1
        self._extra_time = time_2
        self._exception = exception
        self._meta = deepcopy(dict(meta))
        self.now = now
        self._deferred = False

    @classmethod
    def from_context(
        cls,
        context: Context,
        *,
        task_id: str,
        time_1: datetime | None,
        time_2: datetime | None,
        exception: int,
        meta: Mapping[str, object],
        now: datetime,
    ) -> TaskContext:
        return cls(
            player=context.player,
            task_id=task_id,
            time_1=time_1,
            time_2=time_2,
            exception=exception,
            meta=meta,
            now=now,
            scope=context.scope,
        )

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
class PlayerLifecycleContext(Context):
    event: PlayerLifecycleEvent

    @classmethod
    def from_context(
        cls,
        context: Context,
        *,
        event: PlayerLifecycleEvent,
    ) -> PlayerLifecycleContext:
        return cls(player=context.player, event=event, scope=context.scope)


@dataclass(frozen=True, slots=True, eq=False)
class ValidationContext(Context):
    @classmethod
    def from_context(cls, context: Context) -> ValidationContext:
        return cls(player=context.player, scope=context.scope)

    def reject(
        self,
        reason: str,
        details: Mapping[str, Any] | None = None,
    ) -> NoReturn:
        raise ValidationRejected(reason, details)
