from __future__ import annotations

from collections.abc import Mapping

from mythos.registry.accounts.definitions import VirtualAccountTemplate
from mythos.registry.catalog_snapshots import TemplateSnapshot, template_snapshot
from mythos.registry.errors import RegistryError


class VirtualAccountCatalog:
    def __init__(self, templates: Mapping[str, VirtualAccountTemplate]) -> None:
        self._templates = dict(templates)
        self._snapshot = self._build_snapshot()

    def template(self, account_id: str) -> VirtualAccountTemplate:
        try:
            return self._templates[account_id]
        except KeyError as error:
            raise RegistryError(f"Virtual account template not found: {account_id!r}") from error

    def template_or_none(self, account_id: str) -> VirtualAccountTemplate | None:
        return self._templates.get(account_id)

    @property
    def template_ids(self) -> frozenset[str]:
        return frozenset(self._templates)

    def snapshot(self) -> TemplateSnapshot:
        return self._snapshot

    @property
    def template_version(self) -> str:
        return self._snapshot.template_version

    def _build_snapshot(self) -> TemplateSnapshot:
        return template_snapshot(
            (template.snapshot_entry() for template in self._templates.values()),
            prefix="vac1_",
        )
