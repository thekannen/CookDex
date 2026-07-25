from __future__ import annotations

import ast
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _router_paths() -> set[str]:
    paths: set[str] = set()
    for path in (ROOT / "src" / "cookdex" / "webui_server" / "routers").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                func = decorator.func
                if not (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "router"
                    and func.attr in {"get", "post", "put", "patch", "delete"}
                ):
                    continue
                if decorator.args and isinstance(decorator.args[0], ast.Constant):
                    value = decorator.args[0].value
                    if isinstance(value, str):
                        paths.add(value)
    return paths


def test_tasks_api_reference_lists_current_routes() -> None:
    docs = (ROOT / "docs" / "TASKS.md").read_text(encoding="utf-8")

    missing = sorted(path for path in _router_paths() if path not in docs)

    assert missing == []


def test_user_facing_docs_only_advertise_supported_schedule_kinds() -> None:
    schedule_docs = [
        ROOT / "README.md",
        ROOT / "docs" / "DATA_MAINTENANCE.md",
        ROOT / "docs" / "TASKS.md",
        ROOT / "web" / "src" / "constants.js",
    ]

    offenders = []
    for path in schedule_docs:
        text = path.read_text(encoding="utf-8")
        if re.search(r"\bcron\b", text, flags=re.IGNORECASE):
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_direct_db_docs_match_docker_first_setup() -> None:
    task_docs = (ROOT / "docs" / "TASKS.md").read_text(encoding="utf-8")

    assert "pip install 'cookdex[db]'" not in task_docs
    assert "DB credentials in `.env`" not in task_docs


def _node_engine_requirement() -> str:
    package_json = json.loads((ROOT / "web" / "package.json").read_text(encoding="utf-8"))
    return str(package_json["engines"]["node"])


def test_web_package_declares_the_node_version_vite_requires() -> None:
    """package.json must declare whatever the installed Vite actually needs.

    Node 18 was documented long after Vite moved its floor to 20.19, so the
    requirement is pinned in one place and asserted from there.
    """
    requirement = _node_engine_requirement()
    assert "20.19" in requirement
    assert "22.12" in requirement


def test_docs_and_ci_agree_with_the_declared_node_version() -> None:
    """A contributor following the docs, and CI, must both get a usable Node."""
    requirement = _node_engine_requirement()
    major_versions = {int(m) for m in re.findall(r"(\d+)\.\d+", requirement)}

    local_dev = (ROOT / "docs" / "LOCAL_DEV.md").read_text(encoding="utf-8")
    assert "Node 18" not in local_dev, "docs advertise a Node version Vite rejects"
    assert "20.19" in local_dev

    # CI and the Docker build stage must ask for a major line that can satisfy
    # the requirement -- "20" alone resolves below 20.19 on the runners.
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for pinned in re.findall(r'node-version:\s*"([^"]+)"', ci):
        major = int(pinned.split(".")[0])
        assert major in major_versions, f"CI node-version {pinned!r} cannot satisfy {requirement}"
        if major == min(major_versions):
            assert "." in pinned, f"CI node-version {pinned!r} may resolve below the required minor"

    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    for image in re.findall(r"FROM node:(\d+)", dockerfile):
        assert int(image) in major_versions, f"Dockerfile node:{image} cannot satisfy {requirement}"
        if int(image) == min(major_versions):
            raise AssertionError(f"Dockerfile node:{image} may resolve below the required minor")
