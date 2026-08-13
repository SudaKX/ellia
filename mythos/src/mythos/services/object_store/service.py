from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Protocol

from mythos.registry.files.definitions import ObjectReference

if TYPE_CHECKING:
    from mythos.core.config import Settings


class ObjectStoreUnavailableError(Exception):
    pass


class ObjectStoreError(Exception):
    pass


@dataclass(frozen=True)
class PresignedObjectUrl:
    url: str
    expires_at: datetime


class ObjectStoreReader(Protocol):
    async def presign_get(
        self,
        reference: ObjectReference,
        *,
        expires_in_seconds: int,
        content_disposition: str,
        response_cache_control: str,
        response_expires_at: datetime | None,
    ) -> PresignedObjectUrl: ...


class StaticObjectWriter(Protocol):
    async def put_bytes(
        self,
        data: bytes,
        *,
        object_key: str,
        media_type: str,
    ) -> ObjectReference: ...


class ObjectWriter(StaticObjectWriter, Protocol):
    pass


class ObjectStore(ObjectStoreReader, ObjectWriter, Protocol):
    async def list_objects(self, prefix: str) -> list[str]: ...

    async def delete_object(self, key: str) -> None: ...


class UnconfiguredObjectStore:
    async def presign_get(
        self,
        reference: ObjectReference,
        *,
        expires_in_seconds: int,
        content_disposition: str,
        response_cache_control: str,
        response_expires_at: datetime | None,
    ) -> PresignedObjectUrl:
        del reference, expires_in_seconds, content_disposition, response_cache_control, response_expires_at
        raise ObjectStoreUnavailableError("Object storage is not configured.")

    async def put_bytes(
        self,
        data: bytes,
        *,
        object_key: str,
        media_type: str,
    ) -> ObjectReference:
        del data, object_key, media_type
        raise ObjectStoreUnavailableError("Object storage is not configured.")

    async def list_objects(self, prefix: str) -> list[str]:
        del prefix
        raise ObjectStoreUnavailableError("Object storage is not configured.")

    async def delete_object(self, key: str) -> None:
        del key
        raise ObjectStoreUnavailableError("Object storage is not configured.")


class Boto3ObjectStore:
    def __init__(self, client: object, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    async def presign_get(
        self,
        reference: ObjectReference,
        *,
        expires_in_seconds: int,
        content_disposition: str,
        response_cache_control: str,
        response_expires_at: datetime | None,
    ) -> PresignedObjectUrl:
        params: dict[str, object] = {
            "Bucket": self._bucket,
            "Key": reference.key,
            "ResponseContentType": reference.media_type,
            "ResponseContentDisposition": content_disposition,
            "ResponseCacheControl": response_cache_control,
        }
        if response_expires_at is not None:
            params["ResponseExpires"] = response_expires_at
        try:
            url = await asyncio.to_thread(
                self._client.generate_presigned_url,  # type: ignore[union-attr]
                "get_object",
                Params=params,
                ExpiresIn=expires_in_seconds,
            )
        except Exception as error:
            raise ObjectStoreError("Unable to issue an object download URL.") from error
        return PresignedObjectUrl(
            url=url,
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in_seconds),
        )

    async def put_bytes(
        self,
        data: bytes,
        *,
        object_key: str,
        media_type: str,
    ) -> ObjectReference:
        return await asyncio.to_thread(self._put_bytes_sync, data, object_key, media_type)

    def _put_bytes_sync(self, data: bytes, object_key: str, media_type: str) -> ObjectReference:
        digest = hashlib.sha256(data).hexdigest()
        try:
            response = self._client.put_object(  # type: ignore[union-attr]
                Bucket=self._bucket,
                Key=object_key,
                Body=data,
                ContentType=media_type,
            )
        except Exception as error:
            raise ObjectStoreError("Unable to upload a dynamic object.") from error
        return ObjectReference(
            key=object_key,
            content_digest=f"sha256:{digest}",
            media_type=media_type,
            size_bytes=len(data),
        )

    async def list_objects(self, prefix: str) -> list[str]:
        keys: list[str] = []
        continuation_token: str | None = None
        while True:
            params: dict[str, object] = {"Bucket": self._bucket, "Prefix": prefix}
            if continuation_token is not None:
                params["ContinuationToken"] = continuation_token
            try:
                response = await asyncio.to_thread(
                    self._client.list_objects_v2,  # type: ignore[union-attr]
                    **params,
                )
            except Exception as error:
                raise ObjectStoreError("Unable to list objects.") from error
            for obj in response.get("Contents", []):
                key = obj.get("Key")
                if isinstance(key, str):
                    keys.append(key)
            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")
            if not isinstance(continuation_token, str):
                break
        return keys

    async def delete_object(self, key: str) -> None:
        params: dict[str, object] = {"Bucket": self._bucket, "Key": key}
        try:
            await asyncio.to_thread(
                self._client.delete_object,  # type: ignore[union-attr]
                **params,
            )
        except Exception as error:
            raise ObjectStoreError("Unable to delete object.") from error


def create_object_store(settings: Settings) -> ObjectStore:
    if not settings.object_store_configured:
        return UnconfiguredObjectStore()
    try:
        import boto3
        from botocore.config import Config
    except ImportError as error:
        raise RuntimeError("boto3 must be installed to use object storage.") from error
    client = boto3.client(
        "s3",
        endpoint_url=settings.object_store_endpoint,
        region_name=settings.object_store_region,
        aws_access_key_id=settings.object_store_access_key.get_secret_value(),
        aws_secret_access_key=settings.object_store_secret_key.get_secret_value(),
        use_ssl=settings.object_store_use_tls,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    assert settings.object_store_bucket is not None
    return Boto3ObjectStore(client, settings.object_store_bucket)
