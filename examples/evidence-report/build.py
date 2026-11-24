"""Rebuild the committed evidence reports in this folder (RFC-0707).

    python examples/evidence-report/build.py

Writes report.json, report.md, report.html and report.redacted.json from the
inputs next to this script. It does what these commands do:

    urml evidence build --manifest manifest.yaml --envelope envelope.yaml \\
      --profile warehouse --rulebook amr-rules.yaml \\
      --rulebook functional-safety.yaml --rulebook declarations.yaml \\
      --program ../warehouse/pick-to-conveyor.urml.yaml \\
      --as-of 2026-11-24 [--format md|html] [--redact]

`reference/validator/tests/test_evidence_report_example.py` rebuilds them and
fails when a committed file is stale.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from urml_validator.evidence_render import render_html, render_markdown
from urml_validator.evidence_report import EvidenceReport, build_evidence_report, redact_report, render_json

HERE = Path(__file__).resolve().parent
AS_OF = date(2026, 11, 24)
RULEBOOKS = ("amr-rules.yaml", "functional-safety.yaml", "declarations.yaml")
PROGRAM = HERE.parent / "warehouse" / "pick-to-conveyor.urml.yaml"


def _yaml(path: Path) -> dict[str, object]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def build() -> EvidenceReport:
    return build_evidence_report(
        _yaml(HERE / "manifest.yaml"),
        _yaml(HERE / "envelope.yaml"),
        as_of=AS_OF,
        profiles=["warehouse"],
        rulebooks=[_yaml(HERE / name) for name in RULEBOOKS],
        manifest_base_dir=HERE,
        manifest_name="manifest.yaml",
        envelope_name="envelope.yaml",
        rulebook_names=list(RULEBOOKS),
        programs=[(PROGRAM.name, _yaml(PROGRAM))],
    )


def outputs() -> dict[str, str]:
    """Each committed file's name and its text."""
    report = build()
    return {
        "report.json": render_json(report),
        "report.md": render_markdown(report),
        "report.html": render_html(report),
        "report.redacted.json": render_json(redact_report(report)),
    }


def main() -> None:
    for name, text in outputs().items():
        (HERE / name).write_text(text, encoding="utf-8")
        print(f"wrote examples/evidence-report/{name}")


if __name__ == "__main__":
    main()
