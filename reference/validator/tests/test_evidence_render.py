"""The human forms of an evidence report (RFC-0707, step 3): Markdown and static HTML.

The forms render the JSON report and must not drop a finding: every item's id,
status and text, every standard and every input digest appear in each form,
and the notice opens each one. Golden files pin two scenarios; regenerate them
with `URML_REGEN_EVIDENCE=1`, as for the JSON goldens.
"""

from __future__ import annotations

import html
import os
import re
from pathlib import Path

import pytest

from tests.test_evidence_report import FIXTURES, SCENARIOS, _build, _cli_args
from urml_validator._version import __version__
from urml_validator.cli import main
from urml_validator.evidence_render import render_html, render_markdown
from urml_validator.evidence_report import NOTICE, STATUSES

GOLDEN = ("amr-warehouse", "drone-vendor")


def _mask(text: str) -> str:
    return text.replace(f"urml-validator {__version__}", "urml-validator VERSION")


def _md_cell(text: str) -> str:
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


@pytest.mark.parametrize("name", SCENARIOS)
def test_markdown_keeps_every_finding(name: str) -> None:
    report = _build(name)
    md = render_markdown(report)
    assert md.splitlines()[2] == f"> {NOTICE}"
    for section in report.sections:
        assert f"## {section.title}" in md
        if section.note:
            assert section.note in md
        for item in section.items:
            assert f"`{item.id}`" in md
            assert _md_cell(item.text) in md
            assert f"`{item.status}" in md
    for group in report.by_standard:
        assert group.standard in md
    for ref in report.inputs.files:
        assert ref.digest in md


@pytest.mark.parametrize("name", SCENARIOS)
def test_html_keeps_every_finding(name: str) -> None:
    report = _build(name)
    page = render_html(report)
    assert f'<p class="notice">{html.escape(NOTICE)}</p>' in page
    for section in report.sections:
        assert f">{html.escape(section.title)}</h2>" in page
        for item in section.items:
            assert f'<tr id="{html.escape(item.id)}">' in page
            assert html.escape(item.text) in page
    for group in report.by_standard:
        assert html.escape(group.standard) in page
    for ref in report.inputs.files:
        assert ref.digest in page


@pytest.mark.parametrize("name", SCENARIOS)
def test_html_is_one_static_file(name: str) -> None:
    page = render_html(_build(name))
    assert page.startswith("<!doctype html>")
    assert "<script" not in page.lower()
    assert not re.search(r"""(src|href)\s*=\s*["']?(https?:)?//""", page, re.IGNORECASE)
    assert "@import" not in page and "url(" not in page


@pytest.mark.parametrize("name", SCENARIOS)
def test_the_forms_are_deterministic(name: str) -> None:
    assert render_markdown(_build(name)) == render_markdown(_build(name))
    assert render_html(_build(name)) == render_html(_build(name))


@pytest.mark.parametrize("name", GOLDEN)
@pytest.mark.parametrize("form", ["md", "html"])
def test_the_forms_match_their_golden_files(name: str, form: str) -> None:
    golden = FIXTURES / name / f"expected.{form}"
    report = _build(name)
    text = _mask(render_markdown(report) if form == "md" else render_html(report))
    if os.environ.get("URML_REGEN_EVIDENCE") == "1":
        golden.write_text(text, encoding="utf-8")
    assert golden.read_text(encoding="utf-8") == text


@pytest.mark.parametrize("form", ["md", "html"])
def test_cli_renders_each_form(form: str, tmp_path: Path) -> None:
    out = tmp_path / f"report.{form}"
    assert main([*_cli_args("drone-vendor"), "--format", form, "--out", str(out)]) == 1
    assert _mask(out.read_text(encoding="utf-8")) == (FIXTURES / "drone-vendor" / f"expected.{form}").read_text(
        encoding="utf-8"
    )


def test_the_summary_counts_every_status_and_says_gaps_plainly() -> None:
    md = render_markdown(_build("drone-vendor"))
    for status in STATUSES:
        assert f"| `{status}` |" in md
    assert "Gaps: 5 (4 missing, 1 failed check)." in md
    assert "Gaps: none." in render_markdown(_build("amr-warehouse"))
