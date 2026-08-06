from __future__ import annotations

from collections.abc import Mapping, Sequence

from mythos.core.file_ids import FileIdCodec
from mythos.registry.files.tree import (
    FileTree,
    FileTreeDirectoryNotFoundError,
    TreeNode,
    _build_node,
    _insert_file,
    _MutableTreeNode,
)


class PlayerFileTreeDirectoryNotFoundError(FileTreeDirectoryNotFoundError):
    pass


class PlayerFileTree:
    def __init__(
        self,
        root: TreeNode,
        files_by_public_id: Mapping[str, TreeNode],
        tree_version: str,
        file_id_key_fingerprint: str,
        file_ids: FileIdCodec,
    ) -> None:
        self.root = root
        self._files_by_public_id = dict(files_by_public_id)
        self.tree_version = tree_version
        self.file_id_key_fingerprint = file_id_key_fingerprint
        self._file_ids = file_ids

    @classmethod
    def build(
        cls,
        static_tree: FileTree,
        artifact_nodes: Sequence[TreeNode],
        file_ids: FileIdCodec,
        *,
        artifact_catalog_version: str,
        player_version: int,
    ) -> PlayerFileTree:
        root = _copy_static_node(static_tree.root)
        for artifact_node in sorted(artifact_nodes, key=lambda node: node.path):
            assert artifact_node.definition is not None
            assert artifact_node.content is not None
            assert artifact_node.file_id is not None
            _insert_file(root, artifact_node.definition, artifact_node.content, artifact_node.file_id)

        files_by_public_id: dict[str, TreeNode] = {}
        built_root = _build_node(root, files_by_public_id)
        tree_version = _build_tree_version(
            static_tree,
            file_ids,
            artifact_catalog_version,
            player_version,
        )
        return cls(
            built_root,
            files_by_public_id,
            tree_version,
            static_tree.file_id_key_fingerprint,
            file_ids,
        )

    def file(self, file_id: str) -> TreeNode:
        try:
            return self._files_by_public_id[file_id]
        except KeyError as error:
            from mythos.registry.errors import RegistryError

            raise RegistryError("Virtual file not found.") from error

    def file_id_for_stable_id(self, stable_id: str) -> str:
        from mythos.registry.errors import RegistryError

        file_id = self._file_ids.encode(stable_id)
        if file_id not in self._files_by_public_id:
            raise RegistryError("Virtual file not found.") from None
        return file_id

    def directory_chain(self, path: str) -> tuple[TreeNode, ...]:
        current = self.root
        chain = [current]
        for segment in _path_segments(path):
            child = current.children.get(segment)
            if child is None or child.is_file:
                raise PlayerFileTreeDirectoryNotFoundError("Virtual directory not found.")
            current = child
            chain.append(current)
        return tuple(chain)

    def file_chain(self, file_id: str) -> tuple[TreeNode, ...]:
        file = self.file(file_id)
        assert file.definition is not None
        current = self.root
        chain = [current]
        for segment in _path_segments(file.definition.path):
            child = current.children.get(segment)
            if child is None:
                from mythos.registry.errors import RegistryError

                raise RegistryError("Virtual file is not part of this tree.")
            current = child
            chain.append(current)
        if current is not file:
            from mythos.registry.errors import RegistryError

            raise RegistryError("Virtual file is not part of this tree.")
        return tuple(chain)


def _copy_static_node(node: TreeNode) -> _MutableTreeNode:
    return _MutableTreeNode(
        path=node.path,
        definition=node.definition,
        content=node.content,
        file_id=node.file_id,
        children={name: _copy_static_node(child) for name, child in node.children.items()},
    )


def _build_tree_version(
    static_tree: FileTree,
    file_ids: FileIdCodec,
    artifact_catalog_version: str,
    player_version: int,
) -> str:
    return file_ids.encode_player_tree_version(
        static_tree.tree_version,
        artifact_catalog_version,
        player_version,
    )


def _path_segments(path: str) -> tuple[str, ...]:
    if path == "/":
        return ()
    if not path.startswith("/") or "\\" in path:
        raise PlayerFileTreeDirectoryNotFoundError("Virtual directory not found.")
    parts = path.strip("/").split("/")
    if not parts or any(not part or part in {".", ".."} for part in parts):
        raise PlayerFileTreeDirectoryNotFoundError("Virtual directory not found.")
    return tuple(parts)
