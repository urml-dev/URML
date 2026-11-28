---
rfc: 0713
title: A place the validator cannot locate is refused
author: Ido Yahalomi (greenvh@gmail.com)
state: Draft
created: 2026-11-28
updated: 2026-11-28
amends: RFC-0290 (a frame that cannot be resolved no longer passes a geofence or a zone)
supersedes: none
superseded-by: none
---

<p align="center">
  <a href="https://urml.dev"><img src="https://urml.dev/favicon.svg" alt="URML" width="72" height="72"></a>
</p>

<p align="center">
  The standard language for robot intent.
</p>

<p align="center">
  <a href="https://urml.dev"><b>urml.dev</b></a>
</p>

---

# RFC-0713: A place the validator cannot locate is refused

Kind: Spec. This RFC changes the safety-envelope pass of the validator and one capability check, and the Layer 1 and Layer 2 sentences that describe them. It adds one error code. It changes no schema and adds no primitive. It takes section 2 of [RFC-0701](0701-envelope-completeness.md) and one row of its section 4.2 and proposes them on their own, because RFC-0701 is a Draft with seven open questions and none of them bears on these rules.

## Summary

A safety envelope says where a robot may go (geofences) and where it may not (people-occupancy zones). The validator judges every place a program names against them before anything runs. In three cases it cannot tell where the place is, and today it lets the program through:

1. The target is in a coordinate frame that no declared transform relates to the frame of the geofence or the zone. [RFC-0290](0290-frame-transform-graph.md) says the check abstains.
2. A `scan` region names something that is not a declared area: a name the manifest never declared, or a location, which is one point. Nothing resolves the name as a region, and the envelope pass skips the scan.
3. A `scan` area is given as literal coordinates, which carry no frame, and the envelope's geofences and zones use more than one frame. The validator reads the area in the frame of the first geofence.

This RFC proposes that the validator refuses the program in all three. The first and the third get a new code, `envelope.frame_unresolved`. The second uses the existing `capability.missing_location`.

## Motivation

A geofence is an allowlist: a target is admitted when it lies inside one. A people-occupancy zone is a denylist: a target is refused when it lies inside one. When the validator cannot tell where a target lies, declining to judge has the same effect as finding it inside the fence and outside every zone. The check fails open.

The industrial cell in the test fixtures shows it. The manifest declares two frames, `cell` and `base_link`, and `base_link` has a parent and no transform. The hand-loading envelope declares the operator's station as a people-occupancy zone in `cell`, covering x -0.6 to -0.2 and y -0.4 to 0.0. On main at 26d40f0:

```yaml
- move_to:
    pose: { x: -0.4, y: -0.2, z: 0.2 }
    frame: cell          # refused: envelope.occupancy_zone_intrusion
```

```yaml
- move_to:
    pose: { x: -0.4, y: -0.2, z: 0.2 }
    frame: base_link     # accepted
```

The same numbers, named in a frame the zone cannot be related to, pass. A planner does not need to be hostile to write the second form: a language model asked to "move 40 centimetres to the left" may reach for the robot's own frame.

The project has measured this since 2026-09-26. Three rows of the adversarial bench name a target in such a frame (`gap_frame` in the home and industrial corpora, `gap_wgs84` in the drone corpus), and all three passed the gate, labelled as known gaps. [`docs/safety/safety-model.md`](../safety/safety-model.md) listed the abstain among the gaps a reader has to know about.

The other two cases are the same failure reached through `scan`. A scan region named `car_park` on a manifest that declares no such place is accepted today under any geofence, and so is a region named after a declared point. A scan area written as literal coordinates is judged in whichever frame the first geofence happens to use.

Pass 2 already states the principle for every other place argument: "An unresolved name would let the step skip every spatial envelope check, so it is refused here." The rulebook pass states it for zone rules, which refuse a place they cannot see (`rule.place_unknown`, [RFC-0702](0702-rulebooks.md)). The envelope pass is the one that still lets an unplaceable target through.

## Detailed design

### An unresolved frame does not pass

Normative text, for Layer 1 and for the safety-envelope check in Layer 2:

> A geofence or people-occupancy zone applies to a target when the target is in its frame, or resolves into it through the manifest's frame graph. When no transform relates a target's frame to the frame of a declared geofence or zone, the validator MUST NOT treat the check as passed.
>
> - Geofences are an allowlist. When no declared geofence can be related to the target's frame, the validator MUST reject the program with `envelope.frame_unresolved`. When at least one can, the target must lie inside one of those, as today.
> - People-occupancy zones are a denylist. When a zone without `allow_override: true` cannot be related to the target's frame, the validator MUST reject the program with `envelope.frame_unresolved`.

The rule covers every spatial target the envelope pass judges: a literal pose, a declared location, every vertex of a declared area, a docking station, the `detect` search region, a scan area, and the current position the validator tracks for `release`, `set_output` and a bare `hover` ([RFC-0684](0684-aerial-delivery-extension.md)).

A target is refused once for the geofences and once for the zones, not once per vertex. The error names the target, its frame, and each fence or zone with its frame. It suggests declaring a `transform`, naming the target in the other frame, or, for a zone, `allow_override: true` when the deployment has accepted the risk.

A zone marked `allow_override: true` is skipped whether or not it can be related to the target. When it cannot, the validator reports `envelope.frame_unresolved` as a warning. Nothing is refused. The operator learns that the zone could not have been judged, because a frame that connects to nothing is often a mistake in the manifest.

Four things stay as they are:

- A target in the same frame as the fence or zone needs no transform.
- A frame with a parent and no transform stays valid and can be named. It stops letting a target skip a fence or a zone.
- An envelope with no geofence and no zone has nothing to resolve, and no program changes outcome.
- Fleet deconfliction ([RFC-0291](0291-utm-strategic-deconfliction.md)) keeps its fallback to name-based comparison when members share no world frame. It compares robots with each other, not a target with the deployment's limits. RFC-0701 keeps that question open.

### A scan region names a declared area

`scan.area.named_region` MUST name a declared area. A name that is not one is rejected at the capability check with `capability.missing_location`. That covers a name the manifest does not declare, and the name of a declared location.

A location is one point. It has no extent the validator could judge against a geofence or a zone, so a scan "of" a point would be accepted on the strength of one coordinate while the robot covers ground nobody checked. The message says the name is a point and suggests declaring the area.

Other place arguments let a location win when a location and an area share a name. A scan region is the area. Resolving the point there would skip the overlap test, so the validator looks the name up among the declared areas only.

### A literal scan area needs one frame to be read in

A `polygon` or `bounding_box` names no frame. It is read in the frame the envelope's geofences and people-occupancy zones share. When they use more than one frame, the program is rejected with `envelope.frame_unresolved`. That holds when a transform relates the frames too: the transform says how to convert coordinates, and it does not say which frame the author's numbers were written in.

RFC-0701 proposes an optional `scan.area.frame` for this case. This RFC does not add it. A program that needs a region in a deployment with two frames names a declared area, which carries its frame in the manifest.

### Spec changes

- [`spec/layer-1-hal/README.md`](../../spec/layer-1-hal/README.md), "Frame-transform graph": the sentence that says a check needing an undeclared relation abstains is replaced by the rule above.
- [`spec/layer-1-hal/v0.2.0.md`](../../spec/layer-1-hal/v0.2.0.md): §2.1 says a target in a named-only frame cannot pass a fence or zone declared in another frame. §3 states the rule under Pass 3.
- [`spec/layer-1-hal/rulebook.md`](../../spec/layer-1-hal/rulebook.md): one parenthesis that described the envelope pass as abstaining.
- [`spec/layer-2-primitives/v0.1.0.md`](../../spec/layer-2-primitives/v0.1.0.md): §1, the safety-envelope check, and §2.9 `scan`, on what a `named_region` must name and how a literal area is read. The edits add no lines, so the line citations in the coverage matrix still point where they did.

No profile document changes.

### Validator changes

- `errors.py`: `ENVELOPE_FRAME_UNRESOLVED = "envelope.frame_unresolved"`. Error codes are public API; this one is added and none is renamed.
- `validator.py`: `_check_envelope_geofence` and `_check_envelope_occupancy_zones` test, per target, whether any fence and every zone without an override can be related to the target's frame, and refuse when not. `_check_point_in_any_geofence` and `_disk_in_any_geofence` no longer return "passed" when no fence applies. `_check_envelope_occupancy_zones` also emits the warning for an overridden zone it cannot relate, and both `validate` and `validate_fleet` now sort envelope issues into errors and warnings by severity. `_scan_targets` reads a literal area in the one frame the envelope shares, and resolves a named region among the declared areas only. `_check_scan_caps` refuses a `named_region` that is not a declared area.

### Reference runtime changes

None. `URMLRuntime.execute` validates again before its first adapter call, so it refuses the same programs. The goal-line lane confirms it for the four new rejected fixtures.

### Conformance suite changes

Seven fixtures and one envelope:

| Fixture | Expects |
|---|---|
| `industrial/58_move_to_pose_in_unresolved_frame_rejected` | `envelope.frame_unresolved` (a zone that cannot judge the pose) |
| `industrial/59_move_to_pose_in_zone_frame_positive` | accepted and executed: the same pose in the zone's frame, clear of it |
| `drone/39_move_to_pose_in_unresolved_frame_rejected` | `envelope.frame_unresolved` (a geofence that cannot judge the pose) |
| `drone/40_scan_undeclared_region_rejected` | `capability.missing_location` (the region is not declared) |
| `drone/41_scan_region_named_after_location_rejected` | `capability.missing_location` (the region is a declared point) |
| `drone/42_scan_literal_area_two_frame_envelope_rejected` | `envelope.frame_unresolved` (a literal area, a fence in `agl`, a zone in `wgs84`) |
| `home/37_scan_declared_area_positive` | accepted and executed: the region is a declared area inside the fence |

The envelope `drone_two_frame_site` is registered in `ENVELOPE_REGISTRY`. [`docs/safety/envelope-coverage.md`](../safety/envelope-coverage.md) gains the new code on the `move_to` and `scan` rows and the scan region on the list of names that must resolve, and loses the two deferred cells this RFC settles.

### Measurement

Measured on 26d40f0 with the change applied, Python 3.11.

| What was run | Result |
|---|---|
| The 269 conformance fixtures on main | No fixture changes outcome |
| All 276 fixtures, with the seven new ones | 276 of 276 pass |
| Goal-line lane (`python -m urml_conformance --goal-line`) | 133 of 133 rejected fixtures refused by the runtime with zero adapter calls (128 before, plus the five new rejected fixtures) |
| Adversarial bench, three corpora, scripted striker | 0 of 44 envelope rows pass. The three frame rows are stopped. 12 of 12 safe controls accepted |
| Unit tests that pinned the old behavior | Five change, listed under "Backward compatibility" |
| Every shipped example with a test | No example changes outcome |
| Every envelope under `examples/`, crossed with the manifests and programs in its folder (289 combinations, run by a second session on its own copy) | The same error codes on main and on this branch |

Of the 134 manifests under `reference/validator/tests/fixtures/manifests/`, 90 declare a frame that has a parent and no transform. None of the programs run against them names a target in such a frame under an envelope that has a geofence or a zone, which is why no fixture moves.

No pull-request workflow runs the validator, bridge or runtime test suites today, so these numbers come from local runs and not from CI.

## Backward compatibility

A program is refused that was accepted before in exactly these cases:

- It names a target in a frame that no transform relates to any declared geofence, or to a people-occupancy zone without `allow_override: true`.
- It scans a `named_region` that is not a declared area. That includes a region named after a declared location.
- It scans a literal polygon or bounding box under an envelope whose geofences and zones use more than one frame.

A program gains a warning, and is otherwise judged as before, when it names a target in a frame that no transform relates to a zone marked `allow_override: true`.

Five unit tests pinned the old behavior and now assert the new one:

- `reference/validator/tests/test_transforms.py::test_geofence_no_transform_abstains`, now `test_geofence_no_transform_is_refused`
- `reference/validator/tests/test_envelope_coverage.py::TestIndustrialPlaces::test_frames_without_a_transform_abstain`, now `test_frames_without_a_transform_are_refused`
- `reference/validator/tests/test_envelope_coverage.py::TestFlightPlaces::test_detect_search_radius_abstains_without_a_transform`, now `test_detect_search_region_is_refused_without_a_transform`
- `reference/validator/tests/test_envelope_coverage.py::TestScanArea::test_named_region_that_is_not_a_declared_area_is_not_judged`, now `test_named_region_that_is_not_a_declared_area_is_refused`
- `reference/ros2-runtime/tests/test_runtime.py::test_scan_binding_is_threaded_to_runtime_result` scanned a region named `kitchen`, which the home manifest declares as a point. It now scans a literal area.

Three committed bench rows no longer reproduce and are listed as superseded in `test_bench_results_guard.py`: the 2026-09-26 home `post-fix` row, the 2026-09-27 drone `rulebook` row and the 2026-09-27 industrial `release-check` row. Three rows measured on 2026-11-28 replace them under `bench/results/2026-11-28/`. The corpora relabel four rows from `known_gap` to `envelope` and keep their ids: the three frame rows, and `gap_release_in_zone`, which RFC-0684 stopped in September. The industrial corpus then has no known gap left, so `test_corpus_rows_are_labeled` allows zero.

A deployment feels the change in three situations. One names targets in a robot-relative frame, such as `base_link`, under a fence declared in a world frame: those steps are refused until the targets are named in the fence's frame or as declared places. The second declares zones in two frames with no transform between them: every target is refused by the zone in the other frame until the transform is declared or the zones are moved into one frame. The third asks for a scan of a place its manifest declares as a point, such as "scan the kitchen" on a home robot whose rooms are locations: the scan is refused until the manifest declares the room as an area.

The validator's public Python API does not change. `envelope.frame_unresolved` is a new value of `ErrorCode`.

## Drawbacks

- **A robot's own frame has no fixed transform.** For a mobile robot `base_link` moves with the robot, so no declared transform can relate it to the map. Under an envelope with a fence or a zone, a pose named in the robot's own frame is refused, and no declaration admits it. That is the intended result, since the validator cannot know where such a pose lands. It also removes a short way of writing relative moves in fenced deployments. `drive` and `turn` remain for robots that declare relative motion, and their end point is the runtime's to keep inside the envelope.
- **Programs that were accepted are refused.** A deployment that worked yesterday can stop validating after an upgrade, with no change on its side. The error says what to declare, and the cases are narrow, but it is a behavior change on the safety boundary in a 0.x release.
- **Two errors for one cause.** A target in an unrelated frame under an envelope with both a fence and a zone gets `envelope.frame_unresolved` twice, once from each list. Each says a different thing, and the fix is the same for both.
- **"Scan the kitchen" stops working where the kitchen is a point.** Many manifests declare rooms as locations. A scan of such a room was accepted and is now refused until the manifest declares the room as an area with a polygon. The error says so, and the fix is in the manifest, where a model that wrote the program cannot make it.
- **Literal scan areas stop working in two-frame envelopes.** There is no field to say which frame the numbers are in. The author has to declare an area in the manifest.

## Alternatives considered

**Keep abstaining and add a warning.** A warning does not stop a program. The three bench rows would still pass the gate, and the evidence a deployment collects would still say "accepted" for a target nobody placed. Rejected.

**Fail closed for geofences only.** A fence is an allowlist, so "cannot judge" means "not shown to be inside". For a zone the same reasoning runs the other way, and an abstaining denylist clears everything. The motivating example is a zone. Rejected.

**Require a transform on every frame.** The manifest schema could refuse a frame that has a parent and no transform, which would remove the case at its root. 90 of the 134 fixture manifests declare such a frame, mostly `base_link`, and for a mobile robot no fixed transform exists to declare. Rejected.

**Judge a region named after a point at that point.** The first draft of this RFC did this: check the one coordinate against the fences and zones, accept, and leave the ground around it to the runtime. It breaks nothing, since "scan the kitchen" keeps working on a manifest that declares the kitchen as a point. It was rejected because the result reads as more than it is. An accepted scan looks like a judged region, when one coordinate was judged and the area the robot covers was not. Refusing keeps the rule simple: a region is an area, and an area has a polygon the validator can check. Decided by the maintainer on 2026-11-28.

**Add `scan.area.frame` now.** RFC-0701 proposes it. It is a program schema field, so it reaches the Layer 2 schema, the JSON Schema and the prompt contract the LLM bridge sends to a model. A named region covers the need without any of that. Left with RFC-0701.

**Wait for RFC-0701 as a whole.** It has been a Draft since 2026-09-26 and has seven open questions, about profile defaults, speeds, the emergency stop and endurance. None touches these three rules, and the frame rule is the part of it that closes a hole a planner can walk through today.

## Prior art

- RFC-0290 introduced cross-frame checks and chose to abstain where no transform exists, to stay additive. RFC-0701 measured the cost of that choice and wrote the rule this RFC proposes. The normative text above is its section 2, and the measurement there (a16a03f) found what this one found: no fixture and no example changes outcome.
- RFC-0702 made rulebook zone rules refuse a place they cannot express in the zone's frame (`rule.place_unknown`). The bundled FAA rulebook has stopped the drone frame row that way since 2026-09-27. This RFC brings the envelope pass in line with the rulebook pass.
- Saltzer and Schroeder, "The Protection of Information in Computer Systems" (1975), name the principle fail-safe defaults: base a decision on permission, so that a mechanism that cannot decide refuses. A geofence check that passes what it cannot place is the textbook counterexample.
- ArduPilot treats a geofence it cannot evaluate as a reason not to fly. With a fence enabled, its pre-arm check refuses to arm until the vehicle has a position estimate to test against the fence ("Fence requires position").

## Unresolved questions

None are open. The three this RFC was filed with were decided by the maintainer on 2026-11-28.

1. **A region named after a point.** *Resolved: refused.* A scan region must be a declared area. The first draft judged the point.
2. **Poses in a robot-relative frame.** *Resolved: a follow-up RFC.* The validator tracks the robot's position across positioning steps for some checks (RFC-0684). A later RFC will use that to place a pose named in the robot's own frame, and will still refuse when the position is not known. Until then such a pose is refused under a fence or a zone, and relative motion stays with `drive` and `turn`.
3. **Zones with an override in an unrelated frame.** *Resolved: a warning.* They are skipped as before, and the validator says it could not have judged them.

## Implementation note

One pull request carries this RFC, the spec sentences, the validator change, the tests, the seven fixtures and the three bench rows. It stays a draft for the seven-day comment window of [RFC-0001](0001-rfc-process.md). If the RFC is accepted, the state line and the index row change in that pull request before it merges.

RFC-0701 gets a dated note saying which parts moved here. Its `scan.area.frame`, its remaining static checks and its open questions stay with it.

The fixture count on the README badge and in `docs/launch/claims-audit.md` moves from 269 to 276. Those numbers are transcribed by the maintainer from `make audit`, so this pull request reports the drift and does not edit them.

## Self-review (Phase 0)

- [x] The Summary alone tells a reader what is being proposed.
- [x] The Motivation is grounded in a concrete use case, not hypothetical needs.
- [x] The Detailed design names every affected spec document and reference component.
- [x] At least one alternative is genuinely considered (not a strawman).
- [x] Drawbacks are listed; at least one of them is a real downside, not a humblebrag.
- [x] Backward compatibility is honest about what breaks.
- [x] If this RFC adds a Layer-2 primitive, both ROS-2 and non-ROS implementation sketches are present (substrate-neutrality acid test). Not applicable: no primitive is added. The rule reads only the manifest's frame graph and the envelope, and names no substrate.
- [x] The implementation note explains how this lands, not just what.
- [x] The author has re-read [`CLAUDE.md`](../../CLAUDE.md) §What Claude Should Never Do and confirmed this proposal does not violate it.
