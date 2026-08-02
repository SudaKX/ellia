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
        version: str,
        object_key: str,
        object_version_id: str,
        media_type: str,
        download_name: str,
    ) -> str:
        payload = json.dumps(
            (stable_id, version, object_key, object_version_id, media_type, download_name),
            ensure_ascii=True,
            separators=(",", ":"),
        )
        return self._encode("file-content:v2", payload, prefix="ct2_")

    def encode_artifact_content_token(
        self,
        player_id: str,
        stable_id: str,
        artifact_version: str,
        artifact_node_version: str,
        object_key: str,
        object_version_id: str,
        media_type: str,
        download_name: str,
    ) -> str:
        payload = json.dumps(
            (
                player_id,
                stable_id,
                artifact_version,
                artifact_node_version,
                object_key,
                object_version_id,
                media_type,
                download_name,
            ),
            ensure_ascii=True,
            separators=(",", ":"),
        )
        return self._encode("artifact-content:v2", payload, prefix="act2_")

    def encode_tree_version(self, entries: Sequence[tuple[str, ...]]) -> str:
        payload = json.dumps(entries, ensure_ascii=True, separators=(",", ":"))
        return self._encode("file-tree:v1", payload, prefix="ft1_")

    def encode_player_tree_version(
        self,
        static_tree_version: str,
        template_version: str,
        player_version: int,
    ) -> str:
        payload = json.dumps(
            (static_tree_version, template_version, player_version),
            ensure_ascii=True,
            separators=(",", ":"),
        )
        return self._encode("player-file-tree:v2", payload, prefix="pft2_")

    def _encode(self, scope: str, *parts: str, prefix: str = "f1_") -> str:
        payload = ":".join((scope, *parts)).encode()
        digest = hmac.new(self._signing_key, payload, hashlib.sha256).digest()
        return prefix + base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
