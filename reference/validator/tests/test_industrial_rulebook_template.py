"""The industrial rulebook template (ISO 10218-1/-2:2025, ANSI/A3 R15.06-2025, ISO/TS 15066:2016, UL 1740).

Two guarantees, as for the other templates. As shipped it carries no values
and refuses to load. Filled in, it loads, and each of its rules refuses the
programs it is meant to refuse, against the repository's own
simple pick-and-place cell. The example program itself stays accepted.

The values used to fill it here are test values, not limits from the
standards.
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
TEMPLATE = REPO_ROOT / "examples" / "rulebooks" / "industrial-template.yaml"
CELL = REPO_ROOT / "examples" / "industrial"

SPEED_LIMIT = 0.25  # m/s, test value
FORCE_LIMIT = 10.0  # N, test value; "firm" resolves to 8 N
FILLED_LISTS = {
    "except_names": ["pick_place_cycle"],
    "names": ["door_mute"],
    "zones": ["operator_zone"],
    "allowed": ["UL 1740"],
}
#: The operator's deployment rulebook: the robot's UL 1740 listing on record.
LISTED = {"listing_standard": "UL 1740", "nrtl_listing": "Example NRTL, file E000000"}


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _fill(value: Any, key: str = "", quantity: str = "") -> Any:
    if isinstance(value, dict):
        q = value.get("quantity", quantity)
        return {k: _fill(v, k, q) for k, v in value.items()}
    if isinstance(value, list):
        if value == ["FILL_IN"]:
            return list(FILLED_LISTS[key])
        return [_fill(v, key, quantity) for v in value]
    if value == "FILL_IN":
        if key == "max":
            return {"speed_m_per_s": SPEED_LIMIT, "grip_force_n": FORCE_LIMIT}[quantity]
        return {"rulebook_id": "cell_a1_rules", "reviewed": "2026-11-24"}[key]
    if isinstance(value, str):
        return value.replace("FILL_IN", "5.2")
    return value


def _manifest() -> dict[str, Any]:
    """The simple pick-and-place cell, with controller programs, output lines and an operator zone."""
    manifest = copy.deepcopy(_load(CELL / "simple-pick-and-place.manifest.yaml"))
    manifest["programs"] = [
        {"name": "pick_place_cycle", "description": "Commissioned cycle covered by the risk assessment."},
        {"name": "teach_mode_jog", "description": "Not covered by the risk assessment."},
    ]
    manifest.setdefault("outputs", {})["lines"] = [
        {"name": "door_mute", "kind": "digital", "safe_state": False},
        {"name": "cycle_done", "kind": "digital", "safe_state": False},
    ]
    manifest["declared_locations"].append(
        {"name": "operator_station", "pose": {"x": 2.0, "y": 2.0, "z": 0.3}, "frame": "cell"}
    )
    manifest["declared_areas"] = [
        {
            "name": "operator_zone",
            "frame": "cell",
            "polygon": [{"x": 1.5, "y": 1.5}, {"x": 2.5, "y": 1.5}, {"x": 2.5, "y": 2.5}, {"x": 1.5, "y": 2.5}],
        }
    ]
    return manifest


def _deployment(**declarations: Any) -> dict[str, Any]:
    return {
        "rulebook_version": "0.1",
        "rulebook_id": "cell_a1_declarations",
        "title": "Cell A1 listing on record",
        "issuer": {"kind": "deployment", "name": "Example Plant"},
        "source_status": "deployment_declaration",
        "declarations": declarations,
    }


def _run(program: dict[str, Any], listing: dict[str, Any] | None = LISTED) -> ValidationResult:
    books = [_fill(_load(TEMPLATE))]
    if listing is not None:
        books.append(_deployment(**listing))
    return validate(program, _manifest(), None, profiles=("industrial",), policy=None, rulebooks=books)


def _program(*steps: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile": "industrial",
        "behavior": {"type": "sequence", "on_error": "abort_and_report", "steps": list(steps)},
    }


def _rule_codes(result: ValidationResult) -> list[str]:
    return [i.code_str for i in result.all_issues if i.code_str.startswith("rule.")]


def test_the_template_as_shipped_refuses_to_load() -> None:
    with pytest.raises(PydanticValidationError) as exc:
        Rulebook.model_validate(_load(TEMPLATE))
    assert "rulebook_id" in str(exc.value) and "max" in str(exc.value)


def test_the_filled_template_loads() -> None:
    book = Rulebook.model_validate(_fill(_load(TEMPLATE)))
    assert [r.id for r in book.rules] == [
        "collaborative_speed",
        "gripper_contact_force",
        "validated_programs_only",
        "safety_outputs_untouched",
        "outside_cell_layout",
        "listing_standard_declared",
        "listing_on_record",
    ]
    assert len(book.obligations) == 8
    assert {"cell_used_as_validated", "people_trained_for_the_cell"} <= {o.id for o in book.obligations}
    assert "urml_not_part_of_the_listing" in {o.id for o in book.obligations}


def test_the_example_program_is_accepted() -> None:
    result = _run(_load(CELL / "simple-pick-and-place.urml.yaml"))
    assert _rule_codes(result) == [], result.all_issues
    assert result.accepted


@pytest.mark.parametrize(
    ("steps", "code"),
    [
        ([{"move_to": {"location": "pick_bin", "speed": SPEED_LIMIT + 0.1}}], "rule.cap_exceeded"),
        (
            [
                {"move_to": {"location": "pick_bin"}},
                {"detect": {"object": "widget_red", "store_as": "w"}},
                {"grasp": {"target": "$w", "force": FORCE_LIMIT + 2.0}},
            ],
            "rule.cap_exceeded",
        ),
        ([{"call_program": {"name": "teach_mode_jog"}}], "rule.primitive_forbidden"),
        ([{"set_output": {"output": "door_mute", "value": True}}], "rule.primitive_forbidden"),
        ([{"move_to": {"location": "operator_station"}}], "rule.zone_forbidden"),
    ],
    ids=["speed", "gripper_force", "unlisted_program", "safety_output", "operator_zone"],
)
def test_each_rule_refuses_its_program(steps: list[dict[str, Any]], code: str) -> None:
    result = _run(_program(*steps))
    assert _rule_codes(result) == [code], result.all_issues
    assert not result.accepted


def test_the_listed_program_and_other_outputs_are_allowed() -> None:
    result = _run(
        _program(
            {"call_program": {"name": "pick_place_cycle"}},
            {"set_output": {"output": "cycle_done", "value": True}},
        )
    )
    assert _rule_codes(result) == [], result.all_issues
    assert result.accepted


@pytest.mark.parametrize(
    "listing",
    [
        {"nrtl_listing": "Example NRTL, file E000000"},
        {**LISTED, "listing_standard": "UL 3100"},
        {"listing_standard": "UL 1740"},
    ],
    ids=["no-standard", "standard-not-accepted", "no-listing"],
)
def test_a_missing_or_unaccepted_listing_refuses_every_program(listing: dict[str, Any]) -> None:
    result = _run(_program({"move_to": {"location": "pick_bin"}}), listing=listing)
    assert _rule_codes(result) == ["rule.declaration_missing"], result.all_issues
    assert not result.accepted


def test_with_no_deployment_rulebook_the_missing_listing_is_a_warning() -> None:
    result = _run(_program({"move_to": {"location": "pick_bin"}}), listing=None)
    assert _rule_codes(result) == ["rule.declaration_missing"] * 2
    assert result.accepted
