from __future__ import annotations

from collections.abc import Mapping

from mythos.registry.catalog_snapshots import TemplateSnapshot, template_snapshot
from mythos.registry.credits.definitions import CreditTemplate
from mythos.registry.errors import RegistryError


class CreditCatalog:
    def __init__(self, templates: Mapping[str, CreditTemplate]) -> None:
        self._templates = dict(templates)
        self._snapshot = self._build_snapshot()

    def template(self, credit_id: str) -> CreditTemplate:
        try:
            return self._templates[credit_id]
        except KeyError as error:
            raise RegistryError(f"Credit template not found: {credit_id!r}") from error

    def template_or_none(self, credit_id: str) -> CreditTemplate | None:
        return self._templates.get(credit_id)

    @property
    def credit_ids(self) -> frozenset[str]:
        return frozenset(self._templates)

    @property
    def credits(self) -> tuple[CreditTemplate, ...]:
        return tuple(sorted(self._templates.values(), key=lambda item: item.credit_id))

    def snapshot(self) -> TemplateSnapshot:
        return self._snapshot

    @property
    def template_version(self) -> str:
        return self._snapshot.template_version

    def _build_snapshot(self) -> TemplateSnapshot:
        return template_snapshot(
            (template.snapshot_entry() for template in self._templates.values()),
            prefix="cc1_",
        )
