"""The vendor manifest demo stays runnable (RFC-0710).

`examples/vendor-manifests/demo.py` names fourteen conformance fixtures by
their suite name. Fixture files get renumbered and renamed; this test fails
when the demo points at one that no longer exists, or when a listed fixture
stops passing on the mock adapter.

It also pins the wording rule RFC-0710 set for this directory: the demo and
its README name vendors as products a manifest is shaped like, never as
members of a program.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from urml_conformance.fixtures import discover_fixtures

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO_ROOT / "examples" / "vendor-manifests"
DEMO_PY = DEMO_DIR / "demo.py"


def _load_demo() -> ModuleType:
    spec = importlib.util.spec_from_file_location("vendor_manifest_demo", DEMO_PY)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DEMO = _load_demo()


def test_every_listed_fixture_exists_in_the_suite() -> None:
    known = {case.name for case in discover_fixtures()}
    missing = {slug: entry[1] for slug, entry in DEMO.VENDORS.items() if entry[1] not in known}
    assert not missing, f"demo.py names fixtures the suite does not have: {missing}"


def test_kinds_are_arm_or_part() -> None:
    assert {entry[2] for entry in DEMO.VENDORS.values()} == {"arm", "part"}


@pytest.mark.parametrize("slug", sorted(DEMO.VENDORS))
def test_each_entry_passes_on_the_mock(slug: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert DEMO._run(slug) == 0
    out = capsys.readouterr().out
    assert "[PASS]" in out
    assert DEMO.VENDORS[slug][1] in out


def test_unknown_slug_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    assert DEMO._run("no-such-vendor") == 2
    assert "unknown vendor" in capsys.readouterr().out


def test_list_names_every_slug(capsys: pytest.CaptureFixture[str]) -> None:
    DEMO._list()
    out = capsys.readouterr().out
    for slug in DEMO.VENDORS:
        assert slug in out


def test_no_program_or_partner_wording() -> None:
    """Vendors are named as products, not as participants (RFC-0710)."""
    for path in (DEMO_PY, DEMO_DIR / "README.md"):
        text = path.read_text(encoding="utf-8").lower()
        for word in ("lighthouse", "tier-1", "outreach.yaml"):
            assert word not in text, f"{path.name} still says {word!r}"
    readme = (DEMO_DIR / "README.md").read_text(encoding="utf-8")
    assert "reviewed, supplied or endorsed" in readme
