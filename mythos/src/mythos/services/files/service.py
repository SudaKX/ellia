from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from mythos.players.player import Player
from mythos.registry.files import FileTree, FileTreeDirectoryNotFoundError, TreeNode
from mythos.services.object_store.service import ObjectStoreReader, PresignedObjectUrl


class FileAccessDeniedError(Exception):
    pass


class FileDirectoryNotFoundError(Exception):
    pass


class FileContentVersionMismatchError(Exception):
    pass


@dataclass(frozen=True)
class FileSummary:
    file_id: str
    path: str
    revision: str
    media_type: str
    size_bytes: int
    content_token: str


@dataclass(frozen=True)
class DirectoryListing:
    path: str
    directories: tuple[str, ...]
    files: tuple[FileSummary, ...]
    tree_version: str


@dataclass(frozen=True)
class FileMetadata(FileSummary):
    content_digest: str
    download_name: str


class FileService:
    def __init__(
        self,
        tree: FileTree,
        object_store: ObjectStoreReader,
        content_url_ttl_seconds: int,
        content_cache_max_age_seconds: int,
        download_url_ttl_seconds: int,
    ) -> None:
        self._tree = tree
        self._object_store = object_store
        self._content_url_ttl_seconds = content_url_ttl_seconds
        self._content_cache_control = (
            f"private, max-age={content_cache_max_age_seconds}, must-revalidate"
        )
        self._content_object_cache_control = "private, must-revalidate"
        self._download_url_ttl_seconds = download_url_ttl_seconds

    @property
    def tree_version(self) -> str:
        return self._tree.tree_version

    @property
    def content_url_cache_control(self) -> str:
        return self._content_cache_control

    def list_directory(self, player: Player, path: str = "/") -> DirectoryListing:
        try:
            directory_chain = self._tree.directory_chain(path)
        except FileTreeDirectoryNotFoundError as error:
            raise FileDirectoryNotFoundError from error
        if not self._is_allowed_chain(player, directory_chain):
            raise FileDirectoryNotFoundError

        directory = directory_chain[-1]
        directories: list[str] = []
        files: list[FileSummary] = []
        for child in directory.children.values():
            if child.is_file:
                if self._is_allowed_node(player, child):
                    files.append(self._summary(child))
            elif self._directory_has_visible_file(player, child):
                directories.append(child.path)
        if directory.path != "/" and not directories and not files:
            raise FileDirectoryNotFoundError
        return DirectoryListing(
            path=directory.path,
            directories=tuple(sorted(directories)),
            files=tuple(sorted(files, key=lambda item: item.path)),
            tree_version=self._tree.tree_version,
        )

    def metadata(self, player: Player, file_id: str) -> FileMetadata:
        file = self._authorized_file(player, file_id)
        assert file.definition is not None
        assert file.content is not None
        return FileMetadata(
            **self._summary(file).__dict__,
            content_digest=file.content.object_ref.content_digest,
            download_name=file.content.download_name,
        )

    async def issue_content_url(
        self,
        player: Player,
        file_id: str,
        content_token: str,
    ) -> PresignedObjectUrl:
        return await self._issue_url(
            player,
            file_id,
            content_token,
            disposition="inline",
            expires_in_seconds=self._content_url_ttl_seconds,
            response_cache_control=self._content_object_cache_control,
            response_expires_at=datetime.now(UTC) + timedelta(seconds=self._content_url_ttl_seconds),
        )

    async def issue_download_url(
        self,
        player: Player,
        file_id: str,
        content_token: str,
    ) -> PresignedObjectUrl:
        return await self._issue_url(
            player,
            file_id,
            content_token,
            disposition="attachment",
            expires_in_seconds=self._download_url_ttl_seconds,
            response_cache_control="no-store",
            response_expires_at=None,
        )

    async def _issue_url(
        self,
        player: Player,
        file_id: str,
        content_token: str,
        *,
        disposition: str,
        expires_in_seconds: int,
        response_cache_control: str,
        response_expires_at: datetime | None,
    ) -> PresignedObjectUrl:
        file = self._authorized_file(player, file_id)
        assert file.definition is not None
        assert file.content is not None
        if file.content.content_token != content_token:
            raise FileContentVersionMismatchError
        return await self._object_store.presign_get(
            file.content.object_ref,
            expires_in_seconds=expires_in_seconds,
            content_disposition=f'{disposition}; filename="{file.content.download_name}"',
            response_cache_control=response_cache_control,
            response_expires_at=response_expires_at,
        )

    def _authorized_file(self, player: Player, file_id: str) -> TreeNode:
        file = self._tree.file(file_id)
        if not self._is_allowed_chain(player, self._tree.file_chain(file_id)):
            raise FileAccessDeniedError
        return file

    def _directory_has_visible_file(self, player: Player, directory: TreeNode) -> bool:
        if not self._is_allowed_node(player, directory):
            return False
        for child in directory.children.values():
            if child.is_file and self._is_allowed_node(player, child):
                return True
            if not child.is_file and self._directory_has_visible_file(player, child):
                return True
        return False

    def _is_allowed_chain(self, player: Player, chain: tuple[TreeNode, ...]) -> bool:
        return all(self._is_allowed_node(player, node) for node in chain)

    @staticmethod
    def _is_allowed_node(player: Player, node: TreeNode) -> bool:
        return node.definition is None or node.definition.access_rule is None or node.definition.access_rule(player)

    def _summary(self, file: TreeNode) -> FileSummary:
        assert file.definition is not None
        assert file.content is not None
        assert file.file_id is not None
        return FileSummary(
            file_id=file.file_id,
            path=file.definition.path,
            revision=file.definition.revision,
            media_type=file.content.object_ref.media_type,
            size_bytes=file.content.object_ref.size_bytes,
            content_token=file.content.content_token,
        )
