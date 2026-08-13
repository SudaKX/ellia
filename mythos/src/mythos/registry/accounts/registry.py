from __future__ import annotations

from mythos.registry.accounts.catalog import VirtualAccountCatalog
from mythos.registry.accounts.definitions import VirtualAccountTemplate
from mythos.registry.errors import DuplicateStableIdError, RegistryError, RegistryFrozenError


class VirtualAccountRegistry:
    def __init__(self) -> None:
        self._templates: dict[str, VirtualAccountTemplate] = {}
        self._frozen = False
        self._catalog: VirtualAccountCatalog | None = None

    def register_template(self, template: VirtualAccountTemplate) -> None:
        self._ensure_mutable()
        if not template.account_id:
            raise RegistryError("Virtual account templates require an account ID.")
        if template.account_id in self._templates:
            raise DuplicateStableIdError(template.account_id)
        self._templates[template.account_id] = template

    def freeze(self) -> VirtualAccountCatalog:
        if self._catalog is not None:
            return self._catalog
        self._frozen = True
        self._catalog = VirtualAccountCatalog(self._templates)
        return self._catalog

    def _ensure_mutable(self) -> None:
        if self._frozen or self._catalog is not None:
            raise RegistryFrozenError("The virtual account registry is frozen.")
