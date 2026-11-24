"""The harness records adapter calls; it never reads an adapter's own log (RFC-0706).

Fixtures pin the substrate calls a runtime must make with
``expected_execution.audit_methods`` (and ``per_member_audit`` for fleets).
The runner used to read those calls from ``adapter.call_log``, which only the
mock keeps. A real adapter (rclpy, a vendor SDK) was compared as if it had
called nothing: the gazebo-e2e job ran ``home/nav_patrol_positive`` on a live
TurtleBot 4 sim, Nav2 accepted all three goals, and the report still said
``audit methods do not match: actual=[]``.

The runner now wraps every adapter in ``RecordingAdapter`` and compares the
fixture with what the proxy recorded, for every adapter alike.
"""

from __future__ import annotations

from typing import Any

import pytest
from urml_ros2_runtime import MockROSAdapter

from urml_conformance import ConformanceRunner, discover_fixtures
from urml_conformance.fixtures import FixtureCase

_NAV_PATROL = "home/nav_patrol_positive"
_FLEET = "fleet/01_courier_to_arm_handoff_positive"


class _NoCallLogAdapter:
    """Does what the mock does but has no ``call_log``, like a real adapter."""

    def __init__(self) -> None:
        self._inner = MockROSAdapter()

    def __getattr__(self, name: str) -> Any:
        if name == "call_log":
            raise AttributeError(name)
        return getattr(self._inner, name)


class _LyingCallLog(MockROSAdapter):
    """A mock whose own log claims a call the runtime never made."""

    @property
    def call_log(self) -> list[dict[str, Any]]:
        return [{"method": "dock"}]

    @call_log.setter
    def call_log(self, value: list[dict[str, Any]]) -> None:
        pass


def _case(name: str) -> FixtureCase:
    cases = [c for c in discover_fixtures() if c.name == name]
    assert cases, f"fixture {name!r} not found"
    return cases[0]


def _with_audit(case: FixtureCase, methods: list[str]) -> FixtureCase:
    changed = case.model_copy(deep=True)
    assert changed.expected_execution is not None
    changed.expected_execution.audit_methods = methods
    return changed


def test_nav_patrol_pins_three_goals() -> None:
    expected = _case(_NAV_PATROL).expected_execution
    assert expected is not None
    assert expected.audit_methods == ["send_navigation_goal"] * 3


def test_an_adapter_without_a_call_log_passes_on_what_it_was_asked() -> None:
    report = ConformanceRunner(cases=[_case(_NAV_PATROL)], adapter_factory=_NoCallLogAdapter).run()
    assert report.all_passed, report.render()


def test_an_adapter_without_a_call_log_is_still_checked() -> None:
    two_goals = _with_audit(_case(_NAV_PATROL), ["send_navigation_goal"] * 2)
    report = ConformanceRunner(cases=[two_goals], adapter_factory=_NoCallLogAdapter).run()
    assert not report.all_passed
    (failed,) = report.failed_cases()
    assert any(
        "audit methods do not match" in d and d.count("send_navigation_goal") == 5
        for d in failed.diagnostics
    ), failed.diagnostics


def test_an_adapters_own_call_log_is_not_read() -> None:
    report = ConformanceRunner(cases=[_case(_NAV_PATROL)], adapter_factory=_LyingCallLog).run()
    assert report.all_passed, report.render()


def test_fleet_members_without_a_call_log_pass_and_are_checked() -> None:
    case = _case(_FLEET)
    assert case.expected_execution is not None
    per_member = case.expected_execution.per_member_audit
    assert per_member, "fixture must pin per-member audit methods"

    report = ConformanceRunner(cases=[case], adapter_factory=_NoCallLogAdapter).run()
    assert report.all_passed, report.render()

    changed = case.model_copy(deep=True)
    assert changed.expected_execution is not None and changed.expected_execution.per_member_audit
    member = sorted(per_member)[0]
    changed.expected_execution.per_member_audit[member] = []
    report = ConformanceRunner(cases=[changed], adapter_factory=_NoCallLogAdapter).run()
    assert not report.all_passed
    (failed,) = report.failed_cases()
    assert any(f"member {member!r} audit methods do not match" in d for d in failed.diagnostics)


_AUDIT_PINNED = [
    c
    for c in discover_fixtures()
    if c.expected_execution is not None and c.expected_execution.audit_methods is not None
]


def test_the_suite_pins_audit_methods_widely() -> None:
    assert len(_AUDIT_PINNED) >= 100


@pytest.mark.parametrize("case", _AUDIT_PINNED, ids=lambda c: c.name)
def test_harness_record_matches_the_mocks_own_log(case: FixtureCase) -> None:
    """Recording in the harness changes no outcome against the mock.

    The case passes on the harness's record, and the mock's own log names the
    same methods, so the two records agree on every audit-pinned fixture.
    """
    made: list[MockROSAdapter] = []

    def factory() -> MockROSAdapter:
        adapter = MockROSAdapter()
        made.append(adapter)
        return adapter

    report = ConformanceRunner(cases=[case], adapter_factory=factory).run()
    assert report.all_passed, report.render()
    assert case.expected_execution is not None
    assert [e["method"] for e in made[-1].call_log] == case.expected_execution.audit_methods
