"""Cross-check against an independent reading of ISO 21423: OpenRobOps' schemas.

OpenRobOps (InOrbit, Apache-2.0) publishes JSON Schemas for ISO 21423 messages,
derived from the ISO/FDIS 21423 draft. URML does not copy them into this
repository. This test downloads the bundle at a pinned commit and checks
every message the adapter and the simulated robot publish against it.

Passing means URML's reading of the message model agrees with another
implementer's reading of the same draft. It is not a check against the
published ISO 21423:2026, which is still to be done.

Skipped unless URML_ISO21423_SCHEMA_CHECK=1, because it needs the network.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("URML_ISO21423_SCHEMA_CHECK") != "1", reason="set URML_ISO21423_SCHEMA_CHECK=1 (needs the network)"
)

COMMIT = "f163f8e278f32380f71c549210a97c6e77206090"
BUNDLE_URL = (
    f"https://raw.githubusercontent.com/OpenRobOps/iso21423/{COMMIT}/docs/json_schemas/iso21423.bundle.schema.json"
)
MAP_URL = f"https://raw.githubusercontent.com/OpenRobOps/iso21423/{COMMIT}/docs/json_schemas/topic_schema_map.json"


def _get(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=30) as response:
        data = json.loads(response.read())
    assert isinstance(data, dict)
    return data


def test_every_message_matches_the_openrobops_schemas() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    from tests.test_iso21423_adapter import Rig, make_config

    bundle = _get(BUNDLE_URL)
    resources = _get(MAP_URL)["resources"]
    pointers = {name: spec["bundlePointer"] for name, spec in resources.items()}
    pointers.setdefault("requestStatus", "#/$defs/requestStatus")

    def check(resource: str, payload: dict[str, Any]) -> None:
        schema = {"$schema": bundle["$schema"], "$defs": bundle["$defs"], "$ref": pointers[resource]}
        errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(payload), key=str)
        assert not errors, f"{resource}: {errors[0].message} at {list(errors[0].absolute_path)}"

    rig = Rig(make_config(), accepts=["move", "dock", "cancel", "wrapPallet"], vendor_formats=["ExampleRobotics"])
    rig.adapter.send_navigation_goal(location="shelf_a3")
    rig.adapter.send_manipulation_goal(action="grasp")
    rig.adapter.send_docking_goal(station="primary", service="charge", until="full")
    rig.adapter.call_named_program(name="wrap_pallet")

    seen: set[str] = set()
    for topic, payload, _qos, _retain in rig.broker.log:
        if payload is None:
            continue
        parts = topic.split("/")
        resource = "requestStatus" if parts[-1] == "status" and "request" in parts else parts[-1]
        if "request" in parts and parts[-1] != "status":
            resource = "request"
        if resource in pointers:
            check(resource, payload)
            seen.add(resource)
    assert {"identity", "status", "batteryStatus", "odometry", "request", "requestStatus"} <= seen
