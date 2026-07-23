from __future__ import annotations

from collections.abc import Mapping

from mythos.core.file_ids import FileIdCodec
from mythos.registry.errors import RegistryError
from mythos.registry.files.definitions import VirtualFile


class FileCatalog:
    def __init__(self, files: Mapping[str, VirtualFile], file_ids: FileIdCodec) -> None:
        self._files = dict(files)
        self.file_id_key_fingerprint = file_ids.key_fingerprint
        self._public_ids = {file_ids.encode(stable_id): file for stable_id, file in self._files.items()}

    def get(self, file_id: str) -> VirtualFile:
        try:
            return self._public_ids[file_id]
        except KeyError as error:
            raise RegistryError("Virtual file not found.") from error

    def file_id_for(self, file: VirtualFile) -> str:
        for file_id, candidate in self._public_ids.items():
            if candidate is file:
                return file_id
        raise RegistryError("Virtual file is not part of this catalog.")

    def all_files(self) -> tuple[VirtualFile, ...]:
        return tuple(self._files.values())
