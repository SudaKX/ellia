from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mythos.players.context import CommandContext
from mythos.players.player import Player
from mythos.registry.bundle import RegistryBundle
from mythos.registry.progress import NormalProgressNode
from mythos.registry.scripts import Script
from mythos.registry.validations import ValidationAttempt, ValidationOutcome

MODULE_ID = "example"
ENTRY_NODE_ID = "example.entry"
COMPLETED_NODE_ID = "example.completed"
VALIDATION_ID = "example-answer"
_ANSWER = "echo-7"


def register(registries: RegistryBundle) -> None:
    registries.progress.register(NormalProgressNode(ENTRY_NODE_ID, (COMPLETED_NODE_ID,), is_entry=True))
    registries.progress.register(NormalProgressNode(COMPLETED_NODE_ID, (), triggers_checkpoint=True))
    registries.files.register_json_tree_asset(
        MODULE_ID,
        "assets/file-tree.json",
        access_rules={"completed": _has_completed_example},
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
                "lines": ["Recovery console online.", "Read /public/README.txt."],
            },
        )
    )
    registries.scripts.register(
        Script(
            "example.completed",
            "1",
            {
                "schema_version": 1,
                "kind": "notice",
                "lines": ["Archive mounted at /archive."],
            },
            _has_completed_example,
        )
    )
    registries.validations.register_attempt(
        ValidationAttempt("example.answer.submit", VALIDATION_ID, _submit_answer)
    )


def _has_completed_example(player: Player) -> bool:
    return player.progress.is_unlocked(COMPLETED_NODE_ID)


async def _submit_answer(
    context: CommandContext,
    payload: Mapping[str, Any],
) -> ValidationOutcome:
    answer = payload.get("answer")
    if not isinstance(answer, str) or answer.strip().casefold() != _ANSWER:
        return ValidationOutcome(accepted=False)
    if context.player.progress.is_unlocked(COMPLETED_NODE_ID):
        return ValidationOutcome(accepted=True)
    if not context.player.progress.is_frontier(ENTRY_NODE_ID):
        return ValidationOutcome(accepted=False)
    context.player.progress.push(COMPLETED_NODE_ID)
    return ValidationOutcome(accepted=True)
