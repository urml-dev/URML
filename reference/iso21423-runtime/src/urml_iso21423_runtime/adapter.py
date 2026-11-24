"""Iso21423Adapter: URML primitives as ISO 21423 requests to a mobile robot.

STATUS: built from public material based on the ISO/FDIS 21423 draft, not
from the published ISO 21423:2026 text. We are validating it against the
published standard; until that is done, this adapter makes no claim of
conformance to ISO 21423. See the package README.

ISO 21423 (Robotics, Industrial mobile robots, Communications and
interoperability) lets robots, fleet managers and site equipment from
different vendors share one MQTT channel. Every participant is an entity
that publishes its identity and status, and any entity may send another a
request: an ordered list of actions such as ``move`` or ``dock``, answered
by request status messages until it SUCCEEDED, was CANCELED or ABORTED.

This adapter is such an entity. It sends each URML dispatch step as one
request, to the robot itself or to the fleet manager that manages it, and a
step succeeds only when the robot's own request status says SUCCEEDED for
every action. The URML runtime calls it only after the validator has
accepted the program. No ROS, no cloud.

## Method coverage

- ``move_to`` -> a ``move`` request to the place's point in the facility's
  Common Coordinate System. A URML ``speed`` has no field in a move
  request, so a step that asks for one runs only when the robot's rated
  speed is already within it.
- ``dock`` -> a ``dock`` request with the service's station actions
  (``charge`` -> CHARGE; ``park`` -> none). ``until: full`` waits on
  ``batteryStatus``.
- ``grasp`` / ``release`` -> a ``dock`` request with PICK / DROP at the
  station the robot is at.
- ``measure`` -> battery charge, voltage, current and position from what
  the robot publishes.
- ``call_program`` -> a configured vendor action (RFC-0015).
- ``wait`` -> local sleep; ``report`` -> local record.

Returned as not supported: ``detect`` (no detection action in the request
model, so ``pick_from`` cannot run; SPEC-GAPS.md), ``wait_for``, ``scan``,
``capture``, ``speak``, ``listen``. The drone trio is
``not_applicable_iso21423``.

Before a request it refuses to send if the robot has not announced itself,
does not accept the action, is not in an automatic mode, reports a stop,
LOST or OFFLINE, or has dropped off the broker. A request that does not
finish within ``request_timeout_seconds`` is canceled before the failure is
reported.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
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

from urml_iso21423_runtime import messages as m
from urml_iso21423_runtime.broker import password_from_env
from urml_iso21423_runtime.config import Iso21423Config
from urml_iso21423_runtime.transport import PahoTransport, Transport, Will, _require_paho

_NOT_SUPPORTED = (
    "not_supported_on_iso21423: the ISO 21423 request model has no {capability}. "
    "Pair the robot with a companion adapter; the URML program, manifest and validator are unchanged."
)
_NOT_APPLICABLE = "not_applicable_iso21423: {capability} has no meaning for a ground mobile robot."


class _Outcome:
    def __init__(self, ok: bool, reason: str | None, status: dict[str, Any] | None = None) -> None:
        self.ok = ok
        self.reason = reason
        self.status = status or {}


class Iso21423Adapter:
    """Requester-side ISO 21423 adapter implementing the URML ROSAdapter Protocol."""

    BRAND = "iso21423"

    def __init__(
        self,
        config: Iso21423Config,
        transport: Transport | None = None,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if transport is None:
            _require_paho()
        self._c = config
        self._t = transport
        self._sleep = sleep
        self._requests = m.RequestFactory(config)
        self._cond = threading.Condition()
        self._seen: dict[str, tuple[int, dict[str, Any] | None]] = {}
        self._tick = 0
        self._request_status: dict[str, dict[str, Any]] = {}
        self._connected = False
        self._reports: list[dict[str, Any]] = []
        self._closed = False

    # ------------------------------------------------------------------
    # Connection and what the robot publishes
    # ------------------------------------------------------------------

    def _store(self, key: str) -> Callable[[str, dict[str, Any] | None], None]:
        def handler(_topic: str, payload: dict[str, Any] | None) -> None:
            with self._cond:
                self._tick += 1
                self._seen[key] = (self._tick, payload)
                self._cond.notify_all()

        return handler

    def _on_request_status(self, topic: str, payload: dict[str, Any] | None) -> None:
        if payload is None:
            return
        request_uuid = topic.rstrip("/").split("/")[-2]
        with self._cond:
            self._request_status[request_uuid] = payload
            self._cond.notify_all()

    def _connect(self) -> None:
        if self._connected:
            return
        if self._t is None:
            will = Will(
                self._c.topic(self._c.requester_type, self._c.requester_id, "disconnection"),
                {"states": ["LOST_CONNECTION"]},
            )
            self._t = PahoTransport(
                self._c.broker_host,
                self._c.broker_port,
                client_id=f"urml-{self._c.requester_id}",
                will=will,
                tls=self._c.broker_tls.context() if self._c.broker_tls is not None else None,
                username=self._c.broker_username,
                password=password_from_env(self._c.broker_password_env),
            )
        for key in ("identity", "status", "batteryStatus", "odometry", "disconnection"):
            self._t.subscribe(self._c.robot_topic(key), self._store(key), qos=1)
        if self._c.target_type != "IMR" or self._c.target_id != self._c.executor_id:
            self._t.subscribe(self._c.target_topic("identity"), self._store("target_identity"), qos=1)
        self._t.subscribe(self._c.target_topic("request/+/status"), self._on_request_status, qos=2)
        self._t.publish(
            self._c.topic(self._c.requester_type, self._c.requester_id, "identity"),
            m.requester_identity(self._c),
            qos=1,
            retain=True,
        )
        self._connected = True

    def _latest(self, key: str) -> dict[str, Any] | None:
        with self._cond:
            entry = self._seen.get(key)
        return None if entry is None else entry[1]

    def _wait(self, predicate: Callable[[], bool], timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        with self._cond:
            while not predicate():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._cond.wait(remaining)
            return True

    def close(self) -> None:
        if self._closed:
            return
        if self._t is not None:
            self._t.close()
        self._closed = True

    def __enter__(self) -> Iso21423Adapter:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Checks and request execution
    # ------------------------------------------------------------------

    def _offline(self) -> bool:
        with self._cond:
            lost = self._seen.get("disconnection")
            if lost is None or lost[1] is None or "LOST_CONNECTION" not in (lost[1].get("states") or []):
                return False
            later = [self._seen[k][0] for k in ("identity", "status") if k in self._seen]
            return not later or max(later) < lost[0]

    def _preflight(self, action_types: set[str], *, moving: bool) -> str | None:
        self._connect()
        # identity and status are both retained, but on a real broker they arrive one after the other.
        needed = ("identity", "status") if moving else ("identity",)
        if not self._wait(lambda: all(k in self._seen for k in needed), self._c.state_timeout_seconds):
            missing = [k for k in needed if k not in self._seen]
            return (
                f"robot_not_announced: no {' or '.join(missing)} from {self._c.robot_topic(missing[0])} within "
                f"{self._c.state_timeout_seconds:g}s."
            )
        if self._offline():
            return "robot_offline: the broker published the robot's LOST_CONNECTION will."
        identity_key = "target_identity" if "target_identity" in self._seen else "identity"
        accepted = m.accepted_requests(self._latest(identity_key))
        missing = sorted(action_types - accepted)
        if missing:
            return (
                f"action_not_accepted: the {'fleet manager' if identity_key == 'target_identity' else 'robot'} "
                f"does not accept {', '.join(missing)} (its identity lists {', '.join(sorted(accepted)) or 'none'})."
            )
        status = self._latest("status")
        if moving:
            current_mode = m.mode(status)
            if current_mode not in m.AUTO_MODES:
                return f"robot_not_available: operating mode is {current_mode or 'not reported'}."
            blocked = m.blocking_states(status)
            if blocked:
                return f"robot_not_available: the robot reports {', '.join(blocked)}."
        return None

    def _send(self, details: list[dict[str, Any]]) -> _Outcome:
        assert self._t is not None
        request = self._requests.request(details)
        request_uuid = str(uuid.uuid4())
        topic = self._c.target_topic(f"request/{request_uuid}")
        self._t.publish(topic, request, qos=2, retain=True)

        def terminal() -> bool:
            status = self._request_status.get(request_uuid)
            return status is not None and status.get("status") in m.TERMINAL

        finished = self._wait(terminal, self._c.request_timeout_seconds)
        if not finished:
            cancel = self._requests.request([m.cancel(self._c.requester_id, request["sequenceId"])])
            cancel_uuid = str(uuid.uuid4())
            cancel_topic = self._c.target_topic(f"request/{cancel_uuid}")
            self._t.publish(cancel_topic, cancel, qos=2, retain=True)
            self._wait(
                lambda: (self._request_status.get(cancel_uuid) or {}).get("status") in m.TERMINAL,
                self._c.state_timeout_seconds,
            )
            self._t.publish(cancel_topic, None, qos=2, retain=True)
            self._t.publish(topic, None, qos=2, retain=True)
            return _Outcome(
                False,
                f"request_timeout: request {request['sequenceId']} did not finish within "
                f"{self._c.request_timeout_seconds:g}s; cancel sent.",
            )
        self._t.publish(topic, None, qos=2, retain=True)  # clear the retained request
        status = self._request_status[request_uuid]
        if status.get("status") == "SUCCEEDED" and not m.failed_details(status):
            return _Outcome(True, None, status)
        reasons = "; ".join(m.failed_details(status)) or status.get("status", "?")
        return _Outcome(False, f"request_{str(status.get('status', '')).lower()}: {reasons}.", status)

    def _here(self) -> str | None:
        odometry = self._latest("odometry") or {}
        point = (odometry.get("pose") or {}).get("locationPoint") or {}
        if point.get("ccsId") != self._c.ccs_id or "x" not in point:
            return None
        return self._c.place_near(float(point["x"]), float(point["y"]))

    def _pose(self) -> dict[str, float] | None:
        odometry = self._latest("odometry") or {}
        pose = odometry.get("pose") or {}
        point = pose.get("locationPoint") or {}
        if "x" not in point:
            return None
        out = {"x": float(point["x"]), "y": float(point["y"])}
        yaw = (pose.get("orientation") or {}).get("yaw")
        if yaw is not None:
            out["theta"] = float(yaw)
        return out

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
                reason="iso21423_requires_named_location: a raw pose has no Common Coordinate System point; "
                "name the place.",
            )
        place = self._c.places.get(location)
        if place is None:
            return NavigationResult(
                success=False,
                reason=f"location_not_configured: {location!r} is not a place in iso21423_adapter.yaml.",
            )
        reason = self._preflight({"move"}, moving=True)
        if reason is not None:
            return NavigationResult(success=False, reason=reason)
        if speed is not None and speed > 0:
            rated = ((self._latest("identity") or {}).get("details") or {}).get("ratedSpeed")
            if rated is None or float(rated) > speed:
                return NavigationResult(
                    success=False,
                    reason=f"speed_not_expressible: an ISO 21423 move request carries no speed limit, and the "
                    f"robot's rated speed ({rated if rated is not None else 'not reported'}) is above the "
                    f"{speed:g} m/s the program asks for.",
                )
        outcome = self._send([m.move(self._c, place)])
        if not outcome.ok:
            return NavigationResult(success=False, reason=outcome.reason)
        return NavigationResult(success=True, final_pose=self._pose(), frame=self._c.ccs_id)

    def send_docking_goal(self, *, station: str, service: str, until: str | None = None) -> NavigationResult:
        name = self._c.primary_dock if station == "primary" else station
        dock_cfg = self._c.docks.get(name) if name is not None else None
        if dock_cfg is None:
            return NavigationResult(
                success=False,
                reason=f"station_not_configured: dock station {station!r} is not in iso21423_adapter.yaml "
                "(set primary_dock for a dock without `at:`).",
            )
        if service not in self._c.dock_services:
            return NavigationResult(
                success=False, reason=f"service_not_configured: dock service {service!r} has no entry in dock_services."
            )
        actions = self._c.dock_services[service]
        if until is not None and not (until == "full" and "CHARGE" in actions):
            return NavigationResult(
                success=False,
                reason=f"until_not_supported: only `until: full` on a charging service is supported, "
                f"not {until!r} on {service!r}.",
            )
        reason = self._preflight({"dock"}, moving=True)
        if reason is not None:
            return NavigationResult(success=False, reason=reason)
        outcome = self._send([m.dock(self._c, self._c.places[dock_cfg.location], dock_cfg.dock_id, actions)])
        if not outcome.ok:
            return NavigationResult(success=False, reason=outcome.reason)
        if until == "full":
            full = self._c.full_charge

            def charged() -> bool:
                battery = (self._seen.get("batteryStatus") or (0, None))[1] or {}
                return float(battery.get("batterySoc", 0.0)) >= full or battery.get("batteryChargingState") == "FULL"

            if not self._wait(charged, self._c.charge_timeout_seconds):
                soc = float((self._latest("batteryStatus") or {}).get("batterySoc", 0.0))
                return NavigationResult(
                    success=False, reason=f"charge_incomplete: batterySoc is {soc:g}, full is {full:g}."
                )
        return NavigationResult(success=True, final_pose=self._pose(), frame=self._c.ccs_id)

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
        reason = self._preflight({"dock"}, moving=True)
        if reason is not None:
            return ManipulationResult(success=False, reason=reason)
        here = self._here()
        station = self._c.dock_at(here) if here is not None else None
        if station is None:
            return ManipulationResult(
                success=False,
                reason=f"not_at_station: ISO 21423 picks and drops through a dock request, and the robot is at "
                f"{here or 'no configured place'}, which is not a configured dock.",
            )
        _name, dock_cfg = station
        dock_action = "PICK" if action == "grasp" else "DROP"
        outcome = self._send([m.dock(self._c, self._c.places[dock_cfg.location], dock_cfg.dock_id, [dock_action])])
        return ManipulationResult(success=outcome.ok, reason=outcome.reason)

    def take_measurement(self, *, what: str, target: str | None, sensor: str | None) -> MeasurementResult:
        self._connect()
        battery = self._latest("batteryStatus") or {}
        odometry = self._latest("odometry") or {}
        soc = battery.get("batterySoc")
        readings: dict[str, tuple[Any, str, Any]] = {
            "battery": (None if soc is None else float(soc) * 100.0, "percent", battery.get("timestamp")),
            "state_of_charge": (None if soc is None else float(soc) * 100.0, "percent", battery.get("timestamp")),
            "voltage": (battery.get("batteryVoltage"), "V", battery.get("timestamp")),
            "current": (battery.get("batteryCurrent"), "A", battery.get("timestamp")),
            "position": ((odometry.get("pose") or {}).get("locationPoint"), self._c.ccs_id, odometry.get("timestamp")),
        }
        value, unit, stamp = readings.get(what, (None, "", None))
        if value is None:
            return MeasurementResult(
                success=False,
                reason=f"measurement_not_reported: the robot has published no {what!r} reading. "
                f"Readable: {', '.join(readings)}.",
            )
        return MeasurementResult(success=True, payload={"value": value, "unit": unit, "timestamp": stamp, "what": what})

    def call_named_program(self, *, name: str, args: dict[str, Any] | None = None) -> ProgramCallResult:
        """``call_program``: send a configured vendor action (RFC-0015).

        ISO 21423 lets vendors define their own action types under their own
        format name. A manifest-declared program resolves to one of those in
        ``program_to_action``; ``call_program`` args are merged into its
        properties.
        """
        spec = self._c.program_to_action.get(name)
        if spec is None:
            return ProgramCallResult(
                success=False,
                reason=f"program_not_configured: program {name!r} is not mapped to a vendor action "
                "in iso21423_adapter.yaml (program_to_action).",
            )
        reason = self._preflight({spec.type}, moving=False)
        if reason is not None:
            return ProgramCallResult(success=False, reason=reason)
        props = {**spec.properties, **(args or {})}
        outcome = self._send([m.detail(spec.type, props, fmt=spec.format, version=spec.version)])
        if not outcome.ok:
            return ProgramCallResult(success=False, reason=outcome.reason)
        message = None
        for entry in outcome.status.get("detailStatuses") or []:
            message = (entry.get("status") or {}).get("message") or message
        return ProgramCallResult(success=True, payload=None if message is None else {"value": message})

    def wait_passively(self, *, duration_seconds: float) -> SubstrateResult:
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
    # Not supported by the request model
    # ------------------------------------------------------------------

    def query_detection(
        self,
        *,
        object_class: str,
        attributes: dict[str, Any] | None = None,
        where_near: str | None = None,
        where_within: float | None = None,
    ) -> DetectionResult:
        return DetectionResult(
            success=False,
            reason=_NOT_SUPPORTED.format(capability="detection action")
            + " pick_from composes detect + grasp, so it cannot run here (see SPEC-GAPS.md).",
        )

    def wait_for_condition(
        self,
        *,
        kind: Literal["event", "signal", "input", "sensor_threshold"],
        name: str | None,
        input_mode: str | None,
        threshold: dict[str, Any] | None,
        timeout_seconds: float | None,
    ) -> WaitResult:
        return WaitResult(success=False, reason=_NOT_SUPPORTED.format(capability=f"source for {kind} conditions"))

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
