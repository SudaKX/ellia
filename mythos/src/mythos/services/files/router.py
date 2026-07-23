from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from mythos.auth.dependencies import get_current_player
from mythos.auth.tokens import PlayerIdentity
from mythos.core.runtime import ApplicationRuntime
from mythos.core.dependencies import get_session
from mythos.players.factory import PlayerNotFoundError
from mythos.registry.errors import RegistryError
from mythos.services.files.service import FileAccessDeniedError, FileDirectoryNotFoundError
from mythos.services.object_store.service import ObjectStoreError, ObjectStoreUnavailableError

router = APIRouter(prefix="/files", tags=["files"])


def _runtime(request: Request) -> ApplicationRuntime:
    return request.app.state.runtime


async def _readonly_player(
    session: AsyncSession,
    identity: PlayerIdentity,
    runtime: ApplicationRuntime,
):
    try:
        return await runtime.player_factory.load(session, identity.player_id, writable=False)
    except PlayerNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player progress not found.") from error


@router.get("")
async def list_files(
    identity: Annotated[PlayerIdentity, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_session)],
    runtime: Annotated[ApplicationRuntime, Depends(_runtime)],
    path: Annotated[str, Query()] = "/",
) -> dict[str, object]:
    player = await _readonly_player(session, identity, runtime)
    try:
        listing = runtime.services.files.list_directory(player, path)
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
    identity: Annotated[PlayerIdentity, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_session)],
    runtime: Annotated[ApplicationRuntime, Depends(_runtime)],
) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    return await _issue_url(file_id, "content", session, identity, runtime)


@router.post("/{file_id}/download-url")
async def issue_download_url(
    file_id: str,
    response: Response,
    identity: Annotated[PlayerIdentity, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_session)],
    runtime: Annotated[ApplicationRuntime, Depends(_runtime)],
) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    return await _issue_url(file_id, "download", session, identity, runtime)


@router.get("/{file_id}")
async def file_metadata(
    file_id: str,
    identity: Annotated[PlayerIdentity, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_session)],
    runtime: Annotated[ApplicationRuntime, Depends(_runtime)],
) -> dict[str, object]:
    player = await _readonly_player(session, identity, runtime)
    try:
        return runtime.services.files.metadata(player, file_id).__dict__
    except FileAccessDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="File access denied.") from error
    except RegistryError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.") from error


async def _issue_url(
    file_id: str,
    kind: str,
    session: AsyncSession,
    identity: PlayerIdentity,
    runtime: ApplicationRuntime,
) -> dict[str, str]:
    player = await _readonly_player(session, identity, runtime)
    try:
        if kind == "content":
            issued = await runtime.services.files.issue_content_url(player, file_id)
        else:
            issued = await runtime.services.files.issue_download_url(player, file_id)
    except FileAccessDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="File access denied.") from error
    except RegistryError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.") from error
    except ObjectStoreUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Object storage is unavailable.") from error
    except ObjectStoreError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to issue file URL.") from error
    return {"url": issued.url, "expires_at": issued.expires_at.isoformat()}
