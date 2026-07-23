from __future__ import annotations

from collections.abc import Mapping

from mythos.registry.errors import CallbackNotFoundError, EndpointNotFoundError
from mythos.registry.modules.callbacks import CommandCallbackRegistration, ViewCallbackRegistration


class ModuleCatalog:
    def __init__(
        self,
        views: Mapping[str, tuple[ViewCallbackRegistration, ...]],
        commands: Mapping[str, Mapping[str, CommandCallbackRegistration]],
    ) -> None:
        self._views = dict(views)
        self._commands = {endpoint_id: dict(entries) for endpoint_id, entries in commands.items()}

    def view_callbacks(self, endpoint_id: str) -> tuple[ViewCallbackRegistration, ...]:
        try:
            return self._views[endpoint_id]
        except KeyError as error:
            raise EndpointNotFoundError(endpoint_id) from error

    def command_callback(self, endpoint_id: str, stable_id: str) -> CommandCallbackRegistration:
        try:
            callbacks = self._commands[endpoint_id]
        except KeyError as error:
            raise EndpointNotFoundError(endpoint_id) from error
        try:
            return callbacks[stable_id]
        except KeyError as error:
            raise CallbackNotFoundError(stable_id) from error
