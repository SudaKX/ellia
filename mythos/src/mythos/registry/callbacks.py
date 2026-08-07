from __future__ import annotations

import uuid
from collections.abc import Callable
import inspect
from typing import TypeVar

from mythos.core.player_interfaces import PlayerInterfaces

_CALLBACK_NAMESPACE = uuid.UUID("4f5b2b0b-34d7-5d8b-87f1-61ba2f1a2959")
_CALLBACK_NAMESPACE_V2 = uuid.UUID("0ad3b6be-0af2-5b6e-9a3d-127f2a65ad84")
_Callback = TypeVar("_Callback", bound=Callable[..., object])
_DEPENDENCIES_ATTRIBUTE = "__player_interface_dependencies__"


def module_handler(module: str) -> Callable[..., Callable[[_Callback], _Callback]]:
    if not module:
        raise ValueError("Module handlers require a module ID.")

    def handler(
        revision: int,
        *,
        dependencies: PlayerInterfaces | None = None,
    ) -> Callable[[_Callback], _Callback]:
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise ValueError("Module handler revisions must be positive integers.")
        dependencies = _validate_dependencies(dependencies)

        def decorate(callback: _Callback) -> _Callback:
            if callback.__qualname__ == "<lambda>":
                raise ValueError("Module handlers require named functions.")
            dependency_key = "unspecified" if dependencies is None else str(int(dependencies))
            key = f"callback-schema-2:{module}:{callback.__qualname__}:{revision}:{dependency_key}"
            setattr(callback, "__callback_id__", str(uuid.uuid5(_CALLBACK_NAMESPACE_V2, key)))
            setattr(callback, _DEPENDENCIES_ATTRIBUTE, dependencies)
            return callback

        return decorate

    return handler


def callback_id(callback: Callable[..., object], *, field_name: str) -> str:
    value = getattr(callback, "__callback_id__", None)
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be decorated with module_handler().")
    try:
        return str(uuid.UUID(value))
    except ValueError as error:
        raise ValueError(f"{field_name} has an invalid callback ID.") from error


def callback_dependencies(
    callback: Callable[..., object],
    *,
    field_name: str,
    required: bool = False,
) -> PlayerInterfaces | None:
    value = getattr(callback, _DEPENDENCIES_ATTRIBUTE, None)
    if value is None:
        if required:
            raise ValueError(f"{field_name} must declare PlayerInterface dependencies.")
        return None
    try:
        return _validate_dependencies(value)
    except ValueError as error:
        raise ValueError(f"{field_name} has invalid PlayerInterface dependencies.") from error


def validate_callback(
    callback: Callable[..., object],
    *,
    field_name: str,
    parameter_count: int,
    asynchronous: bool,
    require_dependencies: bool = False,
) -> None:
    is_async = inspect.iscoroutinefunction(callback) or inspect.iscoroutinefunction(
        getattr(callback, "__call__", None)
    )
    if is_async != asynchronous:
        expected = "asynchronous" if asynchronous else "synchronous"
        raise ValueError(f"{field_name} must be {expected}.")
    callback_id(callback, field_name=field_name)
    callback_dependencies(callback, field_name=field_name, required=require_dependencies)
    try:
        parameters = tuple(inspect.signature(callback).parameters.values())
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} has an unreadable signature.") from error
    positional_kinds = {
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    }
    if len(parameters) != parameter_count or any(
        parameter.kind not in positional_kinds for parameter in parameters
    ):
        raise ValueError(f"{field_name} must accept exactly {parameter_count} parameters as positional arguments.")


def _validate_dependencies(
    dependencies: PlayerInterfaces | None,
) -> PlayerInterfaces | None:
    if dependencies is None:
        return None
    if not isinstance(dependencies, PlayerInterfaces):
        raise ValueError("PlayerInterface dependencies must be a PlayerInterfaces bitmask.")
    if int(dependencies) & ~int(PlayerInterfaces.ALL):
        raise ValueError("PlayerInterface dependencies contain unknown interface bits.")
    return dependencies
