from mythos.core.commands.cache import RequestCache, RequestInProgressError, RequestReplayForbiddenError
from mythos.core.commands.exceptions import CommandRejected
from mythos.core.commands.models import CachedResponse, ResponseFormatError, ResponseSpec


def __getattr__(name: str):
    if name in {"CommandPreCommitHook", "CommandTransactionExecutor"}:
        from mythos.core.commands.executor import CommandPreCommitHook, CommandTransactionExecutor

        globals().update(
            {
                "CommandPreCommitHook": CommandPreCommitHook,
                "CommandTransactionExecutor": CommandTransactionExecutor,
            }
        )
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "CachedResponse",
    "CommandRejected",
    "CommandPreCommitHook",
    "CommandTransactionExecutor",
    "RequestCache",
    "RequestInProgressError",
    "RequestReplayForbiddenError",
    "ResponseFormatError",
    "ResponseSpec",
]
