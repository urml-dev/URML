"""urml_iso21423_runtime: ISO 21423 reference runtime for URML.

STATUS: built from public material based on the ISO/FDIS 21423 draft. We are
validating it against the published ISO 21423:2026; until that is done it
makes no claim of conformance to ISO 21423.

  Iso21423Adapter (+ Iso21423Config, load_iso21423_config)
    Sends each URML dispatch step as an ISO 21423 request to a mobile robot
    or its fleet manager and judges success from the robot's own request
    status. **No ROS 2 dependency.** MQTT goes through ``paho-mqtt``,
    imported lazily (the [mqtt] extra).

  InMemoryBroker + SimulatedImr
    A hermetic stand-in for the broker and a robot, for tests and the demo.
"""

from __future__ import annotations

from urml_iso21423_runtime._version import __version__
from urml_iso21423_runtime.adapter import Iso21423Adapter
from urml_iso21423_runtime.config import Dock, Iso21423Config, Place, VendorAction, load_iso21423_config
from urml_iso21423_runtime.sim import SimulatedImr
from urml_iso21423_runtime.transport import InMemoryBroker, PahoTransport, Transport, Will

__all__ = [
    "Dock",
    "InMemoryBroker",
    "Iso21423Adapter",
    "Iso21423Config",
    "PahoTransport",
    "Place",
    "SimulatedImr",
    "Transport",
    "VendorAction",
    "Will",
    "__version__",
    "load_iso21423_config",
]
