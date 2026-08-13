from __future__ import annotations

import asyncio
import hashlib
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
        self._puzzle_root = puzzle_root.resolve()

    async def materialize(self, sources: tuple[FileReference, ...]) -> Mapping[str, ObjectReference]:
        if not sources:
            return {}
        existing = await self._load_existing()
        resolved: dict[str, ObjectReference] = {}
        uploaded: dict[str, tuple[FileReference, ObjectReference]] = {}

        for source in sources:
            data = await self._source_bytes(source)
            digest = f"sha256:{hashlib.sha256(data).hexdigest()}"
            registration = existing.get(source.source_locator)
            if (
                registration is not None
                and registration.content_digest == digest
                and registration.media_type == source.media_type
            ):
                resolved[source.source_locator] = _reference_from_registration(registration, source.media_type)
                continue
            reference = await self._object_writer.put_bytes(
                data,
                object_key=_object_key(source),
                media_type=source.media_type,
            )
            resolved[source.source_locator] = reference
            uploaded[source.source_locator] = (source, reference)

        await self._record_materialization(sources, uploaded)
        return resolved

    async def _load_existing(self) -> dict[str, StaticFileRegistration]:
        async with self._session_factory() as session:
            result = await session.execute(select(StaticFileRegistration))
            return {registration.source_locator: registration for registration in result.scalars()}

    async def _source_bytes(self, source: FileReference) -> bytes:
        source_path = (self._puzzle_root / source.module / source.relative_path).resolve()
        try:
            source_path.relative_to(self._puzzle_root)
        except ValueError as error:
            raise StaticAssetPublishError(
                f"Static file source escapes the puzzle root: {source.source_locator}"
            ) from error
        try:
            data = await asyncio.to_thread(source_path.read_bytes)
        except OSError as error:
            raise StaticAssetPublishError(f"Static file source is unavailable: {source.source_locator}") from error
        if not source_path.is_file():
            raise StaticAssetPublishError(f"Static file source is not a regular file: {source.source_locator}")
        return data

    async def _record_materialization(
        self,
        sources: tuple[FileReference, ...],
        uploaded: Mapping[str, tuple[FileReference, ObjectReference]],
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
                        _, reference = uploaded[locator]
                        if registration is None:
                            registration = StaticFileRegistration(
                                source_locator=locator,
                                object_key=reference.key,
                                content_digest=reference.content_digest,
                                media_type=reference.media_type,
                                size_bytes=reference.size_bytes,
                                published_at=now,
                                last_seen_at=now,
                            )
                            session.add(registration)
                        else:
                            _update_registration(registration, reference, now)
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
    )


def _update_registration(
    registration: StaticFileRegistration,
    reference: ObjectReference,
    now: datetime,
) -> None:
    registration.object_key = reference.key
    registration.content_digest = reference.content_digest
    registration.media_type = reference.media_type
    registration.size_bytes = reference.size_bytes
    registration.published_at = now
    registration.last_seen_at = now
    registration.retired_at = None
