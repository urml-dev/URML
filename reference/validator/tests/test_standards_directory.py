"""docs/standards/: the directory's YAML source, and the README and JSON generated from it.

directory.yaml is the single source for the repository page and for
urml.dev/standards. This test fails when the generated files are stale, when an
entry misses a field or a link, or when a link is not https.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tools" / "scripts" / "gen_standards_doc.py"
TEMPLATES = ROOT / "examples" / "rulebooks"


def _gen() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gen_standards_doc", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_generated_files_are_current() -> None:
    assert _gen().main(["--check"]) == 0, "run: python tools/scripts/gen_standards_doc.py"


def test_the_json_is_the_yaml() -> None:
    gen = _gen()
    assert json.loads((ROOT / "docs" / "standards" / "directory.json").read_text(encoding="utf-8")) == gen.load()


def test_every_entry_is_complete_and_linked() -> None:
    data = _gen().load()
    entries = [e for g in data["groups"] for e in g["entries"]]
    assert len(entries) >= 20
    for entry in entries:
        assert entry["text"], f"{entry['id']}: no link to the text"
        for field in ("what", "why", "who", "how"):
            assert len(entry[field].split()) >= 6, f"{entry['id']}: {field} is too short to help"


def test_every_template_the_directory_names_exists() -> None:
    data = _gen().load()
    for group in data["groups"]:
        for entry in group["entries"]:
            for link in entry["urml"].get("links", []):
                url = link["url"]
                marker = "/examples/rulebooks/"
                if marker in url:
                    name = url.split(marker, 1)[1]
                    assert (TEMPLATES / name).is_file(), f"{entry['id']}: {name} does not exist"


def test_a_broken_link_is_refused(tmp_path: Path) -> None:
    gen = _gen()
    bad = (ROOT / "docs" / "standards" / "directory.yaml").read_text(encoding="utf-8")
    bad = bad.replace('url: "https://www.iso.org"', 'url: "http://www.iso.org"', 1)
    path = tmp_path / "directory.yaml"
    path.write_text(bad, encoding="utf-8")
    with pytest.raises(gen.DirectoryError):
        gen.load(path)
