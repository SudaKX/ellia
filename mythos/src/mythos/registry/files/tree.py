from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from mythos.core.file_ids import FileIdCodec
from mythos.registry.errors import RegistryError
from mythos.registry.files.definitions import VirtualNode


class FileTreeDirectoryNotFoundError(RegistryError):
    pass


@dataclass(frozen=True)
class TreeNode:
    path: str
    definition: VirtualNode | None
    children: Mapping[str, TreeNode]
    file_id: str | None = None

    @property
    def is_file(self) -> bool:
        return self.definition is not None and self.definition.content is not None


class FileTree:
    def __init__(
        self,
        root: TreeNode,
        files_by_public_id: Mapping[str, TreeNode],
        public_ids_by_stable_id: Mapping[str, str],
        file_id_key_fingerprint: str,
    ) -> None:
        self.root = root
        self._files_by_public_id = MappingProxyType(dict(files_by_public_id))
        self._public_ids_by_stable_id = MappingProxyType(dict(public_ids_by_stable_id))
        self.file_id_key_fingerprint = file_id_key_fingerprint

    @classmethod
    def build(cls, nodes: Mapping[str, VirtualNode], file_ids: FileIdCodec) -> FileTree:
        root = _MutableTreeNode(path="/")
        file_ids_by_stable_id = {
            stable_id: file_ids.encode(stable_id)
            for stable_id, node in nodes.items()
            if node.content is not None
        }
        for node in nodes.values():
            if node.content is None:
                _insert_directory(root, node)
        for node in nodes.values():
            if node.content is not None:
                _insert_file(root, node, file_ids_by_stable_id[node.stable_id])

        files_by_public_id: dict[str, TreeNode] = {}
        frozen_root = _freeze_node(root, files_by_public_id)
        return cls(
            frozen_root,
            files_by_public_id,
            file_ids_by_stable_id,
            file_ids.key_fingerprint,
        )

    def file(self, file_id: str) -> TreeNode:
        try:
            return self._files_by_public_id[file_id]
        except KeyError as error:
            raise RegistryError("Virtual file not found.") from error

    def file_id_for_stable_id(self, stable_id: str) -> str:
        try:
            return self._public_ids_by_stable_id[stable_id]
        except KeyError as error:
            raise RegistryError("Virtual file not found.") from error

    def directory_chain(self, path: str) -> tuple[TreeNode, ...]:
        current = self.root
        chain = [current]
        for segment in _path_segments(path):
            child = current.children.get(segment)
            if child is None or child.is_file:
                raise FileTreeDirectoryNotFoundError("Virtual directory not found.")
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
                raise RegistryError("Virtual file is not part of this tree.")
            current = child
            chain.append(current)
        if current is not file:
            raise RegistryError("Virtual file is not part of this tree.")
        return tuple(chain)


@dataclass
class _MutableTreeNode:
    path: str
    definition: VirtualNode | None = None
    children: dict[str, _MutableTreeNode] | None = None
    file_id: str | None = None

    def __post_init__(self) -> None:
        if self.children is None:
            self.children = {}

    @property
    def is_file(self) -> bool:
        return self.definition is not None and self.definition.content is not None


def _insert_directory(root: _MutableTreeNode, definition: VirtualNode) -> None:
    current = root
    for segment in _path_segments(definition.path):
        assert current.children is not None
        child = current.children.get(segment)
        if child is None:
            child = _MutableTreeNode(path=_child_path(current.path, segment))
            current.children[segment] = child
        elif child.is_file:
            raise RegistryError("A virtual file cannot also be a directory.")
        current = child
    if current.definition is not None:
        raise RegistryError("Virtual node paths must be unique.")
    current.definition = definition


def _insert_file(root: _MutableTreeNode, definition: VirtualNode, file_id: str) -> None:
    segments = _path_segments(definition.path)
    current = root
    for segment in segments[:-1]:
        assert current.children is not None
        child = current.children.get(segment)
        if child is None:
            child = _MutableTreeNode(path=_child_path(current.path, segment))
            current.children[segment] = child
        elif child.is_file:
            raise RegistryError("A virtual file cannot contain child nodes.")
        current = child
    name = segments[-1]
    assert current.children is not None
    if name in current.children:
        raise RegistryError("Virtual node paths must be unique.")
    current.children[name] = _MutableTreeNode(
        path=_child_path(current.path, name),
        definition=definition,
        file_id=file_id,
    )


def _freeze_node(node: _MutableTreeNode, files_by_public_id: dict[str, TreeNode]) -> TreeNode:
    assert node.children is not None
    children = {
        name: _freeze_node(child, files_by_public_id)
        for name, child in sorted(node.children.items())
    }
    frozen = TreeNode(
        path=node.path,
        definition=node.definition,
        children=MappingProxyType(children),
        file_id=node.file_id,
    )
    if frozen.file_id is not None:
        files_by_public_id[frozen.file_id] = frozen
    return frozen


def _path_segments(path: str) -> tuple[str, ...]:
    if path == "/":
        return ()
    if not path.startswith("/") or "\\" in path:
        raise FileTreeDirectoryNotFoundError("Virtual directory not found.")
    parts = path.strip("/").split("/")
    if not parts or any(not part or part in {".", ".."} for part in parts):
        raise FileTreeDirectoryNotFoundError("Virtual directory not found.")
    return tuple(parts)


def _child_path(parent: str, child: str) -> str:
    return f"/{child}" if parent == "/" else f"{parent}/{child}"
