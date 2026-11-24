"""A minimal simulated VDA 5050 3.0.0 mobile robot.

It exists so the adapter can be tested, and the demo run, with no robot
and no broker. It is not a vehicle model: travel is instant, actions
finish at once, and charging jumps to full. What it does follow is the
protocol behaviour a fleet control depends on:

- the order acceptance checks of section 6.1.2 / 6.1.4 (malformed order,
  other order active, wrong start node, unknown mapId, unsupported
  action, operating mode), each reported with the predefined error type
  and the orderId as errorReference;
- node-by-node traversal with ``nodeStates`` / ``edgeStates`` shrinking
  and ``actionStates`` moving WAITING -> FINISHED or FAILED;
- the instant actions ``cancelOrder``, ``stateRequest``, ``startPause``,
  ``stopPause`` and ``factsheetRequest``;
- ``state`` messages that validate against the official state.schema.

``auto_run=False`` makes the vehicle accept orders but not drive them,
which is how the timeout and cancel paths are tested.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from urml_vda5050_runtime.config import MANDATORY_ACTIONS, Vda5050Config
from urml_vda5050_runtime.messages import MessageFactory
from urml_vda5050_runtime.transport import Transport

_ORDER_MODES = frozenset({"AUTOMATIC", "SEMIAUTOMATIC", "INTERVENED"})


class SimulatedVehicle:
    """A VDA 5050 vehicle on ``transport``, identified by ``config``'s manufacturer/serial."""

    def __init__(
        self,
        transport: Transport,
        config: Vda5050Config,
        *,
        start_at: str,
        supported_actions: Iterable[str] | None = None,
        fail_actions: Iterable[str] = (),
        state_of_charge: float = 80.0,
        operating_mode: str = "AUTOMATIC",
        auto_run: bool = True,
    ) -> None:
        self._transport = transport
        self._config = config
        self._factory = MessageFactory(config)
        self._prefix = config.topic_prefix
        self.supported_actions = set(supported_actions or config.supported_actions) | set(MANDATORY_ACTIONS)
        self.fail_actions = set(fail_actions)
        self.auto_run = auto_run
        self.operating_mode = operating_mode
        self.emergency_stop = "NONE"
        self.received_orders: list[dict[str, Any]] = []

        start = config.nodes[start_at]
        self.position = {"x": start.x, "y": start.y, "theta": start.theta or 0.0}
        self.last_node_id = start.node_id
        self.last_node_sequence_id = 0
        self.order_id = ""
        self.order_update_id = 0
        self.node_states: list[dict[str, Any]] = []
        self.edge_states: list[dict[str, Any]] = []
        self.action_states: list[dict[str, Any]] = []
        self.instant_action_states: list[dict[str, Any]] = []
        self.errors: list[dict[str, Any]] = []
        self.loads: list[dict[str, Any]] = []
        self.state_of_charge = state_of_charge
        self.charging = False
        self.paused = False
        self.driving = False
        self._pending: dict[str, Any] | None = None

        transport.subscribe(f"{self._prefix}/order", self._on_order)
        transport.subscribe(f"{self._prefix}/instantActions", self._on_instant_actions)
        transport.publish(
            f"{self._prefix}/connection", {**self._factory.header("connection"), "connectionState": "ONLINE"}
        )
        self.publish_state()

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def state(self) -> dict[str, Any]:
        return {
            **self._factory.header("state"),
            "orderId": self.order_id,
            "orderUpdateId": self.order_update_id,
            "lastNodeId": self.last_node_id,
            "lastNodeSequenceId": self.last_node_sequence_id,
            "nodeStates": [dict(n) for n in self.node_states],
            "edgeStates": [dict(e) for e in self.edge_states],
            "mobileRobotPosition": {**self.position, "mapId": self._config.map_id, "localized": True},
            "loads": [dict(load) for load in self.loads],
            "driving": self.driving,
            "paused": self.paused,
            "actionStates": [dict(a) for a in self.action_states],
            "instantActionStates": [dict(a) for a in self.instant_action_states],
            "powerSupply": {"stateOfCharge": self.state_of_charge, "charging": self.charging, "batteryVoltage": 48.0},
            "operatingMode": self.operating_mode,
            "errors": [dict(e) for e in self.errors],
            "safetyState": {"activeEmergencyStop": self.emergency_stop, "fieldViolation": False},
        }

    def publish_state(self) -> None:
        self._transport.publish(f"{self._prefix}/state", self.state())

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def _reject(self, order: dict[str, Any], error_type: str, description: str) -> None:
        refs = [{"referenceKey": "orderId", "referenceValue": str(order.get("orderId", ""))}]
        if "orderUpdateId" in order:
            refs.append({"referenceKey": "orderUpdateId", "referenceValue": str(order["orderUpdateId"])})
        self.errors = [
            {"errorType": error_type, "errorLevel": "WARNING", "errorReferences": refs, "errorDescription": description}
        ]
        self.publish_state()

    def _is_idle(self) -> bool:
        return (
            not self.node_states
            and not self.edge_states
            and all(a["actionStatus"] in ("FINISHED", "FAILED") for a in self.action_states)
        )

    def _on_order(self, _topic: str, order: dict[str, Any]) -> None:
        self.received_orders.append(order)
        nodes = order.get("nodes") or []
        edges = order.get("edges") or []
        sequence = sorted([n.get("sequenceId") for n in nodes] + [e.get("sequenceId") for e in edges])
        if not nodes or len(edges) != len(nodes) - 1 or sequence != list(range(len(sequence))):
            return self._reject(order, "VALIDATION_FAILURE", "order graph is not a continuous node-edge sequence")
        if self.operating_mode not in _ORDER_MODES:
            return self._reject(order, "MOBILE_ROBOT_NOT_AVAILABLE", f"operating mode is {self.operating_mode}")
        if not self._is_idle():
            return self._reject(order, "OTHER_ORDER_ACTIVE", f"order {self.order_id} is still active")
        if any(n.get("nodePosition", {}).get("mapId", self._config.map_id) != self._config.map_id for n in nodes):
            return self._reject(order, "UNKNOWN_MAP_ID", "a node references a map this vehicle does not have")
        if nodes[0].get("nodeId") != self.last_node_id:
            return self._reject(order, "START_NODE_OUT_OF_RANGE", f"vehicle is at {self.last_node_id}")
        for element in [*nodes, *edges]:
            for action in element.get("actions", []):
                if action.get("actionType") not in self.supported_actions:
                    return self._reject(order, "INVALID_ORDER_ACTION", f"unsupported action {action.get('actionType')}")

        self.errors = []
        self.order_id = order["orderId"]
        self.order_update_id = order["orderUpdateId"]
        self.node_states = [
            {"nodeId": n["nodeId"], "sequenceId": n["sequenceId"], "released": n["released"]} for n in nodes[1:]
        ]
        self.edge_states = [
            {"edgeId": e["edgeId"], "sequenceId": e["sequenceId"], "released": e["released"]} for e in edges
        ]
        self.action_states = [
            {"actionId": a["actionId"], "actionType": a["actionType"], "actionStatus": "WAITING"}
            for element in [*nodes, *edges]
            for a in element.get("actions", [])
        ]
        self._pending = order
        self.publish_state()
        if self.auto_run:
            self.run_pending()

    def run_pending(self) -> None:
        """Drive the accepted order to its end (instantly)."""
        order, self._pending = self._pending, None
        if order is None:
            return
        nodes = sorted(order["nodes"], key=lambda n: n["sequenceId"])
        self._run_actions(nodes[0])
        for node in nodes[1:]:
            self.driving = True
            self.edge_states = [e for e in self.edge_states if e["sequenceId"] > node["sequenceId"]]
            self.node_states = [n for n in self.node_states if n["sequenceId"] > node["sequenceId"]]
            position = node.get("nodePosition", {})
            self.position = {
                "x": position.get("x", self.position["x"]),
                "y": position.get("y", self.position["y"]),
                "theta": position.get("theta", self.position["theta"]),
            }
            self.last_node_id = node["nodeId"]
            self.last_node_sequence_id = node["sequenceId"]
            self.state_of_charge = max(0.0, self.state_of_charge - 0.5)
            self.driving = False
            self.publish_state()
            self._run_actions(node)
        self.publish_state()

    def _run_actions(self, node: dict[str, Any]) -> None:
        for action in node.get("actions", []):
            entry = next(a for a in self.action_states if a["actionId"] == action["actionId"])
            entry["actionStatus"], result = self._perform(action)
            if result is not None:
                entry["actionResult"] = result
            self.publish_state()

    def _perform(self, action: dict[str, Any]) -> tuple[str, str | None]:
        kind = action["actionType"]
        params = {p["key"]: p["value"] for p in action.get("actionParameters", [])}
        if kind in self.fail_actions:
            return "FAILED", f"{kind} failed (simulated)"
        if kind == "pick":
            self.loads = [{"loadId": str(params.get("loadId", "load-1")), "loadType": str(params.get("loadType", ""))}]
        elif kind == "drop":
            self.loads = []
        elif kind == "startCharging":
            self.charging = True
            self.state_of_charge = 100.0
        elif kind == "stopCharging":
            self.charging = False
        elif kind == "detectObject":
            return "FINISHED", str(params.get("objectType", "object"))
        return "FINISHED", None

    # ------------------------------------------------------------------
    # Instant actions
    # ------------------------------------------------------------------

    def _on_instant_actions(self, _topic: str, message: dict[str, Any]) -> None:
        for action in message.get("actions", []):
            kind = action.get("actionType")
            entry: dict[str, Any] = {"actionId": action.get("actionId"), "actionType": kind}
            if kind == "stateRequest":
                entry["actionStatus"] = "FINISHED"
            elif kind == "cancelOrder":
                if self._is_idle() and self._pending is None:
                    entry["actionStatus"] = "FAILED"
                    self.errors = [
                        {
                            "errorType": "NO_ORDER_TO_CANCEL",
                            "errorLevel": "WARNING",
                            "errorReferences": [{"referenceKey": "actionId", "referenceValue": str(entry["actionId"])}],
                        }
                    ]
                else:
                    self._pending = None
                    self.node_states, self.edge_states = [], []
                    for state in self.action_states:
                        if state["actionStatus"] not in ("FINISHED", "FAILED"):
                            state["actionStatus"] = "FAILED"
                    entry["actionStatus"] = "FINISHED"
            elif kind in ("startPause", "stopPause"):
                self.paused = kind == "startPause"
                entry["actionStatus"] = "FINISHED"
            elif kind == "factsheetRequest":
                entry["actionStatus"] = "FINISHED"
            else:
                entry["actionStatus"] = "FAILED"
                self.errors = [
                    {
                        "errorType": "INVALID_INSTANT_ACTION",
                        "errorLevel": "WARNING",
                        "errorReferences": [{"referenceKey": "actionId", "referenceValue": str(entry["actionId"])}],
                    }
                ]
            self.instant_action_states.append(entry)
        self.publish_state()
