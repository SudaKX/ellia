"""Explicitly registered puzzle modules."""

from mythos.puzzles.example import register as register_example
from mythos.registry.bundle import RegistryBundle


def register_all(registries: RegistryBundle, *, example_initial_vtb: int = 0) -> None:
    register_example(registries, initial_vtb=example_initial_vtb)
