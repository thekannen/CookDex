"""Route handlers must not block the event loop.

Uvicorn runs one event loop per process. An ``async def`` handler that calls
``requests``, SQLite, SSH or password hashing without awaiting stalls every
other request, including ``/health``. Handlers that don't await anything
should be plain ``def`` so FastAPI runs them in its threadpool.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROUTERS = Path(__file__).resolve().parents[1] / "src" / "cookdex" / "webui_server" / "routers"


def test_async_route_handlers_actually_await() -> None:
    offenders: list[str] = []
    for path in sorted(ROUTERS.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            awaits = any(isinstance(child, (ast.Await, ast.AsyncFor, ast.AsyncWith)) for child in ast.walk(node))
            if not awaits:
                offenders.append(f"{path.name}:{node.lineno} {node.name}")
    assert offenders == [], "Make these plain `def` handlers:\n" + "\n".join(offenders)
