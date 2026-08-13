from __future__ import annotations

import sys

from mythos import __main__


def test_module_entrypoint_forwards_uvicorn_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def run(app: str, **options: object) -> None:
        captured["app"] = app
        captured.update(options)

    monkeypatch.setattr(__main__.uvicorn, "run", run)
    monkeypatch.setattr(
        sys,
        "argv",
        ["mythos", "--host", "0.0.0.0", "--port", "9000", "--reload"],
    )

    __main__.main()

    assert captured == {
        "app": "mythos.main:app",
        "host": "0.0.0.0",
        "port": 9000,
        "reload": True,
    }
