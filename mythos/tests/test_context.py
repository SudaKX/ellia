from uuid import uuid4

import pytest

from mythos.auth.tokens import PlayerIdentity
from mythos.core.commands import CommandRejected, ResponseFormatError, ResponseSpec
from mythos.core.file_ids import FileIdCodec
from mythos.core.followups import FollowupFormatError
from mythos.players.context import CommandContext, PlayerContext, RequestContext
from mythos.players.interfaces import ProgressInterface, ReadOnlyPlayerError
from mythos.players.player import Player
from mythos.persistence.models import PlayerProgress, PlayerProgressFrontierNode, PlayerProgressUnlockedNode
from mythos.registry.bundle import RegistryBundle
from mythos.registry.progress import NormalProgressNode


_REGISTRIES = RegistryBundle()
_REGISTRIES.progress.register(NormalProgressNode("start", ("complete",), is_entry=True))
_REGISTRIES.progress.register(NormalProgressNode("complete", ()))
_CATALOGS = _REGISTRIES.freeze(FileIdCodec("test-file-id-secret"))


def _player(*, writable: bool) -> Player:
    player = Player(uuid4(), None, None, writable=writable)  # type: ignore[arg-type]
    player._progress = ProgressInterface(
        PlayerProgress(
            player_id=uuid4(),
            version=1,
            unlocked_nodes=[
                PlayerProgressUnlockedNode(
                    node_id=_CATALOGS.progress.node_ids_by_str_id["start"]
                )
            ],
            frontier_nodes=[
                PlayerProgressFrontierNode(
                    node_id=_CATALOGS.progress.node_ids_by_str_id["start"]
                )
            ],
        ),
        writable=writable,
        catalogs=_CATALOGS,
    )
    return player


def test_read_context_cannot_modify_progress() -> None:
    player = _player(writable=False)
    context = RequestContext(identity=PlayerIdentity(player_id=player.id), player=player)

    with pytest.raises(ReadOnlyPlayerError, match="cannot modify"):
        context.player.progress.push("complete")
    assert isinstance(context, PlayerContext)


def test_command_context_writes_progress_and_freezes_followups() -> None:
    player = _player(writable=True)
    context = CommandContext(
        identity=PlayerIdentity(player_id=player.id),
        player=player,
        request_id=uuid4(),
    )

    context.player.progress.push("complete")
    context.follow({"event": "checkpoint-set"})
    context.follow({"event": "checkpoint-visible"})

    assert isinstance(context, RequestContext)
    assert isinstance(context, PlayerContext)

    assert context.player.progress.frontier_node_ids == {
        _CATALOGS.progress.node_ids_by_str_id["complete"]
    }
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
