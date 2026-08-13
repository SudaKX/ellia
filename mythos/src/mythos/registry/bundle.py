from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from mythos.core.file_ids import FileIdCodec
from mythos.eventbus import EventCatalog, EventRegistry
from mythos.registry.accounts import VirtualAccountCatalog, VirtualAccountRegistry
from mythos.registry.achievements import AchievementCatalog, AchievementRegistry
from mythos.registry.artifacts import ArtifactCatalog, ArtifactRegistry
from mythos.registry.credits import CreditCatalog, CreditRegistry
from mythos.registry.errors import DuplicateStableIdError, RegistryError
from mythos.registry.files import FileRegistry, FileTree, MergedFileTree
from mythos.registry.hints import HintCatalog, HintRegistry
from mythos.registry.progress import ProgressGraph, ProgressRegistry
from mythos.registry.scripts import ScriptCatalog, ScriptRegistry
from mythos.registry.tasks import TaskCatalog, TaskRegistry
from mythos.registry.validations import ValidationCatalog, ValidationRegistry

if TYPE_CHECKING:
    from mythos.services.files.static_assets import StaticAssetPublisher


@dataclass(frozen=True)
class RuntimeCatalogs:
    files: FileTree
    merged_files: MergedFileTree
    progress: ProgressGraph
    scripts: ScriptCatalog
    validations: ValidationCatalog
    artifacts: ArtifactCatalog
    accounts: VirtualAccountCatalog
    credits: CreditCatalog
    hints: HintCatalog
    events: EventCatalog
    tasks: TaskCatalog
    achievements: AchievementCatalog


class RegistryBundle:
    def __init__(self, puzzle_root: Path | None = None) -> None:
        self.files = FileRegistry(puzzle_root)
        self.progress = ProgressRegistry()
        self.scripts = ScriptRegistry()
        self.validations = ValidationRegistry()
        self.artifacts = ArtifactRegistry()
        self.accounts = VirtualAccountRegistry()
        self.credits = CreditRegistry()
        self.hints = HintRegistry()
        self.events = EventRegistry()
        self.tasks = TaskRegistry()
        self.achievements = AchievementRegistry()
        self._catalogs: RuntimeCatalogs | None = None

    def configure_puzzle_root(self, puzzle_root: Path) -> None:
        self.files.configure_puzzle_root(puzzle_root)

    def freeze(self, file_ids: FileIdCodec) -> RuntimeCatalogs:
        if self._catalogs is not None:
            if self._catalogs.files.file_id_key_fingerprint != file_ids.key_fingerprint:
                raise RuntimeError("RegistryBundle is already frozen with a different file ID key.")
            return self._catalogs
        static_ids = set(self.files._nodes_by_stable_id)
        artifact_ids = set(self.artifacts._node_templates)
        duplicates = static_ids & artifact_ids
        if duplicates:
            raise DuplicateStableIdError(next(iter(sorted(duplicates))))
        files = self.files.freeze(file_ids)
        artifacts = self.artifacts.freeze()
        self.credits.ensure_builtin_vtb()
        credits = self.credits.freeze()
        hints = self.hints.freeze(file_ids)
        _ensure_hint_credits_registered(hints, credits)
        self._catalogs = RuntimeCatalogs(
            files=files,
            merged_files=MergedFileTree.build(files, artifacts, file_ids),
            progress=self.progress.freeze(),
            scripts=self.scripts.freeze(),
            validations=self.validations.freeze(),
            artifacts=artifacts,
            accounts=self.accounts.freeze(),
            credits=credits,
            hints=hints,
            events=self.events.freeze(),
            tasks=self.tasks.freeze(),
            achievements=self.achievements.freeze(file_ids),
        )
        return self._catalogs

    async def materialize_static_files(self, publisher: StaticAssetPublisher) -> None:
        if self._catalogs is not None:
            return
        if self.files.is_materialized and self.hints.is_materialized:
            return
        if self.files.is_materialized != self.hints.is_materialized:
            raise RegistryError("Static file and hint content must be materialized together.")
        sources_by_locator = _merge_static_sources(self.files.sources, self.hints.sources)
        objects_by_source_locator = await publisher.materialize(tuple(sources_by_locator.values()))
        self.files.materialize_static_files(
            {
                source.source_locator: objects_by_source_locator[source.source_locator]
                for source in self.files.sources
            }
        )
        self.hints.materialize_static_content(
            {
                source.source_locator: objects_by_source_locator[source.source_locator]
                for source in self.hints.sources
            }
        )


def _ensure_hint_credits_registered(hints: HintCatalog, credits: CreditCatalog) -> None:
    for hint in hints.hints:
        if hint.credit_id not in credits.credit_ids:
            raise RegistryError(
                f"Hint {hint.stable_id!r} references unregistered credit {hint.credit_id!r}."
            )


def _merge_static_sources(*source_groups):
    sources_by_locator = {}
    for source_group in source_groups:
        for source in source_group:
            existing = sources_by_locator.get(source.source_locator)
            if existing is not None and existing != source:
                raise RegistryError("Static file and hint sources conflict.")
            sources_by_locator[source.source_locator] = source
    return sources_by_locator
