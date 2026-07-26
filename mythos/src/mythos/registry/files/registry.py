from __future__ import annotations

from collections.abc import Mapping

from mythos.core.file_ids import FileIdCodec
from mythos.registry.errors import DuplicateStableIdError, RegistryError, RegistryFrozenError
from mythos.registry.files.definitions import FileContent, FileReference, ObjectReference, VirtualNode
from mythos.registry.files.tree import FileTree


class FileRegistry:
    def __init__(self) -> None:
        self._nodes_by_stable_id: dict[str, VirtualNode] = {}
        self._sources_by_locator: dict[str, FileReference] = {}
        self._file_paths: set[str] = set()
        self._explicit_directory_paths: set[str] = set()
        self._directory_paths: set[str] = set()
        self._objects_by_source_locator: dict[str, ObjectReference] | None = None
        self._frozen = False
        self._tree: FileTree | None = None

    def register_source(self, reference: FileReference) -> str:
        self._ensure_mutable()
        if not reference.module or not reference.relative_path or not reference.media_type:
            raise RegistryError("File sources require a module, relative path, and media type.")
        source_locator = reference.source_locator
        if source_locator in self._sources_by_locator:
            raise RegistryError("Static file source locators must be unique.")
        self._sources_by_locator[source_locator] = reference
        return source_locator

    def register_node(self, node: VirtualNode) -> None:
        self._ensure_mutable()
        self._validate_node(node)
        if node.stable_id in self._nodes_by_stable_id:
            raise DuplicateStableIdError(node.stable_id)
        if node.is_file:
            self._register_file(node)
        else:
            self._register_directory(node)
        self._nodes_by_stable_id[node.stable_id] = node

    @property
    def sources(self) -> tuple[FileReference, ...]:
        self._validate_source_bindings()
        return tuple(self._sources_by_locator.values())

    @property
    def is_materialized(self) -> bool:
        return self._objects_by_source_locator is not None

    def materialize_static_files(self, objects_by_source_locator: Mapping[str, ObjectReference]) -> None:
        self._ensure_mutable()
        self._validate_source_bindings()
        expected_locators = set(self._sources_by_locator)
        actual_locators = set(objects_by_source_locator)
        if actual_locators != expected_locators:
            raise RegistryError("Static file materialization must resolve every registered source exactly once.")
        self._objects_by_source_locator = dict(objects_by_source_locator)

    def freeze(self, file_ids: FileIdCodec) -> FileTree:
        if self._tree is not None:
            if self._tree.file_id_key_fingerprint != file_ids.key_fingerprint:
                raise RegistryError("File registry is already frozen with a different file ID key.")
            return self._tree
        self._validate_source_bindings()
        if self._sources_by_locator and self._objects_by_source_locator is None:
            raise RegistryError("Static file sources must be materialized before the file registry is frozen.")
        self._ensure_no_empty_directories()
        self._frozen = True
        contents_by_stable_id: dict[str, FileContent] = {}
        for node in self._nodes_by_stable_id.values():
            if not node.is_file:
                continue
            assert node.source_locator is not None
            assert node.download_name is not None
            contents_by_stable_id[node.stable_id] = FileContent(
                object_ref=self._objects_by_source_locator[node.source_locator],
                download_name=node.download_name,
            )
        self._tree = FileTree.build(self._nodes_by_stable_id, contents_by_stable_id, file_ids)
        return self._tree

    def _validate_node(self, node: VirtualNode) -> None:
        if not node.stable_id or not node.revision or not _is_canonical_virtual_path(node.path):
            raise RegistryError("Virtual nodes require a stable ID, revision, and canonical absolute path.")
        if node.is_file:
            if not node.download_name or not _is_safe_download_name(node.download_name):
                raise RegistryError("Virtual files require a safe download name.")
            return
        if node.download_name is not None:
            raise RegistryError("Virtual directories cannot define a download name.")

    def _validate_source_bindings(self) -> None:
        referenced_locators = {
            node.source_locator
            for node in self._nodes_by_stable_id.values()
            if node.source_locator is not None
        }
        if missing := referenced_locators - set(self._sources_by_locator):
            raise RegistryError(f"Virtual files reference unknown static sources: {sorted(missing)!r}")
        if unused := set(self._sources_by_locator) - referenced_locators:
            raise RegistryError(f"Static file sources are not bound to a virtual file: {sorted(unused)!r}")

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
        if self._frozen or self._objects_by_source_locator is not None:
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
