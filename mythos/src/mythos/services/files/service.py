from __future__ import annotations

from dataclasses import dataclass

from mythos.players.player import Player
from mythos.registry.files import FileCatalog, VirtualFile
from mythos.services.object_store.service import ObjectStore, PresignedObjectUrl


class FileAccessDeniedError(Exception):
    pass


class FileDirectoryNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class FileSummary:
    file_id: str
    path: str
    revision: str
    media_type: str
    size_bytes: int


@dataclass(frozen=True)
class DirectoryListing:
    path: str
    directories: tuple[str, ...]
    files: tuple[FileSummary, ...]


@dataclass(frozen=True)
class FileMetadata(FileSummary):
    content_digest: str
    download_name: str


class FileService:
    def __init__(
        self,
        catalog: FileCatalog,
        object_store: ObjectStore,
        download_url_ttl_seconds: int,
    ) -> None:
        self._catalog = catalog
        self._object_store = object_store
        self._download_url_ttl_seconds = download_url_ttl_seconds

    def list_directory(self, player: Player, path: str = "/") -> DirectoryListing:
        directory = _normalize_directory_path(path)
        visible_files = tuple(file for file in self._catalog.all_files() if self._is_allowed(player, file))
        if directory != "/" and not any(_is_under_directory(file.path, directory) for file in visible_files):
            raise FileDirectoryNotFoundError

        directories: set[str] = set()
        files: list[FileSummary] = []
        for file in visible_files:
            relative = file.path[len(directory) :].lstrip("/") if directory != "/" else file.path[1:]
            first_segment, separator, _ = relative.partition("/")
            if separator:
                directories.add(_join_directory(directory, first_segment))
            elif first_segment:
                files.append(self._summary(file))
        return DirectoryListing(
            path=directory,
            directories=tuple(sorted(directories)),
            files=tuple(sorted(files, key=lambda item: item.path)),
        )

    def metadata(self, player: Player, file_id: str) -> FileMetadata:
        file = self._authorized_file(player, file_id)
        return FileMetadata(
            **self._summary(file).__dict__,
            content_digest=file.object_ref.content_digest,
            download_name=file.download_name,
        )

    async def issue_content_url(self, player: Player, file_id: str) -> PresignedObjectUrl:
        return await self._issue_url(player, file_id, disposition="inline")

    async def issue_download_url(self, player: Player, file_id: str) -> PresignedObjectUrl:
        return await self._issue_url(player, file_id, disposition="attachment")

    async def _issue_url(self, player: Player, file_id: str, *, disposition: str) -> PresignedObjectUrl:
        file = self._authorized_file(player, file_id)
        return await self._object_store.presign_get(
            file.object_ref,
            expires_in_seconds=self._download_url_ttl_seconds,
            content_disposition=f'{disposition}; filename="{file.download_name}"',
        )

    def _authorized_file(self, player: Player, file_id: str) -> VirtualFile:
        file = self._catalog.get(file_id)
        if not self._is_allowed(player, file):
            raise FileAccessDeniedError
        return file

    def _is_allowed(self, player: Player, file: VirtualFile) -> bool:
        return file.access_rule is None or file.access_rule(player)

    def _summary(self, file: VirtualFile) -> FileSummary:
        return FileSummary(
            file_id=self._catalog.file_id_for(file),
            path=file.path,
            revision=file.revision,
            media_type=file.object_ref.media_type,
            size_bytes=file.object_ref.size_bytes,
        )


def _normalize_directory_path(path: str) -> str:
    if path == "/":
        return path
    if not path.startswith("/") or "\\" in path:
        raise FileDirectoryNotFoundError
    parts = path.strip("/").split("/")
    if not parts or any(not part or part in {".", ".."} for part in parts):
        raise FileDirectoryNotFoundError
    return "/" + "/".join(parts)


def _is_under_directory(file_path: str, directory: str) -> bool:
    return file_path.startswith(directory + "/")


def _join_directory(parent: str, child: str) -> str:
    return f"/{child}" if parent == "/" else f"{parent}/{child}"
