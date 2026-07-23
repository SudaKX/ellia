from __future__ import annotations

from mythos.core.file_ids import FileIdCodec
from mythos.registry.errors import DuplicateStableIdError, RegistryError, RegistryFrozenError
from mythos.registry.files.catalog import FileCatalog
from mythos.registry.files.definitions import VirtualFile


class FileRegistry:
    def __init__(self) -> None:
        self._by_id: dict[str, VirtualFile] = {}
        self._paths: set[str] = set()
        self._frozen = False
        self._catalog: FileCatalog | None = None

    def register(self, file: VirtualFile) -> None:
        if self._frozen:
            raise RegistryFrozenError("The file registry is frozen.")
        if not file.stable_id or not _is_canonical_file_path(file.path):
            raise RegistryError("Files require a stable ID and a canonical absolute virtual path.")
        if not _is_safe_download_name(file.download_name):
            raise RegistryError("Files require a safe download name.")
        if file.stable_id in self._by_id or file.path in self._paths:
            raise DuplicateStableIdError(file.stable_id)
        self._by_id[file.stable_id] = file
        self._paths.add(file.path)

    def freeze(self, file_ids: FileIdCodec) -> FileCatalog:
        if self._catalog is not None:
            if self._catalog.file_id_key_fingerprint != file_ids.key_fingerprint:
                raise RegistryError("File registry is already frozen with a different file ID key.")
            return self._catalog
        self._frozen = True
        self._catalog = FileCatalog(self._by_id, file_ids)
        return self._catalog


def _is_canonical_file_path(path: str) -> bool:
    if not path.startswith("/") or path == "/" or path.endswith("/") or "\\" in path:
        return False
    parts = path.split("/")[1:]
    return all(part and part not in {".", ".."} for part in parts)


def _is_safe_download_name(value: str) -> bool:
    return bool(value) and all(
        32 <= ord(character) <= 126 and character not in '"/\\'
        for character in value
    )
