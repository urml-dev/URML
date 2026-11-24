"""Vda5050Adapter: URML primitives to VDA 5050 orders, as the fleet control.

VDA 5050 is the open interface between a fleet control and mobile robots
(MIT-licensed, maintained by VDA / VDMA). In it, the fleet control owns
the route graph and sends each vehicle ``order`` messages (a node-edge
path with actions on it); the vehicle reports progress on ``state``. This
adapter plays the fleet-control role for one vehicle: every dispatch
step becomes one order, and the step succeeds only when the vehicle's
own state says the order ran to the end and every action FINISHED.

**No ROS 2 dependency** and no cloud: MQTT goes to whatever broker the
deployment names, usually on the site network. The URML runtime calls
this adapter only after the validator has passed the program against
the manifest and envelope. Nothing here is a path around that check.

## Method coverage

- ``move_to`` -> an order along the shortest configured route from the
  vehicle's ``lastNodeId`` to the location's node. URML ``speed`` caps
  every edge's ``maximumSpeed``.
- ``dock`` -> an order to the station, ending in the service's action
  (``charge`` -> ``startCharging``; ``park`` -> none). ``until: full``
  waits for ``powerSupply.stateOfCharge``.
- ``grasp`` / ``release`` -> ``pick`` / ``drop`` at the current node,
  with the node's ``stationName`` / ``stationType`` and the held
  object's class as ``loadType``.
- ``detect`` -> ``detectObject`` at the current node, when the vehicle
  declares it. ``pick_from`` composes detect + grasp, so it needs it too
  (recorded in SPEC-GAPS.md).
- ``measure`` -> a fresh ``state``: battery charge, voltage, current,
  position.
- ``call_program`` -> a configured vendor action (RFC-0015).
- ``wait`` -> local sleep; ``report`` -> local record (no cloud).

Returned as not supported: ``wait_for`` (the vehicle interface carries
no external events), ``scan``, ``capture``, ``speak``, ``listen``. The
drone trio is ``not_applicable_vda5050``.

When an order does not finish within ``order_timeout_seconds`` the
adapter sends ``cancelOrder`` before reporting the failure, so the
vehicle never keeps driving an order the program has given up on.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable, Iterable
from typing import Any, Literal

from urml_ros2_runtime.substrate.base import (
    CaptureResult,
    DetectionResult,
    ListenResult,
    ManipulationResult,
    MeasurementResult,
    NavigationResult,
    ProgramCallResult,
    ScanResult,
    SubstrateResult,
    WaitResult,
)

from urml_vda5050_runtime.config import EdgeSpec, Vda5050Config
from urml_vda5050_runtime.messages import (
    Action,
    MessageFactory,
    action_status,
    blocking_errors,
    describe_error,
    errors_referencing,
    is_idle,
)
from urml_vda5050_runtime.transport import PahoTransport, Transport, _require_paho

_NOT_SUPPORTED = (
    "not_supported_on_vda5050: the VDA 5050 vehicle interface has no {capability}. "
    "Pair the vehicle with a companion adapter; the URML program, manifest and validator are unchanged."
)
_NOT_APPLICABLE = "not_applicable_vda5050: {capability} has no meaning for a ground mobile robot."
_ORDER_MODES = frozenset({"AUTOMATIC", "SEMIAUTOMATIC", "INTERVENED"})


class _OrderOutcome:
    def __init__(self, ok: bool, reason: str | None, state: dict[str, Any] | None) -> None:
        self.ok = ok
        self.reason = reason
        self.state = state or {}


class Vda5050Adapter:
    """Fleet-control-side VDA 5050 adapter implementing the URML ROSAdapter Protocol."""

    BRAND = "vda5050"

    def __init__(
        self,
        config: Vda5050Config,
        transport: Transport | None = None,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if transport is None:
            _require_paho()  # fail at construction, with the install hint, not mid-program
        self._config = config
        self._transport = transport
        self._sleep = sleep
        self._factory = MessageFactory(config)
        self._cond = threading.Condition()
        self._state: dict[str, Any] | None = None
        self._connection_state: str | None = None
        self._connected = False
        self._reports: list[dict[str, Any]] = []
        self._closed = False

    # ------------------------------------------------------------------
    # Connection and state
    # ------------------------------------------------------------------

    def _topic(self, name: str) -> str:
        return f"{self._config.topic_prefix}/{name}"

    def _on_state(self, _topic: str, payload: dict[str, Any]) -> None:
        with self._cond:
            self._state = payload
            self._cond.notify_all()

    def _on_connection(self, _topic: str, payload: dict[str, Any]) -> None:
        with self._cond:
            self._connection_state = payload.get("connectionState")
            self._cond.notify_all()

    def _connect(self) -> None:
        if self._connected:
            return
        if self._transport is None:
            self._transport = PahoTransport(
                self._config.broker_host,
                self._config.broker_port,
                client_id=f"urml-fleet-{self._config.serial_number}",
            )
        self._transport.subscribe(self._topic("state"), self._on_state)
        self._transport.subscribe(self._topic("connection"), self._on_connection)
        self._connected = True

    def _publish(self, name: str, payload: dict[str, Any]) -> None:
        assert self._transport is not None
        self._transport.publish(self._topic(name), payload)

    def _wait(self, predicate: Callable[[dict[str, Any]], bool], timeout: float) -> dict[str, Any] | None:
        """Block until the latest state satisfies ``predicate``; ``None`` on timeout."""
        deadline = time.monotonic() + timeout
        with self._cond:
            while True:
                if self._state is not None and predicate(self._state):
                    return dict(self._state)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._cond.wait(remaining)

    def _fresh_state(self) -> dict[str, Any] | None:
        """Ask for a state message (``stateRequest``) and return the reply."""
        self._connect()
        action_id = self._new_id("state")
        self._publish("instantActions", self._factory.instant_actions([Action("stateRequest", action_id, "NONE")]))
        reply = self._wait(
            lambda s: action_status(s, action_id, instant=True) is not None, self._config.state_timeout_seconds
        )
        if reply is None:
            # Not every vehicle echoes stateRequest; any state it has sent will do.
            with self._cond:
                return dict(self._state) if self._state is not None else None
        return reply

    @staticmethod
    def _new_id(kind: str) -> str:
        return f"urml-{kind}-{uuid.uuid4().hex[:12]}"

    def close(self) -> None:
        if self._closed:
            return
        if self._transport is not None:
            self._transport.close()
        self._closed = True

    def __enter__(self) -> Vda5050Adapter:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Order execution
    # ------------------------------------------------------------------

    def _preflight(self) -> tuple[str | None, str | None]:
        """Return ``(current_location, None)`` or ``(None, failure_reason)``."""
        state = self._fresh_state()
        if state is None:
            return None, (
                f"vehicle_silent: no state message from {self._config.topic_prefix} within "
                f"{self._config.state_timeout_seconds:g}s."
            )
        if self._connection_state in ("OFFLINE", "CONNECTION_BROKEN", "HIBERNATING"):
            return None, f"vehicle_not_connected: connection state is {self._connection_state}."
        mode = state.get("operatingMode")
        if mode not in _ORDER_MODES:
            return None, f"vehicle_not_available: operating mode is {mode}, which accepts no orders."
        stop = (state.get("safetyState") or {}).get("activeEmergencyStop", "NONE")
        if stop != "NONE":
            return None, f"vehicle_emergency_stop: activeEmergencyStop is {stop}."
        # Errors that reference an orderId describe a rejected order and clear when the next
        # order is accepted (section 6.6.5.4), so only the others block a new order.
        blocking = [
            e
            for e in blocking_errors(state)
            if not any(r.get("referenceKey") == "orderId" for r in e.get("errorReferences") or [])
        ]
        if blocking:
            return None, "vehicle_error: " + "; ".join(describe_error(e) for e in blocking)
        if not is_idle(state):
            return None, f"vehicle_busy: order {state.get('orderId')!r} is still running."
        here = self._config.location_for_node_id(str(state.get("lastNodeId", "")))
        if here is None:
            return None, (
                f"vehicle_position_unknown: lastNodeId {state.get('lastNodeId')!r} is not a configured node. "
                "Localize the vehicle on the route graph (initializePosition) first."
            )
        return here, None

    def _run_order(
        self,
        *,
        start: str,
        route: list[tuple[str, EdgeSpec]],
        actions: Iterable[Action] = (),
        speed: float | None = None,
    ) -> _OrderOutcome:
        actions = list(actions)
        order_id = self._new_id("order")
        goal = route[-1][0] if route else start
        goal_node_id = self._config.nodes[goal].node_id
        self._publish(
            "order", self._factory.order(order_id=order_id, start=start, route=route, end_actions=actions, speed=speed)
        )

        def settled(state: dict[str, Any]) -> bool:
            if errors_referencing(state, "orderId", order_id):
                return True  # rejected
            if state.get("orderId") != order_id:
                return False
            return bool(blocking_errors(state)) or is_idle(state)

        state = self._wait(settled, self._config.order_timeout_seconds)
        if state is None:
            self._cancel(order_id)
            return _OrderOutcome(
                False,
                f"order_timeout: order {order_id} did not finish within "
                f"{self._config.order_timeout_seconds:g}s; cancelOrder sent.",
                None,
            )
        rejected = errors_referencing(state, "orderId", order_id)
        if rejected and state.get("orderId") != order_id:
            return _OrderOutcome(False, "order_rejected: " + "; ".join(describe_error(e) for e in rejected), state)
        blocking = blocking_errors(state)
        if blocking and not is_idle(state):
            self._cancel(order_id)
            return _OrderOutcome(
                False, "vehicle_error: " + "; ".join(describe_error(e) for e in blocking) + "; cancelOrder sent.", state
            )
        for action in actions:
            entry = action_status(state, action.action_id) or {}
            if entry.get("actionStatus") != "FINISHED":
                detail = entry.get("actionResult") or entry.get("actionStatus") or "not reported"
                return _OrderOutcome(False, f"action_failed: {action.action_type} ({detail}).", state)
        if state.get("lastNodeId") != goal_node_id:
            return _OrderOutcome(
                False,
                f"goal_not_reached: order ended at node {state.get('lastNodeId')!r}, expected {goal_node_id!r}.",
                state,
            )
        return _OrderOutcome(True, None, state)

    def _cancel(self, order_id: str) -> None:
        cancel = Action("cancelOrder", self._new_id("cancel"), "NONE", {"orderId": order_id})
        self._publish("instantActions", self._factory.instant_actions([cancel]))

    def _action_here(
        self,
        action_type: str,
        parameters: dict[str, Any],
        *,
        at_station: bool = False,
        expect_at: str | None = None,
    ) -> tuple[_OrderOutcome, str | None]:
        """Run one action at the node the vehicle stands on. Returns (outcome, location).

        ``at_station`` adds the node's stationName / stationType (pick, drop).
        ``expect_at`` refuses to act anywhere but that location.
        """
        if not self._config.supports(action_type):
            return (
                _OrderOutcome(
                    False,
                    f"action_not_supported_by_vehicle: {action_type!r} is not in supported_actions "
                    "(the vehicle factsheet's agvActions).",
                    None,
                ),
                None,
            )
        here, reason = self._preflight()
        if here is None:
            return _OrderOutcome(False, reason, None), None
        if expect_at is not None and here != expect_at:
            return (
                _OrderOutcome(
                    False, f"location_mismatch: expected the vehicle at {expect_at!r}, it is at {here!r}.", None
                ),
                here,
            )
        params = dict(parameters)
        if at_station:
            node = self._config.nodes[here]
            params.setdefault("stationName", node.station_name or here)
            if node.station_type:
                params.setdefault("stationType", node.station_type)
        action = Action(action_type, self._new_id("action"), "HARD", params)
        return self._run_order(start=here, route=[], actions=[action]), here

    def _final_pose(self, state: dict[str, Any]) -> dict[str, float] | None:
        position = state.get("mobileRobotPosition")
        if not isinstance(position, dict):
            return None
        return {k: float(position[k]) for k in ("x", "y", "theta") if k in position}

    # ------------------------------------------------------------------
    # Supported
    # ------------------------------------------------------------------

    def send_navigation_goal(
        self,
        *,
        location: str | None = None,
        pose: dict[str, float] | None = None,
        frame: str | None = None,
        carrying: dict[str, Any] | None = None,
        speed: float | None = None,
    ) -> NavigationResult:
        if location is None:
            return NavigationResult(
                success=False,
                reason="vda5050_requires_named_location: VDA 5050 vehicles drive between route-graph "
                "nodes; a raw pose goal has no node to send.",
            )
        if location not in self._config.nodes:
            return NavigationResult(
                success=False,
                reason=f"location_not_configured: {location!r} is declared in the manifest but is not "
                "a node in vda5050_adapter.yaml.",
            )
        here, reason = self._preflight()
        if here is None:
            return NavigationResult(success=False, reason=reason)
        route = self._config.route(here, location)
        if route is None:
            return NavigationResult(
                success=False, reason=f"no_route: no configured edges lead from {here!r} to {location!r}."
            )
        if not route:
            state = self._fresh_state() or {}
            return NavigationResult(success=True, final_pose=self._final_pose(state), frame=self._config.map_id)
        outcome = self._run_order(start=here, route=route, speed=speed)
        if not outcome.ok:
            return NavigationResult(success=False, reason=outcome.reason)
        return NavigationResult(success=True, final_pose=self._final_pose(outcome.state), frame=self._config.map_id)

    def send_docking_goal(self, *, station: str, service: str, until: str | None = None) -> NavigationResult:
        target = self._config.primary_dock if station == "primary" else station
        if target is None or target not in self._config.nodes:
            return NavigationResult(
                success=False,
                reason=f"station_not_configured: dock station {station!r} is not a node in "
                "vda5050_adapter.yaml (set primary_dock for a dock without `at:`).",
            )
        if service not in self._config.dock_services:
            return NavigationResult(
                success=False,
                reason=f"service_not_configured: dock service {service!r} has no entry in dock_services.",
            )
        action_type = self._config.dock_services[service]
        if until is not None and not (until == "full" and action_type == "startCharging"):
            return NavigationResult(
                success=False,
                reason=f"until_not_supported: this adapter supports `until: full` on a charging service "
                f"only, not {until!r} on {service!r}.",
            )
        if action_type is not None and not self._config.supports(action_type):
            return NavigationResult(
                success=False,
                reason=f"action_not_supported_by_vehicle: {action_type!r} is not in supported_actions.",
            )
        here, reason = self._preflight()
        if here is None:
            return NavigationResult(success=False, reason=reason)
        route = self._config.route(here, target)
        if route is None:
            return NavigationResult(
                success=False, reason=f"no_route: no configured edges lead from {here!r} to {target!r}."
            )
        actions = [Action(action_type, self._new_id("action"), "HARD")] if action_type else []
        if not route and not actions:
            state = self._fresh_state() or {}
            return NavigationResult(success=True, final_pose=self._final_pose(state), frame=self._config.map_id)
        outcome = self._run_order(start=here, route=route, actions=actions)
        if not outcome.ok:
            return NavigationResult(success=False, reason=outcome.reason)
        if until == "full":
            full = self._config.full_charge_percent

            def charged(state: dict[str, Any]) -> bool:
                power = state.get("powerSupply") or {}
                return float(power.get("stateOfCharge", 0.0)) >= full or not power.get("charging", False)

            charged_state = self._wait(charged, self._config.charge_timeout_seconds)
            soc = float(((charged_state or {}).get("powerSupply") or {}).get("stateOfCharge", 0.0))
            if charged_state is None or soc < full:
                return NavigationResult(
                    success=False,
                    reason=f"charge_incomplete: charging ended or timed out at {soc:g}% (full is {full:g}%).",
                )
        return NavigationResult(success=True, final_pose=self._final_pose(outcome.state), frame=self._config.map_id)

    def send_manipulation_goal(
        self,
        *,
        action: Literal["grasp", "release"],
        target: dict[str, Any] | None = None,
        force_n: float | None = None,
        approach: Literal["top", "side", "front", "auto"] = "auto",
        release_mode: Literal["drop", "place", "hand_to_user"] | None = None,
        release_at: dict[str, Any] | str | None = None,
        arm: str | None = None,
        grasp_type: str | None = None,
        target_motion: str | None = None,
    ) -> ManipulationResult:
        if release_mode == "hand_to_user":
            return ManipulationResult(success=False, reason=_NOT_SUPPORTED.format(capability="hand-over to a person"))
        action_type = "pick" if action == "grasp" else "drop"
        params: dict[str, Any] = {}
        if isinstance(target, dict) and target.get("class"):
            params["loadType"] = str(target["class"])
        outcome, _ = self._action_here(action_type, params, at_station=True)
        return ManipulationResult(success=outcome.ok, reason=outcome.reason)

    def query_detection(
        self,
        *,
        object_class: str,
        attributes: dict[str, Any] | None = None,
        where_near: str | None = None,
        where_within: float | None = None,
    ) -> DetectionResult:
        if not self._config.supports("detectObject"):
            return DetectionResult(
                success=False,
                reason="action_not_supported_by_vehicle: detection needs the detectObject action, which "
                "this vehicle does not declare. pick_from composes detect + grasp, so it needs it too "
                "(see SPEC-GAPS.md).",
            )
        outcome, here = self._action_here("detectObject", {"objectType": object_class}, expect_at=where_near)
        if not outcome.ok:
            return DetectionResult(success=False, reason=outcome.reason)
        return DetectionResult(
            success=True,
            payload={
                "class": object_class,
                # detectObject reports no object pose; the vehicle's own pose at the station is the
                # best location the interface gives. No confidence is reported either.
                "pose": self._final_pose(outcome.state) or {},
                "frame": self._config.map_id,
                "attributes": attributes or {},
                "confidence": None,
                "station": here,
            },
        )

    def take_measurement(self, *, what: str, target: str | None, sensor: str | None) -> MeasurementResult:
        state = self._fresh_state()
        if state is None:
            return MeasurementResult(success=False, reason="vehicle_silent: no state message to read.")
        power = state.get("powerSupply") or {}
        readings: dict[str, tuple[Any, str]] = {
            "battery": (power.get("stateOfCharge"), "percent"),
            "state_of_charge": (power.get("stateOfCharge"), "percent"),
            "voltage": (power.get("batteryVoltage"), "V"),
            "current": (power.get("batteryCurrent"), "A"),
            "position": (state.get("mobileRobotPosition"), self._config.map_id),
        }
        value, unit = readings.get(what, (None, ""))
        if value is None:
            return MeasurementResult(
                success=False,
                reason=f"measurement_not_reported: the vehicle state carries no {what!r} reading. "
                f"Readable: {', '.join(readings)}.",
            )
        return MeasurementResult(
            success=True, payload={"value": value, "unit": unit, "timestamp": state.get("timestamp"), "what": what}
        )

    def call_named_program(self, *, name: str, args: dict[str, Any] | None = None) -> ProgramCallResult:
        """``call_program``: run a configured vendor action in place (RFC-0015).

        VDA 5050 lets each manufacturer add actions beyond the predefined
        set (section 6.2.3) and list them in the factsheet. A manifest-
        declared program name resolves to one of those actions in
        ``program_to_action``; ``call_program`` args are appended to its
        fixed parameters. The action's ``actionResult`` is the payload.
        """
        spec = self._config.program_to_action.get(name)
        if spec is None:
            return ProgramCallResult(
                success=False,
                reason=f"program_not_configured: program {name!r} is not mapped to a vehicle action "
                "in vda5050_adapter.yaml (program_to_action).",
            )
        outcome, _ = self._action_here(spec.action_type, {**spec.parameters, **(args or {})})
        if not outcome.ok:
            return ProgramCallResult(success=False, reason=outcome.reason)
        result = None
        for entry in outcome.state.get("actionStates", []):
            if entry.get("actionType") == spec.action_type and entry.get("actionResult") is not None:
                result = entry["actionResult"]
        return ProgramCallResult(success=True, payload=None if result is None else {"value": result})

    def wait_passively(self, *, duration_seconds: float) -> SubstrateResult:
        # Between orders a VDA 5050 vehicle holds at its last node by itself.
        if duration_seconds > 0:
            self._sleep(duration_seconds)
        return SubstrateResult(success=True)

    def emit_report(
        self,
        *,
        to: str,
        facts: dict[str, Any],
        attachments: list[str] | None,
        status: Literal["success", "partial", "failure"],
        severity: Literal["info", "notice", "warning", "error"],
    ) -> SubstrateResult:
        self._reports.append({"to": to, "status": status, "severity": severity, "facts": facts})
        return SubstrateResult(success=True)

    # ------------------------------------------------------------------
    # Not supported by the vehicle interface
    # ------------------------------------------------------------------

    def wait_for_condition(
        self,
        *,
        kind: Literal["event", "signal", "input", "sensor_threshold"],
        name: str | None,
        input_mode: str | None,
        threshold: dict[str, Any] | None,
        timeout_seconds: float | None,
    ) -> WaitResult:
        return WaitResult(
            success=False,
            reason=_NOT_SUPPORTED.format(capability=f"source for {kind} conditions")
            + " A fleet-level runtime that sees the other robots can resolve wait_for events.",
        )

    def run_scan(
        self,
        *,
        area: dict[str, Any],
        pattern: Literal["serpentine", "spiral", "grid", "adaptive"],
        overlap: float,
        altitude: float | None,
        media: Literal["photo", "video", "sensor_only"],
        sensor: str | None,
    ) -> ScanResult:
        return ScanResult(success=False, reason=_NOT_SUPPORTED.format(capability="area-scan controller"))

    def capture_media(
        self,
        *,
        media: Literal["photo", "video"],
        target: str | None,
        duration_seconds: float | None,
        attributes: dict[str, Any] | None,
        camera: str | None = None,
    ) -> CaptureResult:
        return CaptureResult(success=False, reason=_NOT_SUPPORTED.format(capability="recordable camera"))

    def emit_speech(
        self,
        *,
        utterance: str,
        locale: str | None,
        style: Literal["notice", "warning", "conversational"],
        interrupt: bool,
    ) -> SubstrateResult:
        return SubstrateResult(success=False, reason=_NOT_SUPPORTED.format(capability="speaker"))

    def acquire_speech(
        self,
        *,
        prompt: str | None,
        locale: str | None,
        timeout_seconds: float | None,
        expected: Literal["free_form", "confirmation", "choice"],
        choices: list[str] | None,
    ) -> ListenResult:
        return ListenResult(success=False, reason=_NOT_SUPPORTED.format(capability="microphone"))

    def send_takeoff_goal(self, *, altitude: float, climb_rate: float | None = None) -> NavigationResult:
        return NavigationResult(success=False, reason=_NOT_APPLICABLE.format(capability="take_off"))

    def send_land_goal(
        self,
        *,
        at: str | None = None,
        precision: Literal["standard", "precise"] = "standard",
    ) -> NavigationResult:
        return NavigationResult(success=False, reason=_NOT_APPLICABLE.format(capability="land"))

    def send_return_to_home_goal(
        self,
        *,
        speed: float | None = None,
        altitude: float | None = None,
    ) -> NavigationResult:
        return NavigationResult(success=False, reason=_NOT_APPLICABLE.format(capability="return_to_home"))
