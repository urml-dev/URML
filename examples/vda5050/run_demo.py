#!/usr/bin/env python3
"""The warehouse example program, run as VDA 5050 orders. No robot, no broker.

1. Validate ``examples/warehouse/pick-to-conveyor.urml.yaml`` against its
   manifest. Nothing is sent to the vehicle until the validator accepts it.
2. Execute it through ``Vda5050Adapter``, which plays fleet control for one
   vehicle: every dispatch step becomes one VDA 5050 ``order``.
3. Print each order the way the vehicle received it, and the vehicle's
   final state.

The vehicle is ``SimulatedVehicle`` on an ``InMemoryBroker``. Point the
adapter at a real broker (``broker_host`` in ``vda5050_adapter.yaml``, the
``[mqtt]`` extra) and the same orders go to a real vehicle.

Run it with ``reference/vda5050-runtime`` installed:

    python examples/vda5050/run_demo.py

The output is deterministic. ``demo-output.txt`` is the recorded copy, and
a test asserts the two are identical.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml
from urml_ros2_runtime.runtime import URMLRuntime
from urml_validator import validate

from urml_vda5050_runtime import (
    InMemoryBroker,
    SimulatedVehicle,
    Vda5050Adapter,
    load_vda5050_config,
)

HERE = Path(__file__).resolve().parent
WAREHOUSE = HERE.parent / "warehouse"


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _describe_order(order: dict[str, Any]) -> str:
    path = " -> ".join(n["nodeId"] for n in order["nodes"])
    actions = [
        a["actionType"]
        + "("
        + ", ".join(f"{p['key']}={p['value']}" for p in a.get("actionParameters", []))
        + ")"
        for n in order["nodes"]
        for a in n["actions"]
    ]
    speeds = sorted({e["maximumSpeed"] for e in order["edges"] if "maximumSpeed" in e})
    line = f"  order: {path}"
    if speeds:
        line += f"   maximumSpeed {', '.join(f'{s:g}' for s in speeds)} m/s"
    if actions:
        line += f"   actions: {', '.join(actions)}"
    return line


def main() -> int:
    program = _load(WAREHOUSE / "pick-to-conveyor.urml.yaml")
    manifest = _load(WAREHOUSE / "pick-to-conveyor.manifest.yaml")
    config = load_vda5050_config(HERE / "vda5050_adapter.yaml")

    out: list[str] = []
    verdict = validate(
        program, manifest, None, profiles=("warehouse",), manifest_base_dir=WAREHOUSE
    )
    out.append(
        f"validate: {'accepted' if verdict.accepted else 'REJECTED'} (profile warehouse, default policy)"
    )
    if not verdict.accepted:
        print("\n".join(out))
        return 1

    broker = InMemoryBroker()
    vehicle = SimulatedVehicle(broker, config, start_at="charge_dock_1")
    adapter = Vda5050Adapter(config, broker)
    out.append(
        f"vehicle: {config.topic_prefix}  (VDA 5050 {config.protocol_version}, simulated)"
    )
    out.append("")

    result = URMLRuntime(adapter).execute(
        program, manifest, None, ("warehouse",), manifest_base_dir=WAREHOUSE
    )

    for step, order in enumerate(broker.published("order"), start=1):
        out.append(f"{step}. {order['nodes'][-1]['nodeDescriptor']}")
        out.append(_describe_order(order))
    out.append("")
    out.append(
        f"program: {'success' if result.success else 'FAILED'}, {result.steps_executed} URML steps"
    )
    out.append(f"orders sent: {len(broker.published('order'))}")
    out.append(f"vehicle at: {vehicle.last_node_id}, loads: {vehicle.loads or 'none'}")
    print("\n".join(out))
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
