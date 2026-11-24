"""Deployment-side configuration for ``Vda5050Adapter``.

VDA 5050 leaves the route graph to fleet control: the vehicle only ever
sees the nodes and edges of the order it is given. Which graph nodes the
URML location names refer to, which edges connect them, which charger
node a ``dock`` drives to, and which actions this vehicle can perform
are all deployment facts. They do NOT belong in the URML program,
manifest or envelope. They live in a ``vda5050_adapter.yaml`` next to the
URML artifacts, the same principle as the OPC UA runtime's
``opcua_adapter.yaml`` and the PX4 runtime's ``location_to_pose``.
"""

from __future__ import annotations

import heapq
import math
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from urml_vda5050_runtime.broker import BrokerTls, check_env_name

#: The actions VDA 5050 3.0.0 section 6.2.3 requires every mobile robot to support.
MANDATORY_ACTIONS: tuple[str, ...] = ("cancelOrder", "startPause", "stopPause")


class NodeSpec(BaseModel):
    """One node of the fleet-control route graph, keyed by a URML location name."""

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(..., description="VDA 5050 nodeId the vehicle knows this location by.")
    x: float = Field(..., description="X in the map frame, metres.")
    y: float = Field(..., description="Y in the map frame, metres.")
    theta: float | None = Field(None, ge=-math.pi, le=math.pi, description="Heading at the node, radians.")
    allowed_deviation_theta: float | None = Field(None, ge=0, le=math.pi)
    station_name: str | None = Field(
        None,
        description="stationName passed to pick / drop at this node. Defaults to the URML location name.",
    )
    station_type: str | None = Field(None, description="stationType passed to pick / drop at this node.")


class EdgeSpec(BaseModel):
    """A traversable connection between two configured nodes (by URML location name)."""

    model_config = ConfigDict(extra="forbid")

    start: str
    end: str
    edge_id: str | None = Field(None, description="VDA 5050 edgeId. Defaults to '<start>--<end>'.")
    max_speed: float | None = Field(None, gt=0, description="Edge speed limit, m/s. Sent as maximumSpeed.")
    bidirectional: bool = True


class ActionSpec(BaseModel):
    """A vehicle action plus the fixed parameters it is always sent with."""

    model_config = ConfigDict(extra="forbid")

    action_type: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class Vda5050Config(BaseModel):
    """VDA 5050 connection, identity and route-graph config for one vehicle."""

    model_config = ConfigDict(extra="forbid")

    # --- identity and transport -------------------------------------------------
    manufacturer: str = Field(..., pattern=r"^[A-Za-z0-9_.:-]+$")
    serial_number: str = Field(..., pattern=r"^[A-Za-z0-9_.:-]+$")
    interface_name: str = Field("vda5050", pattern=r"^[A-Za-z0-9_.:-]+$")
    protocol_version: str = Field("3.0.0", pattern=r"^\d+\.\d+\.\d+$")
    broker_host: str = "127.0.0.1"
    broker_port: int = Field(1883, gt=0, lt=65536)
    broker_tls: BrokerTls | None = Field(None, description="TLS for the broker connection; see broker.py.")
    broker_username: str | None = Field(None, min_length=1)
    broker_password_env: str | None = Field(
        None, description="The environment variable that holds the broker password. Never the password itself."
    )

    @field_validator("broker_password_env")
    @classmethod
    def _env_name(cls, value: str | None) -> str | None:
        return check_env_name(value)

    @model_validator(mode="after")
    def _password_needs_username(self) -> Vda5050Config:
        if self.broker_password_env is not None and self.broker_username is None:
            raise ValueError("broker_password_env needs broker_username")
        return self

    # --- route graph ------------------------------------------------------------
    map_id: str
    nodes: dict[str, NodeSpec] = Field(default_factory=dict)
    edges: list[EdgeSpec] = Field(default_factory=list)

    # --- capabilities -----------------------------------------------------------
    #: The vehicle's action set, as its factsheet lists it
    #: (protocolFeatures.agvActions). An action outside this list is refused
    #: before anything is sent.
    supported_actions: list[str] = Field(
        default_factory=lambda: [*MANDATORY_ACTIONS, "pick", "drop", "startCharging", "stopCharging"]
    )
    #: dock service name -> the node action that performs it at the station
    #: (None = just drive there and stop).
    dock_services: dict[str, str | None] = Field(default_factory=lambda: {"charge": "startCharging", "park": None})
    #: station a ``dock`` without ``at:`` drives to (URML location name).
    primary_dock: str | None = None
    #: stateOfCharge (percent) at which ``dock(until: full)`` counts as full.
    full_charge_percent: float = Field(100.0, gt=0, le=100)
    #: manifest-declared program name -> vendor action (RFC-0015 call_program).
    program_to_action: dict[str, ActionSpec] = Field(default_factory=dict)

    # --- timing -----------------------------------------------------------------
    order_timeout_seconds: float = Field(300.0, gt=0)
    state_timeout_seconds: float = Field(10.0, gt=0)
    charge_timeout_seconds: float = Field(4 * 3600.0, gt=0)

    @model_validator(mode="after")
    def _edges_reference_known_nodes(self) -> Vda5050Config:
        for edge in self.edges:
            for end in (edge.start, edge.end):
                if end not in self.nodes:
                    raise ValueError(f"edge {edge.start!r} -> {edge.end!r} names unknown node {end!r}")
        if self.primary_dock is not None and self.primary_dock not in self.nodes:
            raise ValueError(f"primary_dock {self.primary_dock!r} is not a configured node")
        return self

    # --------------------------------------------------------------------------
    # Lookups
    # --------------------------------------------------------------------------

    @property
    def topic_prefix(self) -> str:
        """``interfaceName/majorVersion/manufacturer/serialNumber`` (VDA 5050 section 4.2)."""
        major = self.protocol_version.split(".", 1)[0]
        return f"{self.interface_name}/v{major}/{self.manufacturer}/{self.serial_number}"

    def location_for_node_id(self, node_id: str) -> str | None:
        for name, spec in self.nodes.items():
            if spec.node_id == node_id:
                return name
        return None

    def supports(self, action_type: str) -> bool:
        return action_type in self.supported_actions

    def route(self, start: str, goal: str) -> list[tuple[str, EdgeSpec]] | None:
        """Shortest path from ``start`` to ``goal`` over the configured edges.

        Returns ``[(next_location, edge), ...]``, empty when ``start == goal``,
        or ``None`` when no path exists. Edge length is the straight-line
        distance between node positions.
        """
        if start == goal:
            return []
        adjacency: dict[str, list[tuple[str, EdgeSpec]]] = {}
        for edge in self.edges:
            adjacency.setdefault(edge.start, []).append((edge.end, edge))
            if edge.bidirectional:
                adjacency.setdefault(edge.end, []).append((edge.start, edge))
        best: dict[str, float] = {start: 0.0}
        came_from: dict[str, tuple[str, EdgeSpec]] = {}
        frontier: list[tuple[float, str]] = [(0.0, start)]
        while frontier:
            cost, here = heapq.heappop(frontier)
            if here == goal:
                break
            if cost > best.get(here, math.inf):
                continue
            for there, edge in adjacency.get(here, []):
                step = math.dist((self.nodes[here].x, self.nodes[here].y), (self.nodes[there].x, self.nodes[there].y))
                if cost + step < best.get(there, math.inf):
                    best[there] = cost + step
                    came_from[there] = (here, edge)
                    heapq.heappush(frontier, (cost + step, there))
        if goal not in came_from:
            return None
        path: list[tuple[str, EdgeSpec]] = []
        cursor = goal
        while cursor != start:
            previous, edge = came_from[cursor]
            path.append((cursor, edge))
            cursor = previous
        path.reverse()
        return path


def load_vda5050_config(path: str | Path) -> Vda5050Config:
    """Parse a ``vda5050_adapter.yaml`` file into a ``Vda5050Config``."""
    p = Path(path)
    with p.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"vda5050-config file {p} did not contain a YAML mapping at the top level.")
    config = Vda5050Config.model_validate(data)
    if config.broker_tls is not None:
        config = config.model_copy(update={"broker_tls": config.broker_tls.resolved(p.resolve().parent)})
    return config
