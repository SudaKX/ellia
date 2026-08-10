from __future__ import annotations

from dataclasses import dataclass

from mythos.players.interfaces.accounts import Account, InvalidAccountCredentialsError
from mythos.players.player import Player


@dataclass(frozen=True)
class AccountSnapshot:
    current_account: Account | None
    version: int

    def body(self) -> dict[str, object]:
        return {
            "current_account": self.current_account.body() if self.current_account is not None else None,
            "version": self.version,
        }


class AccountService:
    def snapshot(self, player: Player) -> AccountSnapshot:
        return AccountSnapshot(
            current_account=player.accounts.current,
            version=player.accounts.version,
        )

    async def login(self, player: Player, username: str, password: str) -> AccountSnapshot:
        await player.accounts.login(username, password)
        return self.snapshot(player)

    async def logout(self, player: Player) -> AccountSnapshot:
        await player.accounts.logout()
        return self.snapshot(player)


__all__ = ["AccountService", "AccountSnapshot", "InvalidAccountCredentialsError"]
