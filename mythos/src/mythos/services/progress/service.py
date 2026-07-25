from __future__ import annotations

from dataclasses import dataclass

from mythos.players.context import CommandContext
from mythos.players.player import Player
from mythos.registry.progress import ProgressGraph
from mythos.services.progress.checkpoint_store import CheckpointStoreError, LocalCheckpointStore


class CheckpointNotFoundError(Exception):
    pass


class CheckpointIncompatibleError(Exception):
    pass


@dataclass(frozen=True)
class ProgressSnapshot:
    current_account: str
    unlocked_nodes: tuple[str, ...]
    frontier_nodes: tuple[str, ...]
    checkpoint_sequence: int
    version: int

    def body(self) -> dict[str, object]:
        return {
            "current_account": self.current_account,
            "unlocked_nodes": list(self.unlocked_nodes),
            "frontier_nodes": list(self.frontier_nodes),
            "checkpoint_sequence": self.checkpoint_sequence,
            "version": self.version,
        }


class ProgressService:
    def __init__(self, graph: ProgressGraph, checkpoint_store: LocalCheckpointStore) -> None:
        self._graph = graph
        self._checkpoint_store = checkpoint_store

    def snapshot(self, player: Player) -> ProgressSnapshot:
        return ProgressSnapshot(
            current_account=player.progress.current_account,
            unlocked_nodes=self._string_ids(player.progress.unlocked_node_ids),
            frontier_nodes=self._string_ids(player.progress.frontier_node_ids),
            checkpoint_sequence=player.progress.current_checkpoint_sequence,
            version=player.progress.version,
        )

    async def restore(self, context: CommandContext) -> ProgressSnapshot:
        metadata = context.player.progress._current_checkpoint_metadata()
        if metadata is None:
            raise CheckpointNotFoundError
        try:
            checkpoint = await self._checkpoint_store.read(metadata.storage_key)
        except CheckpointStoreError as error:
            raise CheckpointIncompatibleError("Checkpoint file is unavailable.") from error
        if checkpoint.player_id != context.player.id or checkpoint.sequence != metadata.sequence:
            raise CheckpointIncompatibleError("Checkpoint file does not belong to the current player.")
        if checkpoint.graph_hash != self._graph.structure_hash:
            raise CheckpointIncompatibleError("Checkpoint graph does not match the current runtime.")
        try:
            context.player.progress._restore_state(
                checkpoint.unlocked_node_ids,
                checkpoint.frontier_node_ids,
            )
        except Exception as error:
            raise CheckpointIncompatibleError("Checkpoint state is invalid.") from error
        return self.snapshot(context.player)

    def _string_ids(self, node_ids: frozenset[int]) -> tuple[str, ...]:
        try:
            return tuple(sorted(self._graph.str_ids_by_node_id[node_id] for node_id in node_ids))
        except KeyError as error:
            raise CheckpointIncompatibleError("Player progress references an unknown node.") from error
