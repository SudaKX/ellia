from collections.abc import Mapping
from typing import Any


class CommandRejected(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class ValidationRejected(Exception):
    def __init__(self, reason: str, details: Mapping[str, Any] | None = None) -> None:
        self.reason = reason
        self.details = dict(details or {})
        super().__init__(reason)
