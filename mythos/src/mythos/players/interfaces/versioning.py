from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class VersionedPlayerInterface(Protocol):
    @property
    def version(self) -> int:
        """Return the current player-scoped state revision."""
