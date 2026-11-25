"""The EU AI Act rulebook (Regulation (EU) 2024/1689, as amended by Regulation (EU) 2026/1744).

A government rulebook with real citations and no FILL_IN, for a robot whose
programs an AI system proposes. Its rules are records a program waits for.
An operator with no AI system declares ai_system_in_use: false and the
rulebook switches off.
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
RULEBOOK = REPO_ROOT / "examples" / "rulebooks" / "eu-ai-act.yaml"
MACHINERY = REPO_ROOT / "examples" / "rulebooks" / "eu-machinery-regulation.yaml"
CELL = REPO_ROOT / "examples" / "industrial"
AI_ACT = "Regulation (EU) 2024/1689"
EUR_LEX = ("https://eur-lex.europa.eu/eli/reg/2024/1689/oj", "https://eur-lex.europa.eu/eli/reg/2026/1744/oj")

RECORDS: dict[str, Any] = {
    "ai_system_in_use": True,
    "ai_safety_component_assessment": "not_a_safety_component",
    "ai_interaction_disclosure": "people_informed",
    "ai_literacy_measures": "TRN-2026-04",
}
REQUIRED = sorted(k for k in RECORDS if k != "ai_system_in_use")


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _deployment(**declarations: Any) -> dict[str, Any]:
    return {
        "rulebook_version": "0.1",
        "rulebook_id": "cell_a1_ai_records",
        "title": "Cell A1 AI records on file",
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
    assert {r.id for r in book.rules} == {
        "safety_component_assessed",
        "people_told_they_deal_with_ai",
        "ai_literacy_on_record",
    }
    assert "every_proposed_program_is_validated" in {o.id for o in book.obligations}


def test_every_cite_names_the_ai_act_and_links_the_official_journal() -> None:
    data = _load(RULEBOOK)
    assert "FILL_IN" not in yaml.safe_dump(data)
    for entry in data["rules"] + data["obligations"]:
        cite = entry["cite"]
        assert cite["url"] in EUR_LEX, entry["id"]
        standards = [cite["standard"]] if isinstance(cite["standard"], str) else cite["standard"]
        assert AI_ACT in standards, entry["id"]


def test_with_every_record_declared_the_program_is_accepted() -> None:
    result = _run()
    assert _rule_codes(result) == [], result.all_issues
    assert result.accepted


@pytest.mark.parametrize("missing", REQUIRED)
def test_each_missing_record_refuses_the_program(missing: str) -> None:
    result = _run({k: v for k, v in RECORDS.items() if k != missing})
    assert _rule_codes(result) == ["rule.declaration_missing"], result.all_issues
    assert not result.accepted


@pytest.mark.parametrize(
    ("key", "value"),
    [("ai_safety_component_assessment", "not_assessed"), ("ai_interaction_disclosure", "nobody_asked")],
)
def test_a_value_the_act_does_not_name_refuses_the_program(key: str, value: str) -> None:
    result = _run({**RECORDS, key: value})
    assert _rule_codes(result) == ["rule.declaration_missing"], result.all_issues
    assert not result.accepted


def test_a_robot_with_no_ai_system_switches_it_off() -> None:
    result = _run({"ai_system_in_use": False})
    assert _rule_codes(result) == [], result.all_issues
    assert result.accepted


def test_with_no_deployment_rulebook_the_missing_records_are_warnings() -> None:
    result = _run(None)
    assert _rule_codes(result) == ["rule.declaration_missing"] * len(REQUIRED)
    assert result.accepted


def test_it_loads_beside_the_machinery_rulebook_and_the_evidence_report_groups_both() -> None:
    machinery = {
        "risk_assessment": "RA-1",
        "substantial_modification_assessment": "not_a_substantial_modification",
        "conformity_assessment_procedure": "module_A",
        "eu_declaration_of_conformity": "DoC-1",
        "technical_documentation": "TF-1",
        "safety_software_inventory": "SW-1",
    }
    report = build_evidence_report(
        _load(CELL / "simple-pick-and-place.manifest.yaml"),
        as_of=dt.date(2027, 2, 1),
        policy=None,
        rulebooks=[_load(MACHINERY), _load(RULEBOOK), _deployment(**RECORDS, **machinery)],
        default_rulebooks=False,
        profiles=("industrial",),
        manifest_base_dir=CELL,
    )
    standards = {g.standard for g in report.by_standard}
    assert {AI_ACT, "Regulation (EU) 2023/1230"} <= standards
