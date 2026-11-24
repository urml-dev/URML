"""The cybersecurity rulebook template (IEC 62443-3-2:2020, IEC 62443-3-3:2013).

The template refuses programs until the site operator has declared, in a
deployment rulebook, the security level the robot's zone and the URML host's
zone achieved, and where the zone model and the security risk assessment are.
URML checks the declarations, never the security itself.

As for the other templates: as shipped it refuses to load, and filled in it
refuses exactly what it should. The levels here are test values, not targets
from the standard.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError as PydanticValidationError

from urml_validator import ValidationResult, validate
from urml_validator.schemas.rulebook import Rulebook

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = REPO_ROOT / "examples" / "rulebooks" / "cybersecurity-template.yaml"
WAREHOUSE = REPO_ROOT / "examples" / "warehouse"
DECLARED = {
    "robot_zone_security_level": "SL2",
    "urml_zone_security_level": "SL3",
    "zones_and_conduits_record": "ZCR-2026-004",
    "security_risk_assessment_record": "SRA-2026-011",
}
#: Test values: the levels that meet a target of SL 2.
ALLOWED = ["SL2", "SL3", "SL4"]


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _fill(value: Any, key: str = "") -> Any:
    if isinstance(value, dict):
        return {k: _fill(v, k) for k, v in value.items()}
    if isinstance(value, list):
        if value == ["FILL_IN"]:
            return list(ALLOWED)
        return [_fill(v, key) for v in value]
    if value == "FILL_IN":
        return {"rulebook_id": "hall_2_security", "reviewed": "2026-11-24"}[key]
    if isinstance(value, str):
        return value.replace("FILL_IN", "n.n")
    return value


def _deployment(**declarations: Any) -> dict[str, Any]:
    return {
        "rulebook_version": "0.1",
        "rulebook_id": "hall_2_security_declarations",
        "title": "Hall 2 security declarations",
        "issuer": {"kind": "deployment", "name": "Example Operator"},
        "source_status": "deployment_declaration",
        "declarations": declarations,
    }


def _run(*books: dict[str, Any]) -> ValidationResult:
    program = {
        "profile": "warehouse",
        "behavior": {"type": "sequence", "steps": [{"move_to": {"location": "shelf_a3"}}]},
    }
    manifest = copy.deepcopy(_load(WAREHOUSE / "pick-to-conveyor.manifest.yaml"))
    return validate(program, manifest, None, profiles=("warehouse",), policy=None, rulebooks=list(books))


def _issues(result: ValidationResult) -> list[tuple[str, str]]:
    return [(i.code_str, i.severity) for i in result.all_issues if i.code_str.startswith("rule.")]


def test_the_template_as_shipped_refuses_to_load() -> None:
    with pytest.raises(PydanticValidationError) as exc:
        Rulebook.model_validate(_load(TEMPLATE))
    assert "rulebook_id" in str(exc.value)


def test_the_filled_template_loads() -> None:
    book = Rulebook.model_validate(_fill(_load(TEMPLATE)))
    assert [r.id for r in book.rules] == [
        "robot_zone_level_declared",
        "urml_zone_level_declared",
        "zones_and_conduits_on_record",
        "security_risk_assessment_on_record",
    ]
    obligations = [o.id for o in book.obligations]
    assert obligations[0] == "urml_is_not_a_security_control"
    assert "conduit_to_the_robot_protected" in obligations


def test_with_everything_declared_the_program_runs() -> None:
    result = _run(_fill(_load(TEMPLATE)), _deployment(**DECLARED))
    assert _issues(result) == []
    assert result.accepted


@pytest.mark.parametrize(
    ("key", "level"),
    [("robot_zone_security_level", "SL1"), ("urml_zone_security_level", "SL 3")],
    ids=["below_target", "misspelt"],
)
def test_a_level_outside_the_allowed_list_refuses_the_program(key: str, level: str) -> None:
    result = _run(_fill(_load(TEMPLATE)), _deployment(**{**DECLARED, key: level}))
    assert _issues(result) == [("rule.declaration_missing", "error")]
    assert not result.accepted


@pytest.mark.parametrize("key", ["zones_and_conduits_record", "security_risk_assessment_record"])
def test_a_missing_record_refuses_the_program(key: str) -> None:
    declared = {k: v for k, v in DECLARED.items() if k != key}
    result = _run(_fill(_load(TEMPLATE)), _deployment(**declared))
    assert _issues(result) == [("rule.declaration_missing", "error")]


def test_with_no_deployment_rulebook_each_missing_declaration_is_a_warning() -> None:
    result = _run(_fill(_load(TEMPLATE)))
    assert _issues(result) == [("rule.declaration_missing", "warning")] * 4
    assert result.accepted
