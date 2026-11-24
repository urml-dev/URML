"""Deployment-side configuration for ``Iso21423Adapter``.

Which robot or fleet manager to address, the facility's Common Coordinate
System, where each URML location sits in it, which stations are docks and
what a dock service asks the robot to do there are deployment facts. They
live in an ``iso21423_adapter.yaml`` next to the URML artifacts, not in the
program or manifest.
"""

from __future__ import annotations

import math
import uuid
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

#: The station actions a dock request may ask for.
DockAction = Literal["CHARGE", "DUMP", "FILL", "LOAD", "UNLOAD", "PICK", "DROP"]
_ENTITY_TYPE = r"^[A-Z0-9_]+$"


def _uuid(value: str) -> str:
    parsed = uuid.UUID(value)
    if parsed.version not in (1, 2, 3, 4, 5):
        raise ValueError(f"{value!r} is not a version 1 to 5 UUID")
    return str(parsed)


def _default_dock_services() -> dict[str, list[DockAction]]:
    return {"charge": ["CHARGE"], "park": []}


class Place(BaseModel):
    """A URML location as a point in the Common Coordinate System (metres)."""

    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    z: float = 0.0
    yaw: float | None = Field(None, ge=-math.pi, le=math.pi, description="Heading on arrival, radians.")


class Dock(BaseModel):
    """A docking station: a URML location name, optionally with the station's own UUID."""

    model_config = ConfigDict(extra="forbid")

    location: str
    dock_id: str | None = None

    @field_validator("dock_id")
    @classmethod
    def _check_dock_id(cls, value: str | None) -> str | None:
        return None if value is None else _uuid(value)


class VendorAction(BaseModel):
    """A vendor-defined request detail (ISO 21423's extension mechanism)."""

    model_config = ConfigDict(extra="forbid")

    type: str
    version: str = "1.0"
    format: str = Field(..., description="The vendor's format name; ISO-21423 is reserved for standard actions.")
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("format")
    @classmethod
    def _not_standard(cls, value: str) -> str:
        if value == "ISO-21423":
            raise ValueError("a vendor action names its own format, not ISO-21423")
        return value


class Iso21423Config(BaseModel):
    """Which entity to address, the CCS, and the place and station mapping."""

    model_config = ConfigDict(extra="forbid")

    # --- this adapter as an ISO 21423 entity ---------------------------------
    requester_id: str = Field(..., description="This URML adapter's entity UUID.")
    requester_type: str = Field("URML", pattern=_ENTITY_TYPE, description="Entity type the adapter announces.")
    manufacturer_name: str = "URML"

    # --- the entity the requests go to ---------------------------------------
    target_type: str = Field("IMR", pattern=_ENTITY_TYPE, description="IMR, or IMRFM to go through a fleet manager.")
    target_id: str = Field(..., description="UUID of the robot or fleet manager the requests are published to.")
    robot_id: str | None = Field(
        None,
        description="UUID of the robot that executes. Defaults to target_id; set it when target is an IMRFM.",
    )

    # --- transport ------------------------------------------------------------
    broker_host: str = "127.0.0.1"
    broker_port: int = Field(1883, gt=0, lt=65536)
    major_version: int = Field(1, ge=1)

    # --- space -----------------------------------------------------------------
    ccs_id: str = Field(..., description="UUID of the facility's Common Coordinate System.")
    places: dict[str, Place] = Field(default_factory=dict)
    docks: dict[str, Dock] = Field(default_factory=dict, description="Station name -> its dock.")
    primary_dock: str | None = None
    tolerance_radius: float = Field(0.25, gt=0, description="Arrival circle sent with move and dock, metres.")
    #: dock service name -> the station actions it asks for ([] = just dock).
    dock_services: dict[str, list[DockAction]] = Field(default_factory=lambda: _default_dock_services())
    #: manifest-declared program name -> vendor action (RFC-0015 call_program).
    program_to_action: dict[str, VendorAction] = Field(default_factory=dict)

    # --- timing ---------------------------------------------------------------
    request_timeout_seconds: float = Field(300.0, gt=0)
    state_timeout_seconds: float = Field(10.0, gt=0)
    charge_timeout_seconds: float = Field(4 * 3600.0, gt=0)
    full_charge: float = Field(1.0, gt=0, le=1.0, description="batterySoc that counts as full for until: full.")

    @field_validator("requester_id", "target_id", "ccs_id", "robot_id")
    @classmethod
    def _check_uuid(cls, value: str | None) -> str | None:
        return None if value is None else _uuid(value)

    @model_validator(mode="after")
    def _coherent(self) -> Iso21423Config:
        for name, dock in self.docks.items():
            if dock.location not in self.places:
                raise ValueError(f"dock {name!r} names unknown place {dock.location!r}")
        if self.primary_dock is not None and self.primary_dock not in self.docks:
            raise ValueError(f"primary_dock {self.primary_dock!r} is not a configured dock")
        return self

    @property
    def executor_id(self) -> str:
        return self.robot_id or self.target_id

    def topic(self, entity_type: str, entity_id: str, resource: str) -> str:
        return f"/ISO_21423/v{self.major_version}/{entity_type}/{entity_id}/{resource}"

    def robot_topic(self, resource: str) -> str:
        """A resource describing the executing robot (an IMR, whoever publishes it)."""
        return self.topic("IMR", self.executor_id, resource)

    def target_topic(self, resource: str) -> str:
        return self.topic(self.target_type, self.target_id, resource)

    def place_near(self, x: float, y: float) -> str | None:
        """The configured place within twice the tolerance radius of (x, y), nearest first."""
        best: tuple[float, str] | None = None
        for name, place in self.places.items():
            distance = math.dist((x, y), (place.x, place.y))
            if distance <= 2 * self.tolerance_radius and (best is None or distance < best[0]):
                best = (distance, name)
        return None if best is None else best[1]

    def dock_at(self, location: str) -> tuple[str, Dock] | None:
        for name, dock in self.docks.items():
            if dock.location == location:
                return name, dock
        return None


def load_iso21423_config(path: str | Path) -> Iso21423Config:
    """Parse an ``iso21423_adapter.yaml`` file into an ``Iso21423Config``."""
    p = Path(path)
    with p.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"iso21423-config file {p} did not contain a YAML mapping at the top level.")
    return Iso21423Config.model_validate(data)
