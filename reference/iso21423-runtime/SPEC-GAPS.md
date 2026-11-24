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

# SPEC-GAPS: urml-iso21423-runtime

Per the spec-gap protocol (RFC-0014), this runtime is built against the frozen substrate Protocol. Where ISO 21423 and URML do not line up, the mismatch is recorded here, not patched over in the adapter.

## 0. Validation against the published standard (in progress)

The runtime is built from public material based on the ISO/FDIS 21423 draft. We are validating it against the published ISO 21423:2026. The check needs a licensed copy of the standard and covers: topic layout, every message field the adapter sends or reads, the request and per-action state machines, the rejection reasons, the session rules (persistent session, 60 s keep-alive, the `disconnection` will) and the action vocabulary. Each difference is fixed in the adapter or recorded below. Until it is done the runtime makes no claim of conformance.

## 1. `pick_from` needs a detection action

`pick_from` composes navigate, `detect` and `grasp` (RFC-0013). The ISO 21423 request model, as described publicly, has no detection action, so `pick_from` fails at the detect step. The adapter does not fake a detection. This is the same gap as in the VDA 5050 runtime; the options recorded there apply here.

## 2. A move request carries no speed

URML's `speed` on `move_to` is a limit. The ISO 21423 `move` action, as described publicly, has a destination, tolerances and an optional arrival time, but no speed. The adapter runs such a step only when the robot's rated speed, from its identity, is already within the limit, and refuses it otherwise. An arrival time computed from distance and speed would be a request, not a limit, so it is not used.

## 3. Grasp and release go through `dock`

The standard request model offers PICK and DROP as station actions of `dock`, not as actions of their own. The adapter therefore picks and drops only at a configured dock. A robot with a manipulator that picks from arbitrary places needs a vendor action (`call_program`) or a URML change.

## 4. `wait_for` events have no source

As with VDA 5050: an event such as `partner_ready` is not something the robot's interface publishes. A fleet-level runtime that sees the other robots can resolve it.

## 5. Fleet dispatch is not used

ISO 21423 lets a requester send a request with an empty destination to a fleet manager, which picks the robot. URML programs address one robot through its manifest, so the adapter always names the destination.

## 6. The Common Coordinate System is configured, not calibrated

The adapter takes the CCS id and each place's coordinates from its config. It does not compute the transform from reference points or publish the CCS.
