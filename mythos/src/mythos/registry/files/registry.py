from __future__ import annotations

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
        if not file.stable_id or not file.path.startswith("/"):
            raise RegistryError("Files require a stable ID and an absolute virtual path.")
        if file.stable_id in self._by_id or file.path in self._paths:
            raise DuplicateStableIdError(file.stable_id)
        self._by_id[file.stable_id] = file
        self._paths.add(file.path)

    def freeze(self) -> FileCatalog:
        if self._catalog is not None:
            return self._catalog
        self._frozen = True
        self._catalog = FileCatalog(self._by_id)
        return self._catalog
