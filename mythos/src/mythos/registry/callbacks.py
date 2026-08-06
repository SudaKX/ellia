from __future__ import annotations

import uuid
from collections.abc import Callable
import inspect
from typing import TypeVar


_CALLBACK_NAMESPACE = uuid.UUID("4f5b2b0b-34d7-5d8b-87f1-61ba2f1a2959")
_Callback = TypeVar("_Callback", bound=Callable[..., object])


def module_handler(module: str) -> Callable[[int], Callable[[_Callback], _Callback]]:
    if not module:
        raise ValueError("Module handlers require a module ID.")

    def handler(revision: int) -> Callable[[_Callback], _Callback]:
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise ValueError("Module handler revisions must be positive integers.")

        def decorate(callback: _Callback) -> _Callback:
            if callback.__qualname__ == "<lambda>":
                raise ValueError("Module handlers require named functions.")
            key = f"{module}:{callback.__qualname__}:{revision}"
            setattr(callback, "__callback_id__", str(uuid.uuid5(_CALLBACK_NAMESPACE, key)))
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


def validate_callback(
    callback: Callable[..., object],
    *,
    field_name: str,
    parameter_count: int,
    asynchronous: bool,
) -> None:
    is_async = inspect.iscoroutinefunction(callback) or inspect.iscoroutinefunction(
        getattr(callback, "__call__", None)
    )
    if is_async != asynchronous:
        expected = "asynchronous" if asynchronous else "synchronous"
        raise ValueError(f"{field_name} must be {expected}.")
    callback_id(callback, field_name=field_name)
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
