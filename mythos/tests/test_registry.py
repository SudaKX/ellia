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


def test_file_tree_versions_follow_node_revision_and_object_version() -> None:
    file_ids = FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes")

    def build_tree(*, revision: str, object_version_id: str):
        registry = FileRegistry()
        source_locator = registry.register_source(FileReference("test", "assets/file.txt", "text/plain"))
        registry.register_node(
            VirtualNode.file("test.file", "/file.txt", revision, source_locator, "file.txt")
        )
        registry.materialize_static_files(
            {
                source_locator: ObjectReference(
                    "static/test/assets/file.txt",
                    "sha256:" + "a" * 64,
                    "text/plain",
                    4,
                    object_version_id,
                )
            }
        )
        return registry.freeze(file_ids)

    first = build_tree(revision="1", object_version_id="object-v1")
    changed_object = build_tree(revision="1", object_version_id="object-v2")
    changed_revision = build_tree(revision="2", object_version_id="object-v1")

    first_id = first.file_id_for_stable_id("test.file")
    assert changed_object.file_id_for_stable_id("test.file") == first_id
    assert changed_revision.file_id_for_stable_id("test.file") == first_id
    assert first.file(first_id).content is not None
    assert changed_object.file(first_id).content is not None
    assert changed_revision.file(first_id).content is not None
    assert first.file(first_id).content.content_token != changed_object.file(first_id).content.content_token
    assert first.file(first_id).content.content_token != changed_revision.file(first_id).content.content_token
    assert first.tree_version != changed_object.tree_version
    assert first.tree_version != changed_revision.tree_version


def test_file_content_token_follows_representation_metadata() -> None:
    file_ids = FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes")

    def build_tree(*, media_type: str, download_name: str, object_key: str = "static/test/assets/file.txt"):
        registry = FileRegistry()
        source_locator = registry.register_source(FileReference("test", "assets/file.txt", media_type))
        registry.register_node(
            VirtualNode.file("test.file", "/file.txt", "1", source_locator, download_name)
        )
        registry.materialize_static_files(
            {
                source_locator: ObjectReference(
                    object_key,
                    "sha256:" + "a" * 64,
                    media_type,
                    4,
                    "object-v1",
                )
            }
        )
        return registry.freeze(file_ids)

    plain = build_tree(media_type="text/plain", download_name="file.txt")
    html = build_tree(media_type="text/html", download_name="file.txt")
    renamed = build_tree(media_type="text/plain", download_name="renamed.txt")
    moved = build_tree(
        media_type="text/plain",
        download_name="file.txt",
        object_key="static/test/assets/moved-file.txt",
    )
    file_id = plain.file_id_for_stable_id("test.file")
    assert plain.file(file_id).content is not None
    assert html.file(file_id).content is not None
    assert renamed.file(file_id).content is not None
    assert moved.file(file_id).content is not None
    assert plain.file(file_id).content.content_token != html.file(file_id).content.content_token
    assert plain.file(file_id).content.content_token != renamed.file(file_id).content.content_token
    assert plain.file(file_id).content.content_token != moved.file(file_id).content.content_token
    assert plain.tree_version != html.tree_version
    assert plain.tree_version != renamed.tree_version
    assert plain.tree_version != moved.tree_version
