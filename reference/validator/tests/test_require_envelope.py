"""The `require_envelope` rule kind (RFC-0714).

A rulebook rule that requires the site's safety envelope to set a limit. The
validator checks a program against the limits an envelope sets; a limit nobody
set is not checked. This rule turns that silence into a refusal,
`rule.limit_missing`, for a deployment that loads the rulebook.

The conformance fixtures rulebook/14 and rulebook/15 pin the same behavior end
to end, through the runtime, with the shipped example rulebook.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError as PydanticValidationError

from urml_validator import ValidationResult, validate, validate_fleet
from urml_validator.evidence_report import build_evidence_report
from urml_validator.rulebook_engine import rulebook_inventory
from urml_validator.schemas.envelope import SafetyEnvelope
from urml_validator.schemas.manifest import CapabilityManifest
from urml_validator.schemas.rulebook import RULE_KINDS, Rulebook

REPO_ROOT = Path(__file__).resolve().parents[3]
SITE_STANDARD = REPO_ROOT / "examples" / "rulebooks" / "example-site-standard.yaml"

_FIELDS = (
    "geofences",
    "people_occupancy_zones",
    "max_velocity",
    "max_altitude",
    "max_payload",
    "max_grip_force_n",
    "max_drop_height",
)
_SQUARE = [[0.0, 0.0], [5.0, 0.0], [5.0, 5.0], [0.0, 5.0]]
_FENCE = {"geofences": [{"name": "site", "frame": "map", "vertices": _SQUARE}]}
#: An envelope that sets every field the rule kind can name.
_FULL = {
    **_FENCE,
    "people_occupancy_zones": [{"name": "desk", "frame": "map", "vertices": [[4.0, 4.0], [5.0, 4.0], [5.0, 5.0]]}],
    "max_velocity": 0.5,
    "max_altitude": 2.0,
    "max_payload": 1.0,
    "max_grip_force_n": 10.0,
    "max_drop_height": 0.2,
}


def _manifest(robot_id: str = "rover") -> dict[str, Any]:
    return {
        "robot_id": robot_id,
        "frames": [{"name": "map"}],
        "declared_locations": [{"name": "dock", "pose": {"x": 1.0, "y": 1.0}, "frame": "map"}],
        "mobility": {"drive_type": "differential", "max_velocity": 1.0},
    }


_PROGRAM = {"profile": "home", "behavior": {"move_to": {"location": "dock"}}}


def _book(*fields: str, exceptable: bool = False, standard: str | None = None) -> dict[str, Any]:
    cite: dict[str, Any] = {"text": "Acme site standard, section 2"}
    if standard is not None:
        cite["standard"] = standard
    return {
        "rulebook_version": "0.1",
        "rulebook_id": "acme_site_standard",
        "title": "Acme site standard",
        "issuer": {"kind": "organization", "name": "Acme"},
        "source_status": "organization_policy",
        "rules": [
            {
                "id": "limits_declared",
                "title": "Every site declares its limits",
                "cite": cite,
                "exceptable": exceptable,
                "require_envelope": {"fields": list(fields)},
            }
        ],
    }


def _exception() -> dict[str, Any]:
    return {
        "rulebook_version": "0.1",
        "rulebook_id": "acme_plant_3",
        "title": "Acme plant 3",
        "issuer": {"kind": "deployment", "name": "Acme"},
        "source_status": "deployment_declaration",
        "exceptions": [{"rule": "acme_site_standard/limits_declared", "basis": "Commissioning plan CP-7"}],
    }


def _run(envelope: dict[str, Any] | None, *books: dict[str, Any]) -> ValidationResult:
    return validate(_PROGRAM, _manifest(), envelope, policy=None, rulebooks=list(books), default_rulebooks=False)


def _limit_issues(result: ValidationResult) -> list[Any]:
    return [i for i in result.all_issues if i.code_str == "rule.limit_missing"]


# ---------------------------------------------------------------------------
# The format
# ---------------------------------------------------------------------------


def test_it_is_one_of_the_rule_kinds_and_names_envelope_fields_only() -> None:
    assert "require_envelope" in RULE_KINDS
    Rulebook.model_validate(_book(*_FIELDS))
    # Every name is a field of the envelope schema, so the rule cannot name
    # something the envelope cannot carry.
    assert set(_FIELDS) <= set(SafetyEnvelope.model_fields)


@pytest.mark.parametrize(
    ("body", "problem"),
    [
        ({"fields": []}, "at least 1 item"),
        ({}, "Field required"),
        ({"fields": ["geofences", "geofences"]}, "each envelope field once"),
        ({"fields": ["weather"]}, "Input should be"),
        ({"fields": ["link_loss_policy"]}, "Input should be"),
        ({"fields": ["geofences"], "min": 1}, "Extra inputs are not permitted"),
    ],
)
def test_a_malformed_body_is_rejected(body: dict[str, Any], problem: str) -> None:
    data = _book("geofences")
    data["rules"][0]["require_envelope"] = body
    with pytest.raises(PydanticValidationError) as exc:
        Rulebook.model_validate(data)
    assert problem in str(exc.value)


# ---------------------------------------------------------------------------
# Judging
# ---------------------------------------------------------------------------


def test_without_the_rule_an_unset_limit_passes_in_silence() -> None:
    # The gap the rule closes: no geofence, nothing to judge `dock` against.
    assert _run(None).accepted
    assert _run({}).accepted


def test_no_envelope_refuses_the_program_and_names_every_missing_limit() -> None:
    result = _run(None, _book("geofences", "max_velocity"))
    assert not result.accepted
    (issue,) = _limit_issues(result)
    assert issue.severity == "error"
    assert "No safety envelope was given" in issue.message
    assert "geofences, max_velocity" in issue.message
    assert issue.detail["missing_fields"] == ["geofences", "max_velocity"]
    assert issue.detail["rule_kind"] == "require_envelope"
    assert issue.detail["rule_id"] == "limits_declared"
    assert issue.detail["remediation_hint"] == "fix_deployment"
    assert issue.suggestion is not None and "safety envelope" in issue.suggestion


def test_an_envelope_that_leaves_a_limit_unset_is_refused_for_that_limit_only() -> None:
    result = _run(_FENCE, _book("geofences", "max_velocity"))
    (issue,) = _limit_issues(result)
    assert issue.detail["missing_fields"] == ["max_velocity"]
    assert "The safety envelope sets no max_velocity" in issue.message


def test_an_empty_list_is_not_a_declared_limit() -> None:
    result = _run({"geofences": [], "people_occupancy_zones": []}, _book("geofences", "people_occupancy_zones"))
    (issue,) = _limit_issues(result)
    assert issue.detail["missing_fields"] == ["geofences", "people_occupancy_zones"]


def test_a_zero_limit_is_a_declared_limit() -> None:
    # `max_velocity: 0` is a limit the site set, and a strict one.
    program = {"profile": "home", "behavior": {"speak": {"text": "hello"}}}
    manifest = {**_manifest(), "outputs": {"named_endpoints": ["speech"]}}
    result = validate(
        program, manifest, {"max_velocity": 0.0}, policy=None, rulebooks=[_book("max_velocity")],
        default_rulebooks=False,
    )
    assert not _limit_issues(result), result.all_issues


@pytest.mark.parametrize("field", _FIELDS)
def test_each_field_is_missing_when_unset_and_satisfied_when_set(field: str) -> None:
    without = {k: v for k, v in _FULL.items() if k != field}
    (issue,) = _limit_issues(_run(without, _book(field)))
    assert issue.detail["missing_fields"] == [field]
    assert not _limit_issues(_run(_FULL, _book(field)))


def test_a_manifest_limit_does_not_satisfy_the_rule() -> None:
    # The manifest sets max_velocity 1.0. The rule asks what the site allows.
    result = _run(_FENCE, _book("max_velocity"))
    assert [i.detail["missing_fields"] for i in _limit_issues(result)] == [["max_velocity"]]


def test_the_rule_does_not_judge_the_value_and_the_envelope_pass_still_does() -> None:
    book = _book("geofences")
    assert _run(_FENCE, book).accepted
    # `dock` is at (1, 1). A fence that does not contain it satisfies the rule
    # and the envelope pass refuses the step.
    far = {"geofences": [{"name": "site", "frame": "map", "vertices": [[10.0, 10.0], [12.0, 10.0], [12.0, 12.0]]}]}
    result = _run(far, book)
    assert not _limit_issues(result)
    assert [e.code.value for e in result.errors] == ["envelope.geofence_violation"]


def test_it_is_an_error_with_or_without_a_deployment_rulebook() -> None:
    declarations_only = {
        "rulebook_version": "0.1",
        "rulebook_id": "acme_plant_3",
        "title": "Acme plant 3",
        "issuer": {"kind": "deployment", "name": "Acme"},
        "source_status": "deployment_declaration",
        "declarations": {"indoor": True},
    }
    for books in ([_book("geofences")], [_book("geofences"), declarations_only]):
        result = _run({}, *books)
        assert [i.severity for i in _limit_issues(result)] == ["error"]


def test_an_exception_turns_the_refusal_into_a_warning_only_when_the_rule_allows_one() -> None:
    result = _run({}, _book("geofences", exceptable=True), _exception())
    (issue,) = _limit_issues(result)
    assert issue.severity == "warning"
    assert "Commissioning plan CP-7" in issue.message
    assert result.accepted
    # Not exceptable: the deployment rulebook that claims an exception is invalid.
    result = _run({}, _book("geofences"), _exception())
    assert not result.accepted
    assert "rule.rulebook_invalid" in [i.code_str for i in result.all_issues]


def test_the_policy_argument_does_not_skip_it() -> None:
    for policy in (None, "DEFAULT"):
        result = validate(
            _PROGRAM, _manifest(), {}, policy=policy, rulebooks=[_book("geofences")], default_rulebooks=False
        )
        assert _limit_issues(result), policy


def test_a_fleet_is_judged_per_member_that_executes_steps() -> None:
    roster = {"members": [{"name": "alpha", "manifest": "a"}, {"name": "beta", "manifest": "b"}]}
    manifests = {"alpha": _manifest("alpha"), "beta": _manifest("beta")}
    program = {
        "profile": "home",
        "behavior": {
            "type": "sequence",
            "steps": [
                {"type": "on", "member": "alpha", "body": {"move_to": {"location": "dock"}}},
                {"type": "on", "member": "beta", "body": {"move_to": {"location": "dock"}}},
            ],
        },
    }
    result = validate_fleet(
        roster, manifests, program, {"alpha": _FENCE}, policy=None, rulebooks=[_book("geofences")],
        default_rulebooks=False,
    )
    (issue,) = _limit_issues(result)
    assert issue.detail["member"] == "beta"
    assert "of beta" in issue.message
    both = validate_fleet(
        roster, manifests, program, {"alpha": _FENCE, "beta": _FENCE}, policy=None,
        rulebooks=[_book("geofences")], default_rulebooks=False,
    )
    assert not _limit_issues(both)


# ---------------------------------------------------------------------------
# With no program: the inventory and the evidence report
# ---------------------------------------------------------------------------


def test_the_inventory_judges_it_without_a_program() -> None:
    manifest = CapabilityManifest.model_validate(_manifest())
    missing = rulebook_inventory(manifest, None, rulebooks=[_book("geofences")], default_rulebooks=False)
    assert [str(e.code) for e in missing.errors] == ["rule.limit_missing"]
    envelope = SafetyEnvelope.model_validate(_FENCE)
    satisfied = rulebook_inventory(manifest, envelope, rulebooks=[_book("geofences")], default_rulebooks=False)
    assert not satisfied.errors and not satisfied.warnings


def _report(envelope: dict[str, Any] | None, *books: dict[str, Any]) -> Any:
    return build_evidence_report(
        _manifest(), envelope, as_of=dt.date(2026, 11, 28), policy=None, rulebooks=list(books),
        default_rulebooks=False, profiles=("home",),
    )


def _rule_item(report: Any) -> Any:
    (item,) = [
        item
        for section in report.sections
        for item in section.items
        if item.id == "rule.acme_site_standard.limits_declared"
    ]
    return item


def test_the_evidence_report_marks_a_satisfied_rule_checked() -> None:
    report = _report(_FENCE, _book("geofences", standard="Acme Site Standard 2026"))
    item = _rule_item(report)
    assert item.status == "checked"
    assert "sets every limit the rule names" in item.text
    assert item.detail["kind"] == "require_envelope"
    assert item.detail["rule"] == {"fields": ["geofences"]}
    assert "missing_fields" not in item.detail
    (group,) = [g for g in report.by_standard if g.standard == "Acme Site Standard 2026"]
    assert group.items == {"checked": [item.id]}


def test_the_evidence_report_marks_an_unsatisfied_rule_missing() -> None:
    report = _report({}, _book("geofences", "max_velocity", standard="Acme Site Standard 2026"))
    item = _rule_item(report)
    assert item.status == "missing"
    assert "sets no geofences, max_velocity" in item.text
    assert "every program is refused" in item.text
    assert item.detail["missing_fields"] == ["geofences", "max_velocity"]
    (group,) = [g for g in report.by_standard if g.standard == "Acme Site Standard 2026"]
    assert group.items == {"missing": [item.id]}


def test_the_evidence_report_names_an_exception_that_covers_the_rule() -> None:
    report = _report({}, _book("geofences", exceptable=True), _exception())
    item = _rule_item(report)
    assert item.status == "checked"
    assert "An exception from acme_plant_3 applies" in item.text
    assert item.detail["exception"]["basis"] == "Commissioning plan CP-7"


# ---------------------------------------------------------------------------
# The shipped example
# ---------------------------------------------------------------------------


def test_the_shipped_site_standard_requires_a_work_area_and_a_speed_limit() -> None:
    book = yaml.safe_load(SITE_STANDARD.read_text(encoding="utf-8"))
    Rulebook.model_validate(book)
    assert [r["require_envelope"]["fields"] for r in book["rules"]] == [["geofences"], ["max_velocity"]]
    result = _run({"max_velocity": 0.5}, book)
    (issue,) = _limit_issues(result)
    assert issue.detail["rule_id"] == "site_declares_its_work_area"
    assert _run({**_FENCE, "max_velocity": 0.5}, book).accepted
