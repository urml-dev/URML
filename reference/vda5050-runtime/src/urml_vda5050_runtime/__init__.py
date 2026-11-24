"""urml_vda5050_runtime: VDA 5050 fleet-control reference runtime for URML.

Vda5050Adapter (+ Vda5050Config, load_vda5050_config)
  Turns URML dispatch steps into VDA 5050 ``order`` / ``instantActions``
  messages for one mobile robot and judges success from the robot's own
  ``state``. **No ROS 2 dependency.** MQTT goes through ``paho-mqtt``,
  imported lazily (the [mqtt] extra), so this module loads on every host.

InMemoryBroker + SimulatedVehicle
  A hermetic stand-in for the broker and a VDA 5050 vehicle, for tests
  and the offline demo.
"""

from __future__ import annotations

from urml_vda5050_runtime._version import __version__
from urml_vda5050_runtime.adapter import Vda5050Adapter
from urml_vda5050_runtime.broker import BrokerTls
from urml_vda5050_runtime.config import ActionSpec, EdgeSpec, NodeSpec, Vda5050Config, load_vda5050_config
from urml_vda5050_runtime.sim import SimulatedVehicle
from urml_vda5050_runtime.transport import InMemoryBroker, PahoTransport, Transport

__all__ = [
    "ActionSpec",
    "BrokerTls",
    "EdgeSpec",
    "InMemoryBroker",
    "NodeSpec",
    "PahoTransport",
    "SimulatedVehicle",
    "Transport",
    "Vda5050Adapter",
    "Vda5050Config",
    "__version__",
    "load_vda5050_config",
]
