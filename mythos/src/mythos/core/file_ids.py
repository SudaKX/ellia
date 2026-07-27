from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections.abc import Sequence


class FileIdCodec:
    def __init__(self, signing_key: str) -> None:
        self._signing_key = signing_key.encode()

    @property
    def key_fingerprint(self) -> str:
        return hashlib.sha256(self._signing_key).hexdigest()

    def encode(self, stable_id: str) -> str:
        return self._encode("file:v1", stable_id)

    def encode_content_token(
        self,
        stable_id: str,
        revision: str,
        object_key: str,
        object_version_id: str,
        media_type: str,
        download_name: str,
    ) -> str:
        payload = json.dumps(
            (stable_id, revision, object_key, object_version_id, media_type, download_name),
            ensure_ascii=True,
            separators=(",", ":"),
        )
        return self._encode("file-content:v1", payload, prefix="ct1_")

    def encode_tree_version(self, entries: Sequence[tuple[str, ...]]) -> str:
        payload = json.dumps(entries, ensure_ascii=True, separators=(",", ":"))
        return self._encode("file-tree:v1", payload, prefix="ft1_")

    def _encode(self, scope: str, *parts: str, prefix: str = "f1_") -> str:
        payload = ":".join((scope, *parts)).encode()
        digest = hmac.new(self._signing_key, payload, hashlib.sha256).digest()
        return prefix + base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
