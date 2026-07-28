from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from mythos.registry.errors import RegistryError
from mythos.registry.files.definitions import DisplayParams, FileReference, NodeAccessRule, VirtualNode


class _ManifestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class DisplayManifest(_ManifestModel):
    label: Annotated[str, Field(min_length=1)]
    description: str | None = None
    icon: str | None = None
    sort_order: int = 0

    @field_validator("label", "description")
    @classmethod
    def reject_newlines(cls, value: str | None) -> str | None:
        if value is not None and any(character in "\r\n" for character in value):
            raise ValueError("must not contain newlines")
        return value

    def to_display_params(self) -> DisplayParams:
        try:
            return DisplayParams(self.label, self.description, self.icon, self.sort_order)
        except ValueError as error:
            raise RegistryError(str(error)) from error


class SourceManifest(_ManifestModel):
    relative_path: Annotated[str, Field(min_length=1)]
    media_type: Annotated[str, Field(min_length=1)]

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        if value.startswith("/") or "\\" in value:
            raise ValueError("must be a canonical relative path")
        if any(not part or part in {".", ".."} for part in value.split("/")):
            raise ValueError("must be a canonical relative path")
        return value


class _NodeManifest(_ManifestModel):
    stable_id: Annotated[str, Field(min_length=1)]
    name: Annotated[str, Field(min_length=1)]
    revision: Annotated[str, Field(min_length=1)]
    display: DisplayManifest
    access_rule: str | None = None
    hidden: bool = False

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError("must be one canonical path segment")
        return value

    @field_validator("access_rule")
    @classmethod
    def validate_access_rule(cls, value: str | None) -> str | None:
        if value == "":
            raise ValueError("must be a non-empty symbolic name")
        return value


class FileManifest(_NodeManifest):
    kind: Literal["file"]
    source: SourceManifest
    download_name: Annotated[str, Field(min_length=1)]


class DirectoryManifest(_NodeManifest):
    kind: Literal["directory"]
    children: list[ManifestNode]


ManifestNode: TypeAlias = Annotated[FileManifest | DirectoryManifest, Field(discriminator="kind")]


class FileTreeManifest(_ManifestModel):
    schema_version: Literal[1]
    module: Annotated[str, Field(min_length=1)]
    children: list[ManifestNode]


DirectoryManifest.model_rebuild()
FileTreeManifest.model_rebuild()


def parse_json_file_tree(
    document: str | bytes | Mapping[str, object],
    *,
    path_prefix: str,
    access_rules: Mapping[str, NodeAccessRule],
    expected_module: str | None = None,
) -> tuple[tuple[FileReference, ...], tuple[VirtualNode, ...]]:
    manifest = _parse_manifest(document)
    if expected_module is not None and manifest.module != expected_module:
        raise RegistryError("File tree manifest module does not match its asset path.")
    prefix = _canonical_directory_path(path_prefix)
    sources_by_locator: dict[str, FileReference] = {}
    nodes: list[VirtualNode] = []
    stable_ids: set[str] = set()
    paths: set[str] = set()

    def visit(node: ManifestNode, parent_path: str) -> None:
        path = _join_path(parent_path, node.name)
        if node.stable_id in stable_ids:
            raise RegistryError("File tree manifest stable IDs must be unique.")
        if path in paths:
            raise RegistryError("File tree manifest paths must be unique.")
        stable_ids.add(node.stable_id)
        paths.add(path)
        access_rule = _access_rule(node.access_rule, access_rules)
        display = node.display.to_display_params()

        if isinstance(node, DirectoryManifest):
            nodes.append(
                VirtualNode.directory(
                    node.stable_id,
                    path,
                    node.revision,
                    access_rule,
                    display=display,
                    hidden=node.hidden,
                )
            )
            for child in node.children:
                visit(child, path)
            return

        reference = FileReference(manifest.module, node.source.relative_path, node.source.media_type)
        existing = sources_by_locator.get(reference.source_locator)
        if existing is not None and existing != reference:
            raise RegistryError("File tree manifest sources must agree on media type.")
        sources_by_locator[reference.source_locator] = reference
        nodes.append(
            VirtualNode.file(
                node.stable_id,
                path,
                node.revision,
                reference.source_locator,
                node.download_name,
                access_rule,
                display=display,
                hidden=node.hidden,
            )
        )

    for child in manifest.children:
        visit(child, prefix)
    return tuple(sources_by_locator.values()), tuple(nodes)


def _parse_manifest(document: str | bytes | Mapping[str, object]) -> FileTreeManifest:
    try:
        if isinstance(document, (str, bytes)):
            return FileTreeManifest.model_validate_json(document)
        return FileTreeManifest.model_validate(document)
    except ValidationError as error:
        raise RegistryError(f"Invalid file tree manifest: {error}") from error


def _access_rule(value: str | None, access_rules: Mapping[str, NodeAccessRule]) -> NodeAccessRule | None:
    if value is None:
        return None
    try:
        access_rule = access_rules[value]
    except KeyError as error:
        raise RegistryError(f"File tree access rule is not registered: {value!r}") from error
    if not callable(access_rule):
        raise RegistryError("File tree access rules must resolve to callables.")
    return access_rule


def _canonical_directory_path(path: str) -> str:
    if path == "/":
        return path
    if not path.startswith("/") or path.endswith("/") or "\\" in path:
        raise RegistryError("File tree path prefixes must be canonical absolute directory paths.")
    parts = path[1:].split("/")
    if any(not part or part in {".", ".."} for part in parts):
        raise RegistryError("File tree path prefixes must be canonical absolute directory paths.")
    return path


def _join_path(parent: str, name: str) -> str:
    return f"/{name}" if parent == "/" else f"{parent}/{name}"
