"""examples/evidence-report/: the committed reports match what the inputs build (RFC-0707, step 5).

The example is what an auditor reads first, so it must not drift from the
tool. Run `python examples/evidence-report/build.py` after a change that moves
a report, and commit the result. The validator version is masked on both
sides, so a version bump alone does not stale the files.
"""

from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path
from types import ModuleType

import pytest

from urml_validator.cli import main

EXAMPLE = Path(__file__).resolve().parents[3] / "examples" / "evidence-report"
_VERSION = re.compile(r'("name": "urml-validator",\s*"version": ")[^"]+(")|(urml-validator )\d+\.\d+\.\d+\S*')


def _mask(text: str) -> str:
    return _VERSION.sub(lambda m: f"{m.group(1)}VERSION{m.group(2)}" if m.group(1) else f"{m.group(3)}VERSION", text)


def _build_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("evidence_report_example_build", EXAMPLE / "build.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", ["report.json", "report.md", "report.html", "report.redacted.json"])
def test_the_committed_file_is_current(name: str) -> None:
    fresh = _build_module().outputs()[name]
    committed = (EXAMPLE / name).read_text(encoding="utf-8")
    assert _mask(committed) == _mask(fresh), (
        f"examples/evidence-report/{name} is stale; run `python examples/evidence-report/build.py` and commit."
    )


def test_the_readme_command_builds_the_same_report(capsys: pytest.CaptureFixture[str]) -> None:
    cwd = Path.cwd()
    os.chdir(EXAMPLE)
    try:
        code = main(
            [
                "evidence",
                "build",
                "--manifest",
                "manifest.yaml",
                "--envelope",
                "envelope.yaml",
                "--profile",
                "warehouse",
                "--rulebook",
                "amr-rules.yaml",
                "--rulebook",
                "functional-safety.yaml",
                "--rulebook",
                "declarations.yaml",
                "--program",
                "../warehouse/pick-to-conveyor.urml.yaml",
                "--as-of",
                "2026-11-24",
            ]
        )
    finally:
        os.chdir(cwd)
    assert code == 1
    assert _mask(capsys.readouterr().out) == _mask((EXAMPLE / "report.json").read_text(encoding="utf-8"))


def test_the_example_shows_the_gap_its_readme_walks_through() -> None:
    report = _build_module().build()
    gaps = sorted(
        item.id
        for section in report.sections
        for item in section.items
        if item.status == "missing" or item.result == "fail"
    )
    assert gaps == ["rule.hall_2_safety.speed_monitoring_declared", "validated.pick-to-conveyor"]
