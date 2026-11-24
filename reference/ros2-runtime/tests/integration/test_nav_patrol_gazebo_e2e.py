"""End-to-end: a URML conformance fixture driving a simulated robot.

This is the real thing — not a smoke test. It takes the
``home/nav_patrol_positive`` conformance fixture (three plain
``move_to`` goals), runs it through the *same* ``ConformanceRunner``
the hermetic suite uses, but with the ``adapter_factory`` wired to a
live ``RclpyAdapter``. The adapter sends Nav2 ``/navigate_to_pose``
goals to a running TurtleBot 4 Ignition simulation. If the simulated
robot drives to all three poses and Nav2 reports success, the fixture
passes — proving the full path closes:

    URML program -> validator -> ConformanceRunner -> RclpyAdapter
                 -> Nav2 -> simulated TurtleBot 4 actually moves.

## Gating

Two independent gates, both required:

  - ``URML_GAZEBO_E2E=1`` — opt in to the heavy sim test. Distinct from
    ``URML_ROS2_INTEGRATION`` (which only needs rclpy, no simulator).
  - Nav2 must be up and active within a bound: the ``/navigate_to_pose``
    action server answers and ``bt_navigator`` reports the lifecycle
    state ``active``. If not, the test fails with that message rather
    than as a conformance failure. The server exists as soon as
    ``bt_navigator`` is configured, but it rejects every goal until the
    node is active, which needs the robot's ``odom`` transform.

The default ``pytest`` invocation skips this module entirely. The
``gazebo-e2e`` job in ``.github/workflows/ros2-integration.yml`` brings
up the sim, sets the env var, and runs it; it also uploads sim + Nav2
logs as artifacts so a failed first run is diagnosable, not opaque.

## Honest scope

A stock TurtleBot 4 sim exposes Nav2 navigation but its dock is iRobot
Create 3's ``/dock`` action (not Nav2 ``DockRobot``), and it has no
gripper or camera. So this covers the *navigation* slice end-to-end —
the load-bearing one for "does the adapter actually drive a real
robot". Perception / manipulation / docking e2e need a richer sim and
are tracked as follow-ups in INTEGRATION.md.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("URML_GAZEBO_E2E") != "1",
    reason="Set URML_GAZEBO_E2E=1 (and have a TB4+Nav2 sim running) to run the Gazebo e2e test.",
)

_ADAPTER_CONFIG = Path(__file__).parent / "adapter_nav_patrol.yaml"
_FIXTURE_NAME = "home/nav_patrol_positive"

# How long to wait for Nav2 to be up and active before declaring the
# sim absent. The CI job already waits for an active bt_navigator before
# running this test; the bound covers a local run started too early.
_NAV_SERVER_TIMEOUT_S = 120.0


def _wait_for_nav2(timeout_s: float) -> bool:
    """Return True once /navigate_to_pose answers and bt_navigator is active.

    The action server exists from the moment bt_navigator is configured,
    but an inactive bt_navigator rejects every goal. Checking only the
    server let a half-started sim through on 2026-11-24, and the first
    goal of the fixture was rejected.
    """
    import time

    import rclpy
    from rclpy.action import ActionClient
    from rclpy.node import Node

    probe: Node = rclpy.create_node("urml_e2e_nav2_probe")
    try:
        from lifecycle_msgs.msg import State
        from lifecycle_msgs.srv import GetState
        from nav2_msgs.action import NavigateToPose

        # One shared budget: time spent waiting for the action server
        # comes out of the time left for the lifecycle check.
        deadline = time.monotonic() + timeout_s
        client = ActionClient(probe, NavigateToPose, "/navigate_to_pose")
        if not client.wait_for_server(timeout_sec=max(0.0, deadline - time.monotonic())):
            return False
        state = probe.create_client(GetState, "/bt_navigator/get_state")
        while time.monotonic() < deadline:
            if state.wait_for_service(timeout_sec=1.0):
                future = state.call_async(GetState.Request())
                rclpy.spin_until_future_complete(probe, future, timeout_sec=5.0)
                result = future.result()
                if result is not None and result.current_state.id == State.PRIMARY_STATE_ACTIVE:
                    return True
            time.sleep(2.0)
        return False
    finally:
        probe.destroy_node()


def test_nav_patrol_fixture_runs_against_gazebo() -> None:
    """The nav-patrol fixture passes when executed against the live sim."""
    import rclpy

    from urml_conformance import ConformanceRunner, discover_fixtures
    from urml_ros2_runtime.substrate.adapter_config import load_adapter_config
    from urml_ros2_runtime.substrate.rclpy_adapter import RclpyAdapter

    rclpy.init()
    try:
        # Fail fast + actionable if the simulator/Nav2 isn't actually up.
        assert _wait_for_nav2(_NAV_SERVER_TIMEOUT_S), (
            "Nav2 was not up and active within "
            f"{_NAV_SERVER_TIMEOUT_S:.0f}s (/navigate_to_pose answering and "
            "bt_navigator active). Is the TurtleBot 4 sim running with Nav2, "
            "and is the robot publishing odom? See INTEGRATION.md for the "
            "local WSL2 repro."
        )

        config = load_adapter_config(_ADAPTER_CONFIG)

        # Run ONLY the nav-patrol fixture through the same runner the
        # hermetic suite uses — the only difference is the adapter.
        cases = [c for c in discover_fixtures() if c.name == _FIXTURE_NAME]
        assert cases, f"fixture {_FIXTURE_NAME!r} not found in the conformance suite"

        runner = ConformanceRunner(
            cases=cases,
            adapter_factory=lambda: RclpyAdapter(config),
        )
        report = runner.run()
        assert report.all_passed, (
            "nav-patrol fixture failed against the live sim:\n" + report.render()
        )
    finally:
        rclpy.shutdown()
