from __future__ import annotations

import hmac
import hashlib
import base64

import pytest

from mythos.core.file_ids import FileIdCodec
from mythos.players.interfaces import PlayerInterfaces
from mythos.registry.achievements import AchievementDefinition, AchievementRegistry
from mythos.registry.callbacks import module_handler
from mythos.registry.errors import DuplicateStableIdError, RegistryError, RegistryFrozenError


@module_handler("test.achievement")(1, dependencies=PlayerInterfaces.PROGRESS)
def _condition(_player) -> bool:
    return True


@module_handler("test.achievement")(1, dependencies=PlayerInterfaces.CREDITS)
async def _effect(_player) -> None:
    return None


def _definition(stable_id: str = "test.achievement") -> AchievementDefinition:
    return AchievementDefinition(
        stable_id=stable_id,
        immediate=True,
        meta={"title": "Test", "nested": {"value": 1}},
        condition=_condition,
        effect=_effect,
    )


def test_achievement_registry_validates_callbacks_freezes_and_derives_ids() -> None:
    registry = AchievementRegistry()
    definition = _definition()
    registry.register(definition)
    with pytest.raises(DuplicateStableIdError):
        registry.register(_definition())

    catalog = registry.freeze(FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes"))
    public_id = catalog.public_id_for(definition.stable_id)

    assert catalog.achievement(definition.stable_id) is definition
    assert catalog.achievement_by_public_id(public_id) is definition
    assert catalog.dependencies == PlayerInterfaces.PROGRESS | PlayerInterfaces.CREDITS
    assert public_id.startswith("a1_")
    with pytest.raises(RegistryFrozenError):
        registry.register(_definition("test.later"))


def test_achievement_registry_rejects_undecorated_callbacks() -> None:
    def condition(_player) -> bool:
        return True

    async def effect(_player) -> None:
        return None

    with pytest.raises(RegistryError, match="Invalid achievement definition"):
        AchievementRegistry().register(
            AchievementDefinition("test.undecorated", False, {}, condition, effect)
        )


def test_achievement_registry_accepts_grant_only_definition_and_uses_effect_dependencies() -> None:
    definition = AchievementDefinition(
        "test.grant-only",
        True,
        {},
        None,
        _effect,
    )
    registry = AchievementRegistry()
    registry.register(definition)

    catalog = registry.freeze(FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes"))

    assert catalog.achievement("test.grant-only").condition is None
    assert catalog.dependencies == PlayerInterfaces.CREDITS


def test_achievement_id_uses_the_separate_nul_terminated_domain() -> None:
    secret = "test-file-id-signing-key-with-at-least-32-bytes"
    stable_id = "test.achievement"
    expected = "a1_" + base64.urlsafe_b64encode(
        hmac.new(secret.encode(), b"achievement:v1\0" + stable_id.encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()

    assert FileIdCodec(secret).encode_achievement_id(stable_id) == expected


def test_fallback_registration_is_overwritten_before_freeze_and_frozen_afterward() -> None:
    registry = AchievementRegistry()
    registry.set_fallback("legacy.achievement", {"title": "Old"}, False)
    registry.set_fallback("legacy.achievement", {"title": "Newest"}, True)

    catalog = registry.freeze(FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes"))
    fallback = catalog.fallback("legacy.achievement")

    assert fallback.meta_body() == {"title": "Newest"}
    assert fallback.immediate is True
    assert catalog.public_id_for("legacy.achievement").startswith("a1_")
    with pytest.raises(RegistryFrozenError):
        registry.set_fallback("legacy.achievement", {}, False)


def test_fallback_registration_validates_data_and_conflicts_at_freeze() -> None:
    registry = AchievementRegistry()
    with pytest.raises(ValueError, match="fallback IDs"):
        registry.set_fallback("Legacy.Achievement", {}, False)
    with pytest.raises(ValueError, match="JSON serializable"):
        registry.set_fallback("legacy.bad-meta", {"value": object()}, False)
    with pytest.raises(ValueError, match="boolean"):
        registry.set_fallback("legacy.bad-immediate", {}, 1)

    registry.register(_definition())
    registry.set_fallback("test.achievement", {}, False)
    with pytest.raises(RegistryError, match="conflicts with active"):
        registry.freeze(FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes"))
