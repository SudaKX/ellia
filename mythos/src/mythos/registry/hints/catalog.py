from __future__ import annotations

from collections.abc import Mapping

from mythos.core.file_ids import FileIdCodec
from mythos.registry.errors import RegistryError
from mythos.registry.files.definitions import FileContent, ObjectReference
from mythos.registry.hints.definitions import Hint


class HintCatalog:
    def __init__(
        self,
        hints: Mapping[str, Hint],
        objects_by_source_locator: Mapping[str, ObjectReference],
        file_ids: FileIdCodec,
    ) -> None:
        self._hints_by_stable_id = dict(hints)
        self._file_id_key_fingerprint = file_ids.key_fingerprint
        self._hints_by_public_id = {
            file_ids.encode_hint_id(hint.stable_id): hint for hint in self._hints_by_stable_id.values()
        }
        self._public_ids_by_stable_id = {
            hint.stable_id: public_id for public_id, hint in self._hints_by_public_id.items()
        }
        self._contents_by_stable_id = {
            hint.stable_id: FileContent(
                object_ref=objects_by_source_locator[hint.source.source_locator],
                download_name=hint.download_name,
                content_token=file_ids.encode_hint_content_token(
                    hint.stable_id,
                    hint.version,
                    objects_by_source_locator[hint.source.source_locator].key,
                    objects_by_source_locator[hint.source.source_locator].version_id,
                    objects_by_source_locator[hint.source.source_locator].media_type,
                    hint.download_name,
                ),
            )
            for hint in self._hints_by_stable_id.values()
        }

    @property
    def hints(self) -> tuple[Hint, ...]:
        return tuple(sorted(self._hints_by_stable_id.values(), key=lambda hint: (hint.display.sort_order, hint.stable_id)))

    @property
    def file_id_key_fingerprint(self) -> str:
        return self._file_id_key_fingerprint

    def hint(self, public_id: str) -> Hint:
        try:
            return self._hints_by_public_id[public_id]
        except KeyError as error:
            raise RegistryError("Hint not found.") from error

    def content(self, hint: Hint) -> FileContent:
        try:
            return self._contents_by_stable_id[hint.stable_id]
        except KeyError as error:
            raise RegistryError("Hint content not found.") from error

    def public_id_for(self, stable_id: str) -> str:
        try:
            return self._public_ids_by_stable_id[stable_id]
        except KeyError as error:
            raise RegistryError("Hint not found.") from error
