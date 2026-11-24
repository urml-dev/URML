"""A minimal simulated ISO 21423 industrial mobile robot (IMR).

It exists so the adapter can be tested, and the demo run, with no robot and
no broker. It is not a vehicle model: travel is instant and charging jumps
to full. It follows the protocol behaviour a requester depends on, as the
public description of the model gives it:

- retained ``identity``, ``status`` and ``batteryStatus``; ``odometry`` after
  every move, and once more whenever a new entity announces itself (a real
  robot streams it, so a newcomer has a pose within a second or two);
- requests on ``request/<uuid>`` answered on ``request/<uuid>/status`` with
  RECEIVED, ACCEPTED, EXECUTING and a terminal state, each detail with its
  own status;
- rejection as ABORTED with a reason: REJECTED (wrong destination),
  INVALID_IMR_STATE_FOR_ACTION (not in an automatic mode),
  ACTION_NOT_IMPLEMENTED, FORMAT_NOT_SUPPORTED;
- ``cancel``, ``pauseImr`` and ``resumeImr``;
- ``drop()``: the broker publishes the robot's Last Will.

``auto_run=False`` makes the robot accept requests but not finish them,
which is how the timeout and cancel paths are tested.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable
from typing import Any

from urml_iso21423_runtime.config import Iso21423Config
from urml_iso21423_runtime.messages import STANDARD_FORMAT, timestamp
from urml_iso21423_runtime.transport import InMemoryBroker, Transport, Will

STANDARD_ACTIONS = ("move", "pauseImr", "resumeImr", "cancel", "dock", "undock")


class SimulatedImr:
    """An IMR on ``transport`` with the UUID ``config.executor_id``."""

    def __init__(
        self,
        transport: Transport,
        config: Iso21423Config,
        *,
        start_at: str,
        accepts: Iterable[str] = STANDARD_ACTIONS,
        vendor_formats: Iterable[str] = (),
        fail_actions: Iterable[str] = (),
        battery_soc: float = 0.8,
        mode: str = "MODE_AUTO",
        rated_speed: float = 1.5,
        auto_run: bool = True,
    ) -> None:
        self._t = transport
        self._c = config
        self.id = config.executor_id
        self.accepts = list(accepts)
        self.vendor_formats = set(vendor_formats)
        self.fail_actions = set(fail_actions)
        self.mode = mode
        self.extra_states: list[str] = ["IDLE"]
        self.rated_speed = rated_speed
        self.auto_run = auto_run
        start = config.places[start_at]
        self.pose = {"x": start.x, "y": start.y, "z": start.z, "yaw": start.yaw or 0.0}
        self.soc = battery_soc
        self.charging = False
        self.load: str | None = None
        self.received: list[dict[str, Any]] = []
        self._status_seq = itertools.count(1)
        self._pending: dict[str, dict[str, Any]] = {}
        self.will = Will(self._topic("disconnection"), {"states": ["LOST_CONNECTION"]})

        transport.subscribe(self._topic("request/+"), self._on_request, qos=2)
        transport.subscribe(f"/ISO_21423/v{config.major_version}/+/+/identity", self._on_identity, qos=1)
        self.publish_identity()
        self.publish_status()
        self.publish_battery()
        self.publish_odometry()

    # ------------------------------------------------------------------
    # What the robot publishes
    # ------------------------------------------------------------------

    def _topic(self, resource: str) -> str:
        return self._c.topic("IMR", self.id, resource)

    def identity(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": timestamp(),
            "entityType": "IMR",
            "manufacturerName": "Example Robotics",
            "iso21423Version": f"{self._c.major_version}.0",
            "capabilities": {
                "provides": ["identity", "status", "batteryStatus", "odometry", "activeRequestsStatus"],
                "accepts": {"requests": list(self.accepts)},
            },
            "details": {
                "imrModel": "SIM-1",
                "imrSerialNumber": "SIM-0001",
                "imrFootprint": [
                    {"x": 0.5, "y": 0.4},
                    {"x": 0.5, "y": -0.4},
                    {"x": -0.5, "y": -0.4},
                    {"x": -0.5, "y": 0.4},
                ],
                "imrWorkingArea": [
                    {"x": 0.8, "y": 0.7},
                    {"x": 0.8, "y": -0.7},
                    {"x": -0.8, "y": -0.7},
                    {"x": -0.8, "y": 0.7},
                ],
                "imrHeight": 0.4,
                "softwareVersions": [{"moduleName": "sim", "moduleVersion": "1.0"}],
                "ratedSpeed": self.rated_speed,
            },
        }

    def publish_identity(self) -> None:
        self._t.publish(self._topic("identity"), self.identity(), qos=1, retain=True)

    def publish_status(self) -> None:
        states = [self.mode, *self.extra_states]
        if self.charging:
            states.append("CHARGING")
        self._t.publish(
            self._topic("status"), {"entityId": self.id, "timestamp": timestamp(), "states": states}, qos=1, retain=True
        )

    def publish_battery(self) -> None:
        state = "FULL" if self.soc >= 1.0 else ("CHARGING" if self.charging else "DISCHARGING")
        self._t.publish(
            self._topic("batteryStatus"),
            {"timestamp": timestamp(), "batterySoc": self.soc, "batteryChargingState": state, "batteryVoltage": 48.0},
            qos=0,
            retain=True,
        )

    def publish_odometry(self) -> None:
        location = {"ccsId": self._c.ccs_id, "x": self.pose["x"], "y": self.pose["y"], "z": self.pose["z"]}
        self._t.publish(
            self._topic("odometry"),
            {
                "timestamp": timestamp(),
                "pose": {
                    "locationPoint": location,
                    "orientation": {"yaw": self.pose["yaw"], "pitch": 0.0, "roll": 0.0},
                },
                "velocity": {"linear": 0.0, "angular": 0.0},
            },
            qos=0,
        )

    def _on_identity(self, topic: str, payload: dict[str, Any] | None) -> None:
        if payload is not None and payload.get("id") != self.id:
            self.publish_odometry()

    def drop(self) -> None:
        """The robot vanishes; the broker publishes its will."""
        assert isinstance(self._t, InMemoryBroker)
        self._t.drop(self.will)

    # ------------------------------------------------------------------
    # Requests
    # ------------------------------------------------------------------

    def _status(self, request: dict[str, Any], code: str, details: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "source": self.id,
            "destination": request.get("source"),
            "sequenceId": next(self._status_seq),
            "requestSequenceId": request.get("sequenceId", 0),
            "timestamp": timestamp(),
            "status": code,
            "detailStatuses": details,
        }

    @staticmethod
    def _detail_status(
        d: dict[str, Any], code: str, reason: str | None = None, message: str | None = None
    ) -> dict[str, Any]:
        status: dict[str, Any] = {"code": code}
        if reason:
            status["reason"] = reason
        if message:
            status["message"] = message
        return {"type": d.get("type", "?"), "version": d.get("version", "1.0"), "status": status}

    def _report(self, topic: str, request: dict[str, Any], code: str, details: list[dict[str, Any]]) -> None:
        self._t.publish(f"{topic}/status", self._status(request, code, details), qos=2, retain=True)

    def _abort(self, topic: str, request: dict[str, Any], reason: str, message: str) -> None:
        details = [self._detail_status(d, "ABORTED", reason, message) for d in request.get("details") or []]
        self._report(topic, request, "ABORTED", details)

    def _on_request(self, topic: str, request: dict[str, Any] | None) -> None:
        if request is None:
            return  # a cleared retained request
        self.received.append(request)
        details_in = request.get("details") or []
        self._report(topic, request, "RECEIVED", [self._detail_status(d, "RECEIVED") for d in details_in])
        if request.get("destination") not in (None, "", self.id):
            return self._abort(topic, request, "REJECTED", "destination is another entity")
        for d in details_in:
            fmt = d.get("format", STANDARD_FORMAT)
            if fmt != STANDARD_FORMAT and fmt not in self.vendor_formats:
                return self._abort(topic, request, "FORMAT_NOT_SUPPORTED", f"unknown format {fmt}")
            if d.get("type") not in self.accepts:
                return self._abort(topic, request, "ACTION_NOT_IMPLEMENTED", f"{d.get('type')} is not accepted")
        moving = any(d.get("type") in ("move", "dock", "undock") for d in details_in)
        if moving and self.mode not in ("MODE_AUTO", "MODE_SEMIAUTO"):
            return self._abort(topic, request, "INVALID_IMR_STATE_FOR_ACTION", f"operating mode is {self.mode}")
        self._report(topic, request, "ACCEPTED", [self._detail_status(d, "ACCEPTED") for d in details_in])
        self._report(topic, request, "EXECUTING", [self._detail_status(d, "EXECUTING") for d in details_in])
        self._pending[topic] = request
        instant = all(d.get("type") in ("cancel", "pauseImr", "resumeImr") for d in details_in)
        if self.auto_run or instant:
            self.run(topic)

    def run(self, topic: str) -> None:
        request = self._pending.pop(topic, None)
        if request is None:
            return
        results = []
        for d in request.get("details") or []:
            code, reason, message = self._perform(d)
            results.append(self._detail_status(d, code, reason, message))
            if code != "SUCCEEDED":
                break
        done = len(results)
        results += [self._detail_status(d, "CANCELED") for d in (request.get("details") or [])[done:]]
        overall = "SUCCEEDED" if all(r["status"]["code"] == "SUCCEEDED" for r in results) else "ABORTED"
        self._report(topic, request, overall, results)

    def _perform(self, d: dict[str, Any]) -> tuple[str, str | None, str | None]:
        kind = d.get("type")
        props = d.get("properties") or {}
        if kind in self.fail_actions:
            return "ABORTED", "GENERAL_FAILURE", f"{kind} failed (simulated)"
        if kind in ("move", "dock"):
            target = props.get("location") if kind == "move" else props.get("dockLocation")
            if not target or target.get("ccsId") != self._c.ccs_id:
                return "ABORTED", "MALFORMED_REQUEST", "location is not in this robot's CCS"
            self.pose.update(x=target["x"], y=target["y"], z=target.get("z", 0.0))
            self.extra_states = ["IDLE"]
            if kind == "dock":
                for action in props.get("dockActions") or []:
                    if action == "CHARGE":
                        self.charging = True
                        self.soc = 1.0
                    elif action in ("PICK", "LOAD"):
                        self.load = action
                    elif action in ("DROP", "UNLOAD"):
                        self.load = None
                self.extra_states = ["PARKED"]
            self.publish_odometry()
            self.publish_status()
            self.publish_battery()
            return "SUCCEEDED", "OK", None
        if kind == "cancel":
            for topic, pending in list(self._pending.items()):
                if pending.get("source") == props.get("source") and pending.get("sequenceId") == props.get("requestId"):
                    del self._pending[topic]
                    details = [self._detail_status(x, "CANCELED") for x in pending.get("details") or []]
                    self._report(topic, pending, "CANCELED", details)
                    return "SUCCEEDED", "OK", None
            return "ABORTED", "REJECTED", "no such request in progress"
        if kind == "pauseImr":
            self.extra_states = ["PAUSED"]
            self.publish_status()
            return "SUCCEEDED", "OK", None
        if kind == "resumeImr":
            self.extra_states = ["IDLE"]
            self.publish_status()
            return "SUCCEEDED", "OK", None
        if kind == "undock":
            self.charging = False
            self.extra_states = ["IDLE"]
            self.publish_status()
            return "SUCCEEDED", "OK", None
        return "SUCCEEDED", "OK", f"{kind} done"
