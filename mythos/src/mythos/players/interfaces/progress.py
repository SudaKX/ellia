from __future__ import annotations

from typing import TYPE_CHECKING

from mythos.persistence.models import PlayerProgress

if TYPE_CHECKING:
    from mythos.registry.bundle import RuntimeCatalogs


class ReadOnlyPlayerError(Exception):
    pass


class ProgressInterface:
    def __init__(
        self,
        progress: PlayerProgress,
        *,
        writable: bool,
        catalogs: RuntimeCatalogs,
    ) -> None:
        self._progress = progress
        self._writable = writable
        self._catalogs = catalogs

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

    def set_checkpoint(self, checkpoint: str | None) -> None:
        if not self._writable:
            raise ReadOnlyPlayerError("Read-only players cannot modify progress.")
        if checkpoint is not None and len(checkpoint) > 64:
            raise ValueError("Checkpoint IDs must contain at most 64 characters.")
        self._progress.checkpoint = checkpoint
        self._progress.version += 1
