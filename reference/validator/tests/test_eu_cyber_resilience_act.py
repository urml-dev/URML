"""The EU Cyber Resilience Act rulebook (Regulation (EU) 2024/2847).

A government rulebook with real citations and no FILL_IN: it loads as
shipped. Its rules are the records a robot's maker keeps; with every record
declared the example cell's program is accepted, each missing or unaccepted
record refuses it, and with no deployment rulebook loaded the missing records
are warnings.
"""

from __future__ import annotations

import copy
import datetime as dt
from pathlib import Path
from typing import Any

import pytest
import yaml

from urml_validator import ValidationResult, validate
from urml_validator.evidence_report import build_evidence_report
from urml_validator.schemas.rulebook import Rulebook

REPO_ROOT = Path(__file__).resolve().parents[3]
RULEBOOK = REPO_ROOT / "examples" / "rulebooks" / "eu-cyber-resilience-act.yaml"
CELL = REPO_ROOT / "examples" / "industrial"
EUR_LEX = "https://eur-lex.europa.eu/eli/reg/2024/2847/oj"
CRA = "Regulation (EU) 2024/2847"

RECORDS = {
    "cra_product_class": "default",
    "cra_conformity_assessment_procedure": "module_A",
    "cybersecurity_risk_assessment": "CRA-RA-2027-03",
    "software_bill_of_materials": "SBOM-CELL-7 v4",
    "support_period_end": "2032-12",
    "vulnerability_contact": "psirt@robot-maker.example",
    "cra_eu_declaration_of_conformity": "DoC-CELL-7",
}


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _deployment(**declarations: Any) -> dict[str, Any]:
    return {
        "rulebook_version": "0.1",
        "rulebook_id": "cell_a1_cra_records",
        "title": "Cell A1 CRA records on file",
        "issuer": {"kind": "deployment", "name": "Example Plant"},
        "source_status": "deployment_declaration",
        "declarations": declarations,
    }


def _run(records: dict[str, Any] | None = RECORDS) -> ValidationResult:
    program = _load(CELL / "simple-pick-and-place.urml.yaml")
    manifest = copy.deepcopy(_load(CELL / "simple-pick-and-place.manifest.yaml"))
    books = [_load(RULEBOOK)]
    if records is not None:
        books.append(_deployment(**records))
    return validate(program, manifest, None, profiles=("industrial",), policy=None, rulebooks=books)


def _rule_codes(result: ValidationResult) -> list[str]:
    return [i.code_str for i in result.all_issues if i.code_str.startswith("rule.")]


def test_it_loads_as_shipped_as_an_eu_government_rulebook() -> None:
    book = Rulebook.model_validate(_load(RULEBOOK))
    assert (book.issuer.kind, book.issuer.jurisdiction, book.source_status) == ("government", "EU", "enacted_statute")
    assert book.effective == "2027-12-11"
    assert len(book.rules) == len(RECORDS)
    assert {"exploited_vulnerabilities_reported", "urml_is_a_third_party_component"} <= {o.id for o in book.obligations}


def test_every_cite_names_the_regulation_and_links_the_official_journal() -> None:
    data = _load(RULEBOOK)
    assert "FILL_IN" not in yaml.safe_dump(data)
    for entry in data["rules"] + data["obligations"]:
        cite = entry["cite"]
        assert cite["url"] == EUR_LEX, entry["id"]
        assert cite["standard"] == CRA, entry["id"]
        assert cite["text"].startswith(CRA + ", "), entry["id"]


def test_with_every_record_declared_the_program_is_accepted() -> None:
    result = _run()
    assert _rule_codes(result) == [], result.all_issues
    assert result.accepted


@pytest.mark.parametrize("missing", sorted(RECORDS))
def test_each_missing_record_refuses_the_program(missing: str) -> None:
    result = _run({k: v for k, v in RECORDS.items() if k != missing})
    assert _rule_codes(result) == ["rule.declaration_missing"], result.all_issues
    assert not result.accepted


@pytest.mark.parametrize(
    ("key", "value"),
    [("cra_product_class", "low_risk"), ("cra_conformity_assessment_procedure", "self_declared")],
)
def test_a_value_the_regulation_does_not_name_refuses_the_program(key: str, value: str) -> None:
    result = _run({**RECORDS, key: value})
    assert _rule_codes(result) == ["rule.declaration_missing"], result.all_issues
    assert not result.accepted


def test_with_no_deployment_rulebook_the_missing_records_are_warnings() -> None:
    result = _run(None)
    assert _rule_codes(result) == ["rule.declaration_missing"] * len(RECORDS)
    assert result.accepted


def test_the_evidence_report_groups_it_under_the_regulation() -> None:
    report = build_evidence_report(
        _load(CELL / "simple-pick-and-place.manifest.yaml"),
        as_of=dt.date(2027, 12, 11),
        policy=None,
        rulebooks=[_load(RULEBOOK), _deployment(**RECORDS)],
        default_rulebooks=False,
        profiles=("industrial",),
        manifest_base_dir=CELL,
    )
    (group,) = [g for g in report.by_standard if g.standard == CRA]
    data = _load(RULEBOOK)
    assert sum(len(ids) for ids in group.items.values()) == len(data["rules"]) + len(data["obligations"])
