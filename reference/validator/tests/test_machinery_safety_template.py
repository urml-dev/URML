"""The machinery-safety rulebook template (ISO 12100, ISO 13850, ISO 13855, ISO 14119, IEC 60204-1, IEC 61496).

The template refuses programs until the site operator has declared the risk
assessment, the emergency stop's stop category, the safeguard distances, the
interlocking, the protective-device type and the electrical verification, and
it keeps programs off the outputs wired to safeguards. URML checks the
declarations, never the safety measures. The values here are test values.
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
TEMPLATE = REPO_ROOT / "examples" / "rulebooks" / "machinery-safety-template.yaml"
CELL = REPO_ROOT / "examples" / "industrial"
DECLARED = {
    "risk_assessment_record": "RA-2026-031",
    "emergency_stop_category": "category_1",
    "safeguard_distance_record": "SD-2026-007",
    "interlocking_record": "IL-2026-007",
    "protective_device_type": "type_3",
    "electrical_verification_record": "EV-2026-012",
}
FILLED_LISTS = {
    "emergency_stop_category": ["category_0", "category_1"],
    "protective_device_type": ["type_3", "type_4"],
}


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _fill(value: Any, key: str = "", require_key: str = "") -> Any:
    if isinstance(value, dict):
        rkey = value.get("key", require_key) if "key" in value else require_key
        return {k: _fill(v, k, rkey) for k, v in value.items()}
    if isinstance(value, list):
        if value == ["FILL_IN"]:
            return list(FILLED_LISTS[require_key]) if key == "allowed" else ["guard_lock"]
        return [_fill(v, key, require_key) for v in value]
    if value == "FILL_IN":
        return {"rulebook_id": "cell_4_machinery", "reviewed": "2026-11-24"}[key]
    if isinstance(value, str):
        return value.replace("FILL_IN", "n.n")
    return value


def _manifest() -> dict[str, Any]:
    manifest = copy.deepcopy(_load(CELL / "simple-pick-and-place.manifest.yaml"))
    manifest.setdefault("outputs", {})["lines"] = [
        {"name": "guard_lock", "kind": "digital", "safe_state": True},
        {"name": "cycle_done", "kind": "digital", "safe_state": False},
    ]
    return manifest


def _deployment(**declarations: Any) -> dict[str, Any]:
    return {
        "rulebook_version": "0.1",
        "rulebook_id": "cell_4_machinery_declarations",
        "title": "Cell 4 machinery safety declarations",
        "issuer": {"kind": "deployment", "name": "Example Integrator"},
        "source_status": "deployment_declaration",
        "declarations": declarations,
    }


def _run(*books: dict[str, Any], steps: list[dict[str, Any]] | None = None) -> ValidationResult:
    program = {
        "profile": "industrial",
        "behavior": {"type": "sequence", "steps": steps or [{"set_output": {"output": "cycle_done", "value": True}}]},
    }
    return validate(program, _manifest(), None, profiles=("industrial",), policy=None, rulebooks=list(books))


def _issues(result: ValidationResult) -> list[tuple[str, str]]:
    return [(i.code_str, i.severity) for i in result.all_issues if i.code_str.startswith("rule.")]


def test_the_template_as_shipped_refuses_to_load() -> None:
    with pytest.raises(PydanticValidationError):
        Rulebook.model_validate(_load(TEMPLATE))


def test_the_filled_template_loads() -> None:
    book = Rulebook.model_validate(_fill(_load(TEMPLATE)))
    assert [r.id for r in book.rules] == [
        "risk_assessment_on_record",
        "emergency_stop_category_declared",
        "safeguard_distances_on_record",
        "interlocking_on_record",
        "protective_device_type_declared",
        "electrical_verification_on_record",
        "safeguard_outputs_untouched",
    ]
    assert [o.id for o in book.obligations][:2] == [
        "emergency_stop_independent_of_urml",
        "urml_stops_on_emergency_stop",
    ]


def test_with_everything_declared_the_program_runs() -> None:
    result = _run(_fill(_load(TEMPLATE)), _deployment(**DECLARED))
    assert _issues(result) == []
    assert result.accepted


@pytest.mark.parametrize(
    ("key", "value"),
    [("emergency_stop_category", "category_2"), ("protective_device_type", "type_2")],
    ids=["stop-category-2", "device-type-2"],
)
def test_a_value_outside_the_allowed_list_refuses_the_program(key: str, value: str) -> None:
    result = _run(_fill(_load(TEMPLATE)), _deployment(**{**DECLARED, key: value}))
    assert _issues(result) == [("rule.declaration_missing", "error")]
    assert not result.accepted


@pytest.mark.parametrize(
    "key",
    ["risk_assessment_record", "safeguard_distance_record", "interlocking_record", "electrical_verification_record"],
)
def test_a_missing_record_refuses_the_program(key: str) -> None:
    declared = {k: v for k, v in DECLARED.items() if k != key}
    result = _run(_fill(_load(TEMPLATE)), _deployment(**declared))
    assert _issues(result) == [("rule.declaration_missing", "error")]


def test_a_program_that_writes_a_safeguard_output_is_refused() -> None:
    steps = [{"set_output": {"output": "guard_lock", "value": False}}]
    result = _run(_fill(_load(TEMPLATE)), _deployment(**DECLARED), steps=steps)
    assert _issues(result) == [("rule.primitive_forbidden", "error")]


def test_with_no_deployment_rulebook_each_missing_declaration_is_a_warning() -> None:
    result = _run(_fill(_load(TEMPLATE)))
    assert _issues(result) == [("rule.declaration_missing", "warning")] * 6
    assert result.accepted
