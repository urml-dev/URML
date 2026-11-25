"""The EU Machinery Regulation rulebook (Regulation (EU) 2023/1230).

A government rulebook with real citations and no FILL_IN: it loads as
shipped. Its rules are records a program waits for; with every record
declared the example cell's program is accepted, each missing or unaccepted
record refuses it, and with no deployment rulebook loaded the missing records
are warnings. The evidence report groups everything under the regulation.
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
RULEBOOK = REPO_ROOT / "examples" / "rulebooks" / "eu-machinery-regulation.yaml"
CELL = REPO_ROOT / "examples" / "industrial"
EUR_LEX = "https://eur-lex.europa.eu/eli/reg/2023/1230/oj"
STANDARD = "Regulation (EU) 2023/1230"

#: Every record the rulebook asks for, as an operator would declare them.
RECORDS = {
    "risk_assessment": "RA-2026-014, rev 3",
    "substantial_modification_assessment": "not_a_substantial_modification",
    "conformity_assessment_procedure": "module_A",
    "eu_declaration_of_conformity": "DoC-EXAMPLE-7",
    "technical_documentation": "TF-EXAMPLE-7",
    "safety_software_inventory": "SW-INV-EXAMPLE-7, rev 2",
}


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _deployment(**declarations: Any) -> dict[str, Any]:
    return {
        "rulebook_version": "0.1",
        "rulebook_id": "cell_a1_eu_records",
        "title": "Cell A1 EU records on file",
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
    assert (book.issuer.kind, book.issuer.jurisdiction, book.source_status) == (
        "government",
        "EU",
        "enacted_statute",
    )
    assert book.effective == "2027-01-20"
    assert {r.id for r in book.rules} == {
        "risk_assessment_on_record",
        "substantial_modification_assessed",
        "conformity_assessment_procedure_declared",
        "eu_declaration_of_conformity_on_record",
        "technical_documentation_on_record",
        "safety_software_identified",
    }
    assert "urml_is_not_a_safety_component" in {o.id for o in book.obligations}


def test_every_rule_and_obligation_cites_the_regulation() -> None:
    data = _load(RULEBOOK)
    assert "FILL_IN" not in yaml.safe_dump(data), "it ships with every value in place"
    for entry in data["rules"] + data["obligations"]:
        cite = entry["cite"]
        assert cite["url"] == EUR_LEX, entry["id"]
        assert cite["standard"] == STANDARD, entry["id"]
        assert cite["text"].startswith(STANDARD + ", "), entry["id"]


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
    [
        ("conformity_assessment_procedure", "self_declared"),
        ("substantial_modification_assessment", "not_checked"),
    ],
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
        as_of=dt.date(2027, 2, 1),
        policy=None,
        rulebooks=[_load(RULEBOOK), _deployment(**RECORDS)],
        default_rulebooks=False,
        profiles=("industrial",),
        manifest_base_dir=CELL,
    )
    (group,) = [g for g in report.by_standard if g.standard == STANDARD]
    assert group.keyed_by == "standard"
    ids = [item for items in group.items.values() for item in items]
    data = _load(RULEBOOK)
    assert len(ids) == len(data["rules"]) + len(data["obligations"])
