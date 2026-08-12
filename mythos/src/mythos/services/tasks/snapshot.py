from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from mythos.registry.tasks import TaskSnapshot


class TaskSnapshotError(RuntimeError):
    pass


class TaskSnapshotStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    async def read(self) -> TaskSnapshot | None:
        return await asyncio.to_thread(self._read_sync)

    async def write(self, snapshot: TaskSnapshot) -> None:
        await asyncio.to_thread(self._write_sync, snapshot)

    def _read_sync(self) -> TaskSnapshot | None:
        if not self._path.exists():
            return None
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Task snapshot root must be an object.")
            return TaskSnapshot.from_dict(payload)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise TaskSnapshotError("Task snapshot is unreadable.") from error

    def _write_sync(self, snapshot: TaskSnapshot) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(self._path.suffix + ".tmp")
        payload = json.dumps(snapshot.as_dict(), ensure_ascii=True, indent=2, sort_keys=True) + "\n"
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self._path)
        except OSError as error:
            raise TaskSnapshotError("Task snapshot could not be written.") from error
