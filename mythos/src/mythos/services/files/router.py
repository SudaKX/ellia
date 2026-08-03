from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse

from mythos.auth.dependencies import get_current_player
from mythos.auth.tokens import PlayerIdentity
from mythos.core.runtime import ApplicationRuntime
from mythos.core.dependencies import get_runtime
from mythos.players.context import RequestContext
from mythos.players.dependencies import get_context
from mythos.players.interface_selection import PlayerInterfaces
from mythos.registry.errors import RegistryError
from mythos.services.files.service import (
    DirectorySummary,
    DirectoryTree,
    FileAccessDeniedError,
    FileContentVersionMismatchError,
    FileDirectoryNotFoundError,
    FileMetadata,
    FileSummary,
)
from mythos.services.object_store.service import ObjectStoreError, ObjectStoreUnavailableError

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/ls")
async def list_files(
    response: Response,
    context: Annotated[
        RequestContext,
        Depends(get_context(PlayerInterfaces.PROGRESS | PlayerInterfaces.ACCOUNTS)),
    ],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
    path: Annotated[str, Query()] = "/",
) -> dict[str, object]:
    return _list_directory_response(response, context, runtime, path, dynamic=False)


@router.get("/s/ls")
async def list_static_files(
    response: Response,
    context: Annotated[
        RequestContext,
        Depends(get_context(PlayerInterfaces.PROGRESS | PlayerInterfaces.ACCOUNTS)),
    ],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
    path: Annotated[str, Query()] = "/",
) -> dict[str, object]:
    return _list_directory_response(response, context, runtime, path, dynamic=False)


@router.get("/d/ls")
async def list_dynamic_files(
    response: Response,
    context: Annotated[RequestContext, Depends(get_context(PlayerInterfaces.ALL))],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
    path: Annotated[str, Query()] = "/",
) -> dict[str, object]:
    return _list_directory_response(response, context, runtime, path, dynamic=True)


def _list_directory_response(
    response: Response,
    context: RequestContext,
    runtime: ApplicationRuntime,
    path: str,
    *,
    dynamic: bool,
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Authorization"
    service = runtime.services.files
    try:
        listing = (
            service.list_dynamic_directory(context.player, path)
            if dynamic
            else service.list_directory(context.player, path)
        )
    except FileDirectoryNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Directory not found.") from error
    return {
        "path": listing.path,
        "directories": [_directory_summary(item) for item in listing.directories],
        "files": [_file_summary(item) for item in listing.files],
        "tree_version": listing.tree_version,
    }


@router.get("/tree")
async def file_tree(
    response: Response,
    context: Annotated[
        RequestContext,
        Depends(get_context(PlayerInterfaces.PROGRESS | PlayerInterfaces.ACCOUNTS)),
    ],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
    path: Annotated[str, Query()] = "/",
) -> dict[str, object]:
    return _tree_response(response, context, runtime, path, dynamic=False)


@router.get("/s/tree")
async def static_file_tree(
    response: Response,
    context: Annotated[
        RequestContext,
        Depends(get_context(PlayerInterfaces.PROGRESS | PlayerInterfaces.ACCOUNTS)),
    ],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
    path: Annotated[str, Query()] = "/",
) -> dict[str, object]:
    return _tree_response(response, context, runtime, path, dynamic=False)


@router.get("/d/tree")
async def dynamic_file_tree(
    response: Response,
    context: Annotated[RequestContext, Depends(get_context(PlayerInterfaces.ALL))],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
    path: Annotated[str, Query()] = "/",
) -> dict[str, object]:
    return _tree_response(response, context, runtime, path, dynamic=True)


def _tree_response(
    response: Response,
    context: RequestContext,
    runtime: ApplicationRuntime,
    path: str,
    *,
    dynamic: bool,
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Authorization"
    service = runtime.services.files
    try:
        tree = (
            service.dynamic_directory_tree(context.player, path)
            if dynamic
            else service.directory_tree(context.player, path)
        )
    except FileDirectoryNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Directory not found.") from error
    tree_version = (
        service.player_tree_version(context.player)
        if dynamic
        else service.tree_version
    )
    return {**_directory_tree(tree), "tree_version": tree_version}


@router.get("/version")
async def file_tree_version(
    identity: Annotated[PlayerIdentity, Depends(get_current_player)],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
    if_none_match: Annotated[str | None, Header()] = None,
) -> Response:
    del identity
    return _version_response(runtime.services.files.tree_version, if_none_match)


@router.get("/d/version")
async def dynamic_file_tree_version(
    context: Annotated[RequestContext, Depends(get_context(PlayerInterfaces.ALL))],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
    if_none_match: Annotated[str | None, Header()] = None,
) -> Response:
    return _version_response(
        runtime.services.files.player_tree_version(context.player),
        if_none_match,
    )


def _version_response(tree_version: str, if_none_match: str | None) -> Response:
    etag = f'"{tree_version}"'
    headers = {"Cache-Control": "private, no-cache", "ETag": etag, "Vary": "Authorization"}
    if if_none_match == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return JSONResponse(content={"tree_version": tree_version}, headers=headers)


@router.get("/{file_id}/{content_token}/content-url")
async def issue_content_url(
    file_id: str,
    content_token: str,
    response: Response,
    context: Annotated[RequestContext, Depends(get_context(PlayerInterfaces.ALL))],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
) -> dict[str, str]:
    response.headers["Cache-Control"] = runtime.services.files.content_url_cache_control
    response.headers["Vary"] = "Authorization"
    response.headers["ETag"] = f'"{content_token}"'
    return await _issue_url(file_id, content_token, "content", context, runtime)


@router.get("/{file_id}/{content_token}/download-url")
async def issue_download_url(
    file_id: str,
    content_token: str,
    response: Response,
    context: Annotated[RequestContext, Depends(get_context(PlayerInterfaces.ALL))],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Authorization"
    return await _issue_url(file_id, content_token, "download", context, runtime)


@router.get("/{file_id}")
async def file_metadata(
    file_id: str,
    response: Response,
    context: Annotated[RequestContext, Depends(get_context(PlayerInterfaces.ALL))],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Authorization"
    try:
        metadata = runtime.services.files.metadata(context.player, file_id)
    except FileAccessDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="File access denied.") from error
    except RegistryError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.") from error
    return {
        **_file_metadata(metadata),
        "tree_version": runtime.services.files.player_tree_version(context.player),
    }


async def _issue_url(
    file_id: str,
    content_token: str,
    kind: str,
    context: RequestContext,
    runtime: ApplicationRuntime,
) -> dict[str, str]:
    try:
        if kind == "content":
            issued = await runtime.services.files.issue_content_url(context.player, file_id, content_token)
        else:
            issued = await runtime.services.files.issue_download_url(context.player, file_id, content_token)
    except FileAccessDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="File access denied.") from error
    except FileContentVersionMismatchError as error:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="File content version is stale.",
        ) from error
    except RegistryError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.") from error
    except ObjectStoreUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Object storage is unavailable.") from error
    except ObjectStoreError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to issue file URL.") from error
    return {
        "url": issued.url,
        "expires_at": issued.expires_at.isoformat(),
        "content_token": content_token,
    }


def _directory_summary(item: DirectorySummary) -> dict[str, object]:
    return {"path": item.path, "display": item.display.as_dict()}


def _file_summary(item: FileSummary) -> dict[str, object]:
    return {
        "file_id": item.file_id,
        "path": item.path,
        "version": item.version,
        "media_type": item.media_type,
        "size_bytes": item.size_bytes,
        "content_token": item.content_token,
        "display": item.display.as_dict(),
    }


def _file_metadata(item: FileMetadata) -> dict[str, object]:
    return {
        **_file_summary(item),
        "content_digest": item.content_digest,
        "download_name": item.download_name,
    }


def _directory_tree(item: DirectoryTree) -> dict[str, object]:
    return {
        "path": item.path,
        "display": item.display.as_dict(),
        "directories": [_directory_tree(directory) for directory in item.directories],
        "files": [_file_summary(file) for file in item.files],
    }
