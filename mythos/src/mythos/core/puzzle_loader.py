from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import TypeAlias, cast 


class PuzzlePluginError(RuntimeError):
    """Raised when the configured external puzzle package cannot be loaded."""


PuzzleRegisterAll: TypeAlias = Callable[..., None]


def load_puzzle_register_all(puzzle_root: Path) -> PuzzleRegisterAll:
    root = puzzle_root.resolve()
    package_init = root / "__init__.py"
    if not package_init.is_file():
        raise PuzzlePluginError(
            f"Puzzle plugin package is unavailable: expected {package_init}."
        )

    parent = str(root.parent)
    sys.path[:] = [entry for entry in sys.path if entry != parent]
    sys.path.insert(0, parent)
    importlib.invalidate_caches()

    package = sys.modules.get("puzzles")
    if package is None:
        try:
            package = importlib.import_module("puzzles")
        except Exception as error:
            raise PuzzlePluginError(f"Could not import puzzle plugin from {root}.") from error

    actual_root = _module_root(package)
    if actual_root != root:
        raise PuzzlePluginError(
            f"Puzzle plugin root conflict: configured {root}, loaded {actual_root}."
        )

    register_all = getattr(package, "register_all", None)
    if not callable(register_all):
        raise PuzzlePluginError(
            f"Puzzle plugin {root} must expose a callable register_all(registries, *, environment)."
        )
    return cast(PuzzleRegisterAll, register_all)


def _module_root(module: ModuleType) -> Path:
    module_file = getattr(module, "__file__", None)
    if not isinstance(module_file, str):
        raise PuzzlePluginError("Puzzle plugin must be a regular package with an __init__.py file.")
    return Path(module_file).resolve().parent
