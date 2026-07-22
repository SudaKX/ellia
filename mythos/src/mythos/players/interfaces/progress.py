from __future__ import annotations

from mythos.persistence.models import PlayerProgress
from mythos.players.effects import SetCheckpointEffect


class ReadOnlyPlayerError(Exception):
    pass


class ProgressInterface:
    def __init__(self, progress: PlayerProgress, *, writable: bool) -> None:
        self._progress = progress
        self._writable = writable

    @property
    def current_account(self) -> str:
        return self._progress.current_account

    @property
    def story_node(self) -> str:
        return self._progress.story_node

    @property
    def checkpoint(self) -> str | None:
        return self._progress.checkpoint

    @property
    def version(self) -> int:
        return self._progress.version

    def set_checkpoint(self, checkpoint: str | None) -> SetCheckpointEffect:
        if not self._writable:
            raise ReadOnlyPlayerError("Read-only players cannot create write effects.")
        if checkpoint is not None and len(checkpoint) > 64:
            raise ValueError("Checkpoint IDs must contain at most 64 characters.")
        return SetCheckpointEffect(
            kind="progress.set_checkpoint",
            checkpoint=checkpoint,
            _execute_callback=lambda: self._execute_set_checkpoint(checkpoint),
        )

    async def _execute_set_checkpoint(self, checkpoint: str | None) -> None:
        self._progress.checkpoint = checkpoint
        self._progress.version += 1
