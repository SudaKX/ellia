from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from mythos.core.file_ids import FileIdCodec
from mythos.registry.errors import DuplicateStableIdError, RegistryError, RegistryFrozenError
from mythos.registry.callbacks import validate_callback
from mythos.registry.files.definitions import (
    FileContent,
    FileReference,
    NodeAccessRule,
    ObjectReference,
    StaticNode,
    StaticNodeSpec,
    is_canonical_source_module,
    is_canonical_source_relative_path,
    is_safe_download_name,
)
from mythos.registry.files.tree import FileTree
from mythos.registry.files.versions import static_node_version


class FileRegistry:
    def __init__(self, puzzle_root: Path | None = None) -> None:
        self._nodes_by_stable_id: dict[str, StaticNode] = {}
        self._sources_by_locator: dict[str, FileReference] = {}
        self._file_paths: set[str] = set()
        self._explicit_directory_paths: set[str] = set()
        self._directory_paths: set[str] = set()
        self._objects_by_source_locator: dict[str, ObjectReference] | None = None
        self._frozen = False
        self._tree: FileTree | None = None
        self._puzzle_root: Path | None = None
        if puzzle_root is not None:
            self.configure_puzzle_root(puzzle_root)

    def configure_puzzle_root(self, puzzle_root: Path) -> None:
        self._ensure_mutable()
        resolved_root = puzzle_root.resolve()
        if self._puzzle_root is not None and self._puzzle_root != resolved_root:
            raise RegistryError("File registry is already configured with a different puzzle root.")
        self._puzzle_root = resolved_root

    def register_source(self, reference: FileReference) -> str:
        self._ensure_mutable()
        if (
            not is_canonical_source_module(reference.module)
            or not is_canonical_source_relative_path(reference.relative_path)
            or not reference.media_type
        ):
            raise RegistryError("File sources require canonical module and relative path values.")
        source_locator = reference.source_locator
        if source_locator in self._sources_by_locator:
            raise RegistryError("Static file source locators must be unique.")
        self._sources_by_locator[source_locator] = reference
        return source_locator

    def register_node(self, node: StaticNodeSpec) -> None:
        self._ensure_mutable()
        node = node.to_runtime_node()
        self._validate_node(node)
        if node.stable_id in self._nodes_by_stable_id:
            raise DuplicateStableIdError(node.stable_id)
        if node.is_file:
            self._register_file(node)
        else:
            self._register_directory(node)
        self._nodes_by_stable_id[node.stable_id] = node

    def register_json_tree(
        self,
        document: str | bytes | Mapping[str, object],
        *,
        path_prefix: str = "/",
        access_rules: Mapping[str, NodeAccessRule] | None = None,
    ) -> None:
        from mythos.registry.files.manifest import parse_json_file_tree

        sources, nodes = parse_json_file_tree(
            document,
            path_prefix=path_prefix,
            access_rules=access_rules or {},
        )
        self._register_manifest(sources, nodes)

    def register_json_tree_asset(
        self,
        module: str,
        relative_asset_path: str,
        *,
        path_prefix: str = "/",
        access_rules: Mapping[str, NodeAccessRule] | None = None,
    ) -> None:
        from mythos.registry.files.manifest import parse_json_file_tree

        manifest_path = self._manifest_asset_path(module, relative_asset_path)
        try:
            document = manifest_path.read_bytes()
        except OSError as error:
            raise RegistryError(f"File tree manifest is unavailable: {manifest_path}") from error
        sources, nodes = parse_json_file_tree(
            document,
            path_prefix=path_prefix,
            access_rules=access_rules or {},
            expected_module=module,
        )
        self._register_manifest(sources, nodes)

    def _register_manifest(
        self,
        sources: tuple[FileReference, ...],
        nodes: tuple[StaticNodeSpec, ...],
    ) -> None:
        snapshot = (
            dict(self._nodes_by_stable_id),
            dict(self._sources_by_locator),
            set(self._file_paths),
            set(self._explicit_directory_paths),
            set(self._directory_paths),
        )
        try:
            for source in sources:
                registered = self._sources_by_locator.get(source.source_locator)
                if registered is None:
                    self.register_source(source)
                elif registered != source:
                    raise RegistryError("JSON file tree conflicts with an existing static file source.")
            for node in nodes:
                self.register_node(node)
        except Exception:
            (
                self._nodes_by_stable_id,
                self._sources_by_locator,
                self._file_paths,
                self._explicit_directory_paths,
                self._directory_paths,
            ) = snapshot
            raise

    def _manifest_asset_path(self, module: str, relative_asset_path: str) -> Path:
        if self._puzzle_root is None:
            raise RegistryError("File registry requires a configured puzzle root to read manifest assets.")
        if not module or "/" in module or "\\" in module or module in {".", ".."}:
            raise RegistryError("Manifest asset modules must be one canonical path segment.")
        if (
            not relative_asset_path
            or relative_asset_path.startswith("/")
            or "\\" in relative_asset_path
            or any(not part or part in {".", ".."} for part in relative_asset_path.split("/"))
        ):
            raise RegistryError("Manifest asset paths must be canonical module-relative paths.")
        module_root = (self._puzzle_root / module).resolve()
        try:
            module_root.relative_to(self._puzzle_root)
        except ValueError as error:
            raise RegistryError("Manifest asset modules must remain within the puzzle root.") from error
        manifest_path = (module_root / relative_asset_path).resolve()
        try:
            manifest_path.relative_to(module_root)
        except ValueError as error:
            raise RegistryError("Manifest asset paths must remain within their module directory.") from error
        return manifest_path

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
        self._frozen = True
        resolved_nodes: dict[str, StaticNode] = {}
        contents_by_stable_id: dict[str, FileContent] = {}
        for node in self._nodes_by_stable_id.values():
            object_reference = (
                self._objects_by_source_locator[node.source_locator]
                if node.is_file and node.source_locator is not None
                else None
            )
            resolved = StaticNode(
                node.stable_id,
                node.path,
                static_node_version(node, object_reference),
                node.display,
                node.access_rule,
                node.hidden,
                node.download_name,
                node.source_locator,
            )
            resolved_nodes[resolved.stable_id] = resolved
            if object_reference is not None:
                assert resolved.download_name is not None
                contents_by_stable_id[resolved.stable_id] = FileContent(
                    object_ref=object_reference,
                    download_name=resolved.download_name,
                    content_token=resolved.version,
                )
        self._tree = FileTree.build(resolved_nodes, contents_by_stable_id, file_ids)
        return self._tree

    def _validate_node(self, node: StaticNode) -> None:
        if not node.stable_id or not _is_canonical_virtual_path(node.path):
            raise RegistryError("Virtual nodes require a stable ID and canonical absolute path.")
        if not isinstance(node.hidden, bool):
            raise RegistryError("Virtual node hidden flags must be booleans.")
        if node.access_rule is not None:
            try:
                validate_callback(
                    node.access_rule,
                    field_name="Static node access rule",
                    parameter_count=1,
                    asynchronous=False,
                    require_dependencies=True,
                )
            except ValueError as error:
                raise RegistryError(str(error)) from error
        if node.is_file:
            if not node.download_name or not is_safe_download_name(node.download_name):
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

    def _register_directory(self, node: StaticNode) -> None:
        if node.path in self._file_paths or node.path in self._explicit_directory_paths:
            raise RegistryError("Virtual node paths must be unique.")
        self._ensure_no_file_ancestor(node.path)
        self._explicit_directory_paths.add(node.path)
        self._directory_paths.update(_directory_paths_for(node.path, include_self=True))

    def _register_file(self, node: StaticNode) -> None:
        if node.path in self._file_paths or node.path in self._directory_paths:
            raise RegistryError("A virtual file cannot also be a directory.")
        self._ensure_no_file_ancestor(node.path)
        self._file_paths.add(node.path)
        self._directory_paths.update(_directory_paths_for(node.path, include_self=False))

    def _ensure_no_file_ancestor(self, path: str) -> None:
        for ancestor in _directory_paths_for(path, include_self=False):
            if ancestor in self._file_paths:
                raise RegistryError("A virtual file cannot contain child nodes.")

    def _ensure_mutable(self) -> None:
        if self._frozen or self._objects_by_source_locator is not None:
            raise RegistryFrozenError("The file registry is frozen.")


def _is_canonical_virtual_path(path: str) -> bool:
    if not path.startswith("/") or path == "/" or path.endswith("/") or "\\" in path:
        return False
    parts = path.split("/")[1:]
    return all(part and part not in {".", ".."} for part in parts)


def _directory_paths_for(path: str, *, include_self: bool) -> tuple[str, ...]:
    parts = path.split("/")[1:]
    last_index = len(parts) if include_self else len(parts) - 1
    return tuple("/" + "/".join(parts[:index]) for index in range(1, last_index + 1))
