from __future__ import annotations

import hashlib
from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mythos.core.file_ids import FileIdCodec
from mythos.persistence.base import utcnow
from mythos.persistence.models.artifacts import PlayerArtifact, PlayerArtifactNode
from mythos.registry.artifacts import ArtifactCatalog, ArtifactNode, ArtifactNodeTemplate, ArtifactTemplate
from mythos.registry.files import FileTree
from mythos.registry.files.definitions import DisplayParams, FileContent, ObjectReference
from mythos.registry.files.player_tree import PlayerFileTree
from mythos.registry.files.tree import TreeNode
from mythos.services.object_store.service import ObjectStore

if TYPE_CHECKING:
    from mythos.players.context import CommandContext


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
    ) -> None:
        self._player_id = player_id
        self._catalog = catalog
        self._object_store = object_store
        self._file_ids = file_ids
        self._session = session
        self._writable = writable
        self._artifacts: dict[str, PlayerArtifact] = dict(artifacts or {})
        self._nodes: dict[str, PlayerArtifactNode] = dict(nodes or {})
        self._player_tree_cache: PlayerFileTree | None = None

    @property
    def player_id(self) -> UUID:
        return self._player_id

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
            )
        return self._player_tree_cache

    @staticmethod
    def _artifact_object_key(
        player_id: UUID,
        artifact_id: str,
        revision: str,
        content_digest: str,
    ) -> str:
        return f"artifacts/{player_id}/{artifact_id}/{revision}/{content_digest}"

    async def generate(self, artifact_id: str, context: CommandContext) -> tuple[ArtifactNode, ...]:
        if not self._writable:
            raise ReadOnlyArtifactError("Read-only players cannot generate artifacts.")
        template = self._catalog.template(artifact_id)
        node_templates = self._catalog.node_templates_for_artifact(artifact_id)
        if not node_templates:
            raise RuntimeError(f"Artifact {artifact_id!r} has no registered node templates.")

        raw = await template.generator(context)
        content = raw.data
        digest = hashlib.sha256(content).hexdigest()
        object_key = self._artifact_object_key(
            self._player_id,
            artifact_id,
            template.revision,
            digest,
        )
        object_ref = await self._object_store.put_bytes(
            content,
            object_key=object_key,
            media_type=template.media_type,
        )

        artifact = await self._upsert_artifact(template, object_ref, raw.meta)
        generated_nodes: list[ArtifactNode] = []
        for node_template in node_templates:
            runtime_node = await self._generate_node(node_template, artifact, context)
            generated_nodes.append(runtime_node)

        self._player_tree_cache = None
        return tuple(generated_nodes)

    async def _upsert_artifact(
        self,
        template: ArtifactTemplate,
        object_ref: ObjectReference,
        meta: dict[str, Any],
    ) -> PlayerArtifact:
        values = {
            "player_id": self._player_id,
            "artifact_id": template.artifact_id,
            "revision": template.revision,
            "object_key": object_ref.key,
            "object_version_id": object_ref.version_id,
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
            set_={
                column: stmt.excluded[column]
                for column in (
                    "revision",
                    "object_key",
                    "object_version_id",
                    "content_digest",
                    "media_type",
                    "size_bytes",
                    "download_name",
                    "meta",
                    "generated_at",
                )
            },
        )
        await self._session.execute(stmt)
        artifact = await self._session.scalar(
            select(PlayerArtifact)
            .where(
                PlayerArtifact.player_id == self._player_id,
                PlayerArtifact.artifact_id == template.artifact_id,
            )
            .options(selectinload(PlayerArtifact.nodes))
        )
        if artifact is None:
            raise RuntimeError(f"Artifact upsert failed for {template.artifact_id!r}.")
        await self._session.refresh(artifact)
        self._artifacts[template.artifact_id] = artifact
        for node in artifact.nodes:
            self._nodes[node.node_id] = node
        return artifact

    async def _generate_node(
        self,
        node_template: ArtifactNodeTemplate,
        artifact: PlayerArtifact,
        context: CommandContext,
    ) -> ArtifactNode:
        runtime_node = node_template.to_runtime_node()
        runtime_node = await node_template.node_generator(context, runtime_node)
        if runtime_node.stable_id != node_template.stable_id:
            raise RuntimeError("Artifact node generator modified the stable_id.")
        if runtime_node.artifact_locator != node_template.artifact_locator:
            raise RuntimeError("Artifact node generator modified the artifact_locator.")

        values = {
            "player_id": self._player_id,
            "node_id": node_template.stable_id,
            "artifact_id": artifact.artifact_id,
            "path": runtime_node.path,
            "revision": runtime_node.revision,
            "display": runtime_node.display.as_dict(),
            "hidden": runtime_node.hidden,
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
        stmt = sqlite_insert(PlayerArtifactNode).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["player_id", "node_id"],
            set_={
                column: stmt.excluded[column]
                for column in (
                    "artifact_id",
                    "path",
                    "revision",
                    "display",
                    "hidden",
                    "updated_at",
                )
            },
        )
        await self._session.execute(stmt)
        node_record = await self._session.scalar(
            select(PlayerArtifactNode).where(
                PlayerArtifactNode.player_id == self._player_id,
                PlayerArtifactNode.node_id == node_template.stable_id,
            )
        )
        if node_record is None:
            raise RuntimeError(f"Artifact node upsert failed for {node_template.stable_id!r}.")
        self._nodes[node_template.stable_id] = node_record
        return runtime_node

    def tree_nodes(self) -> tuple[TreeNode, ...]:
        nodes: list[TreeNode] = []
        for node_record in self._nodes.values():
            artifact = self._artifacts.get(node_record.artifact_id)
            if artifact is None:
                continue
            node_template = self._catalog.node_template(node_record.node_id)
            object_ref = ObjectReference(
                key=artifact.object_key,
                content_digest=artifact.content_digest,
                media_type=artifact.media_type,
                size_bytes=artifact.size_bytes,
                version_id=artifact.object_version_id,
            )
            content = FileContent(
                object_ref=object_ref,
                download_name=artifact.download_name,
                content_token=self._file_ids.encode_artifact_content_token(
                    str(self._player_id),
                    node_record.node_id,
                    node_record.revision,
                    object_ref.key,
                    object_ref.version_id,
                    object_ref.media_type,
                    artifact.download_name,
                ),
            )
            runtime_node = ArtifactNode(
                stable_id=node_record.node_id,
                path=node_record.path,
                revision=node_record.revision,
                display=DisplayParams(**node_record.display),
                access_rule=node_template.access_rule,
                hidden=node_record.hidden,
                download_name=artifact.download_name,
                artifact_locator=artifact.artifact_id,
            )
            nodes.append(
                TreeNode(
                    path=node_record.path,
                    definition=runtime_node,
                    children=MappingProxyType({}),
                    content=content,
                    file_id=self._file_ids.encode(node_record.node_id),
                )
            )
        return tuple(sorted(nodes, key=lambda node: node.path))

    def version_hash(self) -> str:
        entries = []
        for node_record in sorted(self._nodes.values(), key=lambda record: record.node_id):
            artifact = self._artifacts.get(node_record.artifact_id)
            content_token = ""
            if artifact is not None:
                content_token = self._file_ids.encode_artifact_content_token(
                    str(self._player_id),
                    node_record.node_id,
                    node_record.revision,
                    artifact.object_key,
                    artifact.object_version_id,
                    artifact.media_type,
                    artifact.download_name,
                )
            entries.append(
                (
                    node_record.node_id,
                    node_record.path,
                    node_record.revision,
                    "hidden" if node_record.hidden else "visible",
                    content_token,
                )
            )
        return hashlib.sha256(str(entries).encode()).hexdigest()

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
        )
        artifact_dict: dict[str, PlayerArtifact] = {}
        node_dict: dict[str, PlayerArtifactNode] = {}
        for artifact in artifacts:
            artifact_dict[artifact.artifact_id] = artifact
            for node in artifact.nodes:
                node_dict[node.node_id] = node
        return cls(
            player_id,
            catalog,
            object_store,
            file_ids,
            session,
            writable=writable,
            artifacts=artifact_dict,
            nodes=node_dict,
        )
