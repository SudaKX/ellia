from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID
from mythos.auth.tokens import PlayerIdentity
from mythos.players.player import Player


@dataclass(frozen=True)
class PlayerRequestContext:
    identity: PlayerIdentity
    player: Player
    request_id: UUID | None = None
