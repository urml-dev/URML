"""The action server's ``evidence_log`` parameter, through the rclpy-free core.

``execute_request(..., evidence_log=PATH)`` appends one validation record per
verdict it makes (the bridge's for a sentence, the validator's for every goal)
and hands the log to the runtime for its own refusals and for the execution
record of a goal that runs (RFC-0715, Draft). The rclpy node reads the
``evidence_log`` parameter with ``evidence_log_path`` and passes it here.
Hermetic: ``MockROSAdapter`` and ``EchoProvider``, no ROS 2.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from urml_llm_bridge import EchoProvider
from urml_validator.evidence import ExecutionRecord, ValidationRecord, read_log, read_records, verify_log

from urml_ros2_runtime import MockROSAdapter, NavigationResult, execution_record
from urml_ros2_runtime.action_server import (
    ExecuteRequest,
    PinnedConstraints,
    evidence_log_path,
    execute_request,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FLEXBE = REPO_ROOT / "examples" / "flexbe"
SENTENCE = "Patrol the two waypoints, then come home."


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


MANIFEST = _load(FLEXBE / "turtle.manifest.yaml")
PATROL = _load(FLEXBE / "turtle-patrol.urml.yaml")
NOWHERE: dict[str, Any] = {
    "profile": "home",
    "behavior": {
        "type": "sequence",
        "on_error": "abort_and_report",
        "steps": [{"move_to": {"location": "nowhere_undeclared"}}],
    },
}


def _pinned() -> PinnedConstraints:
    return PinnedConstraints(
        manifest=MANIFEST,
        envelope={"envelope_version": "0.1", "deployment_id": "test", "max_velocity": 0.8},
        policy=None,
    )


def _unlinked(log: Path) -> list[ExecutionRecord]:
    """Execution records with no accepted verdict on the same program earlier in the log."""
    accepted: set[str | None] = set()
    unlinked: list[ExecutionRecord] = []
    for record in read_log(log):
        if isinstance(record, ValidationRecord):
            if record.verdict == "accepted":
                accepted.add(record.program_digest)
        elif record.program_digest not in accepted:
            unlinked.append(record)
    return unlinked


def test_evidence_log_param_blank_is_off() -> None:
    assert evidence_log_path("") is None
    assert evidence_log_path("   ") is None
    assert evidence_log_path(" /var/log/urml/evidence.jsonl ") == Path("/var/log/urml/evidence.jsonl")


def test_a_refused_goal_is_recorded_and_nothing_moves(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    adapter = MockROSAdapter()
    out = execute_request(
        ExecuteRequest(program=NOWHERE, profiles=("home",)), adapter=adapter, pinned=_pinned(), evidence_log=log
    )
    assert out["refused"] is True and "capability.missing_location" in out["reason"]
    assert adapter.call_log == []
    (record,) = read_records(log)
    assert (record.surface, record.stage, record.verdict) == ("action_server", "validation", "refused")
    assert record.codes == ["capability.missing_location"]
    assert record.program == NOWHERE
    assert record.policy == "none" and record.as_of is not None
    assert record.request is None


def test_an_executed_goal_records_its_verdict(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    out = execute_request(
        ExecuteRequest(program=PATROL, profiles=("home",)),
        adapter=MockROSAdapter(),
        pinned=_pinned(),
        evidence_log=str(log),
    )
    assert out["success"] is True, out["reason"]
    (record,) = read_records(log)  # the runtime adds no verdict of its own for a goal it runs
    assert (record.stage, record.verdict) == ("validation", "accepted")


def test_an_executed_goal_links_its_run_to_its_verdict(tmp_path: Path) -> None:
    """The link rule (RFC-0715, Draft): the run's record and an acceptance share a program digest."""
    log = tmp_path / "evidence.jsonl"
    out = execute_request(
        ExecuteRequest(program=PATROL, profiles=("home",)),
        adapter=MockROSAdapter(),
        pinned=_pinned(),
        evidence_log=log,
    )
    assert out["success"] is True and out["reason"] == ""
    verdict, run = read_log(log)
    assert isinstance(verdict, ValidationRecord) and isinstance(run, ExecutionRecord)
    assert (run.surface, run.outcome) == ("action_server", "completed")
    assert run.steps_executed == out["steps_executed"] == len(run.steps)
    assert run.program_digest == verdict.program_digest
    assert _unlinked(log) == []
    assert verify_log(log).intact


def test_a_sentence_goal_links_its_run_to_its_verdicts(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    emission = (FLEXBE / "turtle-patrol.echo-response.json").read_text(encoding="utf-8")
    out = execute_request(
        ExecuteRequest(sentence=SENTENCE, profiles=("home",)),
        adapter=MockROSAdapter(),
        provider=EchoProvider(responses={SENTENCE: emission}),
        pinned=_pinned(),
        evidence_log=log,
    )
    assert out["success"] is True, out["reason"]
    bridge, validation, run = read_log(log)
    assert isinstance(run, ExecutionRecord)
    assert isinstance(bridge, ValidationRecord) and isinstance(validation, ValidationRecord)
    assert run.program_digest == validation.program_digest == bridge.program_digest
    assert _unlinked(log) == []
    assert [record.seq for record in (bridge, validation, run)] == [1, 2, 3]
    assert verify_log(log).intact


def test_a_failed_goal_is_recorded_as_a_failed_run(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    adapter = MockROSAdapter()
    adapter.set_navigation_result(NavigationResult(success=False, reason="path_blocked"))
    out = execute_request(
        ExecuteRequest(program=PATROL, profiles=("home",)), adapter=adapter, pinned=_pinned(), evidence_log=log
    )
    assert (out["success"], out["refused"], out["reason"]) == (False, False, "path_blocked")
    _, run = read_log(log)
    assert isinstance(run, ExecutionRecord)
    assert (run.outcome, run.error) == ("failed", "path_blocked")
    assert _unlinked(log) == []


def test_a_refused_goal_gets_no_execution_record(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    execute_request(
        ExecuteRequest(program=NOWHERE, profiles=("home",)),
        adapter=MockROSAdapter(),
        pinned=_pinned(),
        evidence_log=log,
    )
    assert [type(record) for record in read_log(log)] == [ValidationRecord]


def _no_space(*args: Any, **kwargs: Any) -> Any:
    raise OSError(28, "No space left on device")


def test_a_run_whose_record_cannot_be_written_keeps_its_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The verdict was written and the goal ran. Only the run's own record fails,
    so `success` stands and `reason` says the record is missing."""
    monkeypatch.setattr(execution_record, "append_record", _no_space)
    log = tmp_path / "evidence.jsonl"
    events: list[dict[str, Any]] = []
    adapter = MockROSAdapter()
    out = execute_request(
        ExecuteRequest(program=PATROL, profiles=("home",)),
        adapter=adapter,
        pinned=_pinned(),
        evidence_log=log,
        feedback=events.append,
    )
    assert (out["success"], out["refused"]) == (True, False)
    assert out["steps_executed"] == 3 and len(adapter.call_log) == 3
    assert out["reason"] == (
        f"the run finished, but its execution record is missing: the evidence log {log} was not written: "
        "[Errno 28] No space left on device"
    )
    assert events[-1] == {"phase": "done", "detail": "execution complete; its execution record was not written"}
    assert [type(record) for record in read_log(log)] == [ValidationRecord]


def test_a_failed_run_whose_record_cannot_be_written_keeps_its_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(execution_record, "append_record", _no_space)
    adapter = MockROSAdapter()
    adapter.set_navigation_result(NavigationResult(success=False, reason="path_blocked"))
    out = execute_request(
        ExecuteRequest(program=PATROL, profiles=("home",)),
        adapter=adapter,
        pinned=_pinned(),
        evidence_log=tmp_path / "evidence.jsonl",
    )
    assert (out["success"], out["refused"]) == (False, False)
    first, second = out["reason"].split("\n")
    assert first == "path_blocked"
    assert second.startswith("the run finished, but its execution record is missing: ")


def test_a_sentence_records_the_bridge_verdict_and_the_validation(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    emission = (FLEXBE / "turtle-patrol.echo-response.json").read_text(encoding="utf-8")
    out = execute_request(
        ExecuteRequest(sentence=SENTENCE, profiles=("home",)),
        adapter=MockROSAdapter(),
        provider=EchoProvider(responses={SENTENCE: emission}),
        pinned=_pinned(),
        evidence_log=log,
    )
    assert out["success"] is True, out["reason"]
    bridge, validation = read_records(log)
    assert (bridge.stage, bridge.verdict, bridge.request) == ("bridge", "accepted", SENTENCE)
    assert (bridge.attempts, bridge.attempt_codes) == (1, [[]])
    assert bridge.program == json.loads(emission)
    assert (validation.stage, validation.verdict, validation.request) == ("validation", "accepted", None)
    assert validation.program_digest == bridge.program_digest


def test_a_bridge_refusal_is_recorded_with_the_request(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    adapter = MockROSAdapter()
    out = execute_request(
        ExecuteRequest(sentence=SENTENCE, profiles=("home",)),
        adapter=adapter,
        provider=EchoProvider(responses={SENTENCE: [json.dumps(NOWHERE)] * 4}),
        pinned=_pinned(),
        evidence_log=log,
    )
    assert out["refused"] is True and "translation failed" in out["reason"]
    assert adapter.call_log == []
    (record,) = read_records(log)
    assert (record.surface, record.stage, record.verdict) == ("action_server", "bridge", "refused")
    assert record.request == SENTENCE
    assert record.attempts == 4 and record.attempt_codes == [["capability.missing_location"]] * 4
    assert record.program == NOWHERE


def test_a_log_that_cannot_be_written_refuses_the_goal(tmp_path: Path) -> None:
    adapter = MockROSAdapter()
    out = execute_request(
        ExecuteRequest(program=PATROL, profiles=("home",)), adapter=adapter, pinned=_pinned(), evidence_log=tmp_path
    )
    assert out["refused"] is True
    assert "evidence log" in out["reason"] and "nothing was executed" in out["reason"]
    assert adapter.call_log == []


def test_the_runtime_gets_the_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import urml_ros2_runtime.action_server as action_server

    seen: list[dict[str, Any]] = []
    real = action_server.URMLRuntime

    class _Spy(real):  # type: ignore[misc,valid-type]
        def __init__(self, adapter: Any, **kwargs: Any) -> None:
            seen.append(kwargs)
            super().__init__(adapter, **kwargs)

    monkeypatch.setattr(action_server, "URMLRuntime", _Spy)
    log = tmp_path / "evidence.jsonl"
    execute_request(
        ExecuteRequest(program=PATROL, profiles=("home",)), adapter=MockROSAdapter(), pinned=_pinned(), evidence_log=log
    )
    # It is also told who is calling, for the execution record's `surface`.
    assert seen == [{"evidence_log": log, "evidence_surface": "action_server"}]


def test_no_log_means_no_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    execute_request(ExecuteRequest(program=NOWHERE, profiles=("home",)), adapter=MockROSAdapter(), pinned=_pinned())
    assert list(tmp_path.iterdir()) == []
