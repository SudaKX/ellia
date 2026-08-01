from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mythos.persistence.base import utcnow
from mythos.persistence.models.static_files import StaticFileRegistration
from mythos.registry.files.definitions import FileReference, ObjectReference
from mythos.services.object_store.service import StaticObjectWriter


class StaticAssetPublishError(Exception):
    pass


class StaticAssetPublisher:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        object_writer: StaticObjectWriter,
        puzzle_root: Path,
    ) -> None:
        self._session_factory = session_factory
        self._object_writer = object_writer
        self._puzzle_root = puzzle_root

    async def materialize(self, sources: tuple[FileReference, ...]) -> Mapping[str, ObjectReference]:
        if not sources:
            return {}
        existing = await self._load_existing()
        resolved: dict[str, ObjectReference] = {}
        uploaded: dict[str, tuple[FileReference, int, ObjectReference]] = {}

        for source in sources:
            source_path, source_mtime_ns = await self._source_state(source)
            registration = existing.get(source.source_locator)
            if registration is not None and registration.source_mtime_ns == source_mtime_ns:
                resolved[source.source_locator] = _reference_from_registration(registration, source.media_type)
                continue
            reference, final_mtime_ns = await self._publish(source, source_path, source_mtime_ns)
            resolved[source.source_locator] = reference
            uploaded[source.source_locator] = (source, final_mtime_ns, reference)

        await self._record_materialization(sources, uploaded)
        return resolved

    async def _load_existing(self) -> dict[str, StaticFileRegistration]:
        async with self._session_factory() as session:
            result = await session.execute(select(StaticFileRegistration))
            return {registration.source_locator: registration for registration in result.scalars()}

    async def _source_state(self, source: FileReference) -> tuple[Path, int]:
        source_path = self._puzzle_root / source.module / source.relative_path
        try:
            stat = await asyncio.to_thread(source_path.stat)
        except OSError as error:
            raise StaticAssetPublishError(f"Static file source is unavailable: {source.source_locator}") from error
        if not source_path.is_file():
            raise StaticAssetPublishError(f"Static file source is not a regular file: {source.source_locator}")
        return source_path, stat.st_mtime_ns

    async def _publish(
        self,
        source: FileReference,
        source_path: Path,
        source_mtime_ns: int,
    ) -> tuple[ObjectReference, int]:
        for _ in range(2):
            reference = await self._object_writer.put_file(
                source_path,
                object_key=_object_key(source),
                media_type=source.media_type,
            )
            _, current_mtime_ns = await self._source_state(source)
            if current_mtime_ns == source_mtime_ns:
                return reference, source_mtime_ns
            source_mtime_ns = current_mtime_ns
        raise StaticAssetPublishError(f"Static file source changed while publishing: {source.source_locator}")

    async def _record_materialization(
        self,
        sources: tuple[FileReference, ...],
        uploaded: Mapping[str, tuple[FileReference, int, ObjectReference]],
    ) -> None:
        now = utcnow()
        active_locators = {source.source_locator for source in sources}
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(select(StaticFileRegistration))
                registrations = {registration.source_locator: registration for registration in result.scalars()}
                for source in sources:
                    locator = source.source_locator
                    registration = registrations.get(locator)
                    if locator in uploaded:
                        _, source_mtime_ns, reference = uploaded[locator]
                        if registration is None:
                            registration = StaticFileRegistration(
                                source_locator=locator,
                                source_mtime_ns=source_mtime_ns,
                                object_key=reference.key,
                                object_version_id=reference.version_id,
                                content_digest=reference.content_digest,
                                media_type=reference.media_type,
                                size_bytes=reference.size_bytes,
                                published_at=now,
                                last_seen_at=now,
                            )
                            session.add(registration)
                        else:
                            _update_registration(registration, source_mtime_ns, reference, now)
                    elif registration is not None:
                        registration.media_type = source.media_type
                        registration.last_seen_at = now
                        registration.retired_at = None
                    else:
                        raise StaticAssetPublishError(f"Static file registration disappeared: {locator}")
                for locator, registration in registrations.items():
                    if locator not in active_locators and registration.retired_at is None:
                        registration.retired_at = now


def _object_key(source: FileReference) -> str:
    return f"static/{source.module}/{source.relative_path}"


def _reference_from_registration(registration: StaticFileRegistration, media_type: str | None = None) -> ObjectReference:
    return ObjectReference(
        key=registration.object_key,
        content_digest=registration.content_digest,
        media_type=media_type or registration.media_type,
        size_bytes=registration.size_bytes,
        version_id=registration.object_version_id,
    )


def _update_registration(
    registration: StaticFileRegistration,
    source_mtime_ns: int,
    reference: ObjectReference,
    now: datetime,
) -> None:
    registration.source_mtime_ns = source_mtime_ns
    registration.object_key = reference.key
    registration.object_version_id = reference.version_id
    registration.content_digest = reference.content_digest
    registration.media_type = reference.media_type
    registration.size_bytes = reference.size_bytes
    registration.published_at = now
    registration.last_seen_at = now
    registration.retired_at = None
