from __future__ import annotations

import base64
import hashlib
import hmac
import json


class FileIdCodec:
    def __init__(self, signing_key: str) -> None:
        self._signing_key = signing_key.encode()

    @property
    def key_fingerprint(self) -> str:
        return hashlib.sha256(self._signing_key).hexdigest()

    def encode(self, stable_id: str) -> str:
        return self._encode("file:v1", stable_id)

    def encode_hint_id(self, stable_id: str) -> str:
        return self._encode("hint:v1", stable_id, prefix="h1_")

    def encode_artifact_content_token(
        self,
        player_id: str,
        artifact_id: str,
        node_id: str,
        artifact_version: str,
        node_version: str,
        media_type: str,
        download_name: str,
    ) -> str:
        return _fingerprint(
            "act3_",
            {
                "schema": 3,
                "player_id": player_id,
                "artifact_id": artifact_id,
                "artifact_version": artifact_version,
                "node_id": node_id,
                "node_version": node_version,
                "download_name": download_name,
                "media_type": media_type,
            },
        )

    def encode_player_tree_version(
        self,
        static_tree_version: str,
        artifact_catalog_version: str,
        player_version: int,
    ) -> str:
        return _fingerprint(
            "pft3_",
            {
                "schema": 3,
                "file_catalog_version": static_tree_version,
                "artifact_catalog_version": artifact_catalog_version,
                "player_version": player_version,
            },
        )

    def _encode(self, scope: str, *parts: str, prefix: str = "f1_") -> str:
        payload = ":".join((scope, *parts)).encode()
        digest = hmac.new(self._signing_key, payload, hashlib.sha256).digest()
        return prefix + base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _fingerprint(prefix: str, value: object) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    return prefix + hashlib.sha256(payload).hexdigest()
