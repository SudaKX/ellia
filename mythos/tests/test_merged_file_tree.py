import mythos.commands  # noqa: F401  # ensure command models load before validation definitions

import pytest

from mythos.core.file_ids import FileIdCodec
from mythos.registry.artifacts import ArtifactNodeTemplate, ArtifactTemplate, RawArtifact, module_handler
from mythos.registry.bundle import RegistryBundle
from mythos.registry.errors import RegistryError
from mythos.registry.files import (
    FileContent,
    NodeDisplayParams,
    ObjectReference,
    StaticNodeSpec,
    TreeNode,
    TreeNodeSlot,
)
from mythos.registry.files.player_tree import PlayerFileTreeDirectoryNotFoundError


_FILE_IDS = FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes")


def _display(label: str) -> NodeDisplayParams:
    return NodeDisplayParams(label=label, icon="document")


@module_handler("merged-tree")(1)
async def _artifact_generator(_player):
    return RawArtifact(b"content")


@module_handler("merged-tree")(1)
async def _node_generator(_player, _meta, node):
    return node


def _build_catalog(*paths: tuple[str, str]):
    registries = RegistryBundle()
    registries.artifacts.register_template(
        ArtifactTemplate(
            artifact_id="test.artifact",
            media_type="text/plain",
            download_name="artifact.txt",
            generator=_artifact_generator,
        )
    )
    for stable_id, path in paths:
        registries.artifacts.register_node(
            ArtifactNodeTemplate(
                stable_id=stable_id,
                path=path,
                artifact_locator="test.artifact",
                display=_display(stable_id),
                node_generator=_node_generator,
            )
        )
    return registries.freeze(_FILE_IDS)


def test_merged_file_tree_builds_shared_artifact_slots() -> None:
    catalogs = _build_catalog(
        ("test.archive-a", "/archive/a.txt"),
        ("test.archive-b", "/archive/b.txt"),
    )

    archive = catalogs.merged_files.root.children["archive"]
    assert isinstance(archive, TreeNodeSlot)
    assert archive.artifact_locator is None
    assert set(archive.children) == {"a.txt", "b.txt"}
    assert catalogs.merged_files.file_id_for_stable_id("test.archive-a") == _FILE_IDS.encode("test.archive-a")
    assert catalogs.merged_files.resource_version.startswith("mft1_")


def test_merged_file_tree_rejects_static_and_artifact_path_conflicts() -> None:
    registries = RegistryBundle()
    registries.files.register_node(
        StaticNodeSpec.directory(
            "test.archive",
            "/archive",
            display=NodeDisplayParams(label="Archive", icon="folder"),
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
            stable_id="test.archive-file",
            path="/archive",
            artifact_locator="test.artifact",
            display=_display("Archive file"),
            node_generator=_node_generator,
        )
    )

    with pytest.raises(RegistryError, match="paths must be unique"):
        registries.freeze(_FILE_IDS)


def test_merged_file_tree_resource_version_follows_artifact_catalog() -> None:
    first = _build_catalog(("test.node", "/first.txt"))

    changed_registries = RegistryBundle()
    changed_registries.artifacts.register_template(
        ArtifactTemplate(
            artifact_id="test.artifact",
            media_type="text/plain",
            download_name="artifact.txt",
            generator=_artifact_generator,
        )
    )
    changed_registries.artifacts.register_node(
        ArtifactNodeTemplate(
            stable_id="test.node",
            path="/first.txt",
            artifact_locator="test.artifact",
            display=_display("Changed"),
            node_generator=_node_generator,
        )
    )
    changed = changed_registries.freeze(_FILE_IDS)

    assert first.merged_files.resource_version != changed.merged_files.resource_version


def _materialized_node(catalogs, stable_id: str, *, content: bytes = b"content") -> TreeNode:
    template = catalogs.artifacts.node_template(stable_id)
    runtime = template.to_runtime_node(catalogs.artifacts.node_version(stable_id))
    artifact_locator = template.artifact_locator
    file_id = _FILE_IDS.encode(stable_id)
    return TreeNode(
        path=template.path,
        definition=runtime,
        children={},
        content=FileContent(
            object_ref=ObjectReference(
                key=f"artifacts/{stable_id}",
                content_digest="sha256:" + "a" * 64,
                media_type="text/plain",
                size_bytes=len(content),
            ),
            download_name="artifact.txt",
            content_token=f"token-{artifact_locator}",
        ),
        file_id=file_id,
    )


def test_fruiting_resolves_slots_without_copying_merged_topology() -> None:
    catalogs = _build_catalog(("test.archive-a", "/archive/a.txt"))
    merged = catalogs.merged_files
    archive_slot = merged.root.children["archive"]
    node = _materialized_node(catalogs, "test.archive-a")

    player_tree = merged.fruit((node,), tree_version="pft4_test")

    assert player_tree.merged_tree is merged
    assert set(player_tree.nodes_by_path) == {"/archive", "/archive/a.txt"}
    assert player_tree.file(node.file_id) is node
    assert player_tree.directory_chain("/archive")[-1].path == "/archive"
    assert [child.path for child in player_tree.children(player_tree.directory_chain("/archive")[-1])] == [
        "/archive/a.txt"
    ]
    assert merged.root.children["archive"] is archive_slot
    assert isinstance(archive_slot, TreeNodeSlot)


def test_unowned_slots_are_skipped_and_not_file_resolvable() -> None:
    catalogs = _build_catalog(("test.archive-a", "/archive/a.txt"))
    merged = catalogs.merged_files
    player_tree = merged.fruit((), tree_version="pft4_test")

    assert player_tree.children(player_tree.root) == ()
    with pytest.raises(PlayerFileTreeDirectoryNotFoundError):
        player_tree.directory_chain("/archive")
    with pytest.raises(RegistryError, match="not found"):
        player_tree.file(_FILE_IDS.encode("test.archive-a"))


def test_fruiting_maps_are_isolated_between_players() -> None:
    catalogs = _build_catalog(("test.archive-a", "/archive/a.txt"))
    merged = catalogs.merged_files
    first = _materialized_node(catalogs, "test.archive-a", content=b"first")
    second = _materialized_node(catalogs, "test.archive-a", content=b"second")

    first_tree = merged.fruit((first,), tree_version="pft4_first")
    second_tree = merged.fruit((second,), tree_version="pft4_second")

    assert first_tree.nodes_by_path["/archive/a.txt"] is first
    assert second_tree.nodes_by_path["/archive/a.txt"] is second
    assert first_tree.nodes_by_path is not second_tree.nodes_by_path
