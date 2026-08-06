from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mythos.players.context import CommandContext, PlayerLifecycleContext
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
from mythos.registry.files import NodeDisplayParams
from mythos.registry.progress import NormalProgressNode
from mythos.registry.scripts import Script
from mythos.registry.validations import ValidationAttempt, ValidationOutcome

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
_ANSWER = "echo-7"
_handler = module_handler(MODULE_ID)


def register(registries: RegistryBundle) -> None:
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


@_handler(1)
def _is_guest(player: Player) -> bool:
    return player.accounts.is_current(GUEST_ACCOUNT_ID)


@_handler(1)
def _is_guest_completed(player: Player) -> bool:
    return _is_guest(player) and player.progress.is_unlocked(COMPLETED_NODE_ID)


@_handler(1)
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
    context: CommandContext,
    payload: Mapping[str, Any],
) -> ValidationOutcome:
    if not _is_guest(context.player):
        return ValidationOutcome(accepted=False)
    answer = payload.get("answer")
    if not isinstance(answer, str) or answer.strip().casefold() != _ANSWER:
        return ValidationOutcome(accepted=False)
    if context.player.progress.is_unlocked(COMPLETED_NODE_ID):
        return ValidationOutcome(accepted=True)
    if not context.player.progress.is_frontier(ENTRY_NODE_ID):
        return ValidationOutcome(accepted=False)
    await context.player.accounts.issue(
        ADMIN_ACCOUNT_ID,
        ADMIN_USERNAME,
        ADMIN_PASSWORD,
    )
    context.player.progress.push(COMPLETED_NODE_ID)
    await context.player.artifacts.generate_artifact(ADMIN_ACCESS_ARTIFACT_ID, context.player)
    await context.player.artifacts.generate_node(ADMIN_ACCESS_NODE_ID, context.player)
    return ValidationOutcome(accepted=True)
