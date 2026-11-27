---
rfc: 0712
title: What a compatibility claim covers
author: Ido Yahalomi
state: Draft
created: 2026-11-27
updated: 2026-11-27
amends: RFC-0014, RFC-0705
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

# RFC-0712: What a compatibility claim covers

Kind: Spec (conformance). This RFC amends [RFC-0014](0014-substrate-conformance.md) and [RFC-0705](0705-urml-certified.md) and publishes the change in a new conformance specification version, `conformance@0.3.0`. It changes which fixtures a compatibility claim has to pass and what a conformance report records. It adds no primitive and changes no program or manifest schema.

This is a draft. RFC-0711 ([pull request #113](https://github.com/urml-dev/URML/pull/113)) waits for it, because a certificate needs a claim that a real robot can hold.

## Summary

A compatibility claim must pass every fixture that lists a profile, and no robot can. The fixtures of one profile ask for a camera, cell signals, output lines, named programs, a tool-change station and a second robot at once.

This RFC replaces "the whole profile" with "every fixture that applies to the claimed manifest". The validator decides which fixtures apply, from the capabilities the manifest declares, so nobody picks fixtures by hand. A test companion owned by the harness may play the camera and the cell's signals, and the report says which calls it served. A claim counts only fixtures in which the product itself served a call. The report records what stood behind the adapter, and a claim made on a test double is refused. Fleet fixtures leave single-robot claims.

## Motivation

The suite was written to test the validator and the reference runtime against the mock. Measured on 2026-11-27 at commit `d3e046b`:

- Of 269 fixtures, 128 must be refused and 38 are accepted and never executed. Neither kind reaches an adapter, which is why an adapter that fails every call still passes 27 of the 77 industrial fixtures.
- 101 fixtures execute on one robot, and 2 on a fleet. In the industrial profile, 39 of the 48 single-robot ones make the same seven calls in the same order, on different test manifests.
- 47 fixtures script what the camera sees (`adapter_overrides.detection`). The runner applies a script only to the mock, so a real adapter cannot be told what to detect.
- Apart from the mock, no adapter passes a whole profile on a real backend (RFC-0711, open question 1).

## Proposal

### A claim

A claim is made for one robot manifest, with one adapter, in one profile. It says: every fixture of this profile that applies to this manifest passed, on this backend. A registry entry that lists two profiles carries two claims.

### Which fixtures apply

Only a fixture that executes on one robot can apply: `expected_validation.accepted` is true, `expected_execution` is set, and there is no `roster`.

For each one, the harness takes the fixture's own manifest, removes the capabilities the claimed manifest does not declare, and runs the validator's capability pass on the fixture's program against what is left.

1. No capability error: the fixture **applies**.
2. Errors that disappear when perception and cell events are put back: the fixture **applies with the companion** (below).
3. Anything else: the fixture **does not apply**, and the report gives the first error code, for example `capability.missing_program`.

"Capabilities" is a fixed list of manifest parts, published in the conformance specification: `mobility` and the medium the robot moves in, `manipulation` and its grippers, `perception` with its cameras and sensors, `programs`, `docking_stations`, output lines, named endpoints, `declared_events`, `av`, `expression`, `payload_mechanisms`, `whole_body`, and the mobility flags for station keeping and relative motion.

The capability pass is the specification's own statement of what a program needs from a robot (`_check_capabilities`, with 88 `capability.*` codes today). Using it means the rule needs no table of primitives and cannot drift from the validator. The registry check recomputes the result from the entry's manifest, so a report cannot leave a fixture out.

A prototype of the rule, run on the UR-shaped test manifest, finds that 43 of the 48 industrial fixtures apply. The five that do not are the two that set output lines, the two that call named programs, and the one that needs a tool-change station.

### The conformance world

Fixtures name places, stations, object classes, events, report sinks, output lines and programs. Each profile's names are published in a generated file, `conformance/worlds/<profile>.yaml`, which CI checks against the fixtures. The single-robot industrial fixtures use three places, one station, two object classes, one event, one report sink, three output lines and three programs.

The submitter maps the names its applicable fixtures use to its own cell or simulator in one binding file. The values are the adapter's business. The keys are checked, and the report pins the file by sha256.

### The companion

An arm has no door switch and often no camera. An integrator supplies them, and so may the harness, through a companion it owns: the mock adapter, composed with the product's adapter one fixture at a time.

The companion serves a call in two cases only.

- **The fixture scripts the answer.** A scripted detection is what the camera sees in that fixture, so the companion serves `query_detection` whether or not the product has a camera.
- **The claimed manifest declares no perception, or no events, and the fixture needs them** (case 2 above). The companion then serves the perception calls (`query_detection`, `run_scan`, `take_measurement`, `capture_media`) or `wait_for_condition`.

It never serves motion, manipulation, docking, flight, outputs, programs, speech or expression. A fixture that scripts an answer from one of those does not apply, because a real robot cannot be told to fail on cue. One fixture does that today.

The report records, for every call in every fixture, whether the product or the companion served it.

### What counts

A fixture counts toward a claim only when the product served at least one of its calls. A claim needs every applicable fixture to pass and at least one to count.

There is no minimum number. Profiles hold between 0 and 48 executing fixtures, so any fixed floor would be arbitrary. A claim states its size instead, in the registry entry and wherever the claim is shown:

> URML-compatible, industrial profile, conformance 0.3.0. 43 tests in 5 call sequences. Served by the product: motion, gripper, cell signal, report, and detection in 1 test. Served by the test companion: detection in 41 tests. Not applicable: 5 (output lines, named programs, tool-change station). Backend: simulator.

Those are facts about scope, not a score. The rule stays all or nothing.

Fixtures that stop at the validator are not counted. They test the validator, which the submitter did not write. Refused programs belong to the goal-line lane of RFC-0711.

### Fleet fixtures

A fixture with a roster is never part of a single-robot claim. A fleet claim is made for a roster of products, and this RFC does not define one. Until an RFC does, the registry accepts no fleet claim.

### The backend

A report names the adapter and nothing about what stood behind it. It gains `backend`, declared by the submitter: a kind, a name and a version.

- `hardware`: the robot itself.
- `simulator`: software that computes the response of the robot or its controller from a model, such as the maker's controller simulator or a physics engine.
- `recorded`: responses captured earlier from one of those two and replayed.
- `fake`: a test double that answers without a model of the robot.

The registry refuses a claim whose backend is `fake`, as it already refuses the mock. The declaration is public and can be challenged. In a certified run the Licensor's reproduction confirms it (`reproduction.substrate` in RFC-0711).

### Fixture work the rule exposes

In the conformance release that carries this RFC:

- `drive` and `turn` get executing fixtures. They have none, so a robot that moves only by relative motion, such as the GoPiGo3 in the registry, can hold no claim.
- `drone/hover_positive` gets a take-off before the hover. It assumes a vehicle that is already in the air.
- `drone/flight_only_positive`, the one executing fixture without `audit_methods`, gets them. Until then no call of its is checked.

The 39 industrial fixtures that share one call sequence stay for now. They test the validator against 41 manifests, and the claim text shows the repetition.

### The acceptance test for this RFC

Before this RFC is accepted, one adapter holds a self-reported claim under the new rule on a simulator. The candidate is the project's UR adapter on URSim. A first-party package may self-report. It cannot be certified.

## What a claim still does not show

**The product's own limits.** Fixtures run on the public test manifests. The claimed manifest only selects them.

**The product's camera, where the scene is scripted.** That is 47 fixtures today.

**That the manifest is true.** A maker who leaves `programs` out of the manifest drops the named-program fixtures. The claim lists what did not apply and why, and the manifest is public.

**Safety, compliance or fitness.** Unchanged.

## Backward compatibility

No registry entry carries a claim, so no claim changes. "A claim covers a whole profile or nothing" in `registry/README.md` and "for whole profiles" in section 3 of the conformance specification are replaced. Clause 6 of the contract changes from "for the profiles it claims" to the fixtures of those profiles that apply to the runtime's manifest. The other five clauses stay.

The report format stays `urml.conformance-report/1`, because every new field is optional. A run without a claimed manifest behaves as today, which keeps the hermetic self-test on the mock.

The `research` profile has no executing fixture. It can carry no claim until it has one.

## Drawbacks

The harness grows a list of manifest parts, a reduction step, a companion and a record of who served each call. All of it sits in the code that grants claims.

Two claims for the same profile can cover different fixtures. A claim cannot be read without its scope.

The list of parts is coarse. An arm with a charging dock and no tool changer still gets the tool-change fixture, because both are docking stations. Refining the list changes which fixtures apply and needs a conformance release.

A call the companion serves can hide a fault in the product. A product never proves here that it can act on a detection its own camera made.

Some profiles stay thin under any rule: `av` has one executing fixture, `social` two, and the six in `educational` share one call sequence.

## Alternatives considered

1. **Keep the whole profile and add the companion only.** It lifts the UR adapter to 71 of 77 on fakes. The six that remain need output lines, named programs, a tool-change station and a second robot, so an arm without them could never claim.
2. **Split profiles into modules.** Claims per module need a taxonomy and a tag on every fixture, both kept by hand. The reduction computes the same partition from the manifest.
3. **Check the fixture's program against the claimed manifest itself.** It needs the fixture world's names injected into that manifest and makes applicability depend on numbers such as a gripper's force range.
4. **Leave it.** No robot holds a claim, so no certificate exists.

## Prior art

- ISO/IEC 9646, the conformance testing methodology for protocols: an implementation states what it supports in a conformance statement, and the statement selects the test cases. Bluetooth qualification works this way. Here the capability manifest is the statement.
- Vulkan and OpenGL ES conformance: a test for an optional feature the implementation does not advertise is reported as not supported, not as failed.

## Implementation plan

In the pull request that carries this RFC, before it is accepted:

- `spec/conformance/v0.3.0.md`: clause 6 and section 3 as above, the list of capability parts, the companion's two cases, the backend kinds, the binding file.
- `reference/validator`: a public function that returns the capability-pass errors for a program and a manifest, and the reduction of one manifest to the parts another declares.
- `conformance/src/urml_conformance/`: a new `claim.py` (which fixtures apply, the companion, who served each call); `runner.py` and `__main__.py` take a claimed manifest, a binding file and a backend; `report.py` gains the optional claim block and per-fixture scope; `recording.py` binds the optional capabilities of a composed adapter; `registry.py` replaces the whole-profile check in `check_report` with the recomputed scope and refuses a `fake` backend; `fixtures.py` generates the world files.
- `conformance/fixtures/`: the three fixture changes above.
- `registry/README.md`, `docs/registry/SUBMISSION.md`, `conformance/README.md`, `conformance/CONFORMANCE_KIT.md`, `TRADEMARK.md`, `docs/glossary.md`: what "URML-compatible" covers.

## Regulatory alignment

None changes.

## Open questions

1. **The companion's list.** Perception and cell events. Should report sinks join it, or anything leave it?
2. **Scripted scenes.** Should a product that declares a camera have to serve scripted detections in a simulated scene one day? Today 41 of a UR arm's 43 fixtures never touch its camera.
3. **Numbers on a claim.** The specification says there are no scores. Is a count of tests and call sequences acceptable as a statement of scope?
4. **`recorded` backends.** Accepted here for a self-reported claim. Should they be?
5. **Fleet claims.** Left undefined. Does a buyer of a mixed fleet need one soon?

## Process note

This RFC takes the comment window that [RFC-0001](0001-rfc-process.md) sets, like RFC-0711: it stays open for at least seven days before it is accepted.

RFC-0711 was drafted against `conformance@0.3.0` as well. It follows this RFC and takes the version after it.
