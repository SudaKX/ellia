"""Explicitly registered puzzle modules."""

from mythos.puzzles.example import register as register_example
from mythos.registry.bundle import RegistryBundle


def register_all(registries: RegistryBundle) -> None:
    register_example(registries)
