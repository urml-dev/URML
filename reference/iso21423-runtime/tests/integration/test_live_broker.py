"""Live MQTT: adapter and simulated robot on separate connections to a real broker.

Skipped unless ``URML_ISO21423_BROKER=host:port`` is set and paho-mqtt is
installed. Checks what the hermetic suite cannot: retained identity and status
reaching a late subscriber one after the other, QoS 2 requests and their
status on paho's network thread, clearing a retained request with a zero-byte
message, and the broker publishing a Last Will when a client vanishes.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

BROKER = os.environ.get("URML_ISO21423_BROKER")
pytestmark = pytest.mark.skipif(not BROKER, reason="set URML_ISO21423_BROKER=host:port to run")
REPO = Path(__file__).resolve().parents[4]

DOOMED_CLIENT = """
import sys, time
from urml_iso21423_runtime import PahoTransport, Will
host, port, client_id, topic = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
PahoTransport(host, port, client_id=client_id, will=Will(topic, {"states": ["LOST_CONNECTION"]}))
print("connected", flush=True)
time.sleep(60)
"""


def _broker() -> tuple[str, int]:
    assert BROKER is not None
    host, _, port = BROKER.partition(":")
    return host, int(port or 1883)


def test_requests_round_trip_over_a_real_broker() -> None:
    pytest.importorskip("paho.mqtt.client")
    from urml_iso21423_runtime import Iso21423Adapter, PahoTransport, SimulatedImr, load_iso21423_config

    host, port = _broker()
    config = load_iso21423_config(REPO / "examples" / "iso21423" / "iso21423_adapter.yaml").model_copy(
        update={
            # Fresh ids per run, so retained messages from earlier runs stay off our topics.
            "requester_id": str(uuid.uuid4()),
            "target_id": str(uuid.uuid4()),
            "broker_host": host,
            "broker_port": port,
            "request_timeout_seconds": 10.0,
            "state_timeout_seconds": 5.0,
        }
    )
    robot_link = PahoTransport(host, port, client_id=f"robot-{config.target_id}")
    robot = SimulatedImr(robot_link, config, start_at="charge_dock_1", battery_soc=0.4)
    time.sleep(0.5)  # the robot's retained identity is on the broker before the adapter connects
    try:
        with Iso21423Adapter(config) as adapter:
            moved = adapter.send_navigation_goal(location="shelf_a3")
            assert moved.success, moved.reason
            docked = adapter.send_docking_goal(station="primary", service="dock", until="full")
            assert docked.success, docked.reason
        assert (robot.pose["x"], robot.pose["y"]) == (-4.0, 0.0)
        assert robot.soc == 1.0
    finally:
        robot_link.close()


def test_the_broker_publishes_a_vanished_clients_will() -> None:
    pytest.importorskip("paho.mqtt.client")
    from urml_iso21423_runtime import PahoTransport

    host, port = _broker()
    topic = f"/ISO_21423/v1/IMR/{uuid.uuid4()}/disconnection"
    got: list[object] = []
    watcher = PahoTransport(host, port, client_id=f"watch-{uuid.uuid4()}")
    watcher.subscribe(topic, lambda _t, p: got.append(p), qos=1)
    # A client in its own process, killed outright: its connection drops with no DISCONNECT,
    # which is what a crashed robot looks like to the broker.
    doomed = subprocess.Popen(
        [sys.executable, "-c", DOOMED_CLIENT, host, str(port), f"doomed-{uuid.uuid4()}", topic],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert doomed.stdout is not None and doomed.stdout.readline().strip() == "connected"
        time.sleep(0.5)
        doomed.send_signal(signal.SIGKILL)
        doomed.wait(timeout=10)
        deadline = time.monotonic() + 10
        while not got and time.monotonic() < deadline:
            time.sleep(0.1)
    finally:
        if doomed.poll() is None:
            doomed.kill()
        watcher.close()
    assert got and got[-1] == {"states": ["LOST_CONNECTION"]}
