"""Every data file a fixture names is bundled into the wheel.

``hatch_build.py`` copies the manifests, envelopes, policies and rulebooks
the fixtures name from outside ``conformance/`` into the wheel. A file
registered from anywhere else would be missing from an installed suite,
which then fails with ``FileNotFoundError`` (as 0.5.0 did on PyPI). The
``conformance-wheel`` workflow runs the suite from a built wheel; this test
catches the same gap without a build.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from urml_conformance.fixtures import (
    _DATA_ROOT,
    ENVELOPE_REGISTRY,
    MANIFEST_REGISTRY,
    POLICY_REGISTRY,
    RULEBOOK_REGISTRY,
)

_HATCH_BUILD = Path(__file__).resolve().parents[1] / "hatch_build.py"


def _bundled() -> dict[str, str]:
    """Read ``BUNDLED`` from hatch_build.py without importing hatchling."""
    tree = ast.parse(_HATCH_BUILD.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "BUNDLED":
            assert node.value is not None
            value = ast.literal_eval(node.value)
            assert isinstance(value, dict)
            return value
    raise AssertionError("BUNDLED not found in hatch_build.py")


_REGISTERED = sorted(
    {
        path
        for registry in (MANIFEST_REGISTRY, ENVELOPE_REGISTRY, POLICY_REGISTRY, RULEBOOK_REGISTRY)
        for path in registry.values()
    }
)


def _is_bundled(rel: str, bundled: dict[str, str]) -> bool:
    for rel_dir, pattern in bundled.items():
        prefix = rel_dir + "/"
        if rel.startswith(prefix):
            inner = Path(rel[len(prefix) :])
            return pattern == "**/*" or inner.match(pattern)
    return False


def test_the_registries_are_not_empty() -> None:
    assert len(_REGISTERED) > 100


@pytest.mark.parametrize("path", _REGISTERED, ids=lambda p: p.name)
def test_registered_file_is_bundled(path: Path) -> None:
    assert path.is_file(), f"registered file does not exist: {path}"
    rel = path.relative_to(_DATA_ROOT).as_posix()
    assert _is_bundled(rel, _bundled()), (
        f"{rel} is not under a directory hatch_build.py bundles; an installed suite would not find it"
    )
