from __future__ import annotations

from collections.abc import Mapping

from mythos.registry.artifacts.definitions import ArtifactNodeTemplate, ArtifactTemplate
from mythos.registry.errors import RegistryError


class ArtifactCatalog:
    def __init__(
        self,
        templates: Mapping[str, ArtifactTemplate],
        node_templates: Mapping[str, ArtifactNodeTemplate],
    ) -> None:
        self._templates = dict(templates)
        self._node_templates = dict(node_templates)

    def template(self, artifact_id: str) -> ArtifactTemplate:
        try:
            return self._templates[artifact_id]
        except KeyError as error:
            raise RegistryError(f"Artifact template not found: {artifact_id!r}") from error

    def node_template(self, stable_id: str) -> ArtifactNodeTemplate:
        try:
            return self._node_templates[stable_id]
        except KeyError as error:
            raise RegistryError(f"Artifact node template not found: {stable_id!r}") from error

    def node_templates_for_artifact(self, artifact_id: str) -> tuple[ArtifactNodeTemplate, ...]:
        return tuple(
            template
            for template in self._node_templates.values()
            if template.artifact_locator == artifact_id
        )

    @property
    def template_ids(self) -> frozenset[str]:
        return frozenset(self._templates)

    @property
    def node_stable_ids(self) -> frozenset[str]:
        return frozenset(self._node_templates)
