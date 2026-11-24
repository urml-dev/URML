"""Hermetic tests for Iso21423Adapter: no broker, no robot, no paho-mqtt.

The adapter talks to a ``SimulatedImr`` over an ``InMemoryBroker`` that keeps
retained messages. These tests check the adapter against URML's reading of
the request model; they are not a check against the published standard,
which is still to be done (see the package README).
"""

from __future__ import annotations

import sys
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from urml_ros2_runtime.substrate.base import ROSAdapter

from urml_iso21423_runtime import (
    Dock,
    InMemoryBroker,
    Iso21423Adapter,
    Iso21423Config,
    Place,
    SimulatedImr,
    VendorAction,
    load_iso21423_config,
)

REPO = Path(__file__).resolve().parents[3]
UUID_RE = r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"


def make_config(**overrides: Any) -> Iso21423Config:
    base: dict[str, Any] = {
        "requester_id": "5f4d2824-d279-4fdf-9050-62e0cef72f25",
        "target_id": "42177726-26f7-4f5c-b735-a12a427bb96d",
        "ccs_id": "2385eed2-86ca-4dc9-8f17-dac062ce9a08",
        "places": {
            "charge_dock_1": Place(x=-4.0, y=0.0),
            "shelf_a3": Place(x=6.0, y=-2.0),
            "conveyor_a": Place(x=0.0, y=4.0),
            "aisle_mid": Place(x=3.0, y=0.0),
        },
        "docks": {
            "charge_dock_1": Dock(location="charge_dock_1", dock_id="7c2e4f6a-1b3d-4c5e-8f9a-0b1c2d3e4f5a"),
            "shelf_a3": Dock(location="shelf_a3"),
            "conveyor_a": Dock(location="conveyor_a"),
        },
        "primary_dock": "charge_dock_1",
        "program_to_action": {
            "wrap_pallet": VendorAction(type="wrapPallet", format="ExampleRobotics", properties={"layers": 3})
        },
        "request_timeout_seconds": 0.2,
        "state_timeout_seconds": 0.2,
        "charge_timeout_seconds": 0.2,
    }
    base.update(overrides)
    return Iso21423Config(**base)


class Rig:
    def __init__(self, config: Iso21423Config, **robot: Any) -> None:
        self.config = config
        self.broker = InMemoryBroker()
        robot.setdefault("start_at", "charge_dock_1")
        self.robot = SimulatedImr(self.broker, config, **robot)
        self.adapter = Iso21423Adapter(config, self.broker, sleep=lambda _s: None)

    def requests(self) -> list[dict[str, Any]]:
        return [p for t, p in self.broker.published_requests()]

    def details(self) -> list[list[dict[str, Any]]]:
        return [r["details"] for r in self.requests()]


def _published_requests(self: InMemoryBroker) -> list[tuple[str, dict[str, Any]]]:
    return [(t, p) for t, p, _q, _r in self.log if p is not None and "/request/" in t and not t.endswith("/status")]


InMemoryBroker.published_requests = _published_requests  # type: ignore[attr-defined]


@pytest.fixture
def rig() -> Iterator[Rig]:
    r = Rig(make_config())
    yield r
    r.adapter.close()


# ---------------------------------------------------------------------------
# Config and topics
# ---------------------------------------------------------------------------


def test_topics_follow_the_entity_namespace() -> None:
    cfg = make_config()
    assert cfg.robot_topic("identity") == f"/ISO_21423/v1/IMR/{cfg.target_id}/identity"
    fm = make_config(target_type="IMRFM", robot_id="91403a21-7534-4467-99a6-79c46a130fe8")
    assert fm.target_topic("request/x") == f"/ISO_21423/v1/IMRFM/{fm.target_id}/request/x"
    assert fm.robot_topic("status") == "/ISO_21423/v1/IMR/91403a21-7534-4467-99a6-79c46a130fe8/status"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"target_id": "not-a-uuid"}, "badly formed"),
        ({"docks": {"d": Dock(location="nowhere")}}, "unknown place"),
        ({"primary_dock": "nowhere"}, "primary_dock"),
        ({"program_to_action": {"p": {"type": "x", "format": "ISO-21423"}}}, "own format"),
        ({"requester_type": "urml"}, "requester_type"),
    ],
)
def test_bad_config_is_refused(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        make_config(**overrides)


def test_example_config_loads(tmp_path: Path) -> None:
    cfg = load_iso21423_config(REPO / "examples" / "iso21423" / "iso21423_adapter.yaml")
    assert cfg.primary_dock == "charge_dock_1"
    bad = tmp_path / "bad.yaml"
    bad.write_text("- a list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="YAML mapping"):
        load_iso21423_config(bad)


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


def test_adapter_satisfies_the_substrate_protocol(rig: Rig) -> None:
    assert isinstance(rig.adapter, ROSAdapter)


def test_the_adapter_announces_itself(rig: Rig) -> None:
    rig.adapter.send_navigation_goal(location="aisle_mid")
    identity = rig.broker.retained(f"/ISO_21423/v1/URML/{rig.config.requester_id}/identity")
    assert identity is not None
    assert identity["capabilities"] == {"provides": ["identity"], "accepts": {"requests": []}}


def test_move_to_is_one_move_request(rig: Rig) -> None:
    result = rig.adapter.send_navigation_goal(location="shelf_a3")
    assert result.success, result.reason
    assert result.final_pose == {"x": 6.0, "y": -2.0, "theta": 0.0}
    (request,) = rig.requests()
    assert request["source"] == rig.config.requester_id
    assert request["destination"] == rig.config.target_id
    (move,) = request["details"]
    assert move["type"] == "move" and move["format"] == "ISO-21423" and move["blocking"] is True
    assert move["properties"]["location"] == {"ccsId": rig.config.ccs_id, "x": 6.0, "y": -2.0, "z": 0.0}
    assert move["properties"]["toleranceRadius"] == 0.25


def test_requests_are_retained_qos2_and_cleared_after(rig: Rig) -> None:
    rig.adapter.send_navigation_goal(location="shelf_a3")
    sends = [(t, p, q, r) for t, p, q, r in rig.broker.log if "/request/" in t and not t.endswith("/status")]
    (topic, payload, qos, retain), (clear_topic, cleared, _q, clear_retain) = sends
    assert qos == 2 and retain and payload is not None
    assert clear_topic == topic and cleared is None and clear_retain
    assert rig.broker.retained(topic) is None
    request_uuid = topic.rsplit("/", 1)[-1]
    assert uuid.UUID(request_uuid).version == 4


def test_sequence_ids_count_up(rig: Rig) -> None:
    rig.adapter.send_navigation_goal(location="shelf_a3")
    rig.adapter.send_navigation_goal(location="conveyor_a")
    assert [r["sequenceId"] for r in rig.requests()] == [1, 2]


@pytest.mark.parametrize(
    ("kwargs", "prefix"),
    [
        ({"location": "loading_bay_9"}, "location_not_configured"),
        ({"pose": {"x": 1.0, "y": 2.0}}, "iso21423_requires_named_location"),
    ],
)
def test_navigation_refusals_send_nothing(rig: Rig, kwargs: dict[str, Any], prefix: str) -> None:
    result = rig.adapter.send_navigation_goal(**kwargs)
    assert not result.success and (result.reason or "").startswith(prefix)
    assert rig.requests() == []


def test_a_speed_the_request_cannot_carry_is_refused(rig: Rig) -> None:
    slow = rig.adapter.send_navigation_goal(location="shelf_a3", speed=0.5)
    assert not slow.success and (slow.reason or "").startswith("speed_not_expressible")
    assert rig.requests() == []
    fast_enough = rig.adapter.send_navigation_goal(location="shelf_a3", speed=2.0)  # rated 1.5
    assert fast_enough.success, fast_enough.reason


def test_dock_charge_until_full(rig: Rig) -> None:
    rig.robot.soc = 0.3
    assert rig.adapter.send_navigation_goal(location="aisle_mid").success
    result = rig.adapter.send_docking_goal(station="primary", service="charge", until="full")
    assert result.success, result.reason
    (dock,) = rig.requests()[-1]["details"]
    assert dock["type"] == "dock"
    assert dock["properties"]["dockActions"] == ["CHARGE"]
    assert dock["properties"]["dockId"] == "7c2e4f6a-1b3d-4c5e-8f9a-0b1c2d3e4f5a"
    assert rig.robot.soc == 1.0


def test_dock_park_has_no_station_actions(rig: Rig) -> None:
    assert rig.adapter.send_docking_goal(station="conveyor_a", service="park").success
    assert "dockActions" not in rig.requests()[-1]["details"][0]["properties"]


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
    assert rig.requests() == []


def test_grasp_and_release_are_pick_and_drop_at_a_station(rig: Rig) -> None:
    assert rig.adapter.send_navigation_goal(location="shelf_a3").success
    assert rig.adapter.send_manipulation_goal(action="grasp", target={"class": "tote"}).success
    assert rig.requests()[-1]["details"][0]["properties"]["dockActions"] == ["PICK"]
    assert rig.robot.load == "PICK"
    assert rig.adapter.send_navigation_goal(location="conveyor_a").success
    assert rig.adapter.send_manipulation_goal(action="release", release_mode="place").success
    assert rig.requests()[-1]["details"][0]["properties"]["dockActions"] == ["DROP"]
    assert rig.robot.load is None


def test_grasp_away_from_a_station_is_refused(rig: Rig) -> None:
    assert rig.adapter.send_navigation_goal(location="aisle_mid").success
    result = rig.adapter.send_manipulation_goal(action="grasp")
    assert not result.success and (result.reason or "").startswith("not_at_station")


def test_detect_is_not_supported(rig: Rig) -> None:
    result = rig.adapter.query_detection(object_class="tote")
    assert not result.success and "pick_from" in (result.reason or "")


def test_measurements(rig: Rig) -> None:
    rig.adapter.send_navigation_goal(location="aisle_mid")
    battery = rig.adapter.take_measurement(what="battery", target=None, sensor=None)
    assert battery.success and battery.payload is not None and battery.payload["value"] == pytest.approx(80.0)
    position = rig.adapter.take_measurement(what="position", target=None, sensor=None)
    assert position.success and position.payload is not None and position.payload["value"]["x"] == 3.0
    missing = rig.adapter.take_measurement(what="current", target=None, sensor=None)
    assert not missing.success and (missing.reason or "").startswith("measurement_not_reported")


def test_call_program_sends_the_vendor_action() -> None:
    rig = Rig(make_config(), accepts=["move", "dock", "cancel", "wrapPallet"], vendor_formats=["ExampleRobotics"])
    result = rig.adapter.call_named_program(name="wrap_pallet", args={"tension": "high"})
    assert result.success, result.reason
    (action,) = rig.requests()[-1]["details"]
    assert action == {
        "type": "wrapPallet",
        "version": "1.0",
        "format": "ExampleRobotics",
        "blocking": True,
        "atomic": False,
        "properties": {"layers": 3, "tension": "high"},
    }
    unmapped = rig.adapter.call_named_program(name="nope")
    assert not unmapped.success and (unmapped.reason or "").startswith("program_not_configured")


# ---------------------------------------------------------------------------
# Refusals, rejections, timeouts, disconnection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("setup", "prefix"),
    [
        (lambda r: setattr(r, "mode", "MODE_MANUAL"), "robot_not_available: operating mode is MODE_MANUAL"),
        (lambda r: setattr(r, "extra_states", ["LOST"]), "robot_not_available: the robot reports LOST"),
        (lambda r: setattr(r, "extra_states", ["STOP_CATEGORY_1"]), "robot_not_available"),
        (lambda r: setattr(r, "accepts", ["dock"]), "action_not_accepted"),
    ],
)
def test_preflight_refuses_without_sending(setup: Any, prefix: str) -> None:
    rig = Rig(make_config())
    setup(rig.robot)
    rig.robot.publish_identity()
    rig.robot.publish_status()
    result = rig.adapter.send_navigation_goal(location="shelf_a3")
    assert not result.success and (result.reason or "").startswith(prefix), result.reason
    assert rig.requests() == []


def test_a_robot_that_never_announced_itself_is_reported() -> None:
    adapter = Iso21423Adapter(make_config(), InMemoryBroker(), sleep=lambda _s: None)
    result = adapter.send_navigation_goal(location="shelf_a3")
    assert not result.success and (result.reason or "").startswith("robot_not_announced")


def test_a_dropped_robot_is_offline_until_it_speaks_again(rig: Rig) -> None:
    rig.robot.drop()
    result = rig.adapter.send_navigation_goal(location="shelf_a3")
    assert not result.success and (result.reason or "").startswith("robot_offline")
    rig.robot.publish_status()  # back on the broker
    assert rig.adapter.send_navigation_goal(location="shelf_a3").success


def test_a_robot_rejection_reports_its_reason(rig: Rig) -> None:
    rig.robot.fail_actions.add("move")
    result = rig.adapter.send_navigation_goal(location="shelf_a3")
    assert not result.success
    assert result.reason == "request_aborted: move ABORTED (GENERAL_FAILURE): move failed (simulated)."


def test_a_format_the_robot_does_not_know_is_aborted() -> None:
    rig = Rig(make_config(), accepts=["move", "wrapPallet"])
    result = rig.adapter.call_named_program(name="wrap_pallet")
    assert not result.success and "FORMAT_NOT_SUPPORTED" in (result.reason or "")


def test_a_timeout_cancels_the_request() -> None:
    rig = Rig(make_config(), auto_run=False)
    result = rig.adapter.send_navigation_goal(location="shelf_a3")
    assert not result.success and (result.reason or "").startswith("request_timeout")
    move_request, cancel_request = rig.requests()
    (cancel,) = cancel_request["details"]
    assert cancel["type"] == "cancel"
    assert cancel["properties"] == {"source": rig.config.requester_id, "requestId": move_request["sequenceId"]}
    statuses = [p for t, p in rig.broker.published("status") if p and p.get("requestSequenceId") == 1]
    assert statuses[-1]["status"] == "CANCELED"
    retained_requests = [t for t in rig.broker._retained if "/request/" in t and not t.endswith("/status")]
    assert retained_requests == []


def test_through_a_fleet_manager() -> None:
    robot_id = "91403a21-7534-4467-99a6-79c46a130fe8"
    cfg = make_config(target_type="IMRFM", robot_id=robot_id)
    broker = InMemoryBroker()
    robot = SimulatedImr(broker, cfg, start_at="charge_dock_1")
    fm_identity = {
        "id": cfg.target_id,
        "timestamp": "2026-11-24T10:00:00.000Z",
        "entityType": "IMRFM",
        "manufacturerName": "Example Fleet",
        "capabilities": {"provides": ["identity"], "accepts": {"requests": ["move"]}, "manages": [robot_id]},
    }
    broker.publish(cfg.target_topic("identity"), fm_identity, qos=1, retain=True)
    # The fleet manager relays requests on its topic to the robot's topic and back.
    broker.subscribe(
        cfg.target_topic("request/+"),
        lambda t, p: p and broker.publish(cfg.robot_topic("request/" + t.rsplit("/", 1)[-1]), p, qos=2, retain=True),
    )
    broker.subscribe(
        cfg.robot_topic("request/+/status"),
        lambda t, p: (
            p and broker.publish(cfg.target_topic("request/" + t.split("/")[-2] + "/status"), p, qos=2, retain=True)
        ),
    )
    adapter = Iso21423Adapter(cfg, broker, sleep=lambda _s: None)
    result = adapter.send_navigation_goal(location="shelf_a3")
    assert result.success, result.reason
    assert robot.received[-1]["destination"] == robot_id
    refused = adapter.send_docking_goal(station="charge_dock_1", service="park")
    assert not refused.success and "fleet manager does not accept dock" in (refused.reason or "")


def test_unsupported_and_not_applicable(rig: Rig) -> None:
    for r in (
        rig.adapter.wait_for_condition(kind="event", name="x", input_mode=None, threshold=None, timeout_seconds=None),
        rig.adapter.run_scan(area={}, pattern="grid", overlap=0.1, altitude=None, media="sensor_only", sensor=None),
        rig.adapter.capture_media(media="photo", target=None, duration_seconds=None, attributes=None),
        rig.adapter.emit_speech(utterance="hi", locale=None, style="notice", interrupt=False),
        rig.adapter.acquire_speech(prompt=None, locale=None, timeout_seconds=None, expected="free_form", choices=None),
        rig.adapter.send_manipulation_goal(action="release", release_mode="hand_to_user"),
    ):
        assert not r.success and (r.reason or "").startswith("not_supported_on_iso21423")
    for r in (
        rig.adapter.send_takeoff_goal(altitude=1.0),
        rig.adapter.send_land_goal(),
        rig.adapter.send_return_to_home_goal(),
    ):
        assert not r.success and (r.reason or "").startswith("not_applicable_iso21423")
    assert rig.adapter.wait_passively(duration_seconds=1.0).success
    assert rig.adapter.emit_report(to="x", facts={}, attachments=None, status="success", severity="info").success


def test_ids_are_valid_uuids(rig: Rig) -> None:
    import re

    rig.adapter.send_navigation_goal(location="shelf_a3")
    for t, p, _q, _r in rig.broker.log:
        for part in t.split("/"):
            if len(part) == 36:
                assert re.match(UUID_RE, part), t
        if isinstance(p, dict) and "source" in p:
            assert re.match(UUID_RE, p["source"])


def test_missing_paho_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("paho", "paho.mqtt", "paho.mqtt.client"):
        monkeypatch.setitem(sys.modules, name, None)
    with pytest.raises(RuntimeError, match=r"\[mqtt\] extra"):
        Iso21423Adapter(make_config())


def test_conformance_runner_accepts_factory() -> None:
    from urml_conformance import ConformanceRunner

    assert ConformanceRunner(adapter_factory=lambda: Rig(make_config()).adapter) is not None


def test_example_config_matches_the_example_program() -> None:
    program = yaml.safe_load((REPO / "examples" / "iso21423" / "aisle-run.urml.yaml").read_text(encoding="utf-8"))
    cfg = load_iso21423_config(REPO / "examples" / "iso21423" / "iso21423_adapter.yaml")
    for step in program["behavior"]["steps"]:
        target = (step.get("move_to") or {}).get("location") or (step.get("dock") or {}).get("at")
        if target:
            assert target in cfg.places
