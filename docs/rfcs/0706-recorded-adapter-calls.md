---
rfc: 0706
title: The conformance harness records adapter calls
author: Ido Yahalomi (greenvh@gmail.com)
state: Draft
created: 2026-11-24
updated: 2026-11-24
supersedes: —
superseded-by: —
---

<p align="center">
  <a href="https://urml.dev"><img src="https://urml.dev/favicon.svg" alt="URML" width="72" height="72"></a>
</p>

<p align="center">
  A small, opinionated, human-readable language for describing robot intent.
</p>

<p align="center">
  <a href="https://urml.dev"><b>urml.dev</b></a>
</p>

---

# RFC-0706: The conformance harness records adapter calls

## Summary

The conformance suite checks which substrate calls a runtime makes (`expected_execution.audit_methods`, and `per_member_audit` for fleets) by reading a `call_log` list off the adapter. Only the mock adapter keeps one. Every real adapter, `RclpyAdapter` included, was compared as if it had called nothing, and so failed 102 of the 103 fixtures that check execution. This RFC moves the recording into the harness: `ConformanceRunner` wraps every adapter in the recording proxy the goal-line lane already uses, and compares the fixture's expected methods with the calls the proxy saw. No adapter has to keep a log, and every adapter is held to the same check as the mock. Measured on `aa9b5aa`, the proxy's record equals the mock's `call_log` on all 100 single-robot fixtures and all 6 adapters of the 2 fleet fixtures, so no fixture changes outcome against the mock.

## Motivation

On 2026-11-24 the `gazebo-e2e` job ran the `home/nav_patrol_positive` fixture through `RclpyAdapter` against a live TurtleBot 4 simulation with Nav2. Nav2 accepted all three patrol goals; the runtime reported success with 3 steps executed, which is what the fixture expects. The report still failed:

```text
[FAIL] home/nav_patrol_positive
  - audit methods do not match: actual=[], expected=['send_navigation_goal', 'send_navigation_goal', 'send_navigation_goal']
```

The runner read `getattr(adapter, "call_log", [])`. `RclpyAdapter` has no `call_log`, so the robot's three goals counted as zero calls. A comment above that line said the check was meant for the mock only, and the code did not do what the comment said.

The scope is wider than one job. Of the 269 fixtures, 103 carry `expected_execution`; 100 pin `audit_methods` and 2 pin `per_member_audit`. An adapter without a `call_log` could pass at most 1 of those 103. Conformance clause 6 ([`spec/conformance/v0.2.0.md`](../../spec/conformance/v0.2.0.md) §2) requires a runtime to pass the suite "with the runtime's own adapter", and the URML-Certified tier (RFC-0705) reproduces exactly that run. Until now no third-party adapter could pass it in full, however correct its behavior.

PR #17 stops the false failure for single-robot fixtures: the runner skips the audit comparison when the adapter has no `call_log`. That is a stopgap with a cost. A real runtime is now tested less than the mock: the suite no longer checks that it sends three navigation goals rather than one, or that it sends them in order. Certification would inherit that gap. The fleet lane still has the original bug, because `FleetRuntime` builds `per_member_audit` from each adapter's `call_log`.

The call sequence is worth checking on real substrates, not only on the mock. It is the part of execution a runtime author is most likely to get subtly wrong (a dropped retry, a duplicated goal, a step that silently no-ops), and clause 2 forbids exactly that silent no-op.

## Detailed design

### The recording moves into the harness

`conformance/src/urml_conformance/goal_line.py` already defines `RecordingAdapter`: a proxy that wraps any adapter object, records every method call (name, positional and keyword arguments) before forwarding it, and passes plain attribute reads through unrecorded. It binds the wrapped adapter's public methods up front, so runtime-checkable Protocol checks (`isinstance` with `inspect.getattr_static` on Python 3.12+) answer the same way they would for the bare adapter. The goal-line lane has used it since c7dec9b to prove a rejected program reaches the adapter with zero calls.

This RFC makes the same proxy the source of truth for the main lane:

1. `RecordingAdapter` and `RecordedCall` move to a shared module, `urml_conformance/recording.py`. `goal_line.py` imports them from there and keeps re-exporting them, so existing imports do not break.
2. `ConformanceRunner` wraps every adapter its `adapter_factory` returns in a `RecordingAdapter` before handing it to the runtime. For a fleet case it wraps each member's adapter.
3. `audit_methods` is compared with `[call.method for call in proxy.calls]`. `per_member_audit` is compared, member by member, with the same list from that member's proxy. The runtime's own `audit_log` and `per_member_audit` fields are no longer read by the harness.
4. The skip that PR #17 adds (`call_log is None`) is removed. Every adapter is checked.

What counts as a call is unchanged in practice: any public method the runtime invokes on the adapter. The measurement below shows that, for the reference runtime and the mock, this is the same list the mock's `call_log` records today.

### Spec changes

- [`spec/conformance/v0.2.0.md`](../../spec/conformance/v0.2.0.md) §2, clause 6, gains one sentence: *"The suite records the calls the runtime makes on the adapter through a proxy, and compares them with the methods a fixture expects. An adapter is not required to keep its own record of calls."* Whether this lands as v0.2.1 or as an erratum to v0.2.0 is an unresolved question below.
- No Layer-1 to Layer-4 document changes. The substrate Protocol (clause 2) is untouched: it gains no method and no attribute.

### Validator changes

None. The validator never sees the adapter.

### Reference runtime changes

None required. `MockROSAdapter.call_log` stays: unit tests in ros2-runtime, px4-runtime, llm-bridge and validator read it, and `RuntimeResult.audit_log` is built from it. It stops being part of the conformance contract, which it never formally was.

### Conformance suite changes

- `runner.py`: wrap adapters, compare against proxy calls, drop the PR #17 skip (single-robot and fleet lanes).
- `fixtures.py`: the `audit_methods` and `per_member_audit` field descriptions say "the methods the runtime called on the adapter, as recorded by the harness" instead of "the adapter's call_log methods". No fixture file changes.
- `CONFORMANCE_KIT.md`: Step 3 says the audit trace is recorded by the harness, so an adapter author does not implement a call log.
- Tests: the regression test PR #17 adds (an adapter with no `call_log` runs `home/nav_patrol_positive`) changes from "passes because the check is skipped" to "passes because the proxy recorded three `send_navigation_goal` calls". A new test gives an adapter with no `call_log` a runtime that sends two goals instead of three, and expects the audit diagnostic. A fleet test does the same for one member.
- A new `urml-conformance` release carries the change.

### Measurement

Measured on `aa9b5aa` with the reference `URMLRuntime`, `FleetRuntime` and `MockROSAdapter`, wrapping each adapter in `RecordingAdapter` and comparing the proxy's recorded method names with the mock's own `call_log`:

| Set | Fixtures | Proxy record equals `call_log` |
|---|---|---|
| Single robot, `audit_methods` | 100 | 100 |
| Fleet, `per_member_audit` | 2 (6 member adapters) | 2 (6 of 6) |

No fixture changes outcome against the mock.

## Backward compatibility

Fixture files: unchanged.

Adapters: an adapter with no `call_log` goes from failing every audit-pinned fixture (before PR #17), or skipping the check (after it), to being checked like the mock. An adapter that calls the substrate in a different order or number than a fixture expects will start failing those fixtures. That is the check working; such a runtime was never passing them honestly.

An adapter that keeps its own `call_log` with a different shape from the mock's (for example, recording only some methods) is not affected, because the harness no longer reads it.

URML-Certified: RFC-0705 ends a certification when a new urml-conformance version is released. The release that carries this change ends any certification granted before it, and a recertification runs the stricter check.

## Drawbacks

- **Recorded is not performed.** The proxy records that the runtime asked the adapter to send a goal. It does not see whether the robot moved. That is the same limit the mock check has today, and execution success and step counts are still checked, but the audit line will look more like evidence of motion than it is. The kit should say so.
- **A proxy can perturb an adapter.** An adapter that inspects its own type, relies on identity (`adapter is x`), or sets callables on itself in unusual ways could behave differently behind a proxy. The measurement shows no change for the mock, but a vendor adapter may find a case, and the goal-line lane has not yet been run against many third-party adapters.
- **Stricter for third parties.** Runtimes that pass today only because the check is skipped will see new failures. This is intended, and it lands in the same week the certified tier opens, so it may look like moving the goalposts.

## Alternatives considered

**Give `RclpyAdapter` a `call_log`.** This was the first fix considered, and it would make `gazebo-e2e` pass with a real audit check. It was rejected for three reasons. It fixes one adapter: every other real adapter (PX4, ArduPilot, OPC UA, vendor SDKs) would need the same, and the suite would still fail any that forgot. It turns the adapter into the witness of its own behavior: a log the adapter keeps is the adapter's testimony, while a log the harness keeps is independent of it, which matters when the Licensor reproduces a run for certification. And `call_log` is not in the substrate Protocol, so relying on it is an unwritten requirement.

**Add `call_log` to the substrate Protocol.** This makes the requirement explicit, but clause 2 calls the Protocol frozen, and the attribute adds a bookkeeping duty to every runtime for a property the harness can observe on its own. Rejected.

**Keep the PR #17 skip.** Simple and already shipped on that branch. Rejected as the end state because it tests real runtimes less than the mock and leaves the fleet lane broken.

**Record inside `URMLRuntime` instead of the harness.** The runtime could wrap its adapter and fill `RuntimeResult.audit_log` from the proxy, which would also fix `audit_log` for users outside conformance. But conformance must hold for third-party runtimes that are not `URMLRuntime`, so the harness has to record either way. The runtime-side change is listed as an unresolved question rather than folded in.

## Prior art

- The goal-line lane (c7dec9b; RFC-0701 §6, a Draft, proposes making it normative) already records calls through `RecordingAdapter` and judges a runtime by what the proxy saw. This RFC applies the same mechanism to accepted fixtures.
- Test doubles in general split into mocks that record calls and real collaborators that do not. Recording at the boundary, as a spy or proxy around the real collaborator, is the standard way to assert call sequences without changing the collaborator.
- The PX4 SITL work (2026-09-27 run records) reached the same principle from the other side: confirm behavior with a witness that does not steer, rather than trusting the adapter's own acknowledgements.

## Unresolved questions

1. **Spec version.** Does the clause-6 sentence ship as conformance v0.2.1, or as an erratum to v0.2.0? It describes how the suite already measures the goal line, and it removes no obligation, which argues for an erratum. It also changes which runtimes pass, which argues for a version.
2. **Arguments.** The proxy records arguments, not only method names. Should fixtures be able to pin arguments (for example, the navigation goal's pose)? This RFC compares names only, as today.
3. **`RuntimeResult.audit_log` on real substrates.** `URMLRuntime` builds `audit_log` from `call_log`, so it is empty on every real adapter. Recording in the runtime would fix that for production users. That is a runtime-surface change and belongs in its own RFC, if wanted.

## Implementation note

One pull request after this RFC is accepted, on top of PR #17:

1. Move `RecordingAdapter` and `RecordedCall` to `recording.py`; re-export from `goal_line.py`.
2. Wrap adapters in `ConformanceRunner` (single and fleet), compare against the proxy, remove the PR #17 skip.
3. Update the field descriptions, `CONFORMANCE_KIT.md` and the clause-6 sentence.
4. Tests as listed above, plus the measurement re-run in CI as a test (proxy record equals the mock's `call_log` on every audit-pinned fixture).
5. Re-run `gazebo-e2e` on the live TurtleBot 4 sim, where `home/nav_patrol_positive` should pass with the audit check active.

The founder merges. A `urml-conformance` release follows.

## Self-review (Phase 0)

- [x] The Summary alone tells a reader what is being proposed.
- [x] The Motivation is grounded in a concrete use case, not hypothetical needs.
- [x] The Detailed design names every affected spec document and reference component.
- [x] At least one alternative is genuinely considered (not a strawman).
- [x] Drawbacks are listed; at least one of them is a real downside, not a humblebrag.
- [x] Backward compatibility is honest about what breaks.
- [x] If this RFC adds a Layer-2 primitive, both ROS-2 and non-ROS implementation sketches are present (substrate-neutrality acid test). Not applicable: no primitive is added, and the proxy works on any adapter, ROS or not.
- [x] The implementation note explains how this lands, not just what.
- [x] The author has re-read [`CLAUDE.md`](../../CLAUDE.md) §What Claude Should Never Do and confirmed this proposal does not violate it.
