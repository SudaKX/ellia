from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from mythos.players.player import Player
from mythos.registry.files import FileTree, FileTreeDirectoryNotFoundError, NodeDisplayParams, TreeNode
from mythos.registry.files.player_tree import PlayerFileTree
from mythos.core.file_ids import FileIdCodec
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
    version: str
    media_type: str
    size_bytes: int
    content_token: str
    display: NodeDisplayParams


@dataclass(frozen=True)
class DirectorySummary:
    path: str
    display: NodeDisplayParams


@dataclass(frozen=True)
class DirectoryListing:
    path: str
    directories: tuple[DirectorySummary, ...]
    files: tuple[FileSummary, ...]
    tree_version: str


@dataclass(frozen=True)
class FileMetadata(FileSummary):
    content_digest: str
    download_name: str


@dataclass(frozen=True)
class DirectoryTree:
    path: str
    display: NodeDisplayParams
    directories: tuple["DirectoryTree", ...]
    files: tuple[FileSummary, ...]


type _ReadableFileTree = FileTree | PlayerFileTree


class FileService:
    def __init__(
        self,
        static_tree: FileTree,
        object_store: ObjectStoreReader,
        content_url_ttl_seconds: int,
        content_cache_max_age_seconds: int,
        download_url_ttl_seconds: int,
        file_ids: FileIdCodec,
    ) -> None:
        self._static_tree = static_tree
        self._object_store = object_store
        self._content_url_ttl_seconds = content_url_ttl_seconds
        self._content_cache_control = (
            f"private, max-age={content_cache_max_age_seconds}, must-revalidate"
        )
        self._content_object_cache_control = "private, must-revalidate"
        self._download_url_ttl_seconds = download_url_ttl_seconds
        self._file_ids = file_ids

    @property
    def tree_version(self) -> str:
        return self._static_tree.tree_version

    def player_tree_version(self, player: Player) -> str:
        return self._player_tree(player).tree_version

    @property
    def content_url_cache_control(self) -> str:
        return self._content_cache_control

    def _player_tree(self, player: Player) -> PlayerFileTree:
        return player.artifacts.get_tree(self._static_tree, self._file_ids)

    def list_directory(self, player: Player, path: str = "/") -> DirectoryListing:
        return self._list_directory(self._static_tree, player, path)

    def list_dynamic_directory(self, player: Player, path: str = "/") -> DirectoryListing:
        return self._list_directory(self._player_tree(player), player, path)

    def _list_directory(self, tree: _ReadableFileTree, player: Player, path: str) -> DirectoryListing:
        try:
            directory_chain = tree.directory_chain(path)
        except FileTreeDirectoryNotFoundError as error:
            raise FileDirectoryNotFoundError from error
        if not self._is_allowed_chain(player, directory_chain):
            raise FileDirectoryNotFoundError

        directory = directory_chain[-1]
        directories: list[DirectorySummary] = []
        files: list[FileSummary] = []
        for child in directory.children.values():
            if self._is_hidden_node(child) or not self._is_allowed_node(player, child):
                continue
            if child.is_file:
                files.append(self._summary(child))
            else:
                directories.append(self._directory_summary(child))
        return DirectoryListing(
            path=directory.path,
            directories=tuple(sorted(directories, key=self._sort_by_display)),
            files=tuple(sorted(files, key=self._sort_by_display)),
            tree_version=tree.tree_version,
        )

    def directory_tree(self, player: Player, path: str = "/") -> DirectoryTree:
        return self._directory_tree(self._static_tree, player, path)

    def dynamic_directory_tree(self, player: Player, path: str = "/") -> DirectoryTree:
        return self._directory_tree(self._player_tree(player), player, path)

    def _directory_tree(self, tree: _ReadableFileTree, player: Player, path: str) -> DirectoryTree:
        try:
            directory_chain = tree.directory_chain(path)
        except FileTreeDirectoryNotFoundError as error:
            raise FileDirectoryNotFoundError from error
        if not self._is_allowed_chain(player, directory_chain):
            raise FileDirectoryNotFoundError
        return self._build_directory_tree(player, tree, directory_chain[-1])

    def metadata(self, player: Player, file_id: str) -> FileMetadata:
        return self._metadata(self._player_tree(player), player, file_id)

    def _metadata(self, tree: _ReadableFileTree, player: Player, file_id: str) -> FileMetadata:
        file = self._authorized_file(tree, player, file_id)
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
            self._player_tree(player),
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
            self._player_tree(player),
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
        tree: _ReadableFileTree,
        player: Player,
        file_id: str,
        content_token: str,
        *,
        disposition: str,
        expires_in_seconds: int,
        response_cache_control: str,
        response_expires_at: datetime | None,
    ) -> PresignedObjectUrl:
        file = self._authorized_file(tree, player, file_id)
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

    def _authorized_file(self, tree: _ReadableFileTree, player: Player, file_id: str) -> TreeNode:
        file = tree.file(file_id)
        if not self._is_allowed_chain(player, tree.file_chain(file_id)):
            raise FileAccessDeniedError
        return file

    def _build_directory_tree(self, player: Player, tree: _ReadableFileTree, directory: TreeNode) -> DirectoryTree:
        directories: list[DirectoryTree] = []
        files: list[FileSummary] = []
        for child in directory.children.values():
            if self._is_hidden_node(child) or not self._is_allowed_node(player, child):
                continue
            if child.is_file:
                files.append(self._summary(child))
            else:
                directories.append(self._build_directory_tree(player, tree, child))
        return DirectoryTree(
            path=directory.path,
            display=self._display(directory),
            directories=tuple(sorted(directories, key=self._sort_by_display)),
            files=tuple(sorted(files, key=self._sort_by_display)),
        )

    def _is_allowed_chain(self, player: Player, chain: tuple[TreeNode, ...]) -> bool:
        return all(self._is_allowed_node(player, node) for node in chain)

    @staticmethod
    def _is_allowed_node(player: Player, node: TreeNode) -> bool:
        return node.definition is None or node.definition.access_rule is None or node.definition.access_rule(player)

    @staticmethod
    def _is_hidden_node(node: TreeNode) -> bool:
        return node.definition is not None and node.definition.hidden

    @staticmethod
    def _display(node: TreeNode) -> NodeDisplayParams:
        if node.definition is not None:
            return node.definition.display
        label = "/" if node.path == "/" else node.path.rsplit("/", maxsplit=1)[-1]
        return NodeDisplayParams(label=label, icon="folder")

    def _directory_summary(self, directory: TreeNode) -> DirectorySummary:
        return DirectorySummary(path=directory.path, display=self._display(directory))

    @staticmethod
    def _sort_by_display(item: DirectorySummary | DirectoryTree | FileSummary) -> tuple[int, str]:
        return item.display.sort_order, item.path

    def _summary(self, file: TreeNode) -> FileSummary:
        assert file.definition is not None
        assert file.content is not None
        assert file.file_id is not None
        return FileSummary(
            file_id=file.file_id,
            path=file.definition.path,
            version=file.definition.version,
            media_type=file.content.object_ref.media_type,
            size_bytes=file.content.object_ref.size_bytes,
            content_token=file.content.content_token,
            display=self._display(file),
        )
