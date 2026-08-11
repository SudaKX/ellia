from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from mythos.persistence.models import PlayerProgressCheckpoint
from mythos.players.player import Player
from mythos.services.progress.checkpoint_store import LocalCheckpointStore


class ProgressCheckpointHook:
    def __init__(self, store: LocalCheckpointStore) -> None:
        self._store = store

    async def __call__(self, session: AsyncSession, player: Player) -> None:
        progress = player.progress
        checkpoints = progress._drain_pending_checkpoints()
        records: list[PlayerProgressCheckpoint] = []
        for checkpoint in checkpoints:
            storage_key = await self._store.write(checkpoint)
            record = PlayerProgressCheckpoint(
                player_id=checkpoint.player_id,
                sequence=checkpoint.sequence,
                storage_key=storage_key,
            )
            session.add(record)
            records.append(record)
        if records:
            progress._set_current_checkpoint(records[-1])
