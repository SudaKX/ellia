from __future__ import annotations

from mythos.registry.artifacts.catalog import ArtifactCatalog
from mythos.registry.artifacts.definitions import (
    ArtifactNodeTemplate,
    ArtifactTemplate,
    _is_canonical_virtual_path,
)
from mythos.registry.errors import DuplicateStableIdError, RegistryError, RegistryFrozenError


class ArtifactRegistry:
    def __init__(self) -> None:
        self._templates: dict[str, ArtifactTemplate] = {}
        self._node_templates: dict[str, ArtifactNodeTemplate] = {}
        self._frozen = False
        self._catalog: ArtifactCatalog | None = None

    def register_template(self, template: ArtifactTemplate) -> None:
        self._ensure_mutable()
        if not template.artifact_id:
            raise RegistryError("Artifact templates require an artifact ID.")
        if template.artifact_id in self._templates:
            raise DuplicateStableIdError(template.artifact_id)
        self._templates[template.artifact_id] = template

    def register_node(self, node_template: ArtifactNodeTemplate) -> None:
        self._ensure_mutable()
        self._validate_node_template(node_template)
        if node_template.stable_id in self._node_templates:
            raise DuplicateStableIdError(node_template.stable_id)
        if node_template.artifact_locator not in self._templates:
            raise RegistryError(
                f"Artifact node references unknown artifact: {node_template.artifact_locator!r}"
            )
        self._node_templates[node_template.stable_id] = node_template

    def freeze(self) -> ArtifactCatalog:
        if self._catalog is not None:
            return self._catalog
        for node_template in self._node_templates.values():
            if node_template.artifact_locator not in self._templates:
                raise RegistryError(
                    f"Artifact node references unknown artifact: {node_template.artifact_locator!r}"
                )
        self._frozen = True
        self._catalog = ArtifactCatalog(self._templates, self._node_templates)
        return self._catalog

    @staticmethod
    def _validate_node_template(node_template: ArtifactNodeTemplate) -> None:
        if not node_template.stable_id or not _is_canonical_virtual_path(node_template.path):
            raise RegistryError("Artifact nodes require a stable ID and canonical absolute path.")
        if not isinstance(node_template.hidden, bool):
            raise RegistryError("Artifact node hidden flags must be booleans.")
        if not node_template.artifact_locator:
            raise RegistryError("Artifact nodes require an artifact locator.")

    def _ensure_mutable(self) -> None:
        if self._frozen or self._catalog is not None:
            raise RegistryFrozenError("The artifact registry is frozen.")
