from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, NoReturn
from uuid import UUID

from mythos.auth.tokens import PlayerIdentity
from mythos.core.commands.models import CommandRejected
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


@dataclass(frozen=True, slots=True, eq=False)
class PlayerLifecycleContext(PlayerContext):
    event: PlayerLifecycleEvent
