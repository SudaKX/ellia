from __future__ import annotations

from mythos.registry.credits.catalog import CreditCatalog
from mythos.registry.credits.definitions import CREDIT_VTB_ID, CreditTemplate
from mythos.registry.errors import DuplicateStableIdError, RegistryError, RegistryFrozenError


class CreditRegistry:
    def __init__(self) -> None:
        self._templates: dict[str, CreditTemplate] = {}
        self._frozen = False
        self._catalog: CreditCatalog | None = None

    def register_template(self, template: CreditTemplate) -> None:
        self._ensure_mutable()
        if not isinstance(template, CreditTemplate):
            raise RegistryError("Credit registrations require a CreditTemplate.")
        if not template.credit_id:
            raise RegistryError("Credit templates require a credit ID.")
        if template.credit_id in self._templates:
            raise DuplicateStableIdError(template.credit_id)
        self._templates[template.credit_id] = template

    def ensure_builtin_vtb(self) -> None:
        self._ensure_mutable()
        if CREDIT_VTB_ID in self._templates:
            return
        self._templates[CREDIT_VTB_ID] = CreditTemplate(CREDIT_VTB_ID, "VTB")

    def freeze(self) -> CreditCatalog:
        if self._catalog is not None:
            return self._catalog
        self._frozen = True
        self._catalog = CreditCatalog(self._templates)
        return self._catalog

    def _ensure_mutable(self) -> None:
        if self._frozen or self._catalog is not None:
            raise RegistryFrozenError("The credit registry is frozen.")
