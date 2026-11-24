"""The service-robot rulebook template (ANSI/CAN/UL 3300).

As shipped it refuses to load; filled in, it keeps programs within the site's
limits for public spaces and refuses them until the robot's NRTL listing is on
record. The limits and names here are test values, not values from UL 3300.
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
TEMPLATE = REPO_ROOT / "examples" / "rulebooks" / "service-robot-template.yaml"
HOME = REPO_ROOT / "examples" / "home"

FILLED_LISTS = {
    "allowed": ["UL 3300"],
    "zones": ["stair_landing"],
    "except_names": ["tidy_up"],
}
SPEED_LIMIT = 0.2
FORCE_LIMIT = 5.0
LISTED = {"listing_standard": "UL 3300", "nrtl_listing": "Example NRTL, file E000000"}


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _fill(value: Any, key: str = "", parent: str = "") -> Any:
    if isinstance(value, dict):
        quantity = value.get("quantity", parent)
        return {k: _fill(v, k, quantity) for k, v in value.items()}
    if isinstance(value, list):
        if value == ["FILL_IN"]:
            return list(FILLED_LISTS[key])
        return [_fill(v, key, parent) for v in value]
    if value == "FILL_IN":
        if key == "max":
            return {"speed_m_per_s": SPEED_LIMIT, "grip_force_n": FORCE_LIMIT}[parent]
        return {"rulebook_id": "lobby_robot_rules", "reviewed": "2026-11-24"}[key]
    if isinstance(value, str):
        return value.replace("FILL_IN", "n.n")
    return value


def _manifest() -> dict[str, Any]:
    """The home example robot, standing in for a lobby robot, with the stair landing drawn in."""
    manifest = copy.deepcopy(_load(HOME / "patient-fetch.manifest.yaml"))
    manifest["declared_locations"].append({"name": "stairs_top", "pose": {"x": 10.0, "y": 10.0}, "frame": "map"})
    manifest["declared_areas"] = [
        {
            "name": "stair_landing",
            "frame": "map",
            "polygon": [{"x": 9.0, "y": 9.0}, {"x": 11.0, "y": 9.0}, {"x": 11.0, "y": 11.0}, {"x": 9.0, "y": 11.0}],
        }
    ]
    return manifest


def _deployment(**declarations: Any) -> dict[str, Any]:
    return {
        "rulebook_version": "0.1",
        "rulebook_id": "lobby_robot_declarations",
        "title": "Lobby robot listing on record",
        "issuer": {"kind": "deployment", "name": "Example Hotel Operations"},
        "source_status": "deployment_declaration",
        "declarations": declarations,
    }


def _run(*steps: dict[str, Any], books: list[dict[str, Any]] | None = None) -> ValidationResult:
    program = {
        "profile": "home",
        "behavior": {"type": "sequence", "on_error": "abort_and_report", "steps": list(steps)},
    }
    rulebooks = books if books is not None else [_fill(_load(TEMPLATE)), _deployment(**LISTED)]
    return validate(program, _manifest(), None, profiles=("home",), policy=None, rulebooks=rulebooks)


def _codes(result: ValidationResult) -> list[tuple[str, str]]:
    return [(i.code_str, i.severity) for i in result.all_issues if i.code_str.startswith("rule.")]


def _go(place: str, speed: float = SPEED_LIMIT) -> dict[str, Any]:
    return {"move_to": {"location": place, "speed": speed}}


def test_the_template_as_shipped_refuses_to_load() -> None:
    with pytest.raises(PydanticValidationError):
        Rulebook.model_validate(_load(TEMPLATE))


def test_the_filled_template_loads() -> None:
    book = Rulebook.model_validate(_fill(_load(TEMPLATE)))
    assert [r.id for r in book.rules] == [
        "listing_standard_declared",
        "listing_on_record",
        "max_travel_speed",
        "max_grip_force",
        "hazard_zones",
        "covered_programs_only",
    ]
    assert book.obligations[0].id == "urml_not_part_of_the_listing"


def test_a_listed_robot_within_the_limits_runs() -> None:
    result = _run(_go("kitchen"))
    assert _codes(result) == []
    assert result.accepted


def test_a_speed_above_the_cap_is_refused() -> None:
    assert _codes(_run(_go("kitchen", speed=SPEED_LIMIT + 0.1))) == [("rule.cap_exceeded", "error")]


def test_a_hazard_zone_is_refused() -> None:
    assert _codes(_run(_go("stairs_top"))) == [("rule.zone_forbidden", "error")]


def test_an_uncovered_program_is_refused() -> None:
    result = _run({"call_program": {"name": "unlisted_routine"}})
    assert ("rule.primitive_forbidden", "error") in _codes(result)


@pytest.mark.parametrize(
    "declared",
    [
        {"nrtl_listing": "Example NRTL, file E000000"},
        {**LISTED, "listing_standard": "UL 1740"},
        {"listing_standard": "UL 3300"},
    ],
    ids=["no-standard", "standard-not-accepted", "no-listing"],
)
def test_a_missing_or_unaccepted_listing_refuses_every_program(declared: dict[str, Any]) -> None:
    result = _run(_go("kitchen"), books=[_fill(_load(TEMPLATE)), _deployment(**declared)])
    assert _codes(result) == [("rule.declaration_missing", "error")]
    assert not result.accepted


def test_with_no_deployment_rulebook_the_missing_listing_is_a_warning() -> None:
    result = _run(_go("kitchen"), books=[_fill(_load(TEMPLATE))])
    assert _codes(result) == [("rule.declaration_missing", "warning")] * 2
    assert result.accepted
