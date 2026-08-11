from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, TypeAlias

from mythos.players.interfaces import PlayerInterfaces
from mythos.players.player import Player
from mythos.registry.callbacks import callback_dependencies

AchievementCondition: TypeAlias = Callable[[Player], bool]
AchievementEffect: TypeAlias = Callable[[Player], Awaitable[None]]

_ACHIEVEMENT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


@dataclass(frozen=True, slots=True)
class AchievementDefinition:
    stable_id: str
    immediate: bool
    meta: Mapping[str, Any]
    condition: AchievementCondition
    effect: AchievementEffect
    dependencies: PlayerInterfaces = field(init=False, default=PlayerInterfaces.NONE)

    def __post_init__(self) -> None:
        if not isinstance(self.stable_id, str) or not _ACHIEVEMENT_ID_PATTERN.fullmatch(self.stable_id):
            raise ValueError("Achievement IDs must be lowercase slugs up to 128 characters.")
        if not isinstance(self.immediate, bool):
            raise ValueError("Achievement immediate must be a boolean.")
        if not callable(self.condition) or not callable(self.effect):
            raise ValueError("Achievement condition and effect must be callable.")
        object.__setattr__(self, "meta", _freeze_meta(self.meta))
        dependencies = PlayerInterfaces.NONE
        for callback in (self.condition, self.effect):
            declared = callback_dependencies(callback, field_name="Achievement callback")
            if declared is not None:
                dependencies |= declared
        object.__setattr__(self, "dependencies", dependencies)

    def meta_body(self) -> dict[str, Any]:
        return copy_meta(self.meta)


@dataclass(frozen=True, slots=True)
class AchievementFallback:
    stable_id: str
    meta: Mapping[str, Any]
    immediate: bool

    def __post_init__(self) -> None:
        if not isinstance(self.stable_id, str) or not _ACHIEVEMENT_ID_PATTERN.fullmatch(self.stable_id):
            raise ValueError("Achievement fallback IDs must be lowercase slugs up to 128 characters.")
        if not isinstance(self.immediate, bool):
            raise ValueError("Achievement fallback immediate must be a boolean.")
        object.__setattr__(self, "meta", _freeze_meta(self.meta))

    def meta_body(self) -> dict[str, Any]:
        return copy_meta(self.meta)


def copy_meta(meta: Mapping[str, Any]) -> dict[str, Any]:
    value = _thaw_json_value(meta)
    if not isinstance(value, dict):
        raise ValueError("Achievement meta must be a JSON object.")
    return value


def _freeze_meta(meta: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(meta, Mapping):
        raise ValueError("Achievement meta must be a JSON object.")
    try:
        normalized = json.loads(
            json.dumps(dict(meta), ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":"))
        )
    except (TypeError, ValueError) as error:
        raise ValueError("Achievement meta must be JSON serializable.") from error
    if not isinstance(normalized, dict):
        raise ValueError("Achievement meta must be a JSON object.")
    return _freeze_json_value(normalized)


def _freeze_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_json_value(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json_value(item) for item in value)
    return value


def _thaw_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json_value(item) for item in value]
    return value
