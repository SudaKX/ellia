"""Explicitly registered external puzzle modules."""

from puzzles.example import register as register_example
from mythos.registry.bundle import RegistryBundle


def register_all(registries: RegistryBundle, *, environment: str) -> None:
    register_example(
        registries,
        initial_vtb=5 if environment in {"development", "test"} else 0,
    )
