#!/usr/bin/env python3
"""A URML warehouse program, run as ISO 21423 requests. No robot, no broker.

STATUS: the ISO 21423 runtime is built from public material based on the
ISO/FDIS 21423 draft. We are validating it against the published
ISO 21423:2026; until that is done it makes no claim of conformance.

1. Validate ``aisle-run.urml.yaml`` against the warehouse example manifest.
   Nothing is sent until the validator accepts it.
2. Execute it through ``Iso21423Adapter``: every dispatch step becomes one
   ISO 21423 request to the robot.
3. Print each request and the robot's final request status.

The robot is ``SimulatedImr`` on an in-memory broker. The output is
deterministic; ``demo-output.txt`` is the recorded copy, and a test asserts
the two are identical.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml
from urml_ros2_runtime.runtime import URMLRuntime
from urml_validator import validate

from urml_iso21423_runtime import InMemoryBroker, Iso21423Adapter, SimulatedImr, load_iso21423_config

HERE = Path(__file__).resolve().parent
WAREHOUSE = HERE.parent / "warehouse"


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _describe(detail: dict[str, Any]) -> str:
    props = detail.get("properties", {})
    where = props.get("location") or props.get("dockLocation") or {}
    text = f"{detail['type']} to ({where.get('x'):g}, {where.get('y'):g})" if where else detail["type"]
    if props.get("dockActions"):
        text += f" with {', '.join(props['dockActions'])}"
    return text


def main() -> int:
    program = _load(HERE / "aisle-run.urml.yaml")
    manifest = _load(WAREHOUSE / "pick-to-conveyor.manifest.yaml")
    config = load_iso21423_config(HERE / "iso21423_adapter.yaml")

    out: list[str] = []
    verdict = validate(program, manifest, None, profiles=("warehouse",), manifest_base_dir=WAREHOUSE)
    out.append(f"validate: {'accepted' if verdict.accepted else 'REJECTED'} (profile warehouse, default policy)")
    if not verdict.accepted:
        print("\n".join(out))
        return 1

    broker = InMemoryBroker()
    robot = SimulatedImr(broker, config, start_at="charge_dock_1", battery_soc=0.4)
    adapter = Iso21423Adapter(config, broker)
    out.append("robot: simulated IMR on /ISO_21423/v1/IMR/<uuid> (ISO 21423 runtime, draft-based; see README)")
    out.append("")

    result = URMLRuntime(adapter).execute(program, manifest, None, ("warehouse",), manifest_base_dir=WAREHOUSE)

    finals: dict[int, str] = {}
    for topic, payload, _q, _r in broker.log:
        if payload and topic.endswith("/status") and "/request/" in topic:
            finals[payload["requestSequenceId"]] = payload["status"]
    requests = [p for t, p, _q, _r in broker.log if p and "/request/" in t and not t.endswith("/status")]
    for request in requests:
        actions = "; ".join(_describe(d) for d in request["details"])
        out.append(f"request {request['sequenceId']}: {actions}  -> {finals.get(request['sequenceId'], '?')}")
    out.append("")
    out.append(f"program: {'success' if result.success else 'FAILED'}, {result.steps_executed} URML steps")
    out.append(f"requests sent: {len(requests)}")
    out.append(f"robot at: ({robot.pose['x']:g}, {robot.pose['y']:g}), battery {robot.soc:.0%}")
    print("\n".join(out))
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
