"""The home rulebook template (ISO 13482:2014, mobile servant robots).

Two guarantees. The template as shipped carries no values and refuses to load,
so it cannot run by accident. Filled in, it loads, and each of its rules
refuses the programs it is meant to refuse, against the repository's own home
example manifest.

The values used to fill it here are test values, not limits from the standard.
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
TEMPLATE = REPO_ROOT / "examples" / "rulebooks" / "home-template.yaml"
HOME = REPO_ROOT / "examples" / "home"

#: What a maker or care provider might write in place of each FILL_IN. Test values only.
FILLED_LISTS = {
    "zones": ["stairwell"],
    "in_zones": ["cooktop_area"],
    "except_names": ["tidy_up"],
}
SPEED_LIMIT = 0.3
FORCE_LIMIT = 2.0


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _fill(value: Any, key: str = "", parent: str = "") -> Any:
    """Replace every FILL_IN the way an adopter would."""
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
        return {"rulebook_id": "home_helper_rules", "reviewed": "2026-11-24"}[key]
    if isinstance(value, str):
        return value.replace("FILL_IN", "5.1")
    return value


def _filled() -> dict[str, Any]:
    return _fill(_load(TEMPLATE))


def _manifest() -> dict[str, Any]:
    """The patient-fetch home robot, with the home's hazard zones drawn in."""
    manifest = copy.deepcopy(_load(HOME / "patient-fetch.manifest.yaml"))
    manifest["declared_locations"].extend(
        [
            {"name": "stairs_top", "pose": {"x": 10.0, "y": 10.0}, "frame": "map"},
            {"name": "cooktop", "pose": {"x": 5.0, "y": -5.0}, "frame": "map"},
        ]
    )
    manifest["declared_areas"] = [
        {"name": "stairwell", "frame": "map", "polygon": _square(9.0, 9.0)},
        {"name": "cooktop_area", "frame": "map", "polygon": _square(4.0, -6.0)},
    ]
    return manifest


def _square(x: float, y: float, size: float = 2.0) -> list[dict[str, float]]:
    return [{"x": x, "y": y}, {"x": x + size, "y": y}, {"x": x + size, "y": y + size}, {"x": x, "y": y + size}]


def _run(*steps: dict[str, Any]) -> ValidationResult:
    behavior = {"type": "sequence", "on_error": "abort_and_report", "steps": list(steps)}
    program = {"profile": "home", "behavior": behavior}
    return validate(program, _manifest(), None, profiles=("home",), policy=None, rulebooks=[_filled()])


def _rule_codes(result: ValidationResult) -> list[str]:
    return [i.code_str for i in result.all_issues if i.code_str.startswith("rule.")]


def _fetch_at(place: str, force: Any = "gentle", speed: float = SPEED_LIMIT) -> list[dict[str, Any]]:
    return [
        {"move_to": {"location": place, "speed": speed}},
        {"detect": {"object": "mug", "store_as": "mug"}},
        {"grasp": {"target": "$mug", "force": force}},
        {"move_to": {"location": "user", "carrying": "$mug"}},
        {"release": {"mode": "hand_to_user"}},
    ]


def test_the_template_as_shipped_refuses_to_load() -> None:
    with pytest.raises(PydanticValidationError) as exc:
        Rulebook.model_validate(_load(TEMPLATE))
    message = str(exc.value)
    assert "rulebook_id" in message and "max" in message


def test_the_filled_template_loads() -> None:
    book = Rulebook.model_validate(_filled())
    assert {r.id for r in book.rules} == {
        "max_travel_speed",
        "max_grip_force",
        "hazard_zones",
        "no_handling_in_zones",
        "validated_programs_only",
    }
    assert len(book.obligations) == 4


def test_a_fetch_inside_the_rules_is_accepted() -> None:
    result = _run(*_fetch_at("kitchen"))
    assert _rule_codes(result) == [], result.all_issues
    assert result.accepted


def test_a_speed_above_the_cap_is_refused() -> None:
    assert _rule_codes(_run(*_fetch_at("kitchen", speed=SPEED_LIMIT + 0.1))) == ["rule.cap_exceeded"]


def test_a_grip_force_above_the_cap_is_refused() -> None:
    assert _rule_codes(_run(*_fetch_at("kitchen", force=FORCE_LIMIT + 2.0))) == ["rule.cap_exceeded"]


def test_a_target_in_a_hazard_zone_is_refused() -> None:
    assert _rule_codes(_run({"move_to": {"location": "stairs_top"}})) == ["rule.zone_forbidden"]


def test_grasping_in_an_excluded_zone_is_refused() -> None:
    result = _run(*_fetch_at("cooktop"))
    assert _rule_codes(result) == ["rule.primitive_forbidden"]
    assert not result.accepted
