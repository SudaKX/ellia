import asyncio

import pytest

from mythos.endpoints import ResponseAction
from mythos.registry.modules import (
    DuplicateStableIdError,
    ModuleRegistry,
    EndpointNotFoundError,
    RegistryFrozenError,
)


async def _view_callback(_context):
    return (ResponseAction({"ok": True}),)


async def _command_callback(_context, _payload):
    return (ResponseAction({"ok": True}),)


def test_catalog_rejects_duplicate_stable_ids_and_freezes() -> None:
    catalog = ModuleRegistry()
    catalog.register_view("dashboard", "test.dashboard", _view_callback, priority=5)

    with pytest.raises(DuplicateStableIdError):
        catalog.register_command("progress", "test.dashboard", _command_callback)

    catalog.register_view("dashboard", "test.dashboard.priority", _view_callback, priority=1)
    catalog.freeze()

    assert [entry.stable_id for entry in catalog.view_callbacks("dashboard")] == [
        "test.dashboard.priority",
        "test.dashboard",
    ]

    with pytest.raises(RegistryFrozenError):
        catalog.register_command("progress", "test.command", _command_callback)
    with pytest.raises(EndpointNotFoundError):
        catalog.view_callbacks("missing")


def test_catalog_dispatches_registered_command() -> None:
    async def scenario() -> None:
        catalog = ModuleRegistry()
        catalog.register_command("progress", "test.progress", _command_callback)
        catalog.freeze()

        callback = catalog.command_callback("progress", "test.progress").callback
        actions = await callback(None, {})
        assert actions[0].body == {"ok": True}

    asyncio.run(scenario())
