from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mythos.core.file_ids import FileIdCodec
from mythos.persistence.models import (
    PlayerAchievementState,
    PlayerArtifact,
    PlayerCredits,
    PlayerHintDisclosure,
    PlayerProgress,
    PlayerProgressCheckpoint,
    PlayerRecord,
    PlayerTaskState,
    PlayerVirtualAccount,
    PlayerVirtualAccountState,
)
from mythos.players.interfaces.accounts import AccountInterface
from mythos.players.interfaces.achievements import AchievementInterface
from mythos.players.interfaces.artifacts import ArtifactInterface
from mythos.players.interfaces.credits import CreditInterface
from mythos.players.interfaces.hints import HintInterface
from mythos.players.interfaces.progress import ProgressInterface
from mythos.players.interfaces.tasks import TaskInterface
from mythos.players.interfaces import PlayerInterfaces
from mythos.players.player import Player
from mythos.registry.bundle import RuntimeCatalogs
from mythos.services.object_store.service import ObjectStore


class PlayerNotFoundError(Exception):
    pass


class PlayerLoader:
    def __init__(
        self,
        catalogs: RuntimeCatalogs,
        object_store: ObjectStore,
        file_ids: FileIdCodec,
    ) -> None:
        self._catalogs = catalogs
        self._object_store = object_store
        self._file_ids = file_ids

    async def create(self, session: AsyncSession, player_id: UUID, *, writable: bool) -> Player:
        return Player(player_id, session, self, writable=writable)

    async def load_progress(
        self,
        session: AsyncSession,
        player_id: UUID,
        *,
        writable: bool,
        on_mutation: Callable[[], None] | None = None,
    ) -> ProgressInterface:
        progress = await session.scalar(
            select(PlayerProgress)
            .where(PlayerProgress.player_id == player_id)
            .options(
                selectinload(PlayerProgress.unlocked_nodes),
                selectinload(PlayerProgress.frontier_nodes),
            )
        )
        if progress is None:
            raise PlayerNotFoundError
        checkpoint = None
        if progress.current_checkpoint_sequence >= 0:
            checkpoint = await session.get(
                PlayerProgressCheckpoint,
                (player_id, progress.current_checkpoint_sequence),
            )
        return ProgressInterface(
            progress,
            writable=writable,
            catalogs=self._catalogs,
            checkpoint=checkpoint,
            on_mutation=on_mutation,
        )

    async def load_artifacts(
        self,
        session: AsyncSession,
        player_id: UUID,
        *,
        writable: bool,
        on_mutation: Callable[[], None] | None = None,
    ) -> ArtifactInterface:
        return await ArtifactInterface.load(
            session,
            player_id,
            self._catalogs.artifacts,
            self._object_store,
            self._file_ids,
            writable=writable,
            on_mutation=on_mutation,
        )

    async def load_accounts(
        self,
        session: AsyncSession,
        player_id: UUID,
        *,
        writable: bool,
        on_mutation: Callable[[], None] | None = None,
    ) -> AccountInterface:
        accounts = tuple(
            (
                await session.scalars(
                    select(PlayerVirtualAccount).where(PlayerVirtualAccount.player_id == player_id)
                )
            ).all()
        )
        state = await session.get(PlayerVirtualAccountState, player_id)
        if state is None:
            state = PlayerVirtualAccountState(player_id=player_id)
            if writable:
                session.add(state)
        return AccountInterface(
            player_id,
            self._catalogs.accounts,
            session,
            state,
            accounts,
            writable=writable,
            on_mutation=on_mutation,
        )

    async def load_credits(
        self,
        session: AsyncSession,
        player_id: UUID,
        *,
        writable: bool,
        on_mutation: Callable[[], None] | None = None,
    ) -> CreditInterface:
        credits = await session.get(PlayerCredits, player_id)
        if credits is None:
            credits = PlayerCredits(player_id=player_id, vtb=0, version=0)
            if writable:
                session.add(credits)
                await session.flush()
        return CreditInterface(player_id, session, credits, writable=writable, on_mutation=on_mutation)

    async def load_hints(
        self,
        session: AsyncSession,
        player_id: UUID,
        *,
        writable: bool,
        on_mutation: Callable[[], None] | None = None,
    ) -> HintInterface:
        disclosures = tuple(
            (await session.scalars(select(PlayerHintDisclosure).where(PlayerHintDisclosure.player_id == player_id))).all()
        )
        return HintInterface(player_id, session, disclosures, writable=writable, on_mutation=on_mutation)

    async def load_tasks(
        self,
        session: AsyncSession,
        player_id: UUID,
        *,
        writable: bool,
        on_mutation: Callable[[], None] | None = None,
    ) -> TaskInterface:
        records = tuple(
            (
                await session.scalars(
                    select(PlayerTaskState)
                    .where(PlayerTaskState.player_id == player_id)
                    .order_by(PlayerTaskState.task_id)
                )
            ).all()
        )
        return TaskInterface(
            player_id,
            self._catalogs.tasks,
            session,
            records,
            writable=writable,
            on_mutation=on_mutation,
        )

    async def load_achievements(
        self,
        session: AsyncSession,
        player_id: UUID,
        *,
        writable: bool,
        on_mutation: Callable[[], None] | None = None,
    ) -> AchievementInterface:
        records = tuple(
            (
                await session.scalars(
                    select(PlayerAchievementState)
                    .where(PlayerAchievementState.player_id == player_id)
                    .order_by(PlayerAchievementState.achievement_stable_id)
                )
            ).all()
        )
        return AchievementInterface(
            player_id,
            session,
            records,
            writable=writable,
            on_mutation=on_mutation,
        )

    async def lock_player(self, session: AsyncSession, player_id: UUID) -> None:
        result = await session.execute(
            update(PlayerRecord)
            .where(PlayerRecord.id == player_id)
            .values(last_accessed_at=PlayerRecord.last_accessed_at)
        )
        if result.rowcount != 1:
            raise PlayerNotFoundError

    async def load_writable(
        self,
        session: AsyncSession,
        player_id: UUID,
        *,
        interfaces: PlayerInterfaces,
    ) -> Player:
        await self.lock_player(session, player_id)
        return await self.load_locked(session, player_id, interfaces=interfaces)

    async def load_readonly(
        self,
        session: AsyncSession,
        player_id: UUID,
        *,
        interfaces: PlayerInterfaces,
    ) -> Player:
        await self._ensure_exists(session, player_id)
        return await self._create_and_load(
            session,
            player_id,
            interfaces=interfaces,
            writable=False,
        )

    async def load_locked(
        self,
        session: AsyncSession,
        player_id: UUID,
        *,
        interfaces: PlayerInterfaces,
    ) -> Player:
        await self._ensure_exists(session, player_id)
        return await self._create_and_load(
            session,
            player_id,
            interfaces=interfaces,
            writable=True,
        )

    async def reload(
        self,
        session: AsyncSession,
        player_id: UUID,
        *,
        interfaces: PlayerInterfaces,
    ) -> Player:
        """Load a fresh writable aggregate while the caller retains the row lock."""
        return await self.load_locked(session, player_id, interfaces=interfaces)

    async def load(
        self,
        session: AsyncSession,
        player_id: UUID,
        *,
        writable: bool,
        interfaces: PlayerInterfaces = PlayerInterfaces.ALL,
    ) -> Player:
        """Load a player, locking the row before loading writable state."""
        if writable:
            return await self.load_writable(session, player_id, interfaces=interfaces)
        return await self.load_readonly(session, player_id, interfaces=interfaces)

    async def _create_and_load(
        self,
        session: AsyncSession,
        player_id: UUID,
        *,
        interfaces: PlayerInterfaces,
        writable: bool,
    ) -> Player:
        player = await self.create(session, player_id, writable=writable)
        await player.load_interfaces(interfaces)
        return player

    async def _ensure_exists(self, session: AsyncSession, player_id: UUID) -> None:
        record_id = await session.scalar(
            select(PlayerRecord.id).where(PlayerRecord.id == player_id)
        )
        if record_id != player_id:
            raise PlayerNotFoundError
