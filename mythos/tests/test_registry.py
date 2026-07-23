import asyncio

import pytest

from mythos.endpoints import ResponseAction
from mythos.registry.errors import (
    DuplicateStableIdError,
    EndpointNotFoundError,
    RegistryFrozenError,
)
from mythos.registry.bundle import RegistryBundle
from mythos.registry.files import VirtualFile
from mythos.registry.modules import ModuleRegistry
from mythos.registry.scripts import Script


async def _view_callback(_context):
    return (ResponseAction({"ok": True}),)


async def _command_callback(_context, _payload):
    return (ResponseAction({"ok": True}),)


def test_catalog_rejects_duplicate_stable_ids_and_freezes() -> None:
    registry = ModuleRegistry()
    registry.register_view("dashboard", "test.dashboard", _view_callback, priority=5)

    with pytest.raises(DuplicateStableIdError):
        registry.register_command("progress", "test.dashboard", _command_callback)

    registry.register_view("dashboard", "test.dashboard.priority", _view_callback, priority=1)
    catalog = registry.freeze()

    assert [entry.stable_id for entry in catalog.view_callbacks("dashboard")] == [
        "test.dashboard.priority",
        "test.dashboard",
    ]

    with pytest.raises(RegistryFrozenError):
        registry.register_command("progress", "test.command", _command_callback)
    with pytest.raises(EndpointNotFoundError):
        catalog.view_callbacks("missing")


def test_catalog_dispatches_registered_command() -> None:
    async def scenario() -> None:
        registry = ModuleRegistry()
        registry.register_command("progress", "test.progress", _command_callback)
        catalog = registry.freeze()

        callback = catalog.command_callback("progress", "test.progress").callback
        actions = await callback(None, {})
        assert actions[0].body == {"ok": True}

    asyncio.run(scenario())


def test_registry_bundle_freezes_runtime_catalogs() -> None:
    registries = RegistryBundle()
    registries.files.register(VirtualFile("test.file", "/file.txt", "1", b"file"))
    registries.scripts.register(Script("test.script", "1", {"lines": []}))

    file_catalog = registries.files.freeze()
    catalogs = registries.freeze()

    assert catalogs.files is file_catalog
    assert catalogs.files.get("test.file").content == b"file"
    assert [item.stable_id for item in catalogs.scripts.visible(None)] == ["test.script"]
    assert registries.freeze() is catalogs
    with pytest.raises(RegistryFrozenError):
        registries.files.register(VirtualFile("test.other", "/other.txt", "1", b"other"))
