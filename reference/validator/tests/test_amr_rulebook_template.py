"""The AMR rulebook template (ISO 3691-4:2023, ANSI/A3 R15.08).

Two guarantees. The template as shipped carries no values and refuses to load,
so it cannot run by accident. Filled in with an integrator's values, it loads,
and each of its rules refuses the programs it is meant to refuse, against the
repository's own warehouse example manifest.

The values used to fill it here are test values, not limits from either
standard.
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
TEMPLATE = REPO_ROOT / "examples" / "rulebooks" / "amr-template.yaml"
WAREHOUSE = REPO_ROOT / "examples" / "warehouse"

#: What an integrator might write in place of each FILL_IN. Test values only.
FILLED_LISTS = {
    "zones": ["pedestrian_area"],
    "in_zones": ["travel_lane"],
    "except_names": ["wrap_pallet"],
    "names": ["door_interlock"],
    "allowed": ["UL 3100"],
}
#: The operator's deployment rulebook: the robot's UL 3100 listing on record.
LISTED = {"listing_standard": "UL 3100", "nrtl_listing": "Example NRTL, file E000000"}
SPEED_LIMIT = 1.0


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _fill(value: Any, key: str = "") -> Any:
    """Replace every FILL_IN the way an integrator would."""
    if isinstance(value, dict):
        return {k: _fill(v, k) for k, v in value.items()}
    if isinstance(value, list):
        if value == ["FILL_IN"]:
            return list(FILLED_LISTS[key])
        return [_fill(v, key) for v in value]
    if value == "FILL_IN":
        return {"rulebook_id": "site_amr_rules", "reviewed": "2026-11-24", "max": SPEED_LIMIT}[key]
    if isinstance(value, str):
        return value.replace("FILL_IN", "4.2")
    return value


def _filled() -> dict[str, Any]:
    return _fill(_load(TEMPLATE))


def _manifest() -> dict[str, Any]:
    """The warehouse example robot, with the site's zones drawn in and two more places."""
    manifest = copy.deepcopy(_load(WAREHOUSE / "pick-to-conveyor.manifest.yaml"))
    frame = "site"
    manifest.setdefault("declared_locations", []).extend(
        [
            {"name": "break_room", "pose": {"x": 20.0, "y": 20.0, "z": 0.0}, "frame": frame},
            {"name": "lane_shelf", "pose": {"x": 10.0, "y": -10.0, "z": 0.5}, "frame": frame},
        ]
    )
    manifest["declared_areas"] = [
        {"name": "pedestrian_area", "frame": frame, "polygon": _square(18.0, 18.0)},
        {"name": "travel_lane", "frame": frame, "polygon": _square(8.0, -12.0)},
    ]
    return manifest


def _square(x: float, y: float, size: float = 4.0) -> list[dict[str, float]]:
    return [{"x": x, "y": y}, {"x": x + size, "y": y}, {"x": x + size, "y": y + size}, {"x": x, "y": y + size}]


def _deployment(**declarations: Any) -> dict[str, Any]:
    return {
        "rulebook_version": "0.1",
        "rulebook_id": "site_amr_declarations",
        "title": "Site AMR listing on record",
        "issuer": {"kind": "deployment", "name": "Example Site"},
        "source_status": "deployment_declaration",
        "declarations": declarations,
    }


def _run(*steps: dict[str, Any], listing: dict[str, Any] | None = LISTED) -> ValidationResult:
    program = {"profile": "warehouse", "behavior": {"type": "sequence", "steps": list(steps)}}
    books = [_filled()] if listing is None else [_filled(), _deployment(**listing)]
    return validate(program, _manifest(), None, profiles=("warehouse",), policy=None, rulebooks=books)


def _rule_codes(result: ValidationResult) -> list[str]:
    return [i.code_str for i in result.all_issues if i.code_str.startswith("rule.")]


def test_the_template_as_shipped_refuses_to_load() -> None:
    with pytest.raises(PydanticValidationError) as exc:
        Rulebook.model_validate(_load(TEMPLATE))
    message = str(exc.value)
    assert "rulebook_id" in message and "max" in message


def test_the_filled_template_loads() -> None:
    book = Rulebook.model_validate(_filled())
    assert {r.id for r in book.rules} == {
        "max_travel_speed",
        "outside_operating_zones",
        "load_handling_at_stations_only",
        "validated_programs_only",
        "safety_outputs_untouched",
        "listing_standard_declared",
        "listing_on_record",
    }
    assert len(book.obligations) == 7
    assert "urml_not_part_of_the_listing" in {o.id for o in book.obligations}


def test_a_program_inside_the_rules_is_accepted() -> None:
    result = _run(
        {"move_to": {"location": "shelf_a3", "speed": SPEED_LIMIT}},
        {"pick_from": {"source": "shelf_a3", "object": "tote", "force": "gentle", "store_as": "tote"}},
        {"place_at": {"target": "conveyor_a", "held": "$tote", "mode": "place"}},
    )
    assert _rule_codes(result) == [], result.all_issues
    assert result.accepted


def test_a_speed_above_the_cap_is_refused() -> None:
    result = _run({"move_to": {"location": "shelf_a3", "speed": SPEED_LIMIT + 0.5}})
    assert _rule_codes(result) == ["rule.cap_exceeded"]
    assert not result.accepted


def test_a_target_in_a_pedestrian_area_is_refused() -> None:
    result = _run({"move_to": {"location": "break_room"}})
    assert _rule_codes(result) == ["rule.zone_forbidden"]


def test_load_handling_in_a_travel_lane_is_refused() -> None:
    result = _run({"pick_from": {"source": "lane_shelf", "object": "tote", "force": "gentle"}})
    assert "rule.primitive_forbidden" in _rule_codes(result)
    assert not result.accepted


@pytest.mark.parametrize(
    "listing",
    [
        {"nrtl_listing": "Example NRTL, file E000000"},
        {**LISTED, "listing_standard": "UL 1740"},
        {"listing_standard": "UL 3100"},
    ],
    ids=["no-standard", "standard-not-accepted", "no-listing"],
)
def test_a_missing_or_unaccepted_listing_refuses_every_program(listing: dict[str, Any]) -> None:
    result = _run({"move_to": {"location": "shelf_a3", "speed": SPEED_LIMIT}}, listing=listing)
    assert _rule_codes(result) == ["rule.declaration_missing"]
    assert not result.accepted


def test_with_no_deployment_rulebook_the_missing_listing_is_a_warning() -> None:
    result = _run({"move_to": {"location": "shelf_a3", "speed": SPEED_LIMIT}}, listing=None)
    assert _rule_codes(result) == ["rule.declaration_missing"] * 2
    assert result.accepted
