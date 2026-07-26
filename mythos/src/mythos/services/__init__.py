from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mythos.services.container import ServiceContainer

__all__ = ["ServiceContainer"]


def __getattr__(name: str):
    if name == "ServiceContainer":
        from mythos.services.container import ServiceContainer

        return ServiceContainer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
