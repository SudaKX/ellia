from datetime import datetime
from uuid import uuid4

import pytest

from mythos.auth.tokens import PlayerIdentity
from mythos.commands import CommandRejected, ResponseFormatError, ResponseSpec
from mythos.core.file_ids import FileIdCodec
from mythos.core.followups import ContextScope, Followup
from mythos.players.context import (
    CommandContext,
    Context,
    PlayerLifecycleContext,
    RequestContext,
    TaskContext,
    ValidationContext,
)
from mythos.registry.lifecycle import PlayerConstructEvent
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
    assert isinstance(context, Context)


def test_command_context_writes_progress_and_freezes_followups() -> None:
    player = _player(writable=True)
    context = CommandContext(
        identity=PlayerIdentity(player_id=player.id),
        player=player,
        request_id=uuid4(),
        scope=ContextScope.http(),
    )

    context.player.progress.push("complete")
    context.follow(Followup(action="checkpoint-set", data={}))
    context.follow(Followup(action="checkpoint-visible", data={}))

    assert isinstance(context, RequestContext)
    assert isinstance(context, Context)

    assert context.player.progress.frontier_node_ids == {
        _CATALOGS.progress.node_ids_by_str_id["complete"]
    }
    assert context.player.progress.version == 2
    assert context.scope.to_json() == [
        {"action": "checkpoint-set", "data": {}},
        {"action": "checkpoint-visible", "data": {}},
    ]
    context.follow(Followup(action="later", data={}))
    assert context.scope.to_json()[-1] == {"action": "later", "data": {}}


def test_context_rejects_commands_and_invalid_followups() -> None:
    player = _player(writable=True)
    context = CommandContext(
        identity=PlayerIdentity(player_id=player.id),
        player=player,
        request_id=uuid4(),
        scope=ContextScope.http(),
    )

    context.follow(Followup(action="invalid", data={"value": float("nan")}))
    with pytest.raises(ResponseFormatError, match="JSON serializable"):
        ResponseSpec(status_code=200, body={"followups": context.scope.to_json()}, headers={})
    with pytest.raises(CommandRejected) as rejection:
        context.reject(409, "blocked")
    assert rejection.value.status_code == 409
    assert rejection.value.detail == "blocked"


def test_silent_context_discards_followups() -> None:
    player = _player(writable=True)
    context = RequestContext(identity=PlayerIdentity(player_id=player.id), player=player)

    context.follow(Followup(action="ignored", data={}))
    assert context.scope.to_json() == []


def test_followup_format_is_validated_at_response_boundary() -> None:
    player = _player(writable=True)
    context = RequestContext(
        identity=PlayerIdentity(player_id=player.id),
        player=player,
        scope=ContextScope.http(),
    )

    context.follow(Followup(action="invalid", data={"value": float("nan")}))
    with pytest.raises(ResponseFormatError, match="JSON serializable"):
        ResponseSpec(status_code=200, body={"followups": context.scope.to_json()}, headers={})


def test_context_children_share_scope_identity_and_ordered_followups() -> None:
    player = _player(writable=True)
    scope = ContextScope.http()
    base = Context(player=player, scope=scope)
    request = RequestContext.from_context(base, identity=PlayerIdentity(player_id=player.id))
    command = CommandContext.from_context(request, request_id=uuid4())
    task = TaskContext.from_context(
        command,
        task_id="test.task",
        time_1=None,
        time_2=None,
        exception=0,
        meta={},
        now=datetime.now(),
    )
    validation = ValidationContext.from_context(command)
    lifecycle = PlayerLifecycleContext.from_context(
        command,
        event=PlayerConstructEvent(player.id, task.now, "first_login"),
    )

    assert all(context.scope is scope for context in (request, command, task, validation, lifecycle))
    request.follow(Followup(action="request", data={}))
    task.follow(Followup(action="task", data={}))
    validation.follow(Followup(action="validation", data={}))
    lifecycle.follow(Followup(action="lifecycle", data={}))
    assert scope.to_json() == [
        {"action": "request", "data": {}},
        {"action": "task", "data": {}},
        {"action": "validation", "data": {}},
        {"action": "lifecycle", "data": {}},
    ]


def test_followup_checkpoint_rollback_removes_only_new_items() -> None:
    player = _player(writable=True)
    context = RequestContext(
        identity=PlayerIdentity(player_id=player.id),
        player=player,
        scope=ContextScope.http(),
    )

    context.follow(Followup(action="before", data={}))
    context.followup_checkpoint()
    context.follow(Followup(action="discard", data={"value": 1}))
    context.followup_rollback()

    assert context.scope.to_json() == [{"action": "before", "data": {}}]


def test_response_specs_validate_bodies_and_headers() -> None:
    with pytest.raises(ResponseFormatError, match="JSON serializable"):
        ResponseSpec(status_code=200, body={"value": float("nan")}, headers={})
    with pytest.raises(ResponseFormatError, match="control characters"):
        ResponseSpec(status_code=200, body={"ok": True}, headers={"X-Test": "ok\r\nbad"})
