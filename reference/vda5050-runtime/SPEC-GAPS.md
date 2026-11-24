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

# SPEC-GAPS: urml-vda5050-runtime

Per the spec-gap protocol (RFC-0014), this runtime is built against the frozen substrate Protocol. Where VDA 5050 and URML do not line up, the mismatch is recorded here for a maintainer decision, not patched over in the adapter. None of these is filed as an RFC yet.

## 1. `pick_from` needs `detectObject`

`pick_from` is composed in the runtime as navigate, then `detect`, then `grasp` (RFC-0013). On a VDA 5050 vehicle the `pick` action locates the load itself; many vehicles do not offer a separate `detectObject`. On such a vehicle `pick_from` fails at the detect step with `action_not_supported_by_vehicle`, though the vehicle could do the pick.

The adapter does not fake the detection to keep `pick_from` working. A detection result with no detection behind it would put an invented object in the program's bindings.

**Options for a decision:** (a) leave it, and document that `pick_from` on VDA 5050 needs `detectObject`; (b) let an adapter declare that its grasp includes detection, so `pick_from` skips the separate detect (a substrate Protocol change, RFC-0014); (c) have the `pick_from` executor fall back to grasp-only when detection is not supported, binding a result marked unverified.

## 2. `wait_for` events have no source

The warehouse profile's handoff pattern (RFC-0022) uses `wait_for: { event: partner_ready }`. In VDA 5050 the fleet control is the party that knows a partner is ready; the vehicle interface carries no such events, so the adapter returns `not_supported_on_vda5050`. The fleet runtime (`urml_ros2_runtime.fleet`) is the natural place to resolve cross-robot events. This is a gap in which layer resolves events, not in the primitive.

## 3. One order per dispatch step

Each URML step becomes its own fully released order with no horizon. VDA 5050's order updates (extending the base while the vehicle drives) would let a `move_to` followed by `place_at` run without a stop between them, and would let a traffic manager hold the horizon. The Protocol dispatches one step at a time and has no look-ahead, so the adapter cannot stitch steps into one order. Deliberately out of scope for v0.1; traffic management belongs to a fleet manager.

## 4. The factsheet is not read

`supported_actions` is configured by hand from the vehicle's factsheet. The adapter could request the factsheet (`factsheetRequest`) and check the config against it, or a tool could generate the URML manifest's capability blocks from it. Not built yet.

## Upstream: VDA 5050 3.0.0 schemas (resolved)

The `order`, `factsheet` and `visualization` schemas at tag `3.0.0` contain trailing commas and do not parse. This was already reported upstream ([VDA5050/VDA5050#660](https://github.com/VDA5050/VDA5050/issues/660)) and fixed on `main` ([#599](https://github.com/VDA5050/VDA5050/pull/599)). The core team will not re-release the schemas: they live on the branch, not in releases. The test fixtures are therefore copied unmodified from `main` at a pinned commit ([`tests/vda5050_schemas/README.md`](tests/vda5050_schemas/README.md)).

## ISO 21423:2026

ISO 21423:2026 (Robotics, Industrial mobile robots, Communications and interoperability) is implemented separately, in [`reference/iso21423-runtime/`](../iso21423-runtime/), because its request model differs from VDA 5050's orders. That runtime is built from public material based on the ISO/FDIS 21423 draft; its validation against the published standard is in progress, and it makes no conformance claim until that is done.
