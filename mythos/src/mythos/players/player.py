from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from mythos.players.interfaces.artifacts import ArtifactInterface
from mythos.players.interfaces.progress import ProgressInterface


@dataclass(frozen=True)
class Player:
    id: UUID
    progress: ProgressInterface
    artifacts: ArtifactInterface
