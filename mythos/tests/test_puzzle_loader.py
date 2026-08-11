from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import SecretStr

from mythos.core.config import Settings
from mythos.core.puzzle_loader import PuzzlePluginError, load_puzzle_register_all
from mythos.main import create_app


@contextmanager
def _isolated_puzzle_import():
    previous_modules = {
        name: module for name, module in sys.modules.items() if name == "puzzles" or name.startswith("puzzles.")
    }
    previous_path = list(sys.path)
    for name in list(previous_modules):
        del sys.modules[name]
    try:
        yield
    finally:
        for name in list(sys.modules):
            if name == "puzzles" or name.startswith("puzzles."):
                del sys.modules[name]
        sys.modules.update(previous_modules)
        sys.path[:] = previous_path


def _plugin_root(tmp_path: Path, body: str) -> Path:
    root = tmp_path / "puzzles"
    root.mkdir(parents=True)
    (root / "__init__.py").write_text(body, encoding="utf-8")
    return root


def test_loader_imports_external_package_and_validates_its_location(tmp_path: Path) -> None:
    root = _plugin_root(tmp_path, "def register_all(registries, *, environment): pass\n")

    with _isolated_puzzle_import():
        register_all = load_puzzle_register_all(root)

        assert callable(register_all)
        assert sys.path[0] == str(root.parent)
        package = sys.modules["puzzles"]
        assert isinstance(package, ModuleType)
        assert Path(package.__file__).resolve().parent == root.resolve()


def test_loader_rejects_missing_package_init(tmp_path: Path) -> None:
    root = tmp_path / "puzzles"
    root.mkdir()

    with pytest.raises(PuzzlePluginError, match="package is unavailable"):
        load_puzzle_register_all(root)


def test_loader_rejects_missing_register_all(tmp_path: Path) -> None:
    root = _plugin_root(tmp_path, "VALUE = 1\n")

    with _isolated_puzzle_import(), pytest.raises(PuzzlePluginError, match="register_all"):
        load_puzzle_register_all(root)


def test_loader_rejects_switching_to_another_root_in_one_process(tmp_path: Path) -> None:
    first = _plugin_root(tmp_path / "first", "def register_all(registries, *, environment): pass\n")
    second = _plugin_root(tmp_path / "second", "def register_all(registries, *, environment): pass\n")

    with _isolated_puzzle_import():
        load_puzzle_register_all(first)
        with pytest.raises(PuzzlePluginError, match="root conflict"):
            load_puzzle_register_all(second)


def test_create_app_reports_runtime_and_plugin_roots_when_loading_fails(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'app.sqlite3').as_posix()}",
        puzzle_root=tmp_path / "missing-puzzles",
        jwt_signing_key=SecretStr("test-jwt-signing-key-with-at-least-32-bytes"),
        refresh_token_pepper=SecretStr("test-refresh-token-pepper-with-at-least-32-bytes"),
        file_id_signing_key=SecretStr("test-file-id-signing-key-with-at-least-32-bytes"),
    )

    with pytest.raises(PuzzlePluginError, match="PROJECT_ROOT=.*puzzle_root=.*missing-puzzles"):
        create_app(settings)
