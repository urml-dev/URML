"""Bundle the files the fixtures name from outside this package.

Fixtures name manifests, envelopes, policies and rulebooks that live in
``reference/validator/tests/fixtures``, ``examples/fleet`` and
``examples/rulebooks``. A wheel built without them runs only from a
repository checkout: installed from PyPI, the suite failed with
``FileNotFoundError`` on the first fixture that needs one (0.5.0).

The sdist copies them to ``_bundled/`` with their repository layout. The
wheel takes them from the repository when it is built from a checkout and
from ``_bundled/`` when it is built from the sdist (``python -m build``
does the latter), and installs them as ``urml_conformance/_data/``. The
layout is kept, so a manifest's relative ``./hbom/...`` reference still
resolves. ``urml_conformance.fixtures`` reads ``_data/`` when it exists.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# Repository-relative directory -> glob of files the suite reads from it.
BUNDLED: dict[str, str] = {
    "reference/validator/tests/fixtures": "**/*",
    "examples/fleet": "*.yaml",
    "examples/rulebooks": "*.yaml",
}


def _files(root: Path) -> dict[str, str]:
    """Map each bundled file under ``root`` to its repository-relative path."""
    found: dict[str, str] = {}
    for rel_dir, pattern in BUNDLED.items():
        base = root / rel_dir
        if not base.is_dir():
            raise FileNotFoundError(f"bundled directory missing: {base}")
        for path in sorted(base.glob(pattern)):
            if path.is_file():
                found[str(path)] = f"{rel_dir}/{path.relative_to(base).as_posix()}"
    return found


class BundleFixtureData(BuildHookInterface):  # type: ignore[type-arg]
    """Add the outside fixture data to the sdist and the wheel."""

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        project = Path(self.root)
        if self.target_name == "sdist":
            for src, rel in _files(project.parent).items():
                build_data["force_include"][src] = f"_bundled/{rel}"
            return
        if self.target_name != "wheel" or version == "editable":
            # An editable install reads the repository directly.
            return
        bundled = project / "_bundled"
        root = bundled if bundled.is_dir() else project.parent
        for src, rel in _files(root).items():
            build_data["force_include"][src] = f"urml_conformance/_data/{rel}"
