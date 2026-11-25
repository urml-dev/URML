"""The functional-safety rulebook template (ISO 13849, IEC 62061:2021, IEC 61508:2010, IEC 61800-5-2:2016).

The template refuses programs until the operator has declared, in a
deployment rulebook, the performance level (ISO 13849) or safety integrity
level (IEC 62061 or IEC 61508) each safety function reached, and the stop
function the drives perform (IEC 61800-5-2). It keeps programs below the
drives' safely limited speed and away from the drives' safety inputs.
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
    "emergency_stop_safety_level": "PLd",
    "protective_stop_safety_level": "SIL2",
    "speed_monitoring_safety_level": "PLe",
    "safety_validation_record": "VAL-2026-017",
    "drive_stop_function": "SS1",
}
#: Test values: levels meeting a PLr of d, or a required SIL 2 (SIL4 exists under IEC 61508 only).
ALLOWED = ["PLd", "PLe", "SIL2", "SIL3", "SIL4"]
#: Test values for the IEC 61800-5-2 rules.
DRIVE_STOPS = ["STO", "SS1"]
SLS_CAP = 1.0  # m/s
STO_LINE = "sto_request"


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _fill(value: Any, key: str = "", declared: str = "") -> Any:
    if isinstance(value, dict):
        inner = value.get("key", declared)
        return {k: _fill(v, k, inner) for k, v in value.items()}
    if isinstance(value, list):
        if value == ["FILL_IN"]:
            if key == "names":
                return [STO_LINE]
            return list(DRIVE_STOPS if declared == "drive_stop_function" else ALLOWED)
        return [_fill(v, key, declared) for v in value]
    if value == "FILL_IN":
        return {"rulebook_id": "cell_7_safety", "reviewed": "2026-11-24", "max": SLS_CAP}[key]
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


def _run(*books: dict[str, Any], steps: list[dict[str, Any]] | None = None) -> ValidationResult:
    program = {
        "profile": "warehouse",
        "behavior": {"type": "sequence", "steps": steps or [{"move_to": {"location": "shelf_a3"}}]},
    }
    manifest = copy.deepcopy(_load(WAREHOUSE / "pick-to-conveyor.manifest.yaml"))
    manifest.setdefault("outputs", {})["lines"] = [
        {"name": STO_LINE, "kind": "digital", "safe_state": False},
        {"name": "beacon", "kind": "digital", "safe_state": False},
    ]
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
        "drive_stop_function_declared",
        "below_safely_limited_speed",
        "drive_safety_inputs_untouched",
    ]
    obligations = [o.id for o in book.obligations]
    assert "urml_is_not_a_safety_function" in obligations
    assert "urml_cannot_interfere" in obligations
    assert "drive_safety_functions_validated" in obligations


def test_with_every_function_declared_the_program_runs() -> None:
    result = _run(_fill(_load(TEMPLATE)), _deployment(**DECLARED))
    assert _issues(result) == []
    assert result.accepted


def test_an_iec_61508_sil4_declaration_meets_a_sil2_requirement() -> None:
    result = _run(_fill(_load(TEMPLATE)), _deployment(**{**DECLARED, "speed_monitoring_safety_level": "SIL4"}))
    assert _issues(result) == []
    assert result.accepted


@pytest.mark.parametrize(
    ("key", "level"),
    [
        ("emergency_stop_safety_level", "PLc"),
        ("protective_stop_safety_level", "SIL1"),
        ("speed_monitoring_safety_level", "SIL 2"),
    ],
    ids=["pl_too_low", "sil_too_low", "sil_misspelt"],
)
def test_a_level_outside_the_allowed_list_refuses_the_program(key: str, level: str) -> None:
    result = _run(_fill(_load(TEMPLATE)), _deployment(**{**DECLARED, key: level}))
    assert _issues(result) == [("rule.declaration_missing", "error")]
    assert not result.accepted


def test_a_missing_validation_record_refuses_the_program() -> None:
    declared = {k: v for k, v in DECLARED.items() if k != "safety_validation_record"}
    result = _run(_fill(_load(TEMPLATE)), _deployment(**declared))
    assert _issues(result) == [("rule.declaration_missing", "error")]


def test_with_no_deployment_rulebook_each_missing_declaration_is_a_warning() -> None:
    result = _run(_fill(_load(TEMPLATE)))
    assert _issues(result) == [("rule.declaration_missing", "warning")] * 5
    assert result.accepted



def test_an_unaccepted_drive_stop_function_refuses_the_program() -> None:
    result = _run(_fill(_load(TEMPLATE)), _deployment(**{**DECLARED, "drive_stop_function": "SS2"}))
    assert _issues(result) == [("rule.declaration_missing", "error")]
    assert not result.accepted


def test_a_speed_above_the_drives_safely_limited_speed_is_refused() -> None:
    books = (_fill(_load(TEMPLATE)), _deployment(**DECLARED))
    assert _run(*books, steps=[{"move_to": {"location": "shelf_a3", "speed": SLS_CAP}}]).accepted
    result = _run(*books, steps=[{"move_to": {"location": "shelf_a3", "speed": SLS_CAP + 0.2}}])
    assert _issues(result) == [("rule.cap_exceeded", "error")]
    assert not result.accepted


def test_a_drive_safety_input_is_never_written() -> None:
    books = (_fill(_load(TEMPLATE)), _deployment(**DECLARED))
    assert _run(*books, steps=[{"set_output": {"output": "beacon", "value": True}}]).accepted
    result = _run(*books, steps=[{"set_output": {"output": STO_LINE, "value": True}}])
    assert _issues(result) == [("rule.primitive_forbidden", "error")]
    assert not result.accepted
