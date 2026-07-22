from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Mapping

from fastapi.encoders import jsonable_encoder
from mythos.endpoints.actions import Action, ActionExecutionError, is_framework_action
from mythos.endpoints.models import ActionExecutionResult
from mythos.players.context import PlayerRequestContext


class ResponseBodyBuilder:
    _header_name_pattern = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
    def __init__(self) -> None:
        self._response: tuple[int, dict[str, Any], dict[str, str]] | None = None
        self._followups: list[dict[str, Any]] = []

    def set_response(
        self,
        status_code: int,
        body: Mapping[str, Any],
        headers: Mapping[str, str],
    ) -> None:
        if self._response is not None:
            raise ActionExecutionError("A callback may produce only one response action.")
        self._response = (
            status_code,
            self._encode_object(body),
            self._encode_headers(headers),
        )

    def add_followup(self, body: Mapping[str, Any]) -> None:
        self._followups.append(self._encode_object(body))

    def result_parts(self) -> tuple[int, dict[str, Any], dict[str, str], tuple[dict[str, Any], ...]]:
        if self._response is None:
            raise ActionExecutionError("A callback must produce one response action.")
        status_code, body, headers = self._response
        return status_code, body, headers, tuple(self._followups)

    @staticmethod
    def _encode_object(value: Mapping[str, Any]) -> dict[str, Any]:
        try:
            encoded = jsonable_encoder(dict(value))
            json.dumps(encoded, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise ActionExecutionError("Action response bodies must be JSON serializable.") from error
        if not isinstance(encoded, dict):
            raise ActionExecutionError("Action response bodies must encode to JSON objects.")
        return encoded

    @classmethod
    def _encode_headers(cls, headers: Mapping[str, str]) -> dict[str, str]:
        encoded: dict[str, str] = {}
        for key, value in headers.items():
            name = str(key)
            header_value = str(value)
            if not cls._header_name_pattern.fullmatch(name):
                raise ActionExecutionError("Action response headers contain an invalid name.")
            if any(ord(character) < 32 or ord(character) == 127 for character in header_value):
                raise ActionExecutionError("Action response headers contain control characters.")
            encoded[name] = header_value
        return encoded


@dataclass
class ActionRuntime:
    context: PlayerRequestContext
    response_builder: ResponseBodyBuilder


async def execute_actions(
    actions: tuple[Action, ...],
    runtime: ActionRuntime,
) -> ActionExecutionResult:
    for action in actions:
        if not is_framework_action(action):
            raise ActionExecutionError("Callbacks must return framework Action instances.")
        await action.execute(runtime)

    status_code, body, headers, followups = runtime.response_builder.result_parts()
    return ActionExecutionResult(
        owner_player_id=runtime.context.identity.player_id,
        status_code=status_code,
        body=body,
        headers=headers,
        followups=followups,
        state_revision=runtime.context.player.progress.version,
    )
