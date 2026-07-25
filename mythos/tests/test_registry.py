import pytest

from mythos.core.file_ids import FileIdCodec
from mythos.registry.errors import (
    DuplicateStableIdError,
    RegistryError,
    RegistryFrozenError,
)
from mythos.registry.bundle import RegistryBundle
from mythos.registry.files import FileContent, FileRegistry, ObjectReference, VirtualNode
from mythos.registry.scripts import Script
from mythos.registry.validations import ValidationAttempt, ValidationAttemptNotFoundError, ValidationOutcome, ValidationRegistry


async def _attempt_handler(_context, _payload):
    return ValidationOutcome(accepted=True)


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
    registries.validations.register_attempt(ValidationAttempt("test.validation", "test-validation", _attempt_handler))

    file_ids = FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes")
    file_tree = registries.files.freeze(file_ids)
    catalogs = registries.freeze(file_ids)

    assert catalogs.files is file_tree
    file = catalogs.files.file(file_tree.file_id_for_stable_id("test.file"))
    assert file.definition is not None
    assert file.definition.content is not None
    assert file.definition.content.object_ref.size_bytes == 4
    assert [item.stable_id for item in catalogs.scripts.visible(None)] == ["test.script"]
    assert catalogs.validations.attempt("test-validation").stable_id == "test.validation"
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
