"""The runtime writes one execution record per run (RFC-0715, Draft).

With ``evidence_log`` set, a run that got past re-validation ends with one
line in the log: the steps the runtime dispatched and what the adapter
reported back, whether the run completed, failed or raised. The record never
changes the run's result, and a record that could not be written is reported
on the result or on the exception. Hermetic: ``MockROSAdapter``, no ROS 2.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from urml_validator import validate
from urml_validator.evidence import (
    EXECUTION_RECORD_FORMAT,
    ExecutionRecord,
    ValidationRecord,
    append_record,
    build_record,
    content_digest,
    read_log,
    read_records,
    verify_log,
)
from urml_validator.monitor import Sample

from urml_ros2_runtime import (
    MockROSAdapter,
    NavigationResult,
    Shield,
    URMLRuntime,
    ValidationRejectedError,
    __version__,
    execution_record,
)
from urml_ros2_runtime.execution_record import validator_path

REPO_ROOT = Path(__file__).resolve().parents[3]
HOME = REPO_ROOT / "examples" / "home"
FIXTURES = REPO_ROOT / "reference" / "validator" / "tests" / "fixtures"


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


MANIFEST = _load(HOME / "red-mug.manifest.yaml")
ENVELOPE = _load(HOME / "red-mug.envelope.yaml")
SAFE = _load(HOME / "red-mug.urml.yaml")
GRASP_4N = _load(HOME / "red-mug.grasp-4n.urml.yaml")
TURTLEBOT = _load(FIXTURES / "manifests" / "turtlebot4_home.yaml")


def _moves(*locations: str, on_error: str = "abort_and_report") -> dict[str, Any]:
    return {
        "profile": "home",
        "behavior": {
            "type": "sequence",
            "on_error": on_error,
            "steps": [{"move_to": {"location": location}} for location in locations],
        },
    }


def _only_record(log: Path) -> ExecutionRecord:
    (record,) = read_log(log)
    assert isinstance(record, ExecutionRecord)
    return record


class _FailsOnCall(MockROSAdapter):
    """A mock whose n-th navigation raises instead of answering."""

    def __init__(self, call: int, error: BaseException) -> None:
        super().__init__()
        self._raise_on = call
        self._error = error
        self._navigations = 0

    def send_navigation_goal(self, *args: Any, **kwargs: Any) -> NavigationResult:
        self._navigations += 1
        if self._navigations == self._raise_on:
            raise self._error
        return super().send_navigation_goal(*args, **kwargs)


# ---------------------------------------------------------------------------
# A run that completes
# ---------------------------------------------------------------------------


def test_a_completed_run_writes_one_execution_record(tmp_path: Path) -> None:
    log = tmp_path / "nested" / "evidence.jsonl"
    result = URMLRuntime(MockROSAdapter(), evidence_log=log).execute(SAFE, MANIFEST, ENVELOPE, ("home",), policy=None)
    assert result.success and result.evidence_log_error is None
    record = _only_record(log)
    assert record.format == EXECUTION_RECORD_FORMAT
    assert (record.outcome, record.error) == ("completed", None)
    assert [(step.path, step.primitive, step.outcome, step.error) for step in record.steps] == [
        (["behavior", "steps", "0"], "move_to", "ok", None),
        (["behavior", "steps", "1"], "detect", "ok", None),
        (["behavior", "steps", "2"], "grasp", "ok", None),
        (["behavior", "steps", "3"], "move_to", "ok", None),
        (["behavior", "steps", "4"], "release", "ok", None),
    ]
    assert record.steps_executed == result.steps_executed == 5
    assert all(0 <= step.duration_s < 5 for step in record.steps)
    assert record.program_digest == content_digest(SAFE)
    assert record.manifest_digest == content_digest(MANIFEST)
    assert record.envelope_digest == content_digest(ENVELOPE)
    assert record.robot_id == MANIFEST["robot_id"]
    assert record.surface == "runtime"
    assert record.tool.model_dump() == {"name": "urml-ros2-runtime", "version": __version__}
    assert record.recorded_at.endswith("Z")
    assert (record.seq, record.prev) == (1, None)
    assert verify_log(log).intact


def test_the_record_does_not_change_the_result(tmp_path: Path) -> None:
    plain = URMLRuntime(MockROSAdapter()).execute(SAFE, MANIFEST, ENVELOPE, ("home",), policy=None)
    logged = URMLRuntime(MockROSAdapter(), evidence_log=tmp_path / "evidence.jsonl").execute(
        SAFE, MANIFEST, ENVELOPE, ("home",), policy=None
    )
    assert logged == plain


def test_no_log_means_no_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = URMLRuntime(MockROSAdapter()).execute(SAFE, MANIFEST, ENVELOPE, ("home",), policy=None)
    assert result.success and result.evidence_log_error is None
    assert list(tmp_path.iterdir()) == []


def test_the_runtime_names_the_surface_it_was_told(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    URMLRuntime(MockROSAdapter(), evidence_log=log, evidence_surface="mcp").execute(
        SAFE, MANIFEST, ENVELOPE, ("home",), policy=None
    )
    assert _only_record(log).surface == "mcp"


class _RenamedAdapter(MockROSAdapter):
    """A second adapter class with the mock's behavior, to tell two classes apart."""


def test_the_record_names_the_adapter_so_a_mock_run_reads_as_one(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    URMLRuntime(MockROSAdapter(), evidence_log=log).execute(SAFE, MANIFEST, envelope=ENVELOPE, profiles=("home",))
    mock = _only_record(log)
    assert mock.adapter == "urml_ros2_runtime.substrate.mock.MockROSAdapter"
    assert execution_record.adapter_name(MockROSAdapter()) == mock.adapter

    other_log = tmp_path / "other.jsonl"
    URMLRuntime(_RenamedAdapter(), evidence_log=other_log).execute(
        SAFE, MANIFEST, envelope=ENVELOPE, profiles=("home",)
    )
    other = _only_record(other_log)
    assert other.adapter.endswith("._RenamedAdapter")
    # The same program, the same steps, a different adapter: a different run.
    assert [s.model_dump(exclude={"duration_s"}) for s in other.steps] == [
        s.model_dump(exclude={"duration_s"}) for s in mock.steps
    ]
    assert other.record_id != mock.record_id


def test_a_program_without_an_envelope_records_none(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    runtime = URMLRuntime(MockROSAdapter(), evidence_log=log)
    runtime.execute(_moves("kitchen"), TURTLEBOT, profiles=("home",), policy=None)
    record = _only_record(log)
    assert record.envelope_digest is None
    assert record.manifest_digest == content_digest(TURTLEBOT)


def test_each_run_gets_its_own_record_and_the_chain_holds(tmp_path: Path) -> None:
    """Two runs on one runtime, after a verdict already in the log: three chained lines."""
    log = tmp_path / "evidence.jsonl"
    accepted = validate(SAFE, MANIFEST, ENVELOPE, profiles=("home",), policy=None)
    append_record(
        log,
        build_record(
            surface="api", stage="validation", result=accepted, program=SAFE,
            manifest=MANIFEST, envelope=ENVELOPE, policy=None, profiles=("home",),
        ),
    )
    runtime = URMLRuntime(MockROSAdapter(), evidence_log=log)
    runtime.execute(SAFE, MANIFEST, ENVELOPE, ("home",), policy=None)
    runtime.execute(_moves("kitchen"), MANIFEST, ENVELOPE, ("home",), policy=None)
    verdict, first, second = read_log(log)
    assert isinstance(verdict, ValidationRecord)
    assert isinstance(first, ExecutionRecord) and isinstance(second, ExecutionRecord)
    assert (len(first.steps), len(second.steps)) == (5, 1)
    assert (first.seq, second.seq) == (2, 3)
    # The run is tied to its verdict by the digest of the program.
    assert first.program_digest == verdict.program_digest
    check = verify_log(log)
    assert check.intact and (check.validation_records, check.execution_records) == (1, 2)


# ---------------------------------------------------------------------------
# A run that fails
# ---------------------------------------------------------------------------


def test_a_failed_run_records_the_step_that_failed(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    adapter = MockROSAdapter()
    adapter.set_navigation_result(NavigationResult(success=False, reason="path_blocked"))
    result = URMLRuntime(adapter, evidence_log=log).execute(SAFE, MANIFEST, ENVELOPE, ("home",), policy=None)
    assert result.success is False and result.evidence_log_error is None
    record = _only_record(log)
    assert (record.outcome, record.error) == ("failed", "path_blocked")
    assert [(step.path, step.primitive, step.outcome, step.error) for step in record.steps] == [
        (["behavior", "steps", "0"], "move_to", "failed", "path_blocked"),
    ]
    assert record.steps_executed == result.steps_executed == 1


def test_a_failure_with_no_reason_still_carries_an_error(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    adapter = MockROSAdapter()
    adapter.set_navigation_result(NavigationResult(success=False))
    URMLRuntime(adapter, evidence_log=log).execute(_moves("kitchen"), TURTLEBOT, profiles=("home",), policy=None)
    record = _only_record(log)
    assert record.outcome == "failed"
    assert record.steps[0].error == "the adapter reported failure and gave no reason"
    assert record.error == "the run failed and its last outcome gave no reason"


def test_a_run_that_carries_on_after_a_failed_step_records_both(tmp_path: Path) -> None:
    """`on_error: continue` absorbs the failure; the step list still shows it."""
    log = tmp_path / "evidence.jsonl"

    class _FirstMoveFails(MockROSAdapter):
        def send_navigation_goal(self, *args: Any, **kwargs: Any) -> NavigationResult:
            answer = super().send_navigation_goal(*args, **kwargs)
            first = sum(1 for call in self.call_log if call["method"] == "send_navigation_goal") == 1
            return NavigationResult(success=False, reason="path_blocked") if first else answer

    result = URMLRuntime(_FirstMoveFails(), evidence_log=log).execute(
        _moves("kitchen", "user", on_error="continue"), TURTLEBOT, profiles=("home",), policy=None
    )
    assert result.success
    record = _only_record(log)
    assert (record.outcome, record.error, record.steps_executed) == ("completed", None, 2)
    assert [(step.outcome, step.error) for step in record.steps] == [("failed", "path_blocked"), ("ok", None)]


def test_a_refused_program_gets_no_execution_record(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    with pytest.raises(ValidationRejectedError):
        URMLRuntime(MockROSAdapter(), evidence_log=log).execute(GRASP_4N, MANIFEST, ENVELOPE, ("home",), policy=None)
    (record,) = read_log(log)
    assert isinstance(record, ValidationRecord) and record.verdict == "refused"


# ---------------------------------------------------------------------------
# Paths are the validator's paths
# ---------------------------------------------------------------------------


def _path_of_a_validation_error(program: dict[str, Any]) -> list[str]:
    """Where the validator reports the one undeclared location in `program`."""
    result = validate(program, TURTLEBOT, profiles=("home",), policy=None)
    (error,) = [e for e in result.errors if str(e.code) == "capability.missing_location"]
    return list(error.path)


def _retry(location: str) -> dict[str, Any]:
    return {
        "profile": "home",
        "behavior": {"type": "retry", "max_attempts": 3, "behavior": {"move_to": {"location": location}}},
    }


def _nested(location: str) -> dict[str, Any]:
    return {
        "profile": "home",
        "behavior": {
            "type": "parallel",
            "complete_when": "all",
            "branches": [
                {"move_to": {"location": "kitchen"}},
                {
                    "type": "sequence",
                    "steps": [
                        {"move_to": {"location": "user"}},
                        {"type": "retry", "max_attempts": 2, "behavior": {"move_to": {"location": location}}},
                    ],
                },
            ],
        },
    }


def test_a_retried_step_is_recorded_once_per_attempt_under_the_validators_path(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    adapter = MockROSAdapter()
    adapter.set_navigation_result(NavigationResult(success=False, reason="path_blocked"))
    runtime = URMLRuntime(adapter, evidence_log=log)
    result = runtime.execute(_retry("kitchen"), TURTLEBOT, profiles=("home",), policy=None)
    assert not result.success
    record = _only_record(log)
    expected = _path_of_a_validation_error(_retry("nowhere_undeclared"))
    assert expected == ["behavior", "behavior"]
    assert [step.path for step in record.steps] == [expected] * 3
    assert [step.outcome for step in record.steps] == ["failed"] * 3
    assert (record.outcome, record.error, record.steps_executed) == ("failed", "path_blocked", 3)


def test_nested_steps_are_recorded_under_the_validators_paths(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    result = URMLRuntime(MockROSAdapter(), evidence_log=log).execute(
        _nested("charging_dock"), TURTLEBOT, profiles=("home",), policy=None
    )
    assert result.success
    record = _only_record(log)
    deepest = _path_of_a_validation_error(_nested("nowhere_undeclared"))
    assert deepest == ["behavior", "branches", "1", "steps", "1", "behavior"]
    assert [step.path for step in record.steps] == [
        ["behavior", "branches", "0"],
        ["behavior", "branches", "1", "steps", "0"],
        deepest,
    ]


def test_validator_path_only_rewrites_retry_attempts() -> None:
    assert validator_path(["behavior", "steps", "2"]) == ["behavior", "steps", "2"]
    assert validator_path(["behavior", "if_true", "branches", "0"]) == ["behavior", "if_true", "branches", "0"]
    assert validator_path(["behavior", "attempt", "1", "steps", "0", "attempt", "0"]) == [
        "behavior", "behavior", "steps", "0", "behavior",
    ]


# ---------------------------------------------------------------------------
# The shield
# ---------------------------------------------------------------------------


def _sample(t: float, speed: float) -> Sample:
    return Sample(
        t=t,
        signals={"speed": speed, "altitude": 0.0, "payload": 0.0, "grip_force": 0.0, "person_distance": 100.0},
    )


def test_a_shield_halt_after_a_step_is_the_runs_error(tmp_path: Path) -> None:
    """The adapter answered ok for both moves; the shield stopped the run before the third."""
    log = tmp_path / "evidence.jsonl"
    adapter = MockROSAdapter()
    adapter.set_telemetry([_sample(0.0, speed=0.5), _sample(1.0, speed=2.0)])
    runtime = URMLRuntime(adapter, shield=Shield({"max_velocity": 1.0}), evidence_log=log)
    result = runtime.execute(_moves("kitchen", "user", "charging_dock"), TURTLEBOT, profiles=("home",), policy=None)
    assert not result.success
    record = _only_record(log)
    assert record.outcome == "failed" and (record.error or "").startswith("shield.critical_violation")
    assert [(step.path[-1], step.outcome) for step in record.steps] == [("0", "ok"), ("1", "ok")]
    assert record.steps_executed == 2


def test_a_shield_veto_before_the_first_step_records_no_step(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    adapter = MockROSAdapter()
    shield = Shield({"max_velocity": 1.0})
    shield.observe(_sample(0.0, speed=2.0))  # a critical violation is already standing
    result = URMLRuntime(adapter, shield=shield, evidence_log=log).execute(
        _moves("kitchen"), TURTLEBOT, profiles=("home",), policy=None
    )
    assert not result.success and adapter.call_log == []
    record = _only_record(log)
    assert record.outcome == "failed" and (record.error or "").startswith("shield.veto")
    assert record.steps == [] and record.steps_executed == 0


# ---------------------------------------------------------------------------
# A run that raises
# ---------------------------------------------------------------------------


def test_a_run_that_raises_is_recorded_and_the_exception_is_unchanged(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    error = ConnectionError("link lost")
    with pytest.raises(ConnectionError) as excinfo:
        URMLRuntime(_FailsOnCall(2, error), evidence_log=log).execute(
            _moves("kitchen", "user", "charging_dock"), TURTLEBOT, profiles=("home",), policy=None
        )
    assert excinfo.value is error
    assert getattr(error, "__notes__", []) == []
    record = _only_record(log)
    assert (record.outcome, record.error) == ("failed", "ConnectionError: link lost")
    assert [(step.path[-1], step.outcome, step.error) for step in record.steps] == [
        ("0", "ok", None),
        ("1", "failed", "ConnectionError: link lost"),
    ]
    assert record.steps_executed == 1  # the adapter answered one step


def test_an_interrupted_run_is_recorded(tmp_path: Path) -> None:
    """Ctrl-C in the middle of a step: what was dispatched before it still reached the robot."""
    log = tmp_path / "evidence.jsonl"
    with pytest.raises(KeyboardInterrupt):
        URMLRuntime(_FailsOnCall(2, KeyboardInterrupt()), evidence_log=log).execute(
            _moves("kitchen", "user"), TURTLEBOT, profiles=("home",), policy=None
        )
    record = _only_record(log)
    assert (record.outcome, record.error) == ("failed", "KeyboardInterrupt")
    assert [step.outcome for step in record.steps] == ["ok", "failed"]


# ---------------------------------------------------------------------------
# A record that cannot be written
# ---------------------------------------------------------------------------


def test_an_unwritable_log_after_a_completed_run_leaves_success_alone(tmp_path: Path) -> None:
    """`tmp_path` is a directory, so the append fails with a real OSError after the last step."""
    adapter = MockROSAdapter()
    result = URMLRuntime(adapter, evidence_log=tmp_path).execute(SAFE, MANIFEST, ENVELOPE, ("home",), policy=None)
    assert result.success is True and result.steps_executed == 5
    assert len(adapter.call_log) == 5
    assert result.evidence_log_error is not None
    assert result.evidence_log_error.startswith(f"the evidence log {tmp_path} was not written: ")


def test_an_unwritable_log_after_a_failed_run_leaves_the_failure_alone(tmp_path: Path) -> None:
    adapter = MockROSAdapter()
    adapter.set_navigation_result(NavigationResult(success=False, reason="path_blocked"))
    result = URMLRuntime(adapter, evidence_log=tmp_path).execute(SAFE, MANIFEST, ENVELOPE, ("home",), policy=None)
    assert result.success is False
    assert result.last_outcome is not None and result.last_outcome.reason == "path_blocked"
    assert "was not written" in (result.evidence_log_error or "")


def test_an_unwritable_log_after_a_run_that_raised_is_a_note_on_the_exception(tmp_path: Path) -> None:
    with pytest.raises(ConnectionError) as excinfo:
        URMLRuntime(_FailsOnCall(1, ConnectionError("link lost")), evidence_log=tmp_path).execute(
            _moves("kitchen"), TURTLEBOT, profiles=("home",), policy=None
        )
    (note,) = excinfo.value.__notes__
    assert note.startswith(f"the evidence log {tmp_path} was not written: ")


def test_a_fault_in_the_recorder_is_reported_and_not_raised(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Whatever stops the record, the run's result still reaches the caller."""

    def _boom(**kwargs: Any) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(execution_record, "build_execution_record", _boom)
    log = tmp_path / "evidence.jsonl"
    result = URMLRuntime(MockROSAdapter(), evidence_log=log).execute(SAFE, MANIFEST, ENVELOPE, ("home",), policy=None)
    assert result.success is True
    assert result.evidence_log_error == f"the evidence log {log} was not written: RuntimeError: boom"
    assert not log.exists()


def test_a_written_record_reads_back_through_read_records_as_nothing(tmp_path: Path) -> None:
    """`read_records` returns verdicts only, so the registry's reader skips execution records."""
    log = tmp_path / "evidence.jsonl"
    URMLRuntime(MockROSAdapter(), evidence_log=log).execute(SAFE, MANIFEST, ENVELOPE, ("home",), policy=None)
    assert read_records(log) == []
    assert len(read_log(log)) == 1
