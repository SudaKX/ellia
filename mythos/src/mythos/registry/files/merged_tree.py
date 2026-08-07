from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from mythos.core.file_ids import FileIdCodec
from mythos.core.player_interfaces import PlayerInterfaces
from mythos.registry.callbacks import callback_dependencies
from mythos.registry.catalog_snapshots import fingerprint
from mythos.registry.errors import RegistryError
from mythos.registry.files.tree import (
    FileTree,
    TreeEntry,
    TreeNode,
    TreeNodeSlot,
    _child_path,
    _path_segments,
)

if TYPE_CHECKING:
    from mythos.registry.artifacts.catalog import ArtifactCatalog
    from mythos.registry.files.player_tree import PlayerFileTree


class MergedFileTree:
    def __init__(
        self,
        root: TreeNode,
        static_files_by_public_id: Mapping[str, TreeNode],
        slots_by_path: Mapping[str, TreeNodeSlot],
        slots_by_public_id: Mapping[str, TreeNodeSlot],
        public_ids_by_stable_id: Mapping[str, str],
        file_id_key_fingerprint: str,
        resource_version: str,
        required_interfaces: PlayerInterfaces,
    ) -> None:
        self.root = root
        self._static_files_by_public_id = dict(static_files_by_public_id)
        self._slots_by_path = dict(slots_by_path)
        self._slots_by_public_id = dict(slots_by_public_id)
        self._public_ids_by_stable_id = dict(public_ids_by_stable_id)
        self.file_id_key_fingerprint = file_id_key_fingerprint
        self.resource_version = resource_version
        self.required_interfaces = required_interfaces

    @classmethod
    def build(
        cls,
        static_tree: FileTree,
        artifact_catalog: ArtifactCatalog,
        file_ids: FileIdCodec,
    ) -> MergedFileTree:
        root = _copy_static_node(static_tree.root)
        static_files_by_public_id: dict[str, TreeNode] = {}
        public_ids_by_stable_id: dict[str, str] = {}
        _index_static_nodes(root, static_files_by_public_id, public_ids_by_stable_id)

        slots_by_path: dict[str, TreeNodeSlot] = {}
        slots_by_public_id: dict[str, TreeNodeSlot] = {}
        for stable_id in sorted(artifact_catalog.node_stable_ids):
            template = artifact_catalog.node_template(stable_id)
            file_id = file_ids.encode(stable_id)
            if file_id in static_files_by_public_id or file_id in slots_by_public_id:
                raise RegistryError("Static and Artifact file IDs must be unique.")
            _insert_slot(
                root,
                template.path,
                template.artifact_locator,
                file_id,
                slots_by_path,
                slots_by_public_id,
            )
            public_ids_by_stable_id[stable_id] = file_id

        required_interfaces = _required_interfaces(root, artifact_catalog)
        unsupported = required_interfaces & ~(
            PlayerInterfaces.PROGRESS
            | PlayerInterfaces.ARTIFACTS
            | PlayerInterfaces.ACCOUNTS
            | PlayerInterfaces.CREDITS
        )
        if unsupported:
            raise RegistryError("Merged file access rules require unsupported PlayerInterface versions.")

        resource_version = fingerprint(
            "mft1_",
            {
                "schema": 1,
                "static_tree_version": static_tree.tree_version,
                "artifact_catalog_version": artifact_catalog.version,
            },
        )
        return cls(
            root,
            static_files_by_public_id,
            slots_by_path,
            slots_by_public_id,
            public_ids_by_stable_id,
            static_tree.file_id_key_fingerprint,
            resource_version,
            required_interfaces,
        )

    @property
    def slots_by_path(self) -> Mapping[str, TreeNodeSlot]:
        return self._slots_by_path

    def file(self, file_id: str) -> TreeEntry:
        static_file = self._static_files_by_public_id.get(file_id)
        if static_file is not None:
            return static_file
        slot = self._slots_by_public_id.get(file_id)
        if slot is not None:
            return slot
        raise RegistryError("Virtual file not found.")

    def file_id_for_stable_id(self, stable_id: str) -> str:
        try:
            return self._public_ids_by_stable_id[stable_id]
        except KeyError as error:
            raise RegistryError("Virtual file not found.") from error

    def entry_at_path(self, path: str) -> TreeEntry | None:
        current: TreeEntry = self.root
        for segment in _path_segments(path):
            if current.is_file:
                return None
            child = current.children.get(segment)
            if child is None:
                return None
            current = child
        return current

    def fruit(self, artifact_nodes: Sequence[TreeNode], *, tree_version: str) -> PlayerFileTree:
        from mythos.registry.files.player_tree import PlayerFileTree

        nodes_by_path: dict[str, TreeNode] = {}
        for artifact_node in sorted(
            artifact_nodes,
            key=lambda node: (node.path, node.file_id or ""),
        ):
            slot = self._slots_by_path.get(artifact_node.path)
            if slot is None or not slot.is_file:
                continue
            nodes_by_path[artifact_node.path] = artifact_node
            for ancestor_path in _ancestor_paths(artifact_node.path):
                if ancestor_path in nodes_by_path:
                    continue
                entry = self.entry_at_path(ancestor_path)
                if entry is None or entry.is_file:
                    continue
                nodes_by_path[ancestor_path] = TreeNode(
                    path=ancestor_path,
                    definition=None,
                    children={},
                )
        return PlayerFileTree(self, nodes_by_path, tree_version)


def _copy_static_node(node: TreeNode) -> TreeNode:
    return TreeNode(
        path=node.path,
        definition=node.definition,
        children={name: _copy_static_node(child) for name, child in node.children.items()},
        content=node.content,
        file_id=node.file_id,
    )


def _index_static_nodes(
    node: TreeNode,
    files_by_public_id: dict[str, TreeNode],
    public_ids_by_stable_id: dict[str, str],
) -> None:
    if node.file_id is not None:
        if node.file_id in files_by_public_id:
            raise RegistryError("Static file IDs must be unique.")
        files_by_public_id[node.file_id] = node
        assert node.definition is not None
        public_ids_by_stable_id[node.definition.stable_id] = node.file_id
    for child in node.children.values():
        if not isinstance(child, TreeNode):
            raise RegistryError("Static FileTree cannot contain Artifact slots.")
        _index_static_nodes(child, files_by_public_id, public_ids_by_stable_id)


def _insert_slot(
    root: TreeNode,
    path: str,
    artifact_locator: str,
    file_id: str,
    slots_by_path: dict[str, TreeNodeSlot],
    slots_by_public_id: dict[str, TreeNodeSlot],
) -> None:
    segments = _path_segments(path)
    current: TreeEntry = root
    for segment in segments[:-1]:
        child = current.children.get(segment)
        if child is None:
            child = TreeNodeSlot(path=_child_path(current.path, segment), children={})
            current.children[segment] = child
            slots_by_path[child.path] = child
        elif child.is_file:
            raise RegistryError("An Artifact file cannot contain child nodes.")
        current = child

    leaf_name = segments[-1]
    if leaf_name in current.children:
        raise RegistryError("Static and Artifact node paths must be unique.")
    slot = TreeNodeSlot(
        path=path,
        children={},
        artifact_locator=artifact_locator,
        file_id=file_id,
    )
    current.children[leaf_name] = slot
    slots_by_path[path] = slot
    slots_by_public_id[file_id] = slot


def _ancestor_paths(path: str) -> tuple[str, ...]:
    parts = _path_segments(path)
    return tuple("/" + "/".join(parts[:index]) for index in range(1, len(parts)))


def _required_interfaces(root: TreeNode, artifact_catalog: ArtifactCatalog) -> PlayerInterfaces:
    dependencies = PlayerInterfaces.NONE

    def visit(node: TreeEntry) -> None:
        nonlocal dependencies
        if isinstance(node, TreeNode):
            if node.definition is not None and node.definition.access_rule is not None:
                declared = callback_dependencies(
                    node.definition.access_rule,
                    field_name="Static node access rule",
                    required=True,
                )
                assert declared is not None
                dependencies |= declared
        for child in node.children.values():
            visit(child)

    visit(root)
    for stable_id in artifact_catalog.node_stable_ids:
        template = artifact_catalog.node_template(stable_id)
        if template.access_rule is None:
            continue
        declared = callback_dependencies(
            template.access_rule,
            field_name="Artifact node access rule",
            required=True,
        )
        assert declared is not None
        dependencies |= declared
    return dependencies
