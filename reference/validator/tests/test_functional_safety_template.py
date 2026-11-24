"""The functional-safety rulebook template (ISO 13849-1:2023, ISO 13849-2).

The template refuses programs until the operator has declared, in a
deployment rulebook, the performance level each safety function reached.
URML checks the declaration, never the safety function itself.

Two guarantees, as for the other templates: as shipped it refuses to load,
and filled in it refuses exactly what it should. The levels used here are
test values, not requirements from the standard.
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
TEMPLATE = REPO_ROOT / "examples" / "rulebooks" / "functional-safety-template.yaml"
WAREHOUSE = REPO_ROOT / "examples" / "warehouse"
DECLARED = {
    "emergency_stop_performance_level": "d",
    "protective_stop_performance_level": "d",
    "speed_monitoring_performance_level": "d",
    "safety_validation_record": "VAL-2026-017",
}


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _fill(value: Any, key: str = "") -> Any:
    if isinstance(value, dict):
        return {k: _fill(v, k) for k, v in value.items()}
    if isinstance(value, list):
        if value == ["FILL_IN"]:
            return ["d", "e"]  # a required performance level of d, for the test
        return [_fill(v, key) for v in value]
    if value == "FILL_IN":
        return {"rulebook_id": "cell_7_safety", "reviewed": "2026-11-24"}[key]
    if isinstance(value, str):
        return value.replace("FILL_IN", "6.2")
    return value


def _deployment(**declarations: Any) -> dict[str, Any]:
    return {
        "rulebook_version": "0.1",
        "rulebook_id": "cell_7_safety_declarations",
        "title": "Cell 7 safety function declarations",
        "issuer": {"kind": "deployment", "name": "Example Integrator"},
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
        "emergency_stop_declared",
        "protective_stop_declared",
        "speed_monitoring_declared",
        "safety_validation_on_record",
    ]
    assert "urml_is_not_a_safety_function" in [o.id for o in book.obligations]


def test_with_every_function_declared_the_program_runs() -> None:
    result = _run(_fill(_load(TEMPLATE)), _deployment(**DECLARED))
    assert _issues(result) == []
    assert result.accepted


def test_a_level_below_the_requirement_refuses_the_program() -> None:
    result = _run(_fill(_load(TEMPLATE)), _deployment(**{**DECLARED, "emergency_stop_performance_level": "c"}))
    assert _issues(result) == [("rule.declaration_missing", "error")]
    assert not result.accepted


def test_a_missing_validation_record_refuses_the_program() -> None:
    declared = {k: v for k, v in DECLARED.items() if k != "safety_validation_record"}
    result = _run(_fill(_load(TEMPLATE)), _deployment(**declared))
    assert _issues(result) == [("rule.declaration_missing", "error")]


def test_with_no_deployment_rulebook_each_missing_declaration_is_a_warning() -> None:
    result = _run(_fill(_load(TEMPLATE)))
    assert _issues(result) == [("rule.declaration_missing", "warning")] * 4
    assert result.accepted
