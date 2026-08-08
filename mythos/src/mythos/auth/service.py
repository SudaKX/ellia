from __future__ import annotations

import asyncio
import hmac
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mythos.auth.tokens import (
    RefreshCredential,
    create_refresh_credential,
    hash_refresh_secret,
    issue_access_token,
    parse_refresh_credential,
)
from mythos.auth.passwords import password_hasher
from mythos.core.commands.executor import CommandTransactionExecutor
from mythos.core.config import Settings
from mythos.persistence.base import utcnow
from mythos.persistence.models import (
    PlayerCredits,
    PlayerAuth,
    PlayerProgress,
    PlayerProgressFrontierNode,
    PlayerProgressUnlockedNode,
    PlayerRecord,
    PlayerVirtualAccountState,
)
from mythos.registry.progress import ProgressGraph
from mythos.registry.lifecycle import PlayerConstructEvent
from mythos.services.lifecycle import PlayerLifecycleDispatcher
from mythos.players.context import PlayerLifecycleContext

class UsernameAlreadyExistsError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InvalidRefreshCredentialError(Exception):
    pass


@dataclass(frozen=True)
class AuthenticationResult:
    access_token: str
    refresh_credential: RefreshCredential


def normalize_username(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _is_expired(value: datetime | None) -> bool:
    if value is None:
        return True
    expires_at = value
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= utcnow()


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        progress_graph: ProgressGraph,
        command_executor: CommandTransactionExecutor,
        lifecycle_dispatcher: PlayerLifecycleDispatcher,
    ) -> None:
        self.session = session
        self.settings = settings
        self.progress_graph = progress_graph
        self.command_executor = command_executor
        self.lifecycle_dispatcher = lifecycle_dispatcher

    async def register(self, username: str, password: str) -> AuthenticationResult:
        password_hash = await asyncio.to_thread(password_hasher.hash, password)
        player = PlayerRecord(id=uuid4(), username=username, username_normalized=normalize_username(username))
        credential = create_refresh_credential()
        now = utcnow()
        auth = PlayerAuth(
            player_id=player.id,
            password_hash=password_hash,
            refresh_selector=credential.selector,
            refresh_secret_hash=hash_refresh_secret(credential.secret, self.settings),
            refresh_expires_at=now + timedelta(seconds=self.settings.refresh_token_ttl_seconds),
            refresh_rotated_at=now,
        )
        progress = PlayerProgress(
            player_id=player.id,
            unlocked_nodes=[
                PlayerProgressUnlockedNode(node_id=node_id)
                for node_id in self.progress_graph.entry_node_ids
            ],
            frontier_nodes=[
                PlayerProgressFrontierNode(node_id=node_id)
                for node_id in self.progress_graph.entry_node_ids
            ],
        )

        try:
            async with self.session.begin():
                self.session.add_all((player, auth, progress))
                await self.session.flush()
                self.session.add_all((PlayerVirtualAccountState(player_id=player.id), PlayerCredits(player_id=player.id)))
                await self.session.flush()
                await self._construct(player, "registration")
                await self.command_executor.execute_tasks_nocache_itx(self.session, player.id)
        except IntegrityError as error:
            if "players.username_normalized" in str(error).lower():
                raise UsernameAlreadyExistsError from error
            raise

        return AuthenticationResult(
            access_token=issue_access_token(player.id, self.settings),
            refresh_credential=credential,
        )

    async def login(self, username: str, password: str) -> AuthenticationResult:
        normalized_username = normalize_username(username)
        async with self.session.begin():
            result = await self.session.execute(
                select(PlayerRecord, PlayerAuth)
                .join(PlayerAuth, PlayerAuth.player_id == PlayerRecord.id)
                .where(PlayerRecord.username_normalized == normalized_username)
            )
            row = result.one_or_none()
            if row is None:
                raise InvalidCredentialsError

            player, auth = row
            is_valid = await asyncio.to_thread(password_hasher.verify, password, auth.password_hash)
            if not is_valid:
                raise InvalidCredentialsError

            await self._construct(player, "first_login")

            credential = create_refresh_credential()
            now = utcnow()
            player.last_accessed_at = now
            auth.refresh_selector = credential.selector
            auth.refresh_secret_hash = hash_refresh_secret(credential.secret, self.settings)
            auth.refresh_expires_at = now + timedelta(seconds=self.settings.refresh_token_ttl_seconds)
            auth.refresh_rotated_at = now
            await self.command_executor.execute_tasks_nocache_itx(self.session, player.id)

        return AuthenticationResult(
            access_token=issue_access_token(player.id, self.settings),
            refresh_credential=credential,
        )

    async def refresh(self, cookie_value: str | None) -> AuthenticationResult:
        credential = parse_refresh_credential(cookie_value)
        if credential is None:
            raise InvalidRefreshCredentialError

        expected_hash = hash_refresh_secret(credential.secret, self.settings)
        async with self.session.begin():
            auth = await self.session.scalar(
                select(PlayerAuth).where(PlayerAuth.refresh_selector == credential.selector)
            )
            if (
                auth is None
                or auth.refresh_secret_hash is None
                or _is_expired(auth.refresh_expires_at)
                or not hmac.compare_digest(auth.refresh_secret_hash, expected_hash)
            ):
                raise InvalidRefreshCredentialError

            next_credential = create_refresh_credential()
            now = utcnow()
            update_result = await self.session.execute(
                update(PlayerAuth)
                .where(
                    PlayerAuth.player_id == auth.player_id,
                    PlayerAuth.refresh_selector == credential.selector,
                    PlayerAuth.refresh_secret_hash == expected_hash,
                )
                .values(
                    refresh_selector=next_credential.selector,
                    refresh_secret_hash=hash_refresh_secret(next_credential.secret, self.settings),
                    refresh_expires_at=now + timedelta(seconds=self.settings.refresh_token_ttl_seconds),
                    refresh_rotated_at=now,
                )
            )
            if update_result.rowcount != 1:
                raise InvalidRefreshCredentialError
            await self.session.execute(
                update(PlayerRecord)
                .where(PlayerRecord.id == auth.player_id)
                .values(last_accessed_at=now)
            )

        return AuthenticationResult(
            access_token=issue_access_token(auth.player_id, self.settings),
            refresh_credential=next_credential,
        )

    async def logout(self, player_id: UUID) -> None:
        async with self.session.begin():
            await self.command_executor.execute_tasks_nocache_itx(self.session, player_id)
            await self.session.execute(
                update(PlayerAuth)
                .where(PlayerAuth.player_id == player_id)
                .values(
                    refresh_selector=None,
                    refresh_secret_hash=None,
                    refresh_expires_at=None,
                    refresh_rotated_at=None,
                )
            )

    async def _construct(
        self,
        player: PlayerRecord,
        trigger: Literal["registration", "first_login"],
    ) -> None:
        if player.constructed_at is not None:
            return
        constructed_at = utcnow()
        claimed = await self.session.execute(
            update(PlayerRecord)
            .where(
                PlayerRecord.id == player.id,
                PlayerRecord.constructed_at.is_(None),
            )
            .values(constructed_at=constructed_at)
        )
        if claimed.rowcount != 1:
            await self.session.refresh(player, attribute_names=["constructed_at"])
            return
        player.constructed_at = constructed_at
        event = PlayerConstructEvent(
            player_id=player.id,
            occurred_at=constructed_at,
            trigger=trigger,
        )
        await self.command_executor.execute_nocache_itx(
            self.session,
            player.id,
            lambda aggregate: self.lifecycle_dispatcher.publish(
                PlayerLifecycleContext(player=aggregate, event=event)
            ),
        )
