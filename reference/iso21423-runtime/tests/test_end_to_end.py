"""End to end: a URML warehouse program, validated, executed over ISO 21423.

The manifest is the repository's warehouse example, unchanged. The program
and the adapter config are in examples/iso21423/.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from urml_ros2_runtime.errors import ValidationRejectedError
from urml_ros2_runtime.runtime import URMLRuntime

from urml_iso21423_runtime import InMemoryBroker, Iso21423Adapter, SimulatedImr, load_iso21423_config

REPO = Path(__file__).resolve().parents[3]
WAREHOUSE = REPO / "examples" / "warehouse"
EXAMPLE = REPO / "examples" / "iso21423"


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _rig() -> tuple[InMemoryBroker, SimulatedImr, Iso21423Adapter]:
    config = load_iso21423_config(EXAMPLE / "iso21423_adapter.yaml")
    broker = InMemoryBroker()
    robot = SimulatedImr(broker, config, start_at="charge_dock_1", battery_soc=0.4)
    return broker, robot, Iso21423Adapter(config, broker, sleep=lambda _s: None)


def _requests(broker: InMemoryBroker) -> list[dict[str, Any]]:
    return [p for t, p, _q, _r in broker.log if p is not None and "/request/" in t and not t.endswith("/status")]


def test_the_example_program_runs_over_iso21423() -> None:
    broker, robot, adapter = _rig()
    program = _load(EXAMPLE / "aisle-run.urml.yaml")
    manifest = _load(WAREHOUSE / "pick-to-conveyor.manifest.yaml")

    result = URMLRuntime(adapter).execute(program, manifest, None, ("warehouse",), manifest_base_dir=WAREHOUSE)

    assert result.success, result.last_outcome
    assert result.steps_executed == 4
    kinds = [[d["type"] for d in r["details"]] for r in _requests(broker)]
    assert kinds == [["move"], ["move"], ["dock"]]
    assert _requests(broker)[-1]["details"][0]["properties"]["dockActions"] == ["CHARGE"]
    assert (robot.pose["x"], robot.pose["y"]) == (-4.0, 0.0) and robot.soc == 1.0


def test_validator_rejection_sends_nothing_to_the_robot() -> None:
    broker, _robot, adapter = _rig()
    program = _load(EXAMPLE / "aisle-run.urml.yaml")
    program["behavior"]["steps"][0]["move_to"]["location"] = "shelf_z9"
    manifest = _load(WAREHOUSE / "pick-to-conveyor.manifest.yaml")
    with pytest.raises(ValidationRejectedError):
        URMLRuntime(adapter).execute(program, manifest, None, ("warehouse",), manifest_base_dir=WAREHOUSE)
    assert _requests(broker) == []


def test_demo_output_matches_the_recorded_copy() -> None:
    run = subprocess.run(
        [sys.executable, str(EXAMPLE / "run_demo.py")], capture_output=True, text=True, check=False, timeout=120
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout == (EXAMPLE / "demo-output.txt").read_text(encoding="utf-8"), (
        "examples/iso21423/demo-output.txt is stale: rerun run_demo.py > demo-output.txt"
    )
