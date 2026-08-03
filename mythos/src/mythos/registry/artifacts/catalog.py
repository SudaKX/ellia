from __future__ import annotations

from collections.abc import Mapping

from mythos.registry.artifacts.definitions import ArtifactNodeTemplate, ArtifactTemplate
from mythos.registry.catalog_snapshots import (
    TemplateSnapshot,
    template_snapshot,
)
from mythos.registry.errors import RegistryError


class ArtifactCatalog:
    def __init__(
        self,
        templates: Mapping[str, ArtifactTemplate],
        node_templates: Mapping[str, ArtifactNodeTemplate],
    ) -> None:
        self._templates = dict(templates)
        self._node_templates = dict(node_templates)
        self._snapshot = self._build_snapshot()

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
            sorted(
                (
                    template
                    for template in self._node_templates.values()
                    if template.artifact_locator == artifact_id
                ),
                key=lambda template: template.stable_id,
            )
        )

    def template_or_none(self, artifact_id: str) -> ArtifactTemplate | None:
        return self._templates.get(artifact_id)

    def node_template_or_none(self, stable_id: str) -> ArtifactNodeTemplate | None:
        return self._node_templates.get(stable_id)

    @property
    def template_version(self) -> str:
        return self._snapshot.template_version

    def snapshot(self) -> TemplateSnapshot:
        return self._snapshot

    def _build_snapshot(self) -> TemplateSnapshot:
        return template_snapshot(
            (
                *(template.snapshot_entry() for template in self._templates.values()),
                *(template.snapshot_entry() for template in self._node_templates.values()),
            )
        )

    @property
    def template_ids(self) -> frozenset[str]:
        return frozenset(self._templates)

    @property
    def node_stable_ids(self) -> frozenset[str]:
        return frozenset(self._node_templates)
