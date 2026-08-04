from __future__ import annotations

from collections.abc import Mapping
import inspect

from mythos.core.file_ids import FileIdCodec
from mythos.registry.errors import DuplicateStableIdError, RegistryError, RegistryFrozenError
from mythos.registry.files.definitions import FileReference, ObjectReference
from mythos.registry.hints.catalog import HintCatalog
from mythos.registry.hints.definitions import Hint


class HintRegistry:
    def __init__(self) -> None:
        self._hints_by_stable_id: dict[str, Hint] = {}
        self._sources_by_locator: dict[str, FileReference] = {}
        self._objects_by_source_locator: dict[str, ObjectReference] | None = None
        self._catalog: HintCatalog | None = None
        self._frozen = False

    def register(self, hint: Hint) -> None:
        self._ensure_mutable()
        if hint.stable_id in self._hints_by_stable_id:
            raise DuplicateStableIdError(hint.stable_id)
        if not _is_canonical_module(hint.source.module):
            raise RegistryError("Hint source modules must be canonical path segments.")
        if not _is_canonical_relative_path(hint.source.relative_path):
            raise RegistryError("Hint source paths must be canonical module-relative paths.")
        if not hint.source.media_type:
            raise RegistryError("Hint sources require a module, relative path, and media type.")
        if hint.access_rule is not None and _is_async_callable(hint.access_rule):
            raise RegistryError("Hint access rules must be synchronous.")
        existing_source = self._sources_by_locator.get(hint.source.source_locator)
        if existing_source is not None and existing_source != hint.source:
            raise RegistryError("Hints cannot reuse a source locator with a different definition.")
        self._hints_by_stable_id[hint.stable_id] = hint
        self._sources_by_locator[hint.source.source_locator] = hint.source

    @property
    def sources(self) -> tuple[FileReference, ...]:
        return tuple(self._sources_by_locator.values())

    @property
    def is_materialized(self) -> bool:
        return self._objects_by_source_locator is not None

    def materialize_static_content(self, objects_by_source_locator: Mapping[str, ObjectReference]) -> None:
        self._ensure_mutable()
        if set(objects_by_source_locator) != set(self._sources_by_locator):
            raise RegistryError("Hint content materialization must resolve every registered source exactly once.")
        self._objects_by_source_locator = dict(objects_by_source_locator)

    def freeze(self, file_ids: FileIdCodec) -> HintCatalog:
        if self._catalog is not None:
            if self._catalog.file_id_key_fingerprint != file_ids.key_fingerprint:
                raise RegistryError("Hint registry is already frozen with a different file ID key.")
            return self._catalog
        if self._sources_by_locator and self._objects_by_source_locator is None:
            raise RegistryError("Hint sources must be materialized before the hint registry is frozen.")
        self._frozen = True
        self._catalog = HintCatalog(self._hints_by_stable_id, self._objects_by_source_locator or {}, file_ids)
        return self._catalog

    def _ensure_mutable(self) -> None:
        if self._frozen or self._catalog is not None or self._objects_by_source_locator is not None:
            raise RegistryFrozenError("The hint registry is frozen.")


def _is_canonical_module(value: str) -> bool:
    return (
        bool(value)
        and "/" not in value
        and "\\" not in value
        and ":" not in value
        and value not in {".", ".."}
    )


def _is_canonical_relative_path(value: str) -> bool:
    return (
        bool(value)
        and not value.startswith("/")
        and "\\" not in value
        and ":" not in value
        and all(part and part not in {".", ".."} for part in value.split("/"))
    )


def _is_async_callable(callback: object) -> bool:
    return inspect.iscoroutinefunction(callback) or inspect.iscoroutinefunction(getattr(callback, "__call__", None))
