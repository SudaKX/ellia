from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from mythos.auth.dependencies import get_current_player
from mythos.auth.tokens import PlayerIdentity
from mythos.core.dependencies import get_session
from mythos.players.factory import PlayerFactory, PlayerNotFoundError
from mythos.registry.modules import RegistryError
from mythos.services.files.service import FileAccessDeniedError, FileService

router = APIRouter(prefix="/files", tags=["files"])


def _service(request: Request) -> FileService:
    return request.app.state.services.files


@router.get("")
async def list_files(
    identity: Annotated[PlayerIdentity, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[FileService, Depends(_service)],
) -> dict[str, object]:
    try:
        player = await PlayerFactory.load(session, identity.player_id, writable=False)
    except PlayerNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player progress not found.") from error
    return {"items": [{"stable_id": file.stable_id, "path": file.path, "revision": file.revision} for file in service.list_files(player)]}


@router.get("/{stable_id}")
async def read_file(
    stable_id: str,
    identity: Annotated[PlayerIdentity, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[FileService, Depends(_service)],
) -> Response:
    try:
        player = await PlayerFactory.load(session, identity.player_id, writable=False)
        file = service.read(player, stable_id)
    except PlayerNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player progress not found.") from error
    except FileAccessDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="File access denied.") from error
    except RegistryError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.") from error
    return Response(content=file.content, media_type=file.media_type)
