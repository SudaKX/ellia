from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID
from uuid import uuid4

from mythos.players.interfaces.progress import PendingCheckpoint


class LocalCheckpointStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    async def write(self, checkpoint: PendingCheckpoint) -> str:
        return await asyncio.to_thread(self._write_sync, checkpoint)

    async def read(self, storage_key: str) -> StoredCheckpoint:
        return await asyncio.to_thread(self._read_sync, storage_key)

    def _write_sync(self, checkpoint: PendingCheckpoint) -> str:
        storage_key = f"{checkpoint.player_id}/{checkpoint.sequence}-{uuid4().hex}.json"
        final_path = self._root / storage_key
        temporary_path = final_path.with_name(f".{final_path.name}.{uuid4().hex}.tmp")
        payload = {
            "format": "mythos-progress-checkpoint-v1",
            "player_id": str(checkpoint.player_id),
            "sequence": checkpoint.sequence,
            "graph_hash": checkpoint.graph_hash,
            "unlocked_node_ids": checkpoint.unlocked_node_ids,
            "frontier_node_ids": checkpoint.frontier_node_ids,
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        final_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with temporary_path.open("xb") as file:
                file.write(encoded)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, final_path)
        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise
        return storage_key

    def _read_sync(self, storage_key: str) -> StoredCheckpoint:
        try:
            root = self._root.resolve()
            path = (root / storage_key).resolve()
            if not path.is_relative_to(root):
                raise CheckpointStoreError("Checkpoint storage key is outside the configured directory.")
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise CheckpointStoreError("Checkpoint file cannot be read.") from error
        return _parse_checkpoint(payload)


class CheckpointStoreError(Exception):
    pass


class StoredCheckpoint:
    def __init__(
        self,
        player_id: UUID,
        sequence: int,
        graph_hash: str,
        unlocked_node_ids: tuple[int, ...],
        frontier_node_ids: tuple[int, ...],
    ) -> None:
        self.player_id = player_id
        self.sequence = sequence
        self.graph_hash = graph_hash
        self.unlocked_node_ids = unlocked_node_ids
        self.frontier_node_ids = frontier_node_ids


def _parse_checkpoint(payload: Any) -> StoredCheckpoint:
    if not isinstance(payload, dict) or payload.get("format") != "mythos-progress-checkpoint-v1":
        raise CheckpointStoreError("Checkpoint file has an unsupported format.")
    try:
        player_id = UUID(str(payload["player_id"]))
        sequence = payload["sequence"]
        graph_hash = payload["graph_hash"]
        unlocked = payload["unlocked_node_ids"]
        frontier = payload["frontier_node_ids"]
    except (KeyError, ValueError) as error:
        raise CheckpointStoreError("Checkpoint file is missing required fields.") from error
    if (
        type(sequence) is not int
        or not isinstance(graph_hash, str)
        or not isinstance(unlocked, list)
        or not isinstance(frontier, list)
        or any(type(node_id) is not int for node_id in unlocked)
        or any(type(node_id) is not int for node_id in frontier)
    ):
        raise CheckpointStoreError("Checkpoint file has invalid field types.")
    return StoredCheckpoint(player_id, sequence, graph_hash, tuple(unlocked), tuple(frontier))
