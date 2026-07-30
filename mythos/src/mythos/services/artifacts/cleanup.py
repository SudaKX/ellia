from __future__ import annotations

from typing import TYPE_CHECKING
from sqlalchemy import select

from mythos.services.object_store.service import ObjectStore

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ArtifactCleanupService:
    """Sweep object storage to remove artifact objects not referenced by DB rows.

    This is a *best-effort* cleanup strategy: because artifact objects are uploaded
    before the SQL transaction commits, a transaction rollback can leave orphan objects.
    Running this service periodically reclaims that storage.
    """

    def __init__(
        self,
        object_store: ObjectStore,
        artifact_prefix: str = "artifacts/",
    ) -> None:
        self._object_store = object_store
        self._artifact_prefix = artifact_prefix

    async def sweep(self, session: AsyncSession) -> dict[str, int]:
        """Return counts: listed, referenced, deleted, skipped."""
        from mythos.persistence.models.artifacts import PlayerArtifact

        result = await session.execute(
            select(
                PlayerArtifact.object_key,
                PlayerArtifact.object_version_id,
            )
        )
        referenced_keys: set[str] = set()
        referenced_versions: set[tuple[str, str]] = set()
        for key, version_id in result.all():
            referenced_keys.add(key)
            if isinstance(version_id, str):
                referenced_versions.add((key, version_id))

        listed_keys = await self._object_store.list_objects(self._artifact_prefix)
        deleted = 0
        skipped = 0
        for key in listed_keys:
            if key in referenced_keys:
                skipped += 1
                continue
            await self._object_store.delete_object(key)
            deleted += 1

        return {
            "listed": len(listed_keys),
            "referenced": len(referenced_keys),
            "deleted": deleted,
            "skipped": skipped,
        }
