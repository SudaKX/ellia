from types import SimpleNamespace
from uuid import uuid4

import pytest

from mythos.auth.tokens import PlayerIdentity
from mythos.core.commands import CommandRejected, ResponseFormatError, ResponseSpec
from mythos.core.followups import FollowupFormatError
from mythos.players.context import CommandContext, RequestContext
from mythos.players.interfaces import ProgressInterface, ReadOnlyPlayerError
from mythos.players.player import Player


def _player(*, writable: bool) -> Player:
    return Player(
        id=uuid4(),
        progress=ProgressInterface(
            SimpleNamespace(current_account="PLAYER", story_node="intro", checkpoint=None, version=1),
            writable=writable,
        ),
    )


def test_read_context_cannot_modify_progress() -> None:
    player = _player(writable=False)
    context = RequestContext(identity=PlayerIdentity(player_id=player.id), player=player)

    with pytest.raises(ReadOnlyPlayerError, match="cannot modify"):
        context.player.progress.set_checkpoint("first")


def test_command_context_writes_progress_and_freezes_followups() -> None:
    player = _player(writable=True)
    context = CommandContext(
        identity=PlayerIdentity(player_id=player.id),
        player=player,
        request_id=uuid4(),
    )

    context.player.progress.set_checkpoint("first")
    context.follow({"event": "checkpoint-set"})
    context.follow({"event": "checkpoint-visible"})

    assert context.player.progress.checkpoint == "first"
    assert context.player.progress.version == 2
    assert context._freeze_followups() == (
        {"event": "checkpoint-set"},
        {"event": "checkpoint-visible"},
    )
    with pytest.raises(RuntimeError, match="already frozen"):
        context.follow({"event": "later"})


def test_context_rejects_commands_and_invalid_followups() -> None:
    player = _player(writable=True)
    context = CommandContext(
        identity=PlayerIdentity(player_id=player.id),
        player=player,
        request_id=uuid4(),
    )

    with pytest.raises(FollowupFormatError, match="JSON serializable"):
        context.follow({"value": float("nan")})
    with pytest.raises(CommandRejected) as rejection:
        context.reject(409, "blocked")
    assert rejection.value.status_code == 409
    assert rejection.value.detail == "blocked"


def test_response_specs_validate_bodies_and_headers() -> None:
    with pytest.raises(ResponseFormatError, match="JSON serializable"):
        ResponseSpec(status_code=200, body={"value": float("nan")}, headers={})
    with pytest.raises(ResponseFormatError, match="control characters"):
        ResponseSpec(status_code=200, body={"ok": True}, headers={"X-Test": "ok\r\nbad"})
