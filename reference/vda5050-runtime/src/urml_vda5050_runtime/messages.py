"""VDA 5050 wire format: build ``order`` / ``instantActions``, read ``state``.

Everything that knows VDA 5050 field names lives in this module. The
adapter speaks in routes and actions; this module turns them into JSON
the vehicle accepts (VDA 5050 3.0.0, section 7) and reads the vehicle's
``state`` back. A second fleet-interoperability protocol would add a
sibling module with the same three jobs, not change the adapter.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from urml_vda5050_runtime.config import EdgeSpec, NodeSpec, Vda5050Config

#: actionStatus values after which an action will not change again.
TERMINAL_STATUSES = frozenset({"FINISHED", "FAILED"})
#: errorLevel values that stop an order (WARNING does not).
BLOCKING_ERROR_LEVELS = frozenset({"URGENT", "CRITICAL", "FATAL"})


@dataclass(frozen=True)
class Action:
    """One action to attach to an order node or send as an instant action."""

    action_type: str
    action_id: str
    blocking_type: str = "HARD"
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "actionType": self.action_type,
            "actionId": self.action_id,
            "blockingType": self.blocking_type,
        }
        if self.parameters:
            out["actionParameters"] = [{"key": k, "value": v} for k, v in self.parameters.items()]
        return out


class MessageFactory:
    """Stamps protocol headers. ``headerId`` counts up per topic (section 7.2)."""

    def __init__(self, config: Vda5050Config) -> None:
        self._config = config
        self._header_ids: dict[str, itertools.count[int]] = {}

    def header(self, topic: str) -> dict[str, Any]:
        counter = self._header_ids.setdefault(topic, itertools.count())
        now = datetime.now(UTC)
        return {
            "headerId": next(counter),
            "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z",
            "version": self._config.protocol_version,
            "manufacturer": self._config.manufacturer,
            "serialNumber": self._config.serial_number,
        }

    def _node(self, name: str, spec: NodeSpec, sequence_id: int, actions: Iterable[Action]) -> dict[str, Any]:
        position: dict[str, Any] = {"x": spec.x, "y": spec.y, "mapId": self._config.map_id}
        if spec.theta is not None:
            position["theta"] = spec.theta
        if spec.allowed_deviation_theta is not None:
            position["allowedDeviationTheta"] = spec.allowed_deviation_theta
        return {
            "nodeId": spec.node_id,
            "sequenceId": sequence_id,
            "nodeDescriptor": name,
            "released": True,
            "nodePosition": position,
            "actions": [a.to_json() for a in actions],
        }

    def order(
        self,
        *,
        order_id: str,
        start: str,
        route: list[tuple[str, EdgeSpec]],
        end_actions: Iterable[Action] = (),
        speed: float | None = None,
    ) -> dict[str, Any]:
        """A fully released order (base only, no horizon) from ``start`` along ``route``.

        ``end_actions`` run at the last node. With an empty route the order
        is a single node, the one the vehicle is standing on, which is how
        an action is run in place (section 6.1.1: the first node is
        trivially reachable).
        """
        cfg = self._config
        end_actions = list(end_actions)
        nodes = [self._node(start, cfg.nodes[start], 0, end_actions if not route else ())]
        edges: list[dict[str, Any]] = []
        previous = start
        for index, (location, edge) in enumerate(route):
            last = index == len(route) - 1
            edge_json: dict[str, Any] = {
                "edgeId": edge.edge_id or f"{edge.start}--{edge.end}",
                "sequenceId": 2 * index + 1,
                "edgeDescriptor": f"{previous} -> {location}",
                "released": True,
                "actions": [],
            }
            limits = [v for v in (edge.max_speed, speed) if v is not None and v > 0]
            if limits:
                edge_json["maximumSpeed"] = min(limits)
            edges.append(edge_json)
            nodes.append(self._node(location, cfg.nodes[location], 2 * index + 2, end_actions if last else ()))
            previous = location
        return {
            **self.header("order"),
            "orderId": order_id,
            "orderUpdateId": 0,
            "nodes": nodes,
            "edges": edges,
        }

    def instant_actions(self, actions: Iterable[Action]) -> dict[str, Any]:
        return {**self.header("instantActions"), "actions": [a.to_json() for a in actions]}


# ---------------------------------------------------------------------------
# Reading the vehicle state
# ---------------------------------------------------------------------------


def is_idle(state: Mapping[str, Any]) -> bool:
    """Section 6.6.8: no node or edge states, every action FINISHED or FAILED."""
    return (
        not state.get("nodeStates")
        and not state.get("edgeStates")
        and all(a.get("actionStatus") in TERMINAL_STATUSES for a in state.get("actionStates", []))
    )


def action_status(state: Mapping[str, Any], action_id: str, *, instant: bool = False) -> dict[str, Any] | None:
    key = "instantActionStates" if instant else "actionStates"
    for entry in state.get(key, []):
        if entry.get("actionId") == action_id:
            return dict(entry)
    return None


def errors_referencing(state: Mapping[str, Any], key: str, value: str) -> list[dict[str, Any]]:
    """Errors whose ``errorReferences`` point at ``key == value`` (e.g. our orderId)."""
    hits = []
    for error in state.get("errors", []):
        for ref in error.get("errorReferences", []) or []:
            if ref.get("referenceKey") == key and ref.get("referenceValue") == value:
                hits.append(dict(error))
                break
    return hits


def blocking_errors(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(e) for e in state.get("errors", []) if e.get("errorLevel") in BLOCKING_ERROR_LEVELS]


def describe_error(error: Mapping[str, Any]) -> str:
    text = f"{error.get('errorType', 'unknownError')} ({error.get('errorLevel', '?')})"
    if error.get("errorDescription"):
        text += f": {error['errorDescription']}"
    return text
