from __future__ import annotations

import base64
import hashlib
import hmac


class FileIdCodec:
    def __init__(self, signing_key: str) -> None:
        self._signing_key = signing_key.encode()

    @property
    def key_fingerprint(self) -> str:
        return hashlib.sha256(self._signing_key).hexdigest()

    def encode(self, stable_id: str) -> str:
        digest = hmac.new(
            self._signing_key,
            f"file:v1:{stable_id}".encode(),
            hashlib.sha256,
        ).digest()
        return "f1_" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
