from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, TypeAlias

from fastapi.encoders import jsonable_encoder

FollowupBody: TypeAlias = Mapping[str, Any]


class FollowupFormatError(Exception):
    pass


class FollowupCollector:
    def __init__(self) -> None:
        self._items: list[dict[str, Any]] = []
        self._frozen = False

    def add(self, body: FollowupBody) -> None:
        if self._frozen:
            raise RuntimeError("Followups are already frozen.")
        try:
            encoded = jsonable_encoder(dict(body))
            json.dumps(encoded, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise FollowupFormatError("Followups must be JSON serializable.") from error
        if not isinstance(encoded, dict):
            raise FollowupFormatError("Followups must encode to JSON objects.")
        self._items.append(encoded)

    def freeze(self) -> tuple[dict[str, Any], ...]:
        self._frozen = True
        return tuple(self._items)
