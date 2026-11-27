"""Every package ships the license text it is released under.

The Business Source License is a text with parameters. The Change Date and
the Additional Use Grant are written in the file, not in the identifier, so
a package whose metadata says only ``License: BUSL-1.1`` does not say what
its terms are. Releases up to 0.5.2 were published that way.

A wheel or source archive built from a package directory includes that
directory's ``LICENSE``, so each package directory holds a copy of the
repository's ``LICENSE``. These tests keep every copy byte-identical to it.
A change to ``LICENSE`` is copied into each directory in the same commit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ROOT_LICENSE = REPO / "LICENSE"


def _package_dirs() -> list[Path]:
    """Every directory a distribution is built from, plus the plugin bundle."""
    dirs = sorted(p.parent for p in (REPO / "reference").glob("*/pyproject.toml"))
    dirs.append(REPO / "conformance")
    dirs.append(REPO / "plugins" / "urml")
    return dirs


def test_the_package_list_is_not_empty() -> None:
    # The release builds 23 distributions (.github/workflows/release.yml).
    assert len(_package_dirs()) >= 24


@pytest.mark.parametrize("package_dir", _package_dirs(), ids=lambda p: p.name)
def test_package_carries_the_repository_license(package_dir: Path) -> None:
    copy = package_dir / "LICENSE"
    where = copy.relative_to(REPO)
    assert copy.is_file(), f"{where} is missing: copy the repository's LICENSE into {package_dir.relative_to(REPO)}/"
    assert copy.read_bytes() == ROOT_LICENSE.read_bytes(), (
        f"{where} differs from the repository's LICENSE: copy LICENSE over it"
    )
