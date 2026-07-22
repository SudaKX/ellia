import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from mythos.auth.tokens import PlayerIdentity
from mythos.endpoints import EffectAction, FollowupAction, PendingEffectPlan, ResponseAction
from mythos.endpoints.actions import Action, ActionExecutionError, ActionRejected, RejectAction
from mythos.endpoints.execution import ActionRuntime, ResponseBodyBuilder, execute_actions
from mythos.players.context import PlayerRequestContext
from mythos.players.effects import PendingEffect
from mythos.players.interfaces.progress import ProgressInterface
from mythos.players.player import Player


def _runtime() -> ActionRuntime:
    player = Player(
        id=uuid4(),
        progress=ProgressInterface(
            SimpleNamespace(current_account="PLAYER", story_node="intro", checkpoint=None, version=1),
            writable=True,
        ),
    )
    context = PlayerRequestContext(
        identity=PlayerIdentity(player_id=player.id),
        player=player,
    )
    return ActionRuntime(
        context=context,
        response_builder=ResponseBodyBuilder(),
    )


def test_effect_action_freezes_its_plan() -> None:
    player = _runtime().context.player
    plan = PendingEffectPlan().add(player.progress.set_checkpoint("first"))
    action = EffectAction(plan)

    assert action.effects[0].checkpoint == "first"
    with pytest.raises(RuntimeError, match="already owned"):
        plan.add(player.progress.set_checkpoint("second"))


def test_effect_plan_rejects_module_defined_effects() -> None:
    class ModuleEffect(PendingEffect):
        pass

    async def execute() -> None:
        pass

    with pytest.raises(TypeError, match="framework-provided"):
        PendingEffectPlan().add(ModuleEffect("module.effect", execute))


def test_actions_preserve_declared_response_and_followup_order() -> None:
    async def scenario() -> None:
        result = await execute_actions(
            (
                FollowupAction({"name": "first"}),
                FollowupAction({"name": "second"}),
                ResponseAction({"result": "ok"}),
            ),
            _runtime(),
        )
        assert result.body == {"result": "ok"}
        assert result.followups == ({"name": "first"}, {"name": "second"})

    asyncio.run(scenario())


def test_actions_require_one_response_and_propagate_rejection() -> None:
    class ModuleAction(Action):
        async def execute(self, runtime) -> None:
            runtime.response_builder.set_response(200, {"unexpected": True}, {})

    async def scenario() -> None:
        with pytest.raises(ActionExecutionError, match="must produce"):
            await execute_actions((FollowupAction({"name": "only"}),), _runtime())
        with pytest.raises(ActionRejected) as rejection:
            await execute_actions((RejectAction(409, "blocked"),), _runtime())
        assert rejection.value.status_code == 409
        with pytest.raises(ActionExecutionError, match="framework Action"):
            await execute_actions((ModuleAction(),), _runtime())

    asyncio.run(scenario())


def test_effect_action_and_response_output_reject_untrusted_objects() -> None:
    class FakePlan:
        def freeze(self):
            return ()

    async def scenario() -> None:
        with pytest.raises(TypeError, match="framework PendingEffectPlan"):
            EffectAction(FakePlan())  # type: ignore[arg-type]
        with pytest.raises(ActionExecutionError, match="JSON serializable"):
            await execute_actions((ResponseAction({"value": float("nan")}),), _runtime())
        with pytest.raises(ActionExecutionError, match="control characters"):
            await execute_actions((ResponseAction({"ok": True}, headers={"X-Test": "ok\r\nbad"}),), _runtime())

    asyncio.run(scenario())
