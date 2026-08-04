import asyncio
import json

import pytest

from mythos.core.file_ids import FileIdCodec
from mythos.registry.artifacts import (
    ArtifactNodeTemplate,
    ArtifactRegistry,
    ArtifactTemplate,
    module_handler,
)
from mythos.registry.errors import (
    DuplicateStableIdError,
    RegistryError,
    RegistryFrozenError,
)
from mythos.registry.bundle import RegistryBundle
from mythos.registry.files import (
    NodeDisplayParams,
    FileReference,
    FileRegistry,
    FileTreeManifest,
    ObjectReference,
    StaticNode,
)
from mythos.registry.hints import Hint, HintDisplayParams, HintRegistry
from mythos.registry.scripts import Script
from mythos.registry.validations import ValidationAttempt, ValidationAttemptNotFoundError, ValidationOutcome, ValidationRegistry


async def _attempt_handler(_context, _payload):
    return ValidationOutcome(accepted=True)


def _display(label: str, icon: str = "document") -> NodeDisplayParams:
    return NodeDisplayParams(label=label, icon=icon)


@module_handler("test")(1)
async def _artifact_generator(_context):
    from mythos.registry.artifacts import RawArtifact

    return RawArtifact(b"content")


@module_handler("test")(1)
async def _artifact_node_generator(_context, node):
    return node


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


def _hint(stable_id: str, source: FileReference, *, access_rule=None) -> Hint:
    return Hint(
        stable_id=stable_id,
        source=source,
        download_name="hint.txt",
        display=HintDisplayParams(title="Hint"),
        vtb_cost=1,
        revision=1,
        access_rule=access_rule,
    )


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


def test_hint_registry_rejects_unsafe_sources_and_async_access_rules() -> None:
    registry = HintRegistry()

    async def async_rule(_player) -> bool:
        return False

    with pytest.raises(RegistryError, match="canonical .*path"):
        registry.register(_hint("test.traversal", FileReference("test", "../secret.txt", "text/plain")))
    with pytest.raises(RegistryError, match="synchronous"):
        registry.register(_hint("test.async-rule", FileReference("test", "assets/hint.txt", "text/plain"), access_rule=async_rule))


def test_hint_registry_requires_the_original_file_id_key_after_freeze() -> None:
    registry = HintRegistry()
    source = FileReference("test", "assets/hint.txt", "text/plain")
    registry.register(_hint("test.hint", source))
    registry.materialize_static_content(
        {
            source.source_locator: ObjectReference(
                "static/test/assets/hint.txt",
                "sha256:" + "a" * 64,
                "text/plain",
                4,
                "test-version",
            )
        }
    )
    file_ids = FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes")
    catalog = registry.freeze(file_ids)
    assert catalog.public_id_for("test.hint").startswith("h1_")
    with pytest.raises(RegistryError, match="different file ID key"):
        registry.freeze(FileIdCodec("another-file-id-signing-key-with-at-least-32-bytes"))


def test_registry_bundle_freezes_runtime_catalogs() -> None:
    registries = RegistryBundle()
    source_locator = registries.files.register_source(
        FileReference("test", "assets/file.txt", "text/plain")
    )
    registries.files.register_node(
        StaticNode.file(
            "test.file",
            "/file.txt",
            "1",
            source_locator,
            "file.txt",
            display=_display("File"),
        )
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
            StaticNode.file(
                "test.other",
                "/other.txt",
                "1",
                source_locator,
                "other.txt",
                display=_display("Other"),
            )
        )


def test_file_registry_rejects_file_directory_conflicts_and_keeps_empty_directories() -> None:
    file_ids = FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes")
    registry = FileRegistry()
    report_source = registry.register_source(FileReference("test", "assets/report.txt", "text/plain"))
    registry.register_node(
        StaticNode.file(
            "test.report",
            "/report",
            "1",
            report_source,
            "report.txt",
            display=_display("Report"),
        )
    )
    with pytest.raises(RegistryError, match="contain child"):
        guide_source = registry.register_source(FileReference("test", "assets/report-guide.txt", "text/plain"))
        registry.register_node(
            StaticNode.file(
                "test.report-guide",
                "/report/guide.txt",
                "1",
                guide_source,
                "guide.txt",
                display=_display("Guide"),
            )
        )

    descendant_first = FileRegistry()
    guide_source = descendant_first.register_source(FileReference("test", "assets/guide.txt", "text/plain"))
    descendant_first.register_node(
        StaticNode.file(
            "test.guide",
            "/docs/guide.txt",
            "1",
            guide_source,
            "guide.txt",
            display=_display("Guide"),
        )
    )
    with pytest.raises(RegistryError, match="also be a directory"):
        docs_source = descendant_first.register_source(FileReference("test", "assets/docs.txt", "text/plain"))
        descendant_first.register_node(
            StaticNode.file(
                "test.docs-file",
                "/docs",
                "1",
                docs_source,
                "docs.txt",
                display=_display("Docs"),
            )
        )

    empty_directory = FileRegistry()
    empty_directory.register_node(
        StaticNode.directory("test.empty", "/empty", "1", display=_display("Empty", "folder"))
    )
    assert empty_directory.freeze(file_ids).directory_chain("/empty")[-1].path == "/empty"


def test_file_tree_versions_follow_node_version_and_object_version() -> None:
    file_ids = FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes")

    def build_tree(*, version: str, object_version_id: str):
        registry = FileRegistry()
        source_locator = registry.register_source(FileReference("test", "assets/file.txt", "text/plain"))
        registry.register_node(
            StaticNode.file(
                "test.file",
                "/file.txt",
                version,
                source_locator,
                "file.txt",
                display=_display("File"),
            )
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

    first = build_tree(version="1", object_version_id="object-v1")
    changed_object = build_tree(version="1", object_version_id="object-v2")
    changed_version = build_tree(version="2", object_version_id="object-v1")

    first_id = first.file_id_for_stable_id("test.file")
    assert changed_object.file_id_for_stable_id("test.file") == first_id
    assert changed_version.file_id_for_stable_id("test.file") == first_id
    assert first.file(first_id).content is not None
    assert changed_object.file(first_id).content is not None
    assert changed_version.file(first_id).content is not None
    assert first.file(first_id).content.content_token != changed_object.file(first_id).content.content_token
    assert first.file(first_id).content.content_token != changed_version.file(first_id).content.content_token
    assert first.tree_version != changed_object.tree_version
    assert first.tree_version != changed_version.tree_version


def test_file_content_token_follows_representation_metadata() -> None:
    file_ids = FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes")

    def build_tree(*, media_type: str, download_name: str, object_key: str = "static/test/assets/file.txt"):
        registry = FileRegistry()
        source_locator = registry.register_source(FileReference("test", "assets/file.txt", media_type))
        registry.register_node(
            StaticNode.file(
                "test.file",
                "/file.txt",
                "1",
                source_locator,
                download_name,
                display=_display("File"),
            )
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


def test_file_tree_versions_follow_display_params_without_changing_content_tokens() -> None:
    file_ids = FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes")

    def build_tree(display: NodeDisplayParams):
        registry = FileRegistry()
        source_locator = registry.register_source(FileReference("test", "assets/file.txt", "text/plain"))
        registry.register_node(
            StaticNode.file(
                "test.file",
                "/file.txt",
                "1",
                source_locator,
                "file.txt",
                display=display,
            )
        )
        registry.materialize_static_files(
            {
                source_locator: ObjectReference(
                    "static/test/assets/file.txt",
                    "sha256:" + "a" * 64,
                    "text/plain",
                    4,
                    "object-v1",
                )
            }
        )
        return registry.freeze(file_ids)

    first = build_tree(_display("File"))
    renamed = build_tree(_display("Renamed"))
    file_id = first.file_id_for_stable_id("test.file")
    assert first.file(file_id).content is not None
    assert renamed.file(file_id).content is not None
    assert first.tree_version != renamed.tree_version
    assert first.file(file_id).content.content_token == renamed.file(file_id).content.content_token


def test_file_tree_versions_follow_hidden_flags() -> None:
    file_ids = FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes")

    def build_tree(*, hidden: bool):
        registry = FileRegistry()
        registry.register_node(
            StaticNode.directory(
                "test.hidden-directory",
                "/hidden",
                "1",
                display=_display("Hidden", "folder"),
                hidden=hidden,
            )
        )
        return registry.freeze(file_ids)

    assert build_tree(hidden=False).tree_version != build_tree(hidden=True).tree_version


def test_file_registry_registers_json_tree_atomically() -> None:
    registry = FileRegistry()
    manifest = {
        "schema_version": 1,
        "module": "test",
        "children": [
            {
                "kind": "directory",
                "stable_id": "test.docs",
                "name": "docs",
                "version": "1",
                "display": {"label": "Docs", "icon": "folder"},
                "access_rule": "docs-visible",
                "hidden": True,
                "children": [
                    {
                        "kind": "file",
                        "stable_id": "test.guide",
                        "name": "guide.txt",
                        "version": "1",
                        "display": {"label": "Guide", "icon": "document"},
                        "source": {"relative_path": "assets/guide.txt", "media_type": "text/plain"},
                        "download_name": "guide.txt",
                    }
                ],
            },
            {
                "kind": "directory",
                "stable_id": "test.empty",
                "name": "empty",
                "version": "1",
                "display": {"label": "Empty", "icon": "folder"},
                "children": [],
            },
        ],
    }
    registry.register_json_tree(json.dumps(manifest), access_rules={"docs-visible": lambda _player: True})
    assert registry.sources == (FileReference("test", "assets/guide.txt", "text/plain"),)
    assert "DirectoryManifest" in FileTreeManifest.model_json_schema()["$defs"]

    invalid = {**manifest, "unexpected": True}
    with pytest.raises(RegistryError, match="Invalid file tree manifest"):
        FileRegistry().register_json_tree(invalid)

    conflicting = {
        "schema_version": 1,
        "module": "test",
        "children": [
            {
                "kind": "file",
                "stable_id": "test.guide",
                "name": "other.txt",
                "version": "1",
                "display": {"label": "Other", "icon": "document"},
                "source": {"relative_path": "assets/other.txt", "media_type": "text/plain"},
                "download_name": "other.txt",
            }
        ],
    }
    with pytest.raises(DuplicateStableIdError):
        registry.register_json_tree(conflicting)
    assert registry.sources == (FileReference("test", "assets/guide.txt", "text/plain"),)

    registry.materialize_static_files(
        {
            "test:assets/guide.txt": ObjectReference(
                "static/test/assets/guide.txt",
                "sha256:" + "a" * 64,
                "text/plain",
                4,
                "test-version",
            )
        }
    )
    tree = registry.freeze(FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes"))
    assert tree.directory_chain("/docs")[-1].definition is not None
    assert tree.directory_chain("/docs")[-1].definition.hidden is True
    assert tree.directory_chain("/empty")[-1].definition is not None


def test_file_registry_reads_json_tree_assets_from_puzzle_root(tmp_path) -> None:
    puzzle_root = tmp_path / "puzzles"
    manifest_path = puzzle_root / "test" / "assets" / "file-tree.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "module": "test",
                "children": [
                    {
                        "kind": "file",
                        "stable_id": "test.guide",
                        "name": "guide.txt",
                        "version": "1",
                        "display": {"label": "Guide", "icon": "document"},
                        "source": {"relative_path": "assets/guide.txt", "media_type": "text/plain"},
                        "download_name": "guide.txt",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    registry = FileRegistry(puzzle_root)
    registry.register_json_tree_asset("test", "assets/file-tree.json")
    assert registry.sources == (FileReference("test", "assets/guide.txt", "text/plain"),)

    mismatched_path = puzzle_root / "other" / "assets" / "file-tree.json"
    mismatched_path.parent.mkdir(parents=True)
    mismatched_path.write_text(manifest_path.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(RegistryError, match="module does not match"):
        registry.register_json_tree_asset("other", "assets/file-tree.json")
    with pytest.raises(RegistryError, match="canonical module-relative"):
        registry.register_json_tree_asset("test", "../file-tree.json")



def test_registry_bundle_rejects_cross_registry_stable_id_collision() -> None:
    registries = RegistryBundle()
    source_locator = registries.files.register_source(FileReference("test", "assets/file.txt", "text/plain"))
    registries.files.register_node(
        StaticNode.file(
            "test.shared",
            "/file.txt",
            "1",
            source_locator,
            "file.txt",
            display=_display("File"),
        )
    )
    registries.artifacts.register_template(
        ArtifactTemplate(
            artifact_id="test.artifact",
            media_type="text/plain",
            download_name="artifact.txt",
            generator=_artifact_generator,
        )
    )
    registries.artifacts.register_node(
        ArtifactNodeTemplate(
            stable_id="test.shared",
            path="/artifact.txt",
            artifact_locator="test.artifact",
            display=_display("Artifact"),
            node_generator=_artifact_node_generator,
        )
    )
    with pytest.raises(DuplicateStableIdError):
        registries.freeze(None)  # type: ignore[arg-type]

