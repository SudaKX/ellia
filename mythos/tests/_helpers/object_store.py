from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import NamedTuple

from mythos.registry.files import ObjectReference
from mythos.services.object_store.service import PresignedObjectUrl


class UploadRecord(NamedTuple):
    object_key: str
    data: bytes
    media_type: str


class PresignRequest(NamedTuple):
    object_key: str
    content_disposition: str
    response_cache_control: str
    response_expires_at: datetime | None


class FakeObjectStore:
    """In-memory object store double for unit and integration tests."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.uploads: list[UploadRecord] = []
        self.requests: list[PresignRequest] = []

    @property
    def upload_keys(self) -> list[str]:
        return [record.object_key for record in self.uploads]

    @property
    def request_keys(self) -> list[str]:
        return [request.object_key for request in self.requests]

    async def put_bytes(
        self,
        data: bytes,
        *,
        object_key: str,
        media_type: str,
    ) -> ObjectReference:
        self.objects[object_key] = data
        self.uploads.append(UploadRecord(object_key, data, media_type))
        return ObjectReference(
            key=object_key,
            content_digest=f"sha256:{hashlib.sha256(data).hexdigest()}",
            media_type=media_type,
            size_bytes=len(data),
            version_id=f"test-version-{len(self.uploads)}",
        )

    async def put_file(
        self,
        source_path: Path,
        *,
        object_key: str,
        media_type: str,
    ) -> ObjectReference:
        return await self.put_bytes(
            source_path.read_bytes(),
            object_key=object_key,
            media_type=media_type,
        )

    async def presign_get(
        self,
        reference: ObjectReference,
        *,
        expires_in_seconds: int,
        content_disposition: str,
        response_cache_control: str,
        response_expires_at: datetime | None,
    ) -> PresignedObjectUrl:
        self.requests.append(
            PresignRequest(
                reference.key,
                content_disposition,
                response_cache_control,
                response_expires_at,
            )
        )
        return PresignedObjectUrl(
            url=f"https://objects.test/{reference.key}?expires={expires_in_seconds}",
            expires_at=response_expires_at or datetime.now(UTC),
        )

    async def list_objects(self, prefix: str) -> list[str]:
        return sorted(key for key in self.objects if key.startswith(prefix))

    async def delete_object(self, key: str, version_id: str | None = None) -> None:
        del version_id
        self.objects.pop(key, None)
