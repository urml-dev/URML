"""Hermetic tests for Vda5050Adapter: no broker, no robot, no paho-mqtt.

The adapter talks to a ``SimulatedVehicle`` over an ``InMemoryBroker``.
Every message either side publishes is checked against the official
VDA 5050 3.0.0 JSON schemas in ``tests/vda5050_schemas/``.
"""

from __future__ import annotations

import json
import math
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import jsonschema
import pytest
import yaml
from urml_ros2_runtime.substrate.base import ROSAdapter

from urml_vda5050_runtime import (
    ActionSpec,
    EdgeSpec,
    InMemoryBroker,
    NodeSpec,
    SimulatedVehicle,
    Vda5050Adapter,
    Vda5050Config,
    load_vda5050_config,
)

SCHEMAS = Path(__file__).parent / "vda5050_schemas"
REPO = Path(__file__).resolve().parents[3]
TOPIC_SCHEMA = {
    "order": "order.schema",
    "instantActions": "instantActions.schema",
    "state": "state.schema",
    "connection": "connection.schema",
}


def _validator(name: str) -> jsonschema.Draft202012Validator:
    schema = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())


VALIDATORS = {topic: _validator(name) for topic, name in TOPIC_SCHEMA.items()}


def make_config(**overrides: Any) -> Vda5050Config:
    base: dict[str, Any] = {
        "manufacturer": "ExampleAMR",
        "serial_number": "amr-0001",
        "map_id": "warehouse-1",
        "nodes": {
            "charge_dock_1": NodeSpec(node_id="N-CHG1", x=-4.0, y=0.0, theta=0.0),
            "hub": NodeSpec(node_id="N-HUB", x=0.0, y=0.0),
            "shelf_a3": NodeSpec(node_id="N-A3", x=6.0, y=-2.0, station_type="rack", station_name="A3-shelf"),
            "conveyor_a": NodeSpec(node_id="N-CVA", x=0.0, y=4.0, station_type="passive_conveyor"),
            "island": NodeSpec(node_id="N-ISL", x=50.0, y=50.0),
        },
        "edges": [
            EdgeSpec(start="charge_dock_1", end="hub", max_speed=1.0),
            EdgeSpec(start="hub", end="shelf_a3"),
            EdgeSpec(start="hub", end="conveyor_a", edge_id="E-HUB-CVA"),
        ],
        "primary_dock": "charge_dock_1",
        "supported_actions": [
            "cancelOrder",
            "startPause",
            "stopPause",
            "pick",
            "drop",
            "startCharging",
            "stopCharging",
            "detectObject",
            "stateRequest",
            "wrapPallet",
        ],
        "program_to_action": {"wrap_pallet": ActionSpec(action_type="wrapPallet", parameters={"layers": 3})},
        "order_timeout_seconds": 0.2,
        "state_timeout_seconds": 0.2,
        "charge_timeout_seconds": 0.2,
    }
    base.update(overrides)
    return Vda5050Config(**base)


class Rig:
    def __init__(self, config: Vda5050Config, **vehicle_kwargs: Any) -> None:
        self.config = config
        self.broker = InMemoryBroker()
        vehicle_kwargs.setdefault("start_at", "charge_dock_1")
        self.vehicle = SimulatedVehicle(self.broker, config, **vehicle_kwargs)
        self.adapter = Vda5050Adapter(config, self.broker, sleep=lambda _s: None)

    def orders(self) -> list[dict[str, Any]]:
        return self.broker.published("order")

    def instant_actions(self) -> list[dict[str, Any]]:
        return [a for m in self.broker.published("instantActions") for a in m["actions"]]

    def assert_schema_valid(self) -> None:
        for topic, payload in self.broker.log:
            name = topic.rsplit("/", 1)[-1]
            errors = sorted(VALIDATORS[name].iter_errors(payload), key=str)
            assert not errors, f"{topic}: {errors[0].message}"


@pytest.fixture
def rig() -> Iterator[Rig]:
    r = Rig(make_config())
    yield r
    r.assert_schema_valid()
    r.adapter.close()


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def test_topic_prefix_follows_section_4_2() -> None:
    assert make_config().topic_prefix == "vda5050/v3/ExampleAMR/amr-0001"
    assert make_config(interface_name="uagv", protocol_version="2.1.0").topic_prefix == "uagv/v2/ExampleAMR/amr-0001"


def test_route_is_shortest_path_over_configured_edges() -> None:
    cfg = make_config()
    route = cfg.route("charge_dock_1", "shelf_a3")
    assert route is not None
    assert [loc for loc, _ in route] == ["hub", "shelf_a3"]
    assert cfg.route("hub", "hub") == []
    assert cfg.route("hub", "island") is None


def test_one_way_edge_is_not_driven_backwards() -> None:
    cfg = make_config(edges=[EdgeSpec(start="hub", end="shelf_a3", bidirectional=False)])
    assert cfg.route("hub", "shelf_a3") is not None
    assert cfg.route("shelf_a3", "hub") is None


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"edges": [EdgeSpec(start="hub", end="nowhere")]}, "unknown node"),
        ({"primary_dock": "nowhere"}, "primary_dock"),
        ({"serial_number": "amr/1"}, "serial_number"),
    ],
)
def test_bad_config_is_refused(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        make_config(**overrides)


def test_load_config_from_yaml(tmp_path: Path) -> None:
    path = tmp_path / "vda5050_adapter.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "manufacturer": "ExampleAMR",
                "serial_number": "amr-0001",
                "map_id": "m",
                "nodes": {"a": {"node_id": "A", "x": 0, "y": 0}, "b": {"node_id": "B", "x": 1, "y": 0}},
                "edges": [{"start": "a", "end": "b"}],
            }
        ),
        encoding="utf-8",
    )
    cfg = load_vda5050_config(path)
    assert cfg.route("a", "b") is not None
    path.write_text("- not a mapping\n", encoding="utf-8")
    with pytest.raises(ValueError, match="YAML mapping"):
        load_vda5050_config(path)


def test_example_adapter_config_loads() -> None:
    cfg = load_vda5050_config(REPO / "examples" / "vda5050" / "vda5050_adapter.yaml")
    assert cfg.route("charge_dock_1", "shelf_a3") is not None


# ---------------------------------------------------------------------------
# Protocol surface
# ---------------------------------------------------------------------------


def test_adapter_satisfies_the_substrate_protocol(rig: Rig) -> None:
    assert isinstance(rig.adapter, ROSAdapter)


def test_move_to_sends_one_released_order_along_the_route(rig: Rig) -> None:
    result = rig.adapter.send_navigation_goal(location="shelf_a3", speed=0.8)
    assert result.success, result.reason
    assert result.frame == "warehouse-1"
    assert result.final_pose is not None and math.isclose(result.final_pose["x"], 6.0)

    (order,) = rig.orders()
    assert order["orderUpdateId"] == 0
    assert [n["nodeId"] for n in order["nodes"]] == ["N-CHG1", "N-HUB", "N-A3"]
    assert [n["sequenceId"] for n in order["nodes"]] == [0, 2, 4]
    assert [e["sequenceId"] for e in order["edges"]] == [1, 3]
    assert all(n["released"] for n in order["nodes"]) and all(e["released"] for e in order["edges"])
    # URML speed caps every edge; the configured edge limit wins where lower.
    assert [e["maximumSpeed"] for e in order["edges"]] == [0.8, 0.8]
    assert order["edges"][0]["edgeId"] == "charge_dock_1--hub"
    assert rig.vehicle.last_node_id == "N-A3"


def test_edge_limit_applies_when_lower_than_program_speed(rig: Rig) -> None:
    assert rig.adapter.send_navigation_goal(location="hub", speed=1.4).success
    (order,) = rig.orders()
    assert order["edges"][0]["maximumSpeed"] == 1.0


def test_move_to_current_node_sends_nothing(rig: Rig) -> None:
    assert rig.adapter.send_navigation_goal(location="charge_dock_1").success
    assert rig.orders() == []


@pytest.mark.parametrize(
    ("kwargs", "prefix"),
    [
        ({"location": "loading_bay_9"}, "location_not_configured"),
        ({"pose": {"x": 1.0, "y": 2.0}}, "vda5050_requires_named_location"),
        ({"location": "island"}, "no_route"),
    ],
)
def test_navigation_refusals_send_no_order(rig: Rig, kwargs: dict[str, Any], prefix: str) -> None:
    result = rig.adapter.send_navigation_goal(**kwargs)
    assert not result.success and (result.reason or "").startswith(prefix)
    assert rig.orders() == []


def test_dock_charge_until_full(rig: Rig) -> None:
    rig.vehicle.state_of_charge = 40.0
    assert rig.adapter.send_navigation_goal(location="hub").success
    result = rig.adapter.send_docking_goal(station="primary", service="charge", until="full")
    assert result.success, result.reason
    order = rig.orders()[-1]
    assert order["nodes"][-1]["nodeId"] == "N-CHG1"
    assert [a["actionType"] for a in order["nodes"][-1]["actions"]] == ["startCharging"]
    assert rig.vehicle.charging and rig.vehicle.state_of_charge == 100.0


def test_dock_charge_reports_incomplete_charge() -> None:
    rig = Rig(make_config(full_charge_percent=100.0))
    rig.vehicle.supported_actions.add("startCharging")
    # A vehicle that starts charging but never gets there.
    original = rig.vehicle._perform

    def slow_charger(action: dict[str, Any]) -> tuple[str, str | None]:
        status, result = original(action)
        if action["actionType"] == "startCharging":
            rig.vehicle.state_of_charge = 61.0
        return status, result

    rig.vehicle._perform = slow_charger  # type: ignore[method-assign]
    result = rig.adapter.send_docking_goal(station="charge_dock_1", service="charge", until="full")
    assert not result.success and (result.reason or "").startswith("charge_incomplete")
    rig.assert_schema_valid()


def test_dock_park_just_drives(rig: Rig) -> None:
    assert rig.adapter.send_navigation_goal(location="conveyor_a").success
    assert rig.adapter.send_docking_goal(station="charge_dock_1", service="park").success
    assert rig.orders()[-1]["nodes"][-1]["actions"] == []


@pytest.mark.parametrize(
    ("kwargs", "prefix"),
    [
        ({"station": "nowhere", "service": "charge"}, "station_not_configured"),
        ({"station": "charge_dock_1", "service": "wash"}, "service_not_configured"),
        ({"station": "charge_dock_1", "service": "charge", "until": "depleted"}, "until_not_supported"),
        ({"station": "charge_dock_1", "service": "park", "until": "full"}, "until_not_supported"),
    ],
)
def test_dock_refusals(rig: Rig, kwargs: dict[str, Any], prefix: str) -> None:
    result = rig.adapter.send_docking_goal(**kwargs)
    assert not result.success and (result.reason or "").startswith(prefix)
    assert rig.orders() == []


def test_grasp_and_release_become_pick_and_drop_at_the_station(rig: Rig) -> None:
    assert rig.adapter.send_navigation_goal(location="shelf_a3").success
    assert rig.adapter.send_manipulation_goal(action="grasp", target={"class": "tote"}).success
    assert rig.vehicle.loads and rig.vehicle.loads[0]["loadType"] == "tote"
    pick_order = rig.orders()[-1]
    assert len(pick_order["nodes"]) == 1 and pick_order["edges"] == []
    (pick,) = pick_order["nodes"][0]["actions"]
    params = {p["key"]: p["value"] for p in pick["actionParameters"]}
    assert pick["actionType"] == "pick"
    assert params == {"stationName": "A3-shelf", "stationType": "rack", "loadType": "tote"}

    assert rig.adapter.send_navigation_goal(location="conveyor_a").success
    assert rig.adapter.send_manipulation_goal(action="release", release_mode="place").success
    drop = rig.orders()[-1]["nodes"][0]["actions"][0]
    assert drop["actionType"] == "drop"
    assert {p["key"]: p["value"] for p in drop["actionParameters"]}["stationName"] == "conveyor_a"
    assert rig.vehicle.loads == []


def test_hand_to_user_is_not_supported(rig: Rig) -> None:
    result = rig.adapter.send_manipulation_goal(action="release", release_mode="hand_to_user")
    assert not result.success and (result.reason or "").startswith("not_supported_on_vda5050")


def test_failed_action_fails_the_step(rig: Rig) -> None:
    rig.vehicle.fail_actions.add("pick")
    result = rig.adapter.send_manipulation_goal(action="grasp", target={"class": "tote"})
    assert not result.success
    assert result.reason == "action_failed: pick (pick failed (simulated))."


def test_detect_runs_detect_object_at_the_expected_station(rig: Rig) -> None:
    assert rig.adapter.send_navigation_goal(location="shelf_a3").success
    det = rig.adapter.query_detection(object_class="tote", where_near="shelf_a3")
    assert det.success, det.reason
    assert det.payload is not None
    assert det.payload["class"] == "tote" and det.payload["station"] == "shelf_a3"
    assert det.payload["confidence"] is None  # the interface reports none; none is invented
    wrong_place = rig.adapter.query_detection(object_class="tote", where_near="conveyor_a")
    assert not wrong_place.success and (wrong_place.reason or "").startswith("location_mismatch")


def test_detect_without_detect_object_is_refused_before_sending() -> None:
    rig = Rig(make_config(supported_actions=["cancelOrder", "startPause", "stopPause", "pick", "drop"]))
    det = rig.adapter.query_detection(object_class="tote")
    assert not det.success and (det.reason or "").startswith("action_not_supported_by_vehicle")
    assert rig.orders() == []


def test_measurements_come_from_a_fresh_state(rig: Rig) -> None:
    battery = rig.adapter.take_measurement(what="battery", target=None, sensor=None)
    assert battery.success and battery.payload is not None
    assert battery.payload["value"] == 80.0 and battery.payload["unit"] == "percent"
    assert any(a["actionType"] == "stateRequest" for a in rig.instant_actions())
    volts = rig.adapter.take_measurement(what="voltage", target=None, sensor=None)
    assert volts.success and volts.payload is not None and volts.payload["value"] == 48.0
    missing = rig.adapter.take_measurement(what="current", target=None, sensor=None)
    assert not missing.success and (missing.reason or "").startswith("measurement_not_reported")


def test_call_program_runs_the_mapped_vendor_action(rig: Rig) -> None:
    result = rig.adapter.call_named_program(name="wrap_pallet", args={"tension": "high"})
    assert result.success, result.reason
    (action,) = rig.orders()[-1]["nodes"][0]["actions"]
    assert action["actionType"] == "wrapPallet"
    assert {p["key"]: p["value"] for p in action["actionParameters"]} == {"layers": 3, "tension": "high"}
    unmapped = rig.adapter.call_named_program(name="unmapped")
    assert not unmapped.success and (unmapped.reason or "").startswith("program_not_configured")


# ---------------------------------------------------------------------------
# Refusals, rejections, timeouts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("setup", "prefix"),
    [
        (lambda v: setattr(v, "operating_mode", "MANUAL"), "vehicle_not_available"),
        (lambda v: setattr(v, "emergency_stop", "MANUAL"), "vehicle_emergency_stop"),
        (lambda v: setattr(v, "last_node_id", "N-UNKNOWN"), "vehicle_position_unknown"),
        (
            lambda v: v.errors.append({"errorType": "LOCALIZATION_ERROR", "errorLevel": "FATAL"}),
            "vehicle_error",
        ),
    ],
)
def test_preflight_refuses_without_sending_an_order(rig: Rig, setup: Any, prefix: str) -> None:
    setup(rig.vehicle)
    result = rig.adapter.send_navigation_goal(location="hub")
    assert not result.success and (result.reason or "").startswith(prefix), result.reason
    assert rig.orders() == []


def test_vehicle_rejection_is_reported_and_does_not_block_the_next_order(rig: Rig) -> None:
    # The config claims pick; this vehicle cannot do it, so it rejects the order.
    rig.vehicle.supported_actions.discard("pick")
    result = rig.adapter.send_manipulation_goal(action="grasp", target={"class": "tote"})
    assert not result.success
    assert (result.reason or "").startswith("order_rejected: INVALID_ORDER_ACTION (WARNING)")
    assert rig.vehicle.order_id == ""  # never taken over
    # The rejection warning stays on the vehicle until it accepts a new order. It must not
    # stop that new order from being sent.
    assert rig.adapter.send_navigation_goal(location="hub").success
    assert rig.vehicle.errors == []


def test_timeout_cancels_the_order() -> None:
    rig = Rig(make_config(), auto_run=False)
    result = rig.adapter.send_navigation_goal(location="shelf_a3")
    assert not result.success and (result.reason or "").startswith("order_timeout")
    cancel = [a for a in rig.instant_actions() if a["actionType"] == "cancelOrder"]
    assert len(cancel) == 1
    assert cancel[0]["actionParameters"] == [{"key": "orderId", "value": rig.orders()[0]["orderId"]}]
    assert rig.vehicle.node_states == [] and rig.vehicle.edge_states == []
    rig.assert_schema_valid()


def test_busy_vehicle_is_not_sent_a_second_order() -> None:
    rig = Rig(make_config(), auto_run=False)
    rig.adapter.send_navigation_goal(location="shelf_a3")  # times out, cancels
    rig.vehicle.auto_run = False
    # Put an order back on the vehicle directly, as another fleet control might.
    rig.broker.publish(f"{rig.config.topic_prefix}/order", rig.orders()[0] | {"orderId": "someone-else"})
    result = rig.adapter.send_navigation_goal(location="hub")
    assert not result.success and (result.reason or "").startswith("vehicle_busy")


def test_silent_vehicle_is_reported() -> None:
    broker = InMemoryBroker()
    adapter = Vda5050Adapter(make_config(), broker, sleep=lambda _s: None)
    result = adapter.send_navigation_goal(location="hub")
    assert not result.success and (result.reason or "").startswith("vehicle_silent")


def test_unsupported_and_not_applicable(rig: Rig) -> None:
    unsupported = [
        rig.adapter.wait_for_condition(
            kind="event", name="partner_ready", input_mode=None, threshold=None, timeout_seconds=None
        ),
        rig.adapter.run_scan(area={}, pattern="grid", overlap=0.1, altitude=None, media="sensor_only", sensor=None),
        rig.adapter.capture_media(media="photo", target=None, duration_seconds=None, attributes=None),
        rig.adapter.emit_speech(utterance="hi", locale=None, style="notice", interrupt=False),
        rig.adapter.acquire_speech(prompt=None, locale=None, timeout_seconds=None, expected="free_form", choices=None),
    ]
    for r in unsupported:
        assert not r.success and (r.reason or "").startswith("not_supported_on_vda5050")
    for r in (
        rig.adapter.send_takeoff_goal(altitude=1.0),
        rig.adapter.send_land_goal(),
        rig.adapter.send_return_to_home_goal(),
    ):
        assert not r.success and (r.reason or "").startswith("not_applicable_vda5050")
    assert rig.adapter.wait_passively(duration_seconds=0.5).success
    assert rig.adapter.emit_report(
        to="fleet_manager", facts={"a": 1}, attachments=None, status="success", severity="info"
    ).success


def test_missing_paho_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "paho", None)
    monkeypatch.setitem(sys.modules, "paho.mqtt", None)
    monkeypatch.setitem(sys.modules, "paho.mqtt.client", None)
    with pytest.raises(RuntimeError, match=r"\[mqtt\] extra"):
        Vda5050Adapter(make_config())


def test_conformance_runner_accepts_factory() -> None:
    from urml_conformance import ConformanceRunner

    assert ConformanceRunner(adapter_factory=lambda: Rig(make_config()).adapter) is not None
