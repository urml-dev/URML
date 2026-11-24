"""The evidence report: one reproducible picture of a robot deployment (RFC-0707, Draft).

`build_evidence_report` reads the files that describe one deployment (the
capability manifest, the safety envelope, the compliance policy and the
rulebooks with their declarations) and says, item by item, what URML checks
before a program runs, what is only declared, what the runtime must enforce,
what is missing, and what URML cannot see. Every item carries one status from
a closed list:

    checked   the validator checks this before a program runs
    declared  someone states this; URML records who and does not verify it
    runtime   the runtime must enforce this while a program runs
    missing   something a rule, the policy or the envelope needs is absent
    outside   URML cannot see this; someone else must cover it

The report gives no score and no verdict, and never says "safe" or
"compliant". The same inputs, `as_of` date and validator version give the
same bytes (`render_json`), so a reader can rebuild a report and compare
digests instead of trusting its author.

This module implements step 1 of the RFC: the Inputs, Robot, Provenance,
Envelope, Rules, By standard, Outside URML and Counts parts. Programs,
conformance, redaction, signing and the human forms come in later steps.

Not to be confused with `urml_validator.evidence`, the validation-record log
(`--evidence-log`), or with the per-capability `evidence` tags of RFC-0631,
which this report prints.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from urml_validator._version import __version__
from urml_validator.errors import ValidationError
from urml_validator.evidence import content_digest
from urml_validator.policy_engine import evaluate_policy
from urml_validator.rulebook_engine import RulebookInventory, is_aircraft, rulebook_inventory
from urml_validator.schemas.envelope import SafetyEnvelope
from urml_validator.schemas.manifest import CapabilityManifest
from urml_validator.schemas.policy import Policy
from urml_validator.schemas.rulebook import Cite, Rule, Rulebook
from urml_validator.validator import _resolve_policy

#: The report format identifier, carried in every report.
REPORT_FORMAT: Literal["urml.evidence-report/0.1"] = "urml.evidence-report/0.1"

#: The first line of every report, in every form.
NOTICE = (
    "Evidence of declared intent and its checks. Not a safety assessment, "
    "a certification or a compliance determination."
)

Status = Literal["checked", "declared", "runtime", "missing", "outside"]
STATUSES: tuple[Status, ...] = ("checked", "declared", "runtime", "missing", "outside")
Result = Literal["pass", "fail"]

#: The section ids, in report order.
SECTION_IDS = ("robot", "provenance", "envelope", "rules", "outside")


class EvidenceInputError(ValueError):
    """An input could not be read as its artifact, so no report was built."""


# ---------------------------------------------------------------------------
# The report model (normative schema: spec/evidence/v0.1.0/report.schema.json)
# ---------------------------------------------------------------------------


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ItemSource(_Strict):
    """Where an item came from: an input role and a field path in it."""

    input: str = Field(..., description="manifest, envelope, policy, rulebook:<id>, or urml.")
    field: str | None = Field(None, description="Dotted path to the field, when there is one.")


class Item(_Strict):
    """One thing the report knows about the deployment, and how it knows it."""

    id: str = Field(..., description="Unique within the report.")
    status: Status
    text: str = Field(..., description="One plain sentence or two, for a human reader.")
    result: Result | None = Field(None, description="For a `checked` item judged without a program: pass or fail.")
    source: ItemSource
    detail: dict[str, Any] = Field(default_factory=dict)


class Section(_Strict):
    id: str
    title: str
    items: list[Item]


class InputRef(_Strict):
    """One input the report was built from, by content digest."""

    role: Literal["manifest", "envelope", "policy", "rulebook"]
    id: str | None = Field(None, description="robot_id, policy_id or rulebook_id.")
    name: str | None = Field(None, description="The file name as given, without its directory.")
    bundled: bool = False
    digest: str = Field(..., description="sha256 over canonical JSON, as in validation records.")


class Inputs(_Strict):
    files: list[InputRef]
    profiles: list[str]
    policy: Literal["bundled", "file", "off"]
    default_rulebooks: bool
    validator: dict[str, str]


class StandardGroup(_Strict):
    """The items one cited standard accounts for, by status."""

    standard: str
    keyed_by: Literal["standard", "text"] = Field(
        ..., description="`standard` when grouped on cite.standard, `text` on the cite text."
    )
    items: dict[str, list[str]] = Field(..., description="Status to item ids.")


class Counts(_Strict):
    by_status: dict[str, int]
    by_section: dict[str, dict[str, int]]
    failed_checks: int
    gaps: int = Field(..., description="Missing items plus failed checks. 0 means none.")


class EvidenceReport(_Strict):
    """An evidence report (RFC-0707)."""

    format: Literal["urml.evidence-report/0.1"] = REPORT_FORMAT
    notice: str = NOTICE
    as_of: str
    subject: dict[str, str | None]
    inputs: Inputs
    sections: list[Section]
    by_standard: list[StandardGroup]
    counts: Counts


# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------


class _Collector:
    """Gathers items for one section, refusing duplicate ids."""

    def __init__(self, seen: set[str]) -> None:
        self.items: list[Item] = []
        self._seen = seen

    def add(
        self,
        item_id: str,
        status: Status,
        text: str,
        source: str,
        field_path: str | None = None,
        *,
        result: Result | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        if item_id in self._seen:
            raise AssertionError(f"duplicate evidence item id {item_id}")
        self._seen.add(item_id)
        self.items.append(
            Item(
                id=item_id,
                status=status,
                text=text,
                result=result,
                source=ItemSource(input=source, field=field_path),
                detail=_plain(detail or {}),
            )
        )


def _plain(value: Any) -> Any:
    """JSON-ready, with tuples as lists and dict keys as strings."""
    return json.loads(json.dumps(value, default=str))


def _fmt(value: float) -> str:
    return f"{value:g}"


def _evidence_tag(model: Any) -> dict[str, Any] | None:
    ev = getattr(model, "evidence", None)
    return None if ev is None else ev.model_dump(mode="json", exclude_none=True)


def _evidence_phrase(tag: dict[str, Any] | None) -> str:
    if tag is None:
        return "No evidence tag: the claim's source is not recorded."
    ref = tag.get("ref")
    where = f" ({ref['kind']}: {ref['value']})" if ref else ""
    return f"Evidence: {tag['source']}{where}."


def _aerial(manifest: CapabilityManifest) -> bool:
    return is_aircraft(manifest)


# ----- Robot -----


def _robot_section(manifest: CapabilityManifest, seen: set[str]) -> Section:
    c = _Collector(seen)
    mob = manifest.mobility
    if mob is not None:
        tag = _evidence_tag(mob)
        c.add(
            "capability.mobility",
            "checked",
            f"Mobility ({mob.drive_type}), up to {_fmt(mob.max_velocity)} m/s. The validator refuses "
            f"steps faster than this or the envelope's limit. {_evidence_phrase(tag)}",
            "manifest",
            "mobility",
            detail={"drive_type": mob.drive_type, "max_velocity": mob.max_velocity, "evidence": tag},
        )
    manip = manifest.manipulation
    for gripper in manip.grippers if manip is not None else []:
        tag = _evidence_tag(gripper)
        c.add(
            f"capability.gripper.{gripper.name}",
            "checked",
            f"Gripper {gripper.name} ({gripper.kind}), {_fmt(gripper.force_min_n)} to "
            f"{_fmt(gripper.force_max_n)} N. The validator refuses grasps above the maximum or the "
            f"envelope's limit. {_evidence_phrase(tag)}",
            "manifest",
            f"manipulation.grippers.{gripper.name}",
            detail={
                "kind": gripper.kind,
                "force_min_n": gripper.force_min_n,
                "force_max_n": gripper.force_max_n,
                "evidence": tag,
            },
        )
    if manifest.whole_body is not None:
        tag = _evidence_tag(manifest.whole_body)
        c.add(
            "capability.whole_body",
            "checked",
            f"Whole-body declaration ({len(manifest.whole_body.chains)} kinematic chains). {_evidence_phrase(tag)}",
            "manifest",
            "whole_body",
            detail={"chains": len(manifest.whole_body.chains), "evidence": tag},
        )
    perception = manifest.perception
    for camera in perception.cameras if perception is not None else []:
        tag = _evidence_tag(camera)
        c.add(
            f"capability.camera.{camera.name}",
            "checked",
            f"Camera {camera.name}. Capture steps must name a declared camera. {_evidence_phrase(tag)}",
            "manifest",
            f"perception.cameras.{camera.name}",
            detail={"movable": camera.movable, "evidence": tag},
        )
    for sensor in perception.sensors if perception is not None else []:
        tag = _evidence_tag(sensor)
        c.add(
            f"capability.sensor.{sensor.name}",
            "checked",
            f"Sensor {sensor.name} ({sensor.measurement_type}). {_evidence_phrase(tag)}",
            "manifest",
            f"perception.sensors.{sensor.name}",
            detail={"measurement_type": sensor.measurement_type, "evidence": tag},
        )
    for program in manifest.programs:
        c.add(
            f"program.{program.name}",
            "declared",
            f"Opaque program {program.name}. The validator checks a call to it against its declared "
            "arguments; what the program does inside is the robot's own code, which URML does not see.",
            "manifest",
            f"programs.{program.name}",
            detail={"declared_intent": program.declared_intent is not None},
        )
    return Section(id="robot", title="Robot", items=c.items)


# ----- Provenance -----


def _issues_by_rule(issues: Sequence[ValidationError]) -> dict[str, list[ValidationError]]:
    out: dict[str, list[ValidationError]] = {}
    for issue in issues:
        rule_id = (issue.detail or {}).get("rule_id")
        if isinstance(rule_id, str):
            out.setdefault(rule_id, []).append(issue)
    return out


def _check_text(kind: str, rule_id: str, issues: list[ValidationError]) -> tuple[str, Result]:
    errors = [i for i in issues if i.severity == "error"]
    if not issues:
        return f"{kind} {rule_id}: passed.", "pass"
    worst = "error" if errors else "warning"
    messages = "; ".join(i.message for i in issues)
    plural = "finding" if len(issues) == 1 else "findings"
    return (
        f"{kind} {rule_id}: {len(issues)} {plural} ({worst}). {messages}",
        "fail" if errors else "pass",
    )


def _provenance_section(
    manifest: CapabilityManifest,
    policy: Policy | None,
    manifest_base_dir: Path | None,
    seen: set[str],
) -> Section:
    c = _Collector(seen)
    prov = manifest.provenance
    if prov is None:
        c.add(
            "provenance.absent",
            "missing" if policy is not None and policy.rules else "declared",
            "The manifest declares no provenance, so no component origin is on record and the "
            "policy's provenance rules have nothing to check.",
            "manifest",
            "provenance",
        )
    else:
        c.add(
            "provenance.attestation",
            "declared",
            f"Manifest attestation: {prov.manifest_attestation}.",
            "manifest",
            "provenance.manifest_attestation",
            detail={"manifest_attestation": prov.manifest_attestation, "attestation_uri": prov.attestation_uri},
        )
        for comp in prov.components:
            c.add(
                f"component.{comp.id}",
                "declared",
                f"Component {comp.id} ({comp.role}): vendor {comp.vendor}, origin "
                f"{comp.country_of_origin}, final assembly {comp.country_of_final_assembly}.",
                "manifest",
                f"provenance.components.{comp.id}",
                detail={
                    "role": comp.role,
                    "vendor": comp.vendor,
                    "country_of_origin": comp.country_of_origin,
                    "country_of_final_assembly": comp.country_of_final_assembly,
                    "hbom": comp.hbom_ref is not None,
                },
            )
    if policy is None:
        c.add(
            "policy.off",
            "outside",
            "The compliance policy was switched off, so URML checked no provenance or evidence rule.",
            "urml",
        )
        return Section(id="provenance", title="Provenance", items=c.items)
    by_rule = _issues_by_rule(evaluate_policy(manifest, policy, manifest_base_dir=manifest_base_dir))
    for rule in policy.rules:
        issues = by_rule.get(rule.id, [])
        text, result = _check_text("Policy rule", rule.id, issues)
        c.add(
            f"policy_rule.{rule.id}",
            "checked",
            text,
            "policy",
            f"rules.{rule.id}",
            result=result,
            detail={"policy_id": policy.policy_id, "codes": sorted({str(i.code) for i in issues})},
        )
    for erule in policy.evidence_rules:
        issues = by_rule.get(erule.id, [])
        text, result = _check_text("Evidence rule", erule.id, issues)
        c.add(
            f"evidence_rule.{erule.id}",
            "checked",
            text,
            "policy",
            f"evidence_rules.{erule.id}",
            result=result,
            detail={"policy_id": policy.policy_id, "codes": sorted({str(i.code) for i in issues})},
        )
    return Section(id="provenance", title="Provenance", items=c.items)


# ----- Envelope -----


def _grip_max(m: CapabilityManifest) -> float | None:
    grippers = m.manipulation.grippers if m.manipulation is not None else []
    return max((g.force_max_n for g in grippers), default=None)


#: (envelope field, label, unit, manifest value, manifest field, relevant when unset)
_LIMITS: tuple[
    tuple[
        str,
        str,
        str,
        Callable[[CapabilityManifest], float | None],
        str | None,
        Callable[[CapabilityManifest], bool],
    ],
    ...,
] = (
    (
        "max_velocity",
        "speed",
        "m/s",
        lambda m: m.mobility.max_velocity if m.mobility is not None else None,
        "mobility.max_velocity",
        lambda m: m.mobility is not None,
    ),
    (
        "max_altitude",
        "altitude",
        "m",
        lambda m: m.mobility.service_ceiling if m.mobility is not None else None,
        "mobility.service_ceiling",
        _aerial,
    ),
    (
        "max_payload",
        "payload",
        "kg",
        lambda m: m.mobility.max_payload if m.mobility is not None else None,
        "mobility.max_payload",
        lambda m: False,
    ),
    (
        "max_grip_force_n",
        "grip force",
        "N",
        _grip_max,
        "manipulation.grippers.force_max_n",
        lambda m: _grip_max(m) is not None,
    ),
    ("max_drop_height", "drop height", "m", lambda m: None, None, lambda m: False),
)


def _envelope_section(manifest: CapabilityManifest, envelope: SafetyEnvelope | None, seen: set[str]) -> Section:
    c = _Collector(seen)
    if envelope is None:
        c.add(
            "envelope.absent",
            "missing",
            "No safety envelope was given: the site's own limits are not on record, and only the "
            "manifest's limits apply.",
            "envelope",
        )
    for field_name, label, unit, manifest_value, manifest_field, relevant in _LIMITS:
        env_value = getattr(envelope, field_name) if envelope is not None else None
        man_value = manifest_value(manifest)
        item_id = f"limit.{field_name}"
        if env_value is not None:
            effective = env_value if man_value is None else min(env_value, man_value)
            also = (
                ""
                if man_value is None
                else f" The manifest allows {_fmt(man_value)} {unit}; the stricter, {_fmt(effective)} {unit}, applies."
            )
            c.add(
                item_id,
                "checked",
                f"The envelope limits {label} to {_fmt(env_value)} {unit}.{also}",
                "envelope",
                field_name,
                detail={"envelope": env_value, "manifest": man_value, "effective": effective, "unit": unit},
            )
        elif man_value is not None:
            c.add(
                item_id,
                "checked",
                f"The envelope sets no {label} limit; the manifest's {_fmt(man_value)} {unit} applies.",
                "manifest",
                manifest_field,
                detail={"envelope": None, "manifest": man_value, "effective": man_value, "unit": unit},
            )
        elif relevant(manifest):
            c.add(
                item_id,
                "missing",
                f"Neither the envelope nor the manifest sets a {label} limit, so no {label} is checked.",
                "envelope",
                field_name,
            )
    geofences = envelope.geofences if envelope is not None else []
    for fence in geofences:
        c.add(
            f"geofence.{fence.name}",
            "checked",
            f"Geofence {fence.name} (frame {fence.frame}, {len(fence.vertices)} vertices). Every place a "
            "program names must lie inside a declared geofence.",
            "envelope",
            f"geofences.{fence.name}",
            detail={
                "frame": fence.frame,
                "vertices": [list(v) for v in fence.vertices],
                "min_altitude": fence.min_altitude,
                "max_altitude": fence.max_altitude,
            },
        )
    if not geofences and _aerial(manifest):
        c.add(
            "geofence.none",
            "missing",
            "The envelope declares no geofence, so no place an aircraft program names is confined.",
            "envelope",
            "geofences",
        )
    for zone in envelope.people_occupancy_zones if envelope is not None else []:
        c.add(
            f"people_zone.{zone.name}",
            "checked",
            f"People-occupancy zone {zone.name} (frame {zone.frame}). Programs may not target places "
            "inside it" + (" unless overridden." if zone.allow_override else "."),
            "envelope",
            f"people_occupancy_zones.{zone.name}",
            detail={
                "frame": zone.frame,
                "vertices": [list(v) for v in zone.vertices],
                "allow_override": zone.allow_override,
            },
        )
    if envelope is not None and envelope.expression is not None:
        c.add(
            "expression",
            "checked",
            "Expression limits (head and body ranges, gesture limits) for expressive robots.",
            "envelope",
            "expression",
            detail=envelope.expression.model_dump(mode="json", exclude_none=True),
        )
    if envelope is not None and envelope.weather is not None:
        c.add(
            "weather",
            "runtime",
            "Weather limits are on record. The validator cannot see the weather; the runtime or the "
            "operator must check conditions before and during a run.",
            "envelope",
            "weather",
            detail=envelope.weather.model_dump(mode="json", exclude_none=True),
        )
    for index, rule in enumerate(envelope.link_loss_policy if envelope is not None else []):
        c.add(
            f"link_loss.{index}",
            "runtime",
            f"On losing the {rule.role} link, the robot must {rule.action}. The validator checks the "
            "policy against the declared links; acting on a loss happens at run time.",
            "envelope",
            f"link_loss_policy.{index}",
            detail=rule.model_dump(mode="json", exclude_none=True),
        )
    for prop in envelope.monitorable_properties if envelope is not None else []:
        c.add(
            f"monitor.{prop.name}",
            "runtime",
            f"Signal property {prop.name} ({prop.severity}) is judged on telemetry while a program runs, not before.",
            "envelope",
            f"monitorable_properties.{prop.name}",
            detail={"severity": prop.severity, "dialect": prop.dialect, "expression": prop.expression},
        )
    for item_id, text in _SHARED_RUNTIME:
        c.add(item_id, "runtime", text, "urml", "RFC-0701 section 1.3")
    return Section(id="envelope", title="Envelope", items=c.items)


#: RFC-0701 section 1.3: what every motion leaves to the runtime.
_SHARED_RUNTIME: tuple[tuple[str, str], ...] = (
    (
        "runtime.start_position",
        "Where the robot starts. The runtime must not start a program while the robot is outside "
        "every geofence, or inside a people-occupancy zone that does not allow an override.",
    ),
    (
        "runtime.paths",
        "The path between two checked places. The runtime must keep it inside the geofences and out "
        "of the people-occupancy zones.",
    ),
    (
        "runtime.unstated_speed",
        "The speed of a step that states none. The runtime must keep it at or below the strictest speed limit.",
    ),
    (
        "runtime.emergency_stop",
        "On an emergency stop reported by the substrate, the runtime must stop dispatching and stop "
        "every motion it commands. The emergency stop itself is a function of the machine.",
    ),
)


# ----- Rules -----


def _cite_detail(cite: Cite | None) -> dict[str, Any] | None:
    if cite is None:
        return None
    out: dict[str, Any] = {"text": cite.text, "url": cite.url}
    if cite.standard is not None:
        out["standard"] = cite.standards()
    return out


def _value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _rule_text(rule: Rule) -> str:
    return f"{rule.title}."


def _rules_section(inv: RulebookInventory, seen: set[str]) -> Section:
    c = _Collector(seen)
    missing_keys = {
        (str((i.detail or {}).get("rulebook_id")), str((i.detail or {}).get("rule_id")))
        for i in [*inv.errors, *inv.warnings]
        if str(i.code) == "rule.declaration_missing"
    }
    for issue in [*inv.errors, *inv.warnings]:
        code = str(issue.code)
        detail = issue.detail or {}
        if code == "rule.rulebook_invalid":
            label = str(detail.get("rulebook_id") or detail.get("source") or "unknown")
            c.add(
                f"rulebook_invalid.{label}",
                "missing",
                f"A rulebook was given but not applied: {issue.message}",
                f"rulebook:{label}",
                detail={"problems": detail.get("problems")},
            )
        elif code == "rule.defaults_disabled":
            label = str(detail.get("rulebook_id"))
            c.add(
                f"rulebook_off.{label}",
                "outside",
                f"The bundled rulebook {label} would apply but was switched off: {issue.message}",
                f"rulebook:{label}",
            )
    for entry in inv.entries:
        book = entry.book
        src = f"rulebook:{book.rulebook_id}"
        if book.issuer.kind == "deployment":
            continue
        if not entry.applied:
            c.add(
                f"rulebook.{book.rulebook_id}",
                "declared",
                f"Rulebook {book.rulebook_id} ({book.title}) is in scope but {entry.reason}.",
                src,
                "applies_to.unless_declared",
                detail={"bundled": entry.bundled},
            )
            continue
        for rule in book.rules:
            item_id = f"rule.{book.rulebook_id}.{rule.id}"
            body_model = getattr(rule, rule.kind)
            base: dict[str, Any] = {
                "kind": rule.kind,
                "cite": _cite_detail(rule.cite),
                "rule": body_model.model_dump(mode="json", exclude_none=True) if body_model is not None else None,
            }
            if rule.kind == "require_declared":
                body = rule.require_declared
                assert body is not None
                base["key"] = body.key
                base["allowed"] = list(body.allowed) if body.allowed is not None else None
                if (book.rulebook_id, rule.id) in missing_keys:
                    present = body.key in inv.declarations
                    found = (
                        f"declares {body.key}: {_value(inv.declarations[body.key])}, which is not allowed"
                        if present
                        else f"declares no {body.key}"
                    )
                    base["declared_value"] = inv.declarations.get(body.key)
                    c.add(
                        item_id,
                        "missing",
                        f"{_rule_text(rule)} The deployment {found}; every program is refused until it does.",
                        src,
                        f"rules.{rule.id}",
                        detail=base,
                    )
                else:
                    value = inv.declarations[body.key]
                    by = inv.declared_by.get(body.key)
                    base["declared_value"] = value
                    base["declared_by"] = by
                    c.add(
                        item_id,
                        "declared",
                        f"{_rule_text(rule)} Declared {body.key}: {_value(value)}, by {by}. URML checks "
                        "the declaration is there and allowed, not that it is true.",
                        src,
                        f"rules.{rule.id}",
                        detail=base,
                    )
                continue
            exception = inv.exceptions.get((book.rulebook_id, rule.id))
            if exception is not None:
                base["exception"] = {"deployment": exception[0], "basis": exception[1].basis}
            c.add(
                item_id,
                "checked",
                f"{_rule_text(rule)} Checked against every program ({rule.kind})."
                + (f" An exception from {exception[0]} applies." if exception is not None else ""),
                src,
                f"rules.{rule.id}",
                detail=base,
            )
        for obligation in book.obligations:
            c.add(
                f"obligation.{book.rulebook_id}.{obligation.id}",
                "outside",
                f"{obligation.title}. {obligation.text}",
                src,
                f"obligations.{obligation.id}",
                detail={"cite": _cite_detail(obligation.cite)},
            )
    for (rulebook_id, rule_id), (deployment, exc) in sorted(inv.exceptions.items()):
        c.add(
            f"exception.{deployment}.{rulebook_id}.{rule_id}",
            "declared",
            f"Deployment rulebook {deployment} declares an exception to {rulebook_id}/{rule_id}: {exc.basis}.",
            f"rulebook:{deployment}",
            "exceptions",
            detail={"rulebook_id": rulebook_id, "rule_id": rule_id, "expires": exc.expires},
        )
    return Section(id="rules", title="Rules", items=c.items)


# ----- Outside URML -----

_OUTSIDE: tuple[tuple[str, str], ...] = (
    (
        "outside.safety_control",
        "The robot's safety-related control and its safety functions (stops, speed and separation "
        "monitoring, power and force limiting), designed and validated outside URML.",
    ),
    ("outside.below_substrate", "Firmware, controllers and drivers below the substrate."),
    ("outside.site", "Wiring, guarding and the physical site."),
    ("outside.declarations", "Whether any declared item in this report is true."),
    (
        "outside.unmediated",
        "Anything a program does through a path that does not pass through a URML runtime.",
    ),
)


def _outside_section(seen: set[str]) -> Section:
    c = _Collector(seen)
    for item_id, text in _OUTSIDE:
        c.add(item_id, "outside", text, "urml")
    return Section(id="outside", title="Outside URML", items=c.items)


# ----- By standard -----

_CLAUSE = re.compile(r",?\s*(?:clauses?|§|section)\b.*$", re.IGNORECASE)


def _standard_keys(cite: Mapping[str, Any]) -> tuple[list[str], Literal["standard", "text"]]:
    standards = cite.get("standard")
    if standards:
        return list(standards), "standard"
    text = str(cite.get("text", "")).split(";")[0]
    key = _CLAUSE.sub("", text).strip()
    return ([key] if key else []), "text"


def _by_standard(sections: Sequence[Section]) -> list[StandardGroup]:
    groups: dict[str, StandardGroup] = {}
    for section in sections:
        for item in section.items:
            cite = item.detail.get("cite")
            if not isinstance(cite, dict):
                continue
            keys, keyed_by = _standard_keys(cite)
            for key in keys:
                group = groups.get(key)
                if group is None:
                    group = groups[key] = StandardGroup(standard=key, keyed_by=keyed_by, items={})
                elif keyed_by == "standard":
                    group.keyed_by = "standard"
                group.items.setdefault(item.status, []).append(item.id)
    return [groups[k] for k in sorted(groups)]


# ----- Counts -----


def _counts(sections: Sequence[Section]) -> Counts:
    by_status: dict[str, int] = dict.fromkeys(STATUSES, 0)
    by_section: dict[str, dict[str, int]] = {}
    failed = 0
    for section in sections:
        local: dict[str, int] = dict.fromkeys(STATUSES, 0)
        for item in section.items:
            local[item.status] += 1
            by_status[item.status] += 1
            if item.result == "fail":
                failed += 1
        by_section[section.id] = local
    return Counts(
        by_status=by_status,
        by_section=by_section,
        failed_checks=failed,
        gaps=by_status["missing"] + failed,
    )


# ----- Entry point -----


def _model(kind: str, model: type[BaseModel], data: Any) -> Any:
    if isinstance(data, model):
        return data
    try:
        return model.model_validate(data)
    except PydanticValidationError as exc:
        raise EvidenceInputError(f"the {kind} does not follow its schema: {exc.error_count()} error(s)") from exc


def build_evidence_report(
    manifest: Mapping[str, Any] | CapabilityManifest,
    envelope: Mapping[str, Any] | SafetyEnvelope | None = None,
    *,
    as_of: date,
    policy: Mapping[str, Any] | Policy | Literal["DEFAULT"] | None = "DEFAULT",
    rulebooks: Sequence[Mapping[str, Any] | Rulebook] = (),
    default_rulebooks: bool = True,
    profiles: Sequence[str] = (),
    manifest_base_dir: Path | None = None,
    manifest_name: str | None = None,
    envelope_name: str | None = None,
    policy_name: str | None = None,
    rulebook_names: Sequence[str | None] = (),
) -> EvidenceReport:
    """Build the evidence report for one robot deployment.

    Args:
        manifest: The robot's capability manifest.
        envelope: The site's safety envelope, or None when there is none.
        as_of: The date the report describes. Required, so a report never depends on the clock.
        policy: As for `validate()`: "DEFAULT" for the bundled policy, a policy, or None for none.
        rulebooks: Organization and deployment rulebooks, applied after the bundled ones.
        default_rulebooks: False switches the bundled rulebooks off.
        profiles: The profiles the deployment runs; they decide which rulebooks are in scope.
        manifest_base_dir: Where a component's relative HBOM reference resolves (RFC-0005).
        manifest_name, envelope_name, policy_name, rulebook_names: File names for the Inputs
            part, without directories. Optional; digests identify the inputs either way.

    Raises:
        EvidenceInputError: the manifest, envelope or policy does not follow its schema.
    """
    manifest_model: CapabilityManifest = _model("manifest", CapabilityManifest, manifest)
    envelope_model: SafetyEnvelope | None = None if envelope is None else _model("envelope", SafetyEnvelope, envelope)
    policy_errors: list[ValidationError] = []
    policy_model = _resolve_policy(dict(policy) if isinstance(policy, Mapping) else policy, policy_errors)
    if policy_errors:
        raise EvidenceInputError(f"the policy does not follow its schema: {policy_errors[0].message}")

    inv = rulebook_inventory(
        manifest_model,
        envelope_model,
        profiles=profiles,
        rulebooks=rulebooks,
        default_rulebooks=default_rulebooks,
        as_of=as_of,
    )

    seen: set[str] = set()
    sections = [
        _robot_section(manifest_model, seen),
        _provenance_section(manifest_model, policy_model, manifest_base_dir, seen),
        _envelope_section(manifest_model, envelope_model, seen),
        _rules_section(inv, seen),
        _outside_section(seen),
    ]

    files = [
        InputRef(role="manifest", id=manifest_model.robot_id, name=manifest_name, digest=content_digest(manifest)),
    ]
    if envelope_model is not None:
        files.append(
            InputRef(
                role="envelope",
                id=envelope_model.deployment_id,
                name=envelope_name,
                digest=content_digest(envelope),
            )
        )
    if policy_model is not None:
        files.append(
            InputRef(
                role="policy",
                id=policy_model.policy_id,
                name=None if policy == "DEFAULT" else policy_name,
                bundled=policy == "DEFAULT",
                digest=content_digest(policy_model if policy == "DEFAULT" else policy),
            )
        )
    names = list(rulebook_names)
    caller_ids = [(rb.rulebook_id if isinstance(rb, Rulebook) else rb.get("rulebook_id")) for rb in rulebooks]
    for entry in inv.entries:
        book = entry.book
        name = None
        supplied: Any = book
        if not entry.bundled and book.rulebook_id in caller_ids:
            index = caller_ids.index(book.rulebook_id)
            name = names[index] if index < len(names) else None
            supplied = rulebooks[index]
        files.append(
            InputRef(
                role="rulebook",
                id=book.rulebook_id,
                name=name,
                bundled=entry.bundled,
                digest=content_digest(supplied),
            )
        )

    return EvidenceReport(
        as_of=as_of.isoformat(),
        subject={"robot_id": manifest_model.robot_id, "description": manifest_model.description},
        inputs=Inputs(
            files=files,
            profiles=list(dict.fromkeys(profiles)),
            policy="off" if policy_model is None else ("bundled" if policy == "DEFAULT" else "file"),
            default_rulebooks=default_rulebooks,
            validator={"name": "urml-validator", "version": __version__},
        ),
        sections=sections,
        by_standard=_by_standard(sections),
        counts=_counts(sections),
    )


def render_json(report: EvidenceReport) -> str:
    """The report's canonical JSON: sorted keys, two-space indent, one trailing newline."""
    data = report.model_dump(mode="json")
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def report_schema() -> dict[str, Any]:
    """The JSON Schema of the report format (committed as spec/evidence/v0.1.0/report.schema.json)."""
    schema = EvidenceReport.model_json_schema(mode="serialization")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://urml.dev/schemas/evidence/v0.1.0/report.schema.json"
    return schema


__all__ = [
    "NOTICE",
    "REPORT_FORMAT",
    "STATUSES",
    "EvidenceInputError",
    "EvidenceReport",
    "Item",
    "build_evidence_report",
    "render_json",
    "report_schema",
]
