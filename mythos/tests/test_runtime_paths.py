from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr
from sqlalchemy.engine import make_url

from mythos.core.config import PROJECT_ROOT, Settings


def _settings(**overrides) -> Settings:
    values = {
        "environment": "test",
        "_env_file": None,
        "jwt_signing_key": SecretStr("test-jwt-signing-key-with-at-least-32-bytes"),
        "refresh_token_pepper": SecretStr("test-refresh-token-pepper-with-at-least-32-bytes"),
        "file_id_signing_key": SecretStr("test-file-id-signing-key-with-at-least-32-bytes"),
    }
    values.update(overrides)
    return Settings(**values)


def test_project_root_is_the_current_working_directory() -> None:
    assert PROJECT_ROOT == Path.cwd().resolve()


def test_relative_paths_and_sqlite_url_resolve_under_project_root() -> None:
    settings = _settings(
        database_url="sqlite+aiosqlite:///./relative/mythos.sqlite3",
        puzzle_root=Path("plugins") / "puzzles",
        checkpoint_directory=Path("state") / "checkpoints",
        artifact_template_snapshot_path=Path("state") / "artifact.json",
        virtual_account_template_snapshot_path=Path("state") / "accounts.json",
        task_registry_snapshot_path=Path("state") / "tasks.json",
    )

    assert make_url(settings.database_url).database == (
        PROJECT_ROOT / "relative" / "mythos.sqlite3"
    ).as_posix()
    assert settings.puzzle_root == (PROJECT_ROOT / "plugins" / "puzzles").resolve()
    assert settings.checkpoint_directory == (PROJECT_ROOT / "state" / "checkpoints").resolve()
    assert settings.artifact_snapshot_path == (PROJECT_ROOT / "state" / "artifact.json").resolve()
    assert settings.virtual_account_snapshot_path == (PROJECT_ROOT / "state" / "accounts.json").resolve()
    assert settings.task_snapshot_path == (PROJECT_ROOT / "state" / "tasks.json").resolve()


def test_absolute_paths_are_not_prefixed_with_project_root(tmp_path: Path) -> None:
    database_path = tmp_path / "absolute.sqlite3"
    puzzle_root = tmp_path / "puzzles"
    checkpoint_directory = tmp_path / "checkpoints"

    settings = _settings(
        database_url=f"sqlite+aiosqlite:///{database_path.as_posix()}",
        puzzle_root=puzzle_root,
        checkpoint_directory=checkpoint_directory,
    )

    assert make_url(settings.database_url).database == database_path.as_posix()
    assert settings.puzzle_root == puzzle_root.resolve()
    assert settings.checkpoint_directory == checkpoint_directory.resolve()


def test_windows_drive_sqlite_url_is_treated_as_absolute() -> None:
    settings = _settings(database_url="sqlite+aiosqlite:///C:/external/mythos.sqlite3")

    assert make_url(settings.database_url).database == "C:/external/mythos.sqlite3"


def test_default_snapshot_paths_follow_database_directory() -> None:
    settings = _settings(database_url="sqlite+aiosqlite:///./data/custom.sqlite3")

    assert settings.artifact_snapshot_path == PROJECT_ROOT / "data" / "artifact-template-catalog.json"
    assert settings.virtual_account_snapshot_path == PROJECT_ROOT / "data" / "virtual-account-template-catalog.json"
    assert settings.task_snapshot_path == PROJECT_ROOT / "data" / "task-registry-catalog.json"
