import asyncio

import pytest

from mythos.endpoints import ResponseAction
from mythos.core.file_ids import FileIdCodec
from mythos.registry.errors import (
    DuplicateStableIdError,
    EndpointNotFoundError,
    RegistryError,
    RegistryFrozenError,
)
from mythos.registry.bundle import RegistryBundle
from mythos.registry.files import FileContent, FileRegistry, ObjectReference, VirtualNode
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
    registries.files.register(
        VirtualNode(
            "test.file",
            "/file.txt",
            "1",
            FileContent(
                ObjectReference("test/file.txt", "sha256:" + "a" * 64, "text/plain", 4, "test-version"),
                "file.txt",
            ),
        )
    )
    registries.scripts.register(Script("test.script", "1", {"lines": []}))

    file_ids = FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes")
    file_tree = registries.files.freeze(file_ids)
    catalogs = registries.freeze(file_ids)

    assert catalogs.files is file_tree
    file = catalogs.files.file(file_tree.file_id_for_stable_id("test.file"))
    assert file.definition is not None
    assert file.definition.content is not None
    assert file.definition.content.object_ref.size_bytes == 4
    assert [item.stable_id for item in catalogs.scripts.visible(None)] == ["test.script"]
    assert registries.freeze(file_ids) is catalogs
    with pytest.raises(RuntimeError, match="different file ID key"):
        registries.freeze(FileIdCodec("another-file-id-signing-key-with-at-least-32-bytes"))
    with pytest.raises(RegistryFrozenError):
        registries.files.register(
            VirtualNode(
                "test.other",
                "/other.txt",
                "1",
                FileContent(
                    ObjectReference("test/other.txt", "sha256:" + "b" * 64, "text/plain", 5, "test-version"),
                    "other.txt",
                ),
            )
        )


def test_file_registry_rejects_file_directory_conflicts_and_empty_directories() -> None:
    file_ids = FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes")
    registry = FileRegistry()
    registry.register(
        VirtualNode(
            "test.report",
            "/report",
            "1",
            FileContent(
                ObjectReference("test/report", "sha256:" + "a" * 64, "text/plain", 4, "test-version"),
                "report.txt",
            ),
        )
    )
    with pytest.raises(RegistryError, match="contain child"):
        registry.register(
            VirtualNode(
                "test.report-guide",
                "/report/guide.txt",
                "1",
                FileContent(
                    ObjectReference("test/report-guide", "sha256:" + "b" * 64, "text/plain", 4, "test-version"),
                    "guide.txt",
                ),
            )
        )

    descendant_first = FileRegistry()
    descendant_first.register(
        VirtualNode(
            "test.guide",
            "/docs/guide.txt",
            "1",
            FileContent(
                ObjectReference("test/guide", "sha256:" + "a" * 64, "text/plain", 4, "test-version"),
                "guide.txt",
            ),
        )
    )
    with pytest.raises(RegistryError, match="also be a directory"):
        descendant_first.register(
            VirtualNode(
                "test.docs-file",
                "/docs",
                "1",
                FileContent(
                    ObjectReference("test/docs", "sha256:" + "b" * 64, "text/plain", 4, "test-version"),
                    "docs.txt",
                ),
            )
        )

    empty_directory = FileRegistry()
    empty_directory.register(VirtualNode("test.empty", "/empty", "1"))
    with pytest.raises(RegistryError, match="contain a file descendant"):
        empty_directory.freeze(file_ids)
