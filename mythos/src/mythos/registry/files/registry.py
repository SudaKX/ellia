from __future__ import annotations

from mythos.core.file_ids import FileIdCodec
from mythos.registry.errors import DuplicateStableIdError, RegistryError, RegistryFrozenError
from mythos.registry.files.definitions import VirtualNode
from mythos.registry.files.tree import FileTree


class FileRegistry:
    def __init__(self) -> None:
        self._nodes_by_stable_id: dict[str, VirtualNode] = {}
        self._file_paths: set[str] = set()
        self._explicit_directory_paths: set[str] = set()
        self._directory_paths: set[str] = set()
        self._frozen = False
        self._tree: FileTree | None = None

    def register(self, node: VirtualNode) -> None:
        self._ensure_mutable()
        self._validate_node(node)
        if node.stable_id in self._nodes_by_stable_id:
            raise DuplicateStableIdError(node.stable_id)
        if node.content is None:
            self._register_directory(node)
        else:
            self._register_file(node)
        self._nodes_by_stable_id[node.stable_id] = node

    def freeze(self, file_ids: FileIdCodec) -> FileTree:
        if self._tree is not None:
            if self._tree.file_id_key_fingerprint != file_ids.key_fingerprint:
                raise RegistryError("File registry is already frozen with a different file ID key.")
            return self._tree
        self._ensure_no_empty_directories()
        self._frozen = True
        self._tree = FileTree.build(self._nodes_by_stable_id, file_ids)
        return self._tree

    def _validate_node(self, node: VirtualNode) -> None:
        if not node.stable_id or not _is_canonical_virtual_path(node.path):
            raise RegistryError("Virtual nodes require a stable ID and a canonical absolute path.")
        if node.content is not None and not _is_safe_download_name(node.content.download_name):
            raise RegistryError("Virtual files require a safe download name.")

    def _register_directory(self, node: VirtualNode) -> None:
        if node.path in self._file_paths or node.path in self._explicit_directory_paths:
            raise RegistryError("Virtual node paths must be unique.")
        self._ensure_no_file_ancestor(node.path)
        self._explicit_directory_paths.add(node.path)
        self._directory_paths.update(_directory_paths_for(node.path, include_self=True))

    def _register_file(self, node: VirtualNode) -> None:
        if node.path in self._file_paths or node.path in self._directory_paths:
            raise RegistryError("A virtual file cannot also be a directory.")
        self._ensure_no_file_ancestor(node.path)
        self._file_paths.add(node.path)
        self._directory_paths.update(_directory_paths_for(node.path, include_self=False))

    def _ensure_no_file_ancestor(self, path: str) -> None:
        for ancestor in _directory_paths_for(path, include_self=False):
            if ancestor in self._file_paths:
                raise RegistryError("A virtual file cannot contain child nodes.")

    def _ensure_no_empty_directories(self) -> None:
        for directory in self._explicit_directory_paths:
            if not any(path.startswith(directory + "/") for path in self._file_paths):
                raise RegistryError("Virtual directories must contain a file descendant.")

    def _ensure_mutable(self) -> None:
        if self._frozen:
            raise RegistryFrozenError("The file registry is frozen.")


def _is_canonical_virtual_path(path: str) -> bool:
    if not path.startswith("/") or path == "/" or path.endswith("/") or "\\" in path:
        return False
    parts = path.split("/")[1:]
    return all(part and part not in {".", ".."} for part in parts)


def _is_safe_download_name(value: str) -> bool:
    return bool(value) and all(
        32 <= ord(character) <= 126 and character not in '"/\\'
        for character in value
    )


def _directory_paths_for(path: str, *, include_self: bool) -> tuple[str, ...]:
    parts = path.split("/")[1:]
    last_index = len(parts) if include_self else len(parts) - 1
    return tuple("/" + "/".join(parts[:index]) for index in range(1, last_index + 1))
