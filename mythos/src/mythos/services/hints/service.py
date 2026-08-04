from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import inspect

from mythos.core.commands.models import ResponseSpec
from mythos.players.context import CommandContext
from mythos.players.player import Player
from mythos.registry.errors import RegistryError
from mythos.registry.hints import Hint, HintCatalog
from mythos.services.object_store.service import ObjectStoreReader, PresignedObjectUrl


class HintNotFoundError(Exception):
    pass


class HintUnavailableError(Exception):
    pass


class HintContentVersionMismatchError(Exception):
    pass


class HintAccessRuleError(Exception):
    pass


@dataclass(frozen=True)
class HintSummary:
    hint_id: str
    display: dict[str, str | int | None]
    vtb_cost: int
    media_type: str
    size_bytes: int
    disclosed: bool
    content_token: str | None

    def body(self) -> dict[str, object]:
        body: dict[str, object] = {
            "hint_id": self.hint_id,
            "display": self.display,
            "vtb_cost": self.vtb_cost,
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
            "disclosed": self.disclosed,
        }
        if self.content_token is not None:
            body["content_token"] = self.content_token
        return body


class HintService:
    def __init__(
        self,
        catalog: HintCatalog,
        object_store: ObjectStoreReader,
        content_url_ttl_seconds: int,
        content_cache_max_age_seconds: int,
    ) -> None:
        self._catalog = catalog
        self._object_store = object_store
        self._content_url_ttl_seconds = content_url_ttl_seconds
        self._content_object_cache_control = (
            f"private, max-age={content_cache_max_age_seconds}, must-revalidate"
        )

    @property
    def content_url_cache_control(self) -> str:
        return self._content_object_cache_control

    def list(self, player: Player) -> tuple[HintSummary, ...]:
        return tuple(
            self._summary(player, hint)
            for hint in self._catalog.hints
            if self._is_available(player, hint)
        )

    async def disclose(self, context: CommandContext, hint_id: str) -> ResponseSpec:
        hint = self._hint(hint_id)
        self._ensure_available(context.player, hint)
        claim = await context.player.hints.claim(hint.stable_id)
        if claim.created:
            await context.player.credits.try_spend_vtb(hint.vtb_cost)
        return ResponseSpec(status_code=200, body={"hint": self._summary(context.player, hint).body()}, headers={})

    async def issue_content_url(
        self,
        player: Player,
        hint_id: str,
        content_token: str,
    ) -> PresignedObjectUrl:
        hint = self._hint(hint_id)
        self._ensure_available(player, hint)
        disclosure = player.hints.disclosed(hint.stable_id)
        if disclosure is None:
            raise HintUnavailableError
        content = self._catalog.content(hint)
        if content.content_token != content_token:
            raise HintContentVersionMismatchError
        return await self._object_store.presign_get(
            content.object_ref,
            expires_in_seconds=self._content_url_ttl_seconds,
            content_disposition=f'inline; filename="{content.download_name}"',
            response_cache_control=self._content_object_cache_control,
            response_expires_at=datetime.now(UTC) + timedelta(seconds=self._content_url_ttl_seconds),
        )

    def _summary(self, player: Player, hint: Hint) -> HintSummary:
        content = self._catalog.content(hint)
        disclosure = player.hints.disclosed(hint.stable_id)
        return HintSummary(
            hint_id=self._catalog.public_id_for(hint.stable_id),
            display=hint.display.as_dict(),
            vtb_cost=hint.vtb_cost,
            media_type=content.object_ref.media_type,
            size_bytes=content.object_ref.size_bytes,
            disclosed=disclosure is not None,
            content_token=content.content_token if disclosure is not None else None,
        )

    def _hint(self, hint_id: str) -> Hint:
        try:
            return self._catalog.hint(hint_id)
        except RegistryError as error:
            raise HintNotFoundError from error

    @staticmethod
    def _is_available(player: Player, hint: Hint) -> bool:
        if hint.access_rule is None:
            return True
        allowed = hint.access_rule(player)
        if inspect.isawaitable(allowed):
            if inspect.iscoroutine(allowed):
                allowed.close()
            raise HintAccessRuleError("Hint access rules must return booleans synchronously.")
        if not isinstance(allowed, bool):
            raise HintAccessRuleError("Hint access rules must return booleans.")
        return allowed

    def _ensure_available(self, player: Player, hint: Hint) -> None:
        if not self._is_available(player, hint):
            raise HintUnavailableError
