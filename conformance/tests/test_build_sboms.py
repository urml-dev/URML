"""`tools/scripts/build_sboms.py` reads its package list from the release workflow.

The SBOM workflow must cover exactly what the release builds, so the list
comes from `release.yml`. These tests keep that link honest without
building anything.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "tools" / "scripts" / "build_sboms.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_sboms", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_package_list_is_the_release_build_list() -> None:
    packages = _load().release_packages()
    assert packages[0] == "reference/validator"
    assert {"conformance", "reference/vda5050-runtime", "reference/mcp-server"} <= set(packages)
    assert len(packages) == len(set(packages))
    for package in packages:
        assert (REPO_ROOT / package / "pyproject.toml").is_file(), package


def test_the_sbom_workflow_runs_the_script_after_a_release() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "sbom.yml").read_text(encoding="utf-8")
    assert "workflows: [release]" in workflow
    assert "tools/scripts/build_sboms.py" in workflow
    assert "contents: read" in workflow
