"""The audit-method check applies only to adapters that keep a call log.

The mock adapter records every substrate call in ``call_log``, and fixtures
pin the expected sequence with ``expected_execution.audit_methods``. A real
adapter (rclpy, a vendor SDK) keeps no such log. Comparing its absent log
with the fixture's expected methods would fail every real run, however well
the robot did, which is what the gazebo-e2e job hit on the live TurtleBot 4
sim: the patrol succeeded in 3 steps and the report still said
``audit methods do not match: actual=[]``.
"""

from __future__ import annotations

from typing import Any

from urml_ros2_runtime import MockROSAdapter

from urml_conformance import ConformanceRunner, discover_fixtures

_FIXTURE = "home/nav_patrol_positive"


class _NoCallLogAdapter:
    """Behaves like the mock but exposes no ``call_log``, like a real adapter."""

    def __init__(self) -> None:
        self._inner = MockROSAdapter()

    def __getattr__(self, name: str) -> Any:
        if name == "call_log":
            raise AttributeError(name)
        return getattr(self._inner, name)


def _nav_patrol() -> list[Any]:
    cases = [c for c in discover_fixtures() if c.name == _FIXTURE]
    assert cases, f"fixture {_FIXTURE!r} not found"
    assert cases[0].expected_execution is not None
    assert cases[0].expected_execution.audit_methods, "fixture must pin audit methods"
    return cases


def test_an_adapter_without_a_call_log_is_not_failed_on_audit_methods() -> None:
    report = ConformanceRunner(cases=_nav_patrol(), adapter_factory=_NoCallLogAdapter).run()
    assert report.all_passed, report.render()


def test_a_call_log_that_disagrees_still_fails() -> None:
    class _WrongCallLog(MockROSAdapter):
        @property  # type: ignore[override]
        def call_log(self) -> list[dict[str, Any]]:
            return [{"method": "dock"}]

        @call_log.setter
        def call_log(self, value: list[dict[str, Any]]) -> None:
            pass

    report = ConformanceRunner(cases=_nav_patrol(), adapter_factory=_WrongCallLog).run()
    assert not report.all_passed
    diagnostics = report.failed_cases()[0].diagnostics
    assert any("audit methods do not match" in d for d in diagnostics), diagnostics
