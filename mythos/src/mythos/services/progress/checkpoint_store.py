from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

from mythos.players.interfaces.progress import PendingCheckpoint


class LocalCheckpointStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    async def write(self, checkpoint: PendingCheckpoint) -> str:
        return await asyncio.to_thread(self._write_sync, checkpoint)

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
