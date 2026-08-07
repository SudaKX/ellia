from __future__ import annotations

from collections.abc import Mapping

from mythos.registry.errors import RegistryError
from mythos.registry.files.merged_tree import MergedFileTree
from mythos.registry.files.tree import (
    FileTreeDirectoryNotFoundError,
    TreeEntry,
    TreeNode,
    TreeNodeSlot,
    _path_segments,
)


class PlayerFileTreeDirectoryNotFoundError(FileTreeDirectoryNotFoundError):
    pass


class PlayerFileTree:
    def __init__(
        self,
        merged_tree: MergedFileTree,
        nodes_by_path: Mapping[str, TreeNode],
        tree_version: str,
    ) -> None:
        self.merged_tree = merged_tree
        self.root = merged_tree.root
        self._nodes_by_path = dict(nodes_by_path)
        self.tree_version = tree_version
        self.file_id_key_fingerprint = merged_tree.file_id_key_fingerprint

    @property
    def nodes_by_path(self) -> Mapping[str, TreeNode]:
        return self._nodes_by_path

    def file(self, file_id: str) -> TreeNode:
        entry = self.merged_tree.file(file_id)
        file = self._resolve_entry(entry)
        if file is None or not file.is_file:
            raise RegistryError("Virtual file not found.")
        return file

    def file_id_for_stable_id(self, stable_id: str) -> str:
        file_id = self.merged_tree.file_id_for_stable_id(stable_id)
        entry = self.merged_tree.file(file_id)
        if isinstance(entry, TreeNodeSlot) and self._resolve_entry(entry) is None:
            raise RegistryError("Virtual file not found.")
        return file_id

    def directory_chain(self, path: str = "/") -> tuple[TreeNode, ...]:
        try:
            segments = _path_segments(path)
        except FileTreeDirectoryNotFoundError as error:
            raise PlayerFileTreeDirectoryNotFoundError("Virtual directory not found.") from error

        current_entry: TreeEntry = self.merged_tree.root
        current = self._resolve_entry(current_entry)
        assert current is not None
        chain = [current]
        for segment in segments:
            if current_entry.is_file:
                raise PlayerFileTreeDirectoryNotFoundError("Virtual directory not found.")
            child = current_entry.children.get(segment)
            if child is None or child.is_file:
                raise PlayerFileTreeDirectoryNotFoundError("Virtual directory not found.")
            resolved = self._resolve_entry(child)
            if resolved is None:
                raise PlayerFileTreeDirectoryNotFoundError("Virtual directory not found.")
            current_entry = child
            current = resolved
            chain.append(current)
        return tuple(chain)

    def children(self, directory: TreeNode) -> tuple[TreeNode, ...]:
        entry = self.merged_tree.entry_at_path(directory.path)
        if entry is None or entry.is_file:
            raise PlayerFileTreeDirectoryNotFoundError("Virtual directory not found.")
        children: list[TreeNode] = []
        for child in entry.children.values():
            resolved = self._resolve_entry(child)
            if resolved is not None:
                children.append(resolved)
        return tuple(children)

    def file_chain(self, file_id: str) -> tuple[TreeNode, ...]:
        file = self.file(file_id)
        assert file.definition is not None
        try:
            segments = _path_segments(file.definition.path)
        except FileTreeDirectoryNotFoundError as error:
            raise RegistryError("Virtual file is not part of this tree.") from error

        current_entry: TreeEntry = self.merged_tree.root
        current = self._resolve_entry(current_entry)
        assert current is not None
        chain = [current]
        for segment in segments:
            if current_entry.is_file:
                raise RegistryError("Virtual file is not part of this tree.")
            child = current_entry.children.get(segment)
            if child is None:
                raise RegistryError("Virtual file is not part of this tree.")
            resolved = self._resolve_entry(child)
            if resolved is None:
                raise RegistryError("Virtual file is not part of this tree.")
            current_entry = child
            current = resolved
            chain.append(current)
        if current is not file:
            raise RegistryError("Virtual file is not part of this tree.")
        return tuple(chain)

    def _resolve_entry(self, entry: TreeEntry) -> TreeNode | None:
        if isinstance(entry, TreeNode):
            return entry
        return self._nodes_by_path.get(entry.path)
