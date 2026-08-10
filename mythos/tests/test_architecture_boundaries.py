from __future__ import annotations

import ast
from pathlib import Path


SRC_ROOT = Path(__file__).parents[1] / "src" / "mythos"


def _imported_modules(root: Path) -> set[str]:
    modules: set[str] = set()
    paths = (root,) if root.is_file() else root.rglob("*.py")
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules.add(node.module)
    return modules


def test_commands_do_not_depend_on_http_endpoints() -> None:
    imports = _imported_modules(SRC_ROOT / "commands")

    assert not any(module == "mythos.endpoints" or module.startswith("mythos.endpoints.") for module in imports)


def test_services_and_auth_workflow_do_not_depend_on_endpoint_concerns() -> None:
    imports = _imported_modules(SRC_ROOT / "services")
    imports |= _imported_modules(SRC_ROOT / "auth" / "service.py")

    forbidden = {
        "fastapi",
        "fastapi.responses",
        "mythos.commands.cache",
        "mythos.commands.executor",
        "mythos.commands.task",
    }
    assert not imports & forbidden


def test_endpoints_are_the_only_router_boundary() -> None:
    endpoint_imports = _imported_modules(SRC_ROOT / "endpoints")
    main_imports = _imported_modules(SRC_ROOT / "main.py")

    assert "fastapi" in endpoint_imports
    assert not any(module.endswith(".router") for module in endpoint_imports if module.startswith("mythos.services."))
    assert "mythos.endpoints" in main_imports


def test_player_row_locking_stays_in_player_loader() -> None:
    player_imports = _imported_modules(SRC_ROOT / "players" / "player.py")
    loader_imports = _imported_modules(SRC_ROOT / "players" / "loader.py")

    assert "mythos.persistence.models" not in player_imports
    assert "mythos.persistence.models" in loader_imports
