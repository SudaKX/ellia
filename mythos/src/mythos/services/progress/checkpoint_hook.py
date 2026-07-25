from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from mythos.persistence.models import PlayerProgressCheckpoint
from mythos.players.context import CommandContext
from mythos.services.progress.checkpoint_store import LocalCheckpointStore


class ProgressCheckpointHook:
    def __init__(self, store: LocalCheckpointStore) -> None:
        self._store = store

    async def __call__(self, session: AsyncSession, context: CommandContext) -> None:
        progress = context.player.progress
        checkpoints = progress._drain_pending_checkpoints()
        for checkpoint in checkpoints:
            storage_key = await self._store.write(checkpoint)
            session.add(
                PlayerProgressCheckpoint(
                    player_id=checkpoint.player_id,
                    sequence=checkpoint.sequence,
                    storage_key=storage_key,
                )
            )
        if checkpoints:
            progress._set_current_checkpoint_sequence(checkpoints[-1].sequence)
