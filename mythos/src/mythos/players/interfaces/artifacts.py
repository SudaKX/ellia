from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mythos.core.file_ids import FileIdCodec
from mythos.persistence.base import utcnow
from mythos.persistence.models.artifacts import PlayerArtifact, PlayerArtifactNode, PlayerArtifactState
from mythos.registry.artifacts import (
    ArtifactNode,
    ArtifactNodeTemplate,
    ArtifactTemplate,
)
from mythos.registry.artifacts.catalog import ArtifactCatalog
from mythos.registry.artifacts.definitions import _is_canonical_virtual_path
from mythos.registry.files import FileTree
from mythos.registry.files.definitions import (
    FileContent,
    NodeDisplayParams,
    ObjectReference,
    is_safe_download_name,
)
from mythos.registry.files.player_tree import PlayerFileTree
from mythos.registry.files.tree import TreeNode
from mythos.services.object_store.service import ObjectStore

if TYPE_CHECKING:
    from mythos.players.player import Player


class ReadOnlyArtifactError(Exception):
    pass


class ArtifactInterface:
    def __init__(
        self,
        player_id: UUID,
        catalog: ArtifactCatalog,
        object_store: ObjectStore,
        file_ids: FileIdCodec,
        session: AsyncSession,
        *,
        writable: bool,
        artifacts: Mapping[str, PlayerArtifact] | None = None,
        nodes: Mapping[str, PlayerArtifactNode] | None = None,
        player_version: int = 0,
    ) -> None:
        self._player_id = player_id
        self._catalog = catalog
        self._object_store = object_store
        self._file_ids = file_ids
        self._session = session
        self._writable = writable
        self._artifacts: dict[str, PlayerArtifact] = dict(artifacts or {})
        self._nodes: dict[str, PlayerArtifactNode] = dict(nodes or {})
        self._player_version = player_version
        self._player_tree_cache: PlayerFileTree | None = None

    @property
    def player_id(self) -> UUID:
        return self._player_id

    @property
    def player_version(self) -> int:
        return self._player_version

    def has_artifact(self, artifact_id: str) -> bool:
        return artifact_id in self._artifacts

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def get_tree(self, static_tree: FileTree, file_ids: FileIdCodec) -> PlayerFileTree:
        if self._player_tree_cache is None:
            self._player_tree_cache = PlayerFileTree.build(
                static_tree,
                self.tree_nodes(),
                file_ids,
                artifact_catalog_version=self._catalog.version,
                player_version=self._player_version,
            )
        return self._player_tree_cache

    @staticmethod
    def _artifact_object_key(
        player_id: UUID,
        version: str,
    ) -> str:
        return f"artifacts/{player_id}/{version}"

    async def generate_artifact(
        self,
        artifact_id: str,
        player: Player,
    ) -> PlayerArtifact:
        self._ensure_writable()
        existing = self._artifacts.get(artifact_id)
        if existing is not None:
            return existing
        artifact = await self._materialize_artifact(self._catalog.template(artifact_id), player)
        await self._bump_player_version()
        self._player_tree_cache = None
        return artifact

    async def generate_node(
        self,
        node_id: str,
        player: Player,
    ) -> ArtifactNode:
        self._ensure_writable()
        existing = self._nodes.get(node_id)
        if existing is not None:
            return self._runtime_node(existing)
        node = await self._materialize_node(self._catalog.node_template(node_id), player)
        await self._bump_player_version()
        self._player_tree_cache = None
        return node

    async def refresh_artifact(
        self,
        artifact_id: str,
        player: Player,
    ) -> PlayerArtifact | None:
        artifact = self._artifacts.get(artifact_id)
        if artifact is None:
            return None
        template = self._catalog.template_or_none(artifact_id)
        if template is None:
            await self.remove_artifact(artifact_id)
            return None
        if artifact.version == template.version:
            return artifact
        refreshed = await self._materialize_artifact(template, player)
        await self._bump_player_version()
        self._player_tree_cache = None
        return refreshed

    async def refresh_node(
        self,
        node_id: str,
        player: Player,
    ) -> ArtifactNode | None:
        node = self._nodes.get(node_id)
        template = self._catalog.node_template_or_none(node_id)
        if template is None:
            if node is not None:
                await self.remove_node(node_id)
            return None
        if node is None:
            if template.artifact_locator not in self._artifacts:
                return None
            refreshed = await self._materialize_node(template, player)
            await self._bump_player_version()
            self._player_tree_cache = None
            return refreshed
        if (
            node.version == self._catalog.node_version(node_id)
            and node.artifact_id == template.artifact_locator
        ):
            return self._runtime_node(node)
        if template.artifact_locator not in self._artifacts:
            await self.remove_node(node_id)
            return None
        refreshed = await self._materialize_node(template, player)
        await self._bump_player_version()
        self._player_tree_cache = None
        return refreshed

    async def remove_artifact(self, artifact_id: str) -> bool:
        artifact = self._artifacts.get(artifact_id)
        if artifact is None:
            return False
        await self._session.execute(
            delete(PlayerArtifact).where(
                PlayerArtifact.player_id == self._player_id,
                PlayerArtifact.artifact_id == artifact_id,
            )
        )
        self._artifacts.pop(artifact_id, None)
        self._nodes = {
            node_id: node
            for node_id, node in self._nodes.items()
            if node.artifact_id != artifact_id
        }
        await self._bump_player_version()
        self._player_tree_cache = None
        return True

    async def remove_node(self, node_id: str) -> bool:
        if node_id not in self._nodes:
            return False
        await self._session.execute(
            delete(PlayerArtifactNode).where(
                PlayerArtifactNode.player_id == self._player_id,
                PlayerArtifactNode.node_id == node_id,
            )
        )
        self._nodes.pop(node_id, None)
        await self._bump_player_version()
        self._player_tree_cache = None
        return True

    async def refresh_stale(self, player: Player) -> None:
        for artifact_id in tuple(self._artifacts):
            await self.refresh_artifact(artifact_id, player)

        for artifact_id in tuple(self._artifacts):
            for template in self._catalog.node_templates_for_artifact(artifact_id):
                await self.refresh_node(template.stable_id, player)

        for node_id, node in tuple(self._nodes.items()):
            template = self._catalog.node_template_or_none(node_id)
            if template is None or template.artifact_locator != node.artifact_id:
                await self.remove_node(node_id)

    async def _materialize_artifact(
        self,
        template: ArtifactTemplate,
        player: Player,
    ) -> PlayerArtifact:
        raw = await template.generator(player)
        object_ref = await self._object_store.put_bytes(
            raw.data,
            object_key=self._artifact_object_key(
                self._player_id,
                template.version,
            ),
            media_type=template.media_type,
        )
        return await self._upsert_artifact(template, object_ref, raw.meta)

    async def _materialize_node(
        self,
        template: ArtifactNodeTemplate,
        player: Player,
    ) -> ArtifactNode:
        if template.artifact_locator not in self._artifacts:
            raise RuntimeError(f"Artifact {template.artifact_locator!r} must exist before creating a node.")
        expected_version = self._catalog.node_version(template.stable_id)
        runtime_node = template.to_runtime_node(expected_version)
        artifact = self._artifacts[template.artifact_locator]
        runtime_node = await template.node_generator(player, dict(artifact.meta), runtime_node)
        if runtime_node.stable_id != template.stable_id:
            raise RuntimeError("Artifact node generator modified the stable_id.")
        if runtime_node.artifact_locator != template.artifact_locator:
            raise RuntimeError("Artifact node generator modified the artifact_locator.")
        if runtime_node.version != expected_version:
            raise RuntimeError("Artifact node generator modified the version.")
        if not _is_canonical_virtual_path(runtime_node.path):
            raise RuntimeError("Artifact node generator produced a non-canonical path.")
        if runtime_node.download_name is not None and not is_safe_download_name(runtime_node.download_name):
            raise RuntimeError("Artifact node generator produced an unsafe download name.")
        await self._upsert_node(template, runtime_node)
        return runtime_node

    async def _upsert_artifact(
        self,
        template: ArtifactTemplate,
        object_ref: ObjectReference,
        meta: dict[str, Any],
    ) -> PlayerArtifact:
        values = {
            "player_id": self._player_id,
            "artifact_id": template.artifact_id,
            "version": template.version,
            "object_key": object_ref.key,
            "content_digest": object_ref.content_digest,
            "media_type": object_ref.media_type,
            "size_bytes": object_ref.size_bytes,
            "download_name": template.download_name,
            "meta": meta,
            "generated_at": utcnow(),
        }
        stmt = sqlite_insert(PlayerArtifact).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["player_id", "artifact_id"],
            set_={column: stmt.excluded[column] for column in values if column not in {"player_id", "artifact_id"}},
        )
        await self._session.execute(stmt)
        artifact = await self._session.scalar(
            select(PlayerArtifact)
            .where(
                PlayerArtifact.player_id == self._player_id,
                PlayerArtifact.artifact_id == template.artifact_id,
            )
            .options(selectinload(PlayerArtifact.nodes))
            .execution_options(populate_existing=True)
        )
        if artifact is None:
            raise RuntimeError(f"Artifact upsert failed for {template.artifact_id!r}.")
        await self._session.refresh(artifact, attribute_names=["nodes"])
        self._artifacts[template.artifact_id] = artifact
        for node in artifact.nodes:
            self._nodes[node.node_id] = node
        return artifact

    async def _upsert_node(self, template: ArtifactNodeTemplate, runtime_node: ArtifactNode) -> None:
        values = {
            "player_id": self._player_id,
            "node_id": template.stable_id,
            "artifact_id": template.artifact_locator,
            "path": runtime_node.path,
            "version": runtime_node.version,
            "display": runtime_node.display.as_dict(),
            "hidden": runtime_node.hidden,
            "download_name": runtime_node.download_name,
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
        stmt = sqlite_insert(PlayerArtifactNode).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["player_id", "node_id"],
            set_={
                column: stmt.excluded[column]
                for column in ("artifact_id", "path", "version", "display", "hidden", "download_name", "updated_at")
            },
        )
        await self._session.execute(stmt)
        node = await self._session.scalar(
            select(PlayerArtifactNode).where(
                PlayerArtifactNode.player_id == self._player_id,
                PlayerArtifactNode.node_id == template.stable_id,
            ).execution_options(populate_existing=True)
        )
        if node is None:
            raise RuntimeError(f"Artifact node upsert failed for {template.stable_id!r}.")
        await self._session.refresh(node)
        self._nodes[node.node_id] = node

    async def _bump_player_version(self) -> None:
        stmt = sqlite_insert(PlayerArtifactState).values(player_id=self._player_id, version=1)
        stmt = stmt.on_conflict_do_update(
            index_elements=["player_id"],
            set_={"version": PlayerArtifactState.version + 1},
        ).returning(PlayerArtifactState.version)
        version = await self._session.scalar(stmt)
        if version is None:
            raise RuntimeError("Player artifact version increment failed.")
        self._player_version = version

    def _runtime_node(self, node_record: PlayerArtifactNode) -> ArtifactNode:
        template = self._catalog.node_template(node_record.node_id)
        if node_record.download_name is not None and not is_safe_download_name(node_record.download_name):
            raise RuntimeError("Persisted artifact node has an unsafe download name.")
        return ArtifactNode(
            stable_id=node_record.node_id,
            path=node_record.path,
            version=node_record.version,
            display=NodeDisplayParams(**node_record.display),
            access_rule=template.access_rule,
            hidden=node_record.hidden,
            download_name=node_record.download_name,
            artifact_locator=node_record.artifact_id,
        )

    def tree_nodes(self) -> tuple[TreeNode, ...]:
        nodes: list[TreeNode] = []
        for node_record in self._nodes.values():
            artifact = self._artifacts.get(node_record.artifact_id)
            if artifact is None:
                continue
            template = self._catalog.node_template_or_none(node_record.node_id)
            if template is None:
                continue
            artifact_template = self._catalog.template_or_none(artifact.artifact_id)
            if artifact_template is None:
                continue
            object_ref = ObjectReference(
                key=artifact.object_key,
                content_digest=artifact.content_digest,
                media_type=artifact.media_type,
                size_bytes=artifact.size_bytes,
            )
            effective_download_name = node_record.download_name or artifact_template.download_name
            content = FileContent(
                object_ref=object_ref,
                download_name=effective_download_name,
                content_token=self._file_ids.encode_artifact_content_token(
                    str(self._player_id),
                    artifact.artifact_id,
                    node_record.node_id,
                    artifact.version,
                    node_record.version,
                    object_ref.media_type,
                    effective_download_name,
                ),
            )
            runtime_node = self._runtime_node(node_record)
            nodes.append(
                TreeNode(
                    path=node_record.path,
                    definition=runtime_node,
                    children={},
                    content=content,
                    file_id=self._file_ids.encode(node_record.node_id),
                )
            )
        return tuple(sorted(nodes, key=lambda node: node.path))

    def _ensure_writable(self) -> None:
        if not self._writable:
            raise ReadOnlyArtifactError("Read-only players cannot generate artifacts.")

    @classmethod
    async def load(
        cls,
        session: AsyncSession,
        player_id: UUID,
        catalog: ArtifactCatalog,
        object_store: ObjectStore,
        file_ids: FileIdCodec,
        *,
        writable: bool,
    ) -> ArtifactInterface:
        artifacts = await session.scalars(
            select(PlayerArtifact)
            .where(PlayerArtifact.player_id == player_id)
            .options(selectinload(PlayerArtifact.nodes))
            .execution_options(populate_existing=True)
        )
        artifact_dict: dict[str, PlayerArtifact] = {}
        node_dict: dict[str, PlayerArtifactNode] = {}
        for artifact in artifacts:
            artifact_dict[artifact.artifact_id] = artifact
            for node in artifact.nodes:
                node_dict[node.node_id] = node
        state = await session.get(PlayerArtifactState, player_id)
        return cls(
            player_id,
            catalog,
            object_store,
            file_ids,
            session,
            writable=writable,
            artifacts=artifact_dict,
            nodes=node_dict,
            player_version=state.version if state is not None else 0,
        )
