from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from mythos.players.context import PlayerLifecycleContext, TaskContext, ValidationContext
from mythos.players.interfaces import PlayerInterfaces
from mythos.players.player import Player
from mythos.registry.artifacts import (
    ArtifactNode,
    ArtifactNodeTemplate,
    ArtifactTemplate,
    RawArtifact,
    module_handler,
)
from mythos.registry.bundle import RegistryBundle
from mythos.registry.accounts import VirtualAccountTemplate
from mythos.registry.files import FileReference, NodeDisplayParams
from mythos.registry.hints import Hint, HintDisplayParams
from mythos.registry.lifecycle import LifecyclePriority
from mythos.registry.progress import NormalProgressNode
from mythos.registry.scripts import Script
from mythos.registry.validations import ValidationAttempt, ValidationResult

MODULE_ID = "example"
ENTRY_NODE_ID = "example.entry"
COMPLETED_NODE_ID = "example.completed"
VALIDATION_ID = "example-answer"
GUEST_ACCOUNT_ID = "example.guest"
ADMIN_ACCOUNT_ID = "example.admin"
GUEST_USERNAME = "guest"
GUEST_PASSWORD = "guest-echo-7"
ADMIN_USERNAME = "administrator"
ADMIN_PASSWORD = "admin-echo-9"
ADMIN_ACCESS_ARTIFACT_ID = "example.admin-access"
ADMIN_ACCESS_NODE_ID = "example.admin-access-file"
VTB_TASK_ID = "example.vtb-allowance"
VTB_TASK_INTERVAL = timedelta(seconds=60)
VTB_TASK_INITIAL_GRANT = 5
VTB_TASK_CAP = 10
VTB_TASK_META_SCHEMA_VERSION = 1
_ANSWER = "echo-7"
_handler = module_handler(MODULE_ID)


def register(registries: RegistryBundle, *, initial_vtb: int = 0) -> None:
    registries.progress.register(NormalProgressNode(ENTRY_NODE_ID, (COMPLETED_NODE_ID,), is_entry=True))
    registries.progress.register(NormalProgressNode(COMPLETED_NODE_ID, (), triggers_checkpoint=True))
    registries.files.register_json_tree_asset(
        MODULE_ID,
        "assets/file-tree.json",
        access_rules={
            "guest": _is_guest,
            "guest_completed": _is_guest_completed,
            "admin": _is_admin,
        },
    )
    registries.hints.register(
        Hint(
            stable_id="example.hint.echo",
            source=FileReference(MODULE_ID, "assets/hints/echo-clue.txt", "text/plain; charset=utf-8"),
            download_name="echo-clue.txt",
            display=HintDisplayParams(
                title="Echo 线索",
                teaser="从重复片段中寻找稳定信号。",
                icon="hint",
                sort_order=0,
            ),
            vtb_cost=2,
        )
    )
    registries.hints.register(
        Hint(
            stable_id="example.hint.archive",
            source=FileReference(MODULE_ID, "assets/hints/archive-clue.txt", "text/plain; charset=utf-8"),
            download_name="archive-clue.txt",
            display=HintDisplayParams(
                title="归档线索",
                teaser="理解验证完成后的动态文件变化。",
                icon="archive",
                sort_order=1,
            ),
            vtb_cost=3,
        )
    )
    registries.hints.register(
        Hint(
            stable_id="example.hint.final",
            source=FileReference(MODULE_ID, "assets/hints/final-clue.txt", "text/plain; charset=utf-8"),
            download_name="final-clue.txt",
            display=HintDisplayParams(
                title="最终线索",
                teaser="完成 Echo 后解锁的最后提示。",
                icon="key",
                sort_order=2,
            ),
            vtb_cost=5,
            access_rule=_is_guest_completed,
        )
    )
    registries.accounts.register_template(
        VirtualAccountTemplate(
            GUEST_ACCOUNT_ID,
            "Guest Console",
            permission=10,
            metadata={"tier": "guest"},
        )
    )
    registries.accounts.register_template(
        VirtualAccountTemplate(
            ADMIN_ACCOUNT_ID,
            "Archive Administrator",
            permission=99,
            metadata={"tier": "admin"},
        )
    )

    @registries.lifecycle.on_construct
    async def _issue_guest(context: PlayerLifecycleContext) -> None:
        await context.player.accounts.issue(
            GUEST_ACCOUNT_ID,
            GUEST_USERNAME,
            GUEST_PASSWORD,
        )

    if initial_vtb:
        @registries.lifecycle.on_construct
        async def _grant_initial_vtb(context: PlayerLifecycleContext) -> None:
            await context.player.credits.grant_vtb(initial_vtb)

    @registries.tasks.task(VTB_TASK_ID, dependencies=PlayerInterfaces.CREDITS)
    async def _grant_vtb_allowance(context: TaskContext) -> None:
        now = context.now.astimezone(UTC)
        meta = dict(context.meta)
        schema_version = meta.get("schema_version")
        initial_grant_applied = (
            isinstance(schema_version, int)
            and not isinstance(schema_version, bool)
            and schema_version == VTB_TASK_META_SCHEMA_VERSION
            and meta.get("initial_grant_applied") is True
        )
        total_granted = meta.get("total_granted", 0)
        if isinstance(total_granted, bool) or not isinstance(total_granted, int) or total_granted < 0:
            total_granted = 0
        current_vtb = context.player.credits.vtb
        available = max(0, VTB_TASK_CAP - current_vtb)

        if not initial_grant_applied:
            if available == 0:
                context.set_extra_time(now + VTB_TASK_INTERVAL)
                context.defer()
                return
            grant = min(VTB_TASK_INITIAL_GRANT, available)
            await context.player.credits.grant_vtb(grant)
            context.set_extra_time(now + VTB_TASK_INTERVAL)
            context.update_meta(
                {
                    "schema_version": VTB_TASK_META_SCHEMA_VERSION,
                    "initial_grant_applied": True,
                    "total_granted": total_granted + grant,
                    "last_granted_at": now.isoformat(),
                }
            )
            return

        due_at = context.time_2
        if due_at is None:
            due_at = now
        elif due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=UTC)
        else:
            due_at = due_at.astimezone(UTC)
        if now < due_at:
            context.defer()
            return

        interval_seconds = VTB_TASK_INTERVAL.total_seconds()
        due_periods = int((now - due_at).total_seconds() // interval_seconds) + 1
        available = max(0, VTB_TASK_CAP - current_vtb)
        if available == 0:
            context.set_extra_time(now + VTB_TASK_INTERVAL)
            context.defer()
            return

        grant = min(due_periods, available)
        await context.player.credits.grant_vtb(grant)
        next_due_at = due_at + VTB_TASK_INTERVAL * grant
        if grant < due_periods:
            next_due_at = now + VTB_TASK_INTERVAL
        context.set_extra_time(next_due_at)
        context.update_meta(
            {
                "schema_version": VTB_TASK_META_SCHEMA_VERSION,
                "initial_grant_applied": True,
                "total_granted": total_granted + grant,
                "last_granted_at": now.isoformat(),
            }
        )

    @registries.lifecycle.on_construct(priority=LifecyclePriority.LATE)
    async def _activate_vtb_allowance(context: PlayerLifecycleContext) -> None:
        await context.player.tasks.add_task(VTB_TASK_ID)

    registries.artifacts.register_template(
        ArtifactTemplate(
            artifact_id=ADMIN_ACCESS_ARTIFACT_ID,
            media_type="text/plain; charset=utf-8",
            download_name="ADMIN_ACCESS.txt",
            generator=_generate_admin_access,
        )
    )
    registries.artifacts.register_node(
        ArtifactNodeTemplate(
            stable_id=ADMIN_ACCESS_NODE_ID,
            path="/archive/ADMIN_ACCESS.txt",
            artifact_locator=ADMIN_ACCESS_ARTIFACT_ID,
            display=NodeDisplayParams(
                label="ADMIN_ACCESS.txt",
                description="Administrator credentials",
                icon="document",
                sort_order=1,
            ),
            access_rule=_is_guest_completed,
            node_generator=_generate_admin_access_node,
        )
    )

    registries.scripts.register(
        Script(
            "example.boot",
            "1",
            {
                "schema_version": 1,
                "kind": "answer-validator",
                "validation_id": VALIDATION_ID,
                "input": {"name": "answer", "label": "Access token"},
                "lines": ["Guest console online.", "Submit the Echo access token."],
            },
            _is_guest,
        )
    )
    registries.scripts.register(
        Script(
            "example.completed",
            "1",
            {
                "schema_version": 1,
                "kind": "notice",
                "lines": ["Read /archive/ADMIN_ACCESS.txt while signed in as Guest."],
            },
            _is_guest_completed,
        )
    )
    registries.scripts.register(
        Script(
            "example.admin",
            "1",
            {
                "schema_version": 1,
                "kind": "notice",
                "lines": ["Administrator console online. Read /admin/CONTROL.txt."],
            },
            _is_admin,
        )
    )

    registries.validations.register_attempt(
        ValidationAttempt("example.answer.submit", VALIDATION_ID, _submit_answer)
    )


@_handler(1, dependencies=PlayerInterfaces.ACCOUNTS)
def _is_guest(player: Player) -> bool:
    return player.accounts.is_current(GUEST_ACCOUNT_ID)


@_handler(1, dependencies=PlayerInterfaces.ACCOUNTS | PlayerInterfaces.PROGRESS)
def _is_guest_completed(player: Player) -> bool:
    return _is_guest(player) and player.progress.is_unlocked(COMPLETED_NODE_ID)


@_handler(1, dependencies=PlayerInterfaces.ACCOUNTS)
def _is_admin(player: Player) -> bool:
    return player.accounts.is_current(ADMIN_ACCOUNT_ID)


@_handler(1)
async def _generate_admin_access(player: Player) -> RawArtifact:
    return RawArtifact(
        (
            "ADMINISTRATOR ACCESS\n\n"
            f"Player: {player.id}\n"
            f"Username: {ADMIN_USERNAME}\n"
            f"Password: {ADMIN_PASSWORD}\n"
        ).encode(),
        meta={"account_id": ADMIN_ACCOUNT_ID},
    )


@_handler(1)
async def _generate_admin_access_node(
    _player: Player,
    _meta: Mapping[str, Any],
    node: ArtifactNode,
) -> ArtifactNode:
    return node


async def _submit_answer(
    context: ValidationContext,
    payload: Mapping[str, Any],
) -> ValidationResult:
    if not _is_guest(context.player):
        return ValidationResult(accepted=False)
    answer = payload.get("answer")
    if not isinstance(answer, str) or answer.strip().casefold() != _ANSWER:
        return ValidationResult(accepted=False)
    if context.player.progress.is_unlocked(COMPLETED_NODE_ID):
        return ValidationResult(accepted=True)
    if not context.player.progress.is_frontier(ENTRY_NODE_ID):
        return ValidationResult(accepted=False)
    await context.player.accounts.issue(
        ADMIN_ACCOUNT_ID,
        ADMIN_USERNAME,
        ADMIN_PASSWORD,
    )
    context.player.progress.push(COMPLETED_NODE_ID)
    await context.player.artifacts.generate_artifact(ADMIN_ACCESS_ARTIFACT_ID, context.player)
    await context.player.artifacts.generate_node(ADMIN_ACCESS_NODE_ID, context.player)
    return ValidationResult(accepted=True)
