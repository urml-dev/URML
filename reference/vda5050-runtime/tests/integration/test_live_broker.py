"""Live MQTT: adapter and simulated vehicle on separate connections to a real broker.

Skipped unless ``URML_VDA5050_BROKER=host:port`` is set and paho-mqtt is
installed. CI runs it against a Mosquitto service container
(``.github/workflows/vda5050-integration.yml``). It checks what the
hermetic suite cannot: real QoS, real asynchronous delivery on paho's
network thread, and the adapter's waits under them.
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import pytest

BROKER = os.environ.get("URML_VDA5050_BROKER")
pytestmark = pytest.mark.skipif(not BROKER, reason="set URML_VDA5050_BROKER=host:port to run")

REPO = Path(__file__).resolve().parents[4]


def test_order_round_trip_over_a_real_broker() -> None:
    pytest.importorskip("paho.mqtt.client")
    from urml_vda5050_runtime import PahoTransport, SimulatedVehicle, Vda5050Adapter, load_vda5050_config

    assert BROKER is not None
    host, _, port = BROKER.partition(":")
    config = load_vda5050_config(REPO / "examples" / "vda5050" / "vda5050_adapter.yaml").model_copy(
        update={
            # A fresh serial per run keeps retained or stray messages from other runs off our topics.
            "serial_number": f"ci-{uuid.uuid4().hex[:8]}",
            "broker_host": host,
            "broker_port": int(port or 1883),
            "order_timeout_seconds": 10.0,
            "state_timeout_seconds": 5.0,
        }
    )
    vehicle_link = PahoTransport(config.broker_host, config.broker_port, client_id=f"vehicle-{config.serial_number}")
    vehicle_ready = False
    try:
        # The vehicle publishes its first state while the adapter is not yet subscribed,
        # which is what a real vehicle that booted first looks like.
        vehicle = SimulatedVehicle(vehicle_link, config, start_at="charge_dock_1")
        time.sleep(0.5)  # let the vehicle's subscriptions reach the broker
        vehicle_ready = True
        with Vda5050Adapter(config) as adapter:
            moved = adapter.send_navigation_goal(location="shelf_a3", speed=0.8)
            assert moved.success, moved.reason
            picked = adapter.send_manipulation_goal(action="grasp", target={"class": "tote"})
            assert picked.success, picked.reason
            charged = adapter.send_docking_goal(station="primary", service="charge", until="full")
            assert charged.success, charged.reason
        assert vehicle.last_node_id == "N-CHG1"
        assert vehicle.loads and vehicle.loads[0]["loadType"] == "tote"
    finally:
        vehicle_link.close()
        assert vehicle_ready
