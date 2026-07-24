from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from mythos.core.runtime import ApplicationRuntime
from mythos.core.dependencies import get_runtime
from mythos.players.context import PlayerRequestContext
from mythos.players.dependencies import get_read_context
from mythos.registry.errors import RegistryError
from mythos.services.files.service import FileAccessDeniedError, FileDirectoryNotFoundError
from mythos.services.object_store.service import ObjectStoreError, ObjectStoreUnavailableError

router = APIRouter(prefix="/files", tags=["files"])


@router.get("")
async def list_files(
    context: Annotated[PlayerRequestContext, Depends(get_read_context)],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
    path: Annotated[str, Query()] = "/",
) -> dict[str, object]:
    try:
        listing = runtime.services.files.list_directory(context.player, path)
    except FileDirectoryNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Directory not found.") from error
    return {
        "path": listing.path,
        "directories": list(listing.directories),
        "files": [item.__dict__ for item in listing.files],
    }


@router.post("/{file_id}/content-url")
async def issue_content_url(
    file_id: str,
    response: Response,
    context: Annotated[PlayerRequestContext, Depends(get_read_context)],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    return await _issue_url(file_id, "content", context, runtime)


@router.post("/{file_id}/download-url")
async def issue_download_url(
    file_id: str,
    response: Response,
    context: Annotated[PlayerRequestContext, Depends(get_read_context)],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    return await _issue_url(file_id, "download", context, runtime)


@router.get("/{file_id}")
async def file_metadata(
    file_id: str,
    context: Annotated[PlayerRequestContext, Depends(get_read_context)],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
) -> dict[str, object]:
    try:
        return runtime.services.files.metadata(context.player, file_id).__dict__
    except FileAccessDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="File access denied.") from error
    except RegistryError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.") from error


async def _issue_url(
    file_id: str,
    kind: str,
    context: PlayerRequestContext,
    runtime: ApplicationRuntime,
) -> dict[str, str]:
    try:
        if kind == "content":
            issued = await runtime.services.files.issue_content_url(context.player, file_id)
        else:
            issued = await runtime.services.files.issue_download_url(context.player, file_id)
    except FileAccessDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="File access denied.") from error
    except RegistryError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.") from error
    except ObjectStoreUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Object storage is unavailable.") from error
    except ObjectStoreError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to issue file URL.") from error
    return {"url": issued.url, "expires_at": issued.expires_at.isoformat()}
