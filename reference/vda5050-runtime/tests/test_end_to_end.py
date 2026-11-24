"""End to end: an unchanged URML warehouse program, validated, executed over VDA 5050.

The program and manifest are the repository's warehouse example
(``examples/warehouse/``), byte for byte. The only VDA 5050-specific file
is the adapter config (``examples/vda5050/vda5050_adapter.yaml``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
import yaml
from urml_ros2_runtime.errors import ValidationRejectedError
from urml_ros2_runtime.runtime import URMLRuntime

from urml_vda5050_runtime import InMemoryBroker, SimulatedVehicle, Vda5050Adapter, load_vda5050_config

REPO = Path(__file__).resolve().parents[3]
WAREHOUSE = REPO / "examples" / "warehouse"
SCHEMAS = Path(__file__).parent / "vda5050_schemas"


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _rig() -> tuple[InMemoryBroker, SimulatedVehicle, Vda5050Adapter]:
    config = load_vda5050_config(REPO / "examples" / "vda5050" / "vda5050_adapter.yaml")
    broker = InMemoryBroker()
    vehicle = SimulatedVehicle(broker, config, start_at="charge_dock_1")
    return broker, vehicle, Vda5050Adapter(config, broker, sleep=lambda _s: None)


def test_warehouse_example_runs_over_vda5050() -> None:
    broker, vehicle, adapter = _rig()
    program = _load(WAREHOUSE / "pick-to-conveyor.urml.yaml")
    manifest = _load(WAREHOUSE / "pick-to-conveyor.manifest.yaml")

    result = URMLRuntime(adapter).execute(program, manifest, None, ("warehouse",), manifest_base_dir=WAREHOUSE)

    assert result.success, result.last_outcome
    assert result.steps_executed == 3
    orders = broker.published("order")
    # pick_from: drive to the shelf, detectObject, pick. place_at: drive to the conveyor, drop.
    assert [[a["actionType"] for n in o["nodes"] for a in n["actions"]] for o in orders] == [
        [],
        ["detectObject"],
        ["pick"],
        [],
        ["drop"],
    ]
    assert [o["nodes"][-1]["nodeId"] for o in orders] == ["N-A3", "N-A3", "N-A3", "N-CVA", "N-CVA"]
    assert vehicle.last_node_id == "N-CVA" and vehicle.loads == []

    validators = {
        name: jsonschema.Draft202012Validator(json.loads((SCHEMAS / f"{name}.schema").read_text(encoding="utf-8")))
        for name in ("order", "instantActions", "state", "connection")
    }
    for topic, payload in broker.log:
        validators[topic.rsplit("/", 1)[-1]].validate(payload)


def test_validator_rejection_sends_nothing_to_the_vehicle() -> None:
    broker, _vehicle, adapter = _rig()
    program = _load(WAREHOUSE / "pick-to-conveyor.urml.yaml")
    program["behavior"]["steps"][0]["pick_from"]["source"] = "shelf_z9"  # not a declared location
    manifest = _load(WAREHOUSE / "pick-to-conveyor.manifest.yaml")

    with pytest.raises(ValidationRejectedError):
        URMLRuntime(adapter).execute(program, manifest, None, ("warehouse",), manifest_base_dir=WAREHOUSE)

    assert broker.published("order") == []
    assert broker.published("instantActions") == []


def test_demo_output_matches_the_recorded_copy() -> None:
    import subprocess
    import sys

    demo = REPO / "examples" / "vda5050"
    run = subprocess.run(
        [sys.executable, str(demo / "run_demo.py")], capture_output=True, text=True, check=False, timeout=120
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout == (demo / "demo-output.txt").read_text(encoding="utf-8"), (
        "examples/vda5050/demo-output.txt is stale: rerun run_demo.py > demo-output.txt"
    )
