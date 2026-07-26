import pytest
import asyncio

from mythos.core.file_ids import FileIdCodec
from mythos.registry.errors import (
    DuplicateStableIdError,
    RegistryError,
    RegistryFrozenError,
)
from mythos.registry.bundle import RegistryBundle
from mythos.registry.files import FileReference, FileRegistry, ObjectReference, VirtualNode
from mythos.registry.scripts import Script
from mythos.registry.validations import ValidationAttempt, ValidationAttemptNotFoundError, ValidationOutcome, ValidationRegistry


async def _attempt_handler(_context, _payload):
    return ValidationOutcome(accepted=True)


class FakeStaticPublisher:
    async def materialize(self, sources):
        return {
            source.source_locator: ObjectReference(
                f"static/{source.module}/{source.relative_path}",
                "sha256:" + "a" * 64,
                source.media_type,
                4,
                "test-version",
            )
            for source in sources
        }


def test_validation_registry_rejects_duplicates_and_freezes() -> None:
    registry = ValidationRegistry()
    attempt = ValidationAttempt("test.validation", "test-validation", _attempt_handler)
    registry.register_attempt(attempt)

    with pytest.raises(DuplicateStableIdError):
        registry.register_attempt(ValidationAttempt("test.validation", "other-validation", _attempt_handler))
    with pytest.raises(RegistryError, match="must be unique"):
        registry.register_attempt(ValidationAttempt("test.other", "test-validation", _attempt_handler))

    catalog = registry.freeze()
    assert catalog.attempt("test-validation") is attempt
    with pytest.raises(ValidationAttemptNotFoundError):
        catalog.attempt("missing")
    with pytest.raises(RegistryFrozenError):
        registry.register_attempt(ValidationAttempt("test.later", "later", _attempt_handler))


def test_registry_bundle_freezes_runtime_catalogs() -> None:
    registries = RegistryBundle()
    source_locator = registries.files.register_source(
        FileReference("test", "assets/file.txt", "text/plain")
    )
    registries.files.register_node(
        VirtualNode.file("test.file", "/file.txt", "1", source_locator, "file.txt")
    )
    registries.scripts.register(Script("test.script", "1", {"lines": []}))
    registries.validations.register_attempt(ValidationAttempt("test.validation", "test-validation", _attempt_handler))

    file_ids = FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes")
    asyncio.run(registries.materialize_static_files(FakeStaticPublisher()))
    file_tree = registries.files.freeze(file_ids)
    catalogs = registries.freeze(file_ids)

    assert catalogs.files is file_tree
    file = catalogs.files.file(file_tree.file_id_for_stable_id("test.file"))
    assert file.definition is not None
    assert file.content is not None
    assert file.content.object_ref.size_bytes == 4
    assert [item.stable_id for item in catalogs.scripts.visible(None)] == ["test.script"]
    assert catalogs.validations.attempt("test-validation").stable_id == "test.validation"
    assert registries.freeze(file_ids) is catalogs
    with pytest.raises(RuntimeError, match="different file ID key"):
        registries.freeze(FileIdCodec("another-file-id-signing-key-with-at-least-32-bytes"))
    with pytest.raises(RegistryFrozenError):
        registries.files.register_node(
            VirtualNode.file("test.other", "/other.txt", "1", source_locator, "other.txt")
        )


def test_file_registry_rejects_file_directory_conflicts_and_empty_directories() -> None:
    file_ids = FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes")
    registry = FileRegistry()
    report_source = registry.register_source(FileReference("test", "assets/report.txt", "text/plain"))
    registry.register_node(
        VirtualNode.file("test.report", "/report", "1", report_source, "report.txt")
    )
    with pytest.raises(RegistryError, match="contain child"):
        guide_source = registry.register_source(FileReference("test", "assets/report-guide.txt", "text/plain"))
        registry.register_node(
            VirtualNode.file("test.report-guide", "/report/guide.txt", "1", guide_source, "guide.txt")
        )

    descendant_first = FileRegistry()
    guide_source = descendant_first.register_source(FileReference("test", "assets/guide.txt", "text/plain"))
    descendant_first.register_node(
        VirtualNode.file("test.guide", "/docs/guide.txt", "1", guide_source, "guide.txt")
    )
    with pytest.raises(RegistryError, match="also be a directory"):
        docs_source = descendant_first.register_source(FileReference("test", "assets/docs.txt", "text/plain"))
        descendant_first.register_node(
            VirtualNode.file("test.docs-file", "/docs", "1", docs_source, "docs.txt")
        )

    empty_directory = FileRegistry()
    empty_directory.register_node(VirtualNode.directory("test.empty", "/empty", "1"))
    with pytest.raises(RegistryError, match="contain a file descendant"):
        empty_directory.freeze(file_ids)
