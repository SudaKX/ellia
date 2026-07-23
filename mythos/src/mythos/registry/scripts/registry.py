from __future__ import annotations

from mythos.registry.errors import DuplicateStableIdError, RegistryError, RegistryFrozenError
from mythos.registry.scripts.catalog import ScriptCatalog
from mythos.registry.scripts.definitions import Script


class ScriptRegistry:
    def __init__(self) -> None:
        self._scripts: dict[str, Script] = {}
        self._frozen = False
        self._catalog: ScriptCatalog | None = None

    def register(self, script: Script) -> None:
        if self._frozen:
            raise RegistryFrozenError("The script registry is frozen.")
        if not script.stable_id:
            raise RegistryError("Scripts require a stable ID.")
        if script.stable_id in self._scripts:
            raise DuplicateStableIdError(script.stable_id)
        self._scripts[script.stable_id] = script

    def freeze(self) -> ScriptCatalog:
        if self._catalog is not None:
            return self._catalog
        self._frozen = True
        self._catalog = ScriptCatalog(self._scripts)
        return self._catalog
