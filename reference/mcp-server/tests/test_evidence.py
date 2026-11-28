"""The operator's evidence log on the MCP tools.

``URML_MCP_EVIDENCE_LOG`` (or ``--evidence-log``, which wins) is loaded with
the other pins at startup. ``validate_program`` and ``execute_program`` then
append one validation record per verdict, and the runtime appends its own
refusals and one execution record per run (RFC-0715, Draft). No tool takes the
log as an argument, so an agent cannot switch it off or point it elsewhere.
Hermetic: the mock adapter, no MCP transport.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pytest
import yaml
from urml_ros2_runtime import (
    MockROSAdapter,
    URMLRuntime,
    ValidationRejectedError,
    execution_record,
)
from urml_validator.evidence import (
    ExecutionRecord,
    ValidationRecord,
    content_digest,
    read_log,
    read_records,
    verify_log,
)

from urml_mcp import tools

REPO_ROOT = Path(__file__).resolve().parents[3]
HOME = REPO_ROOT / "examples" / "home"
MANIFEST = HOME / "red-mug.manifest.yaml"
ENVELOPE = HOME / "red-mug.envelope.yaml"
PROGRAM = HOME / "red-mug.urml.yaml"
GRASP_4N = HOME / "red-mug.grasp-4n.urml.yaml"


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _pins(log: Path, **extra: str) -> tools.Pinned:
    environ = {
        "URML_MCP_MANIFEST": str(MANIFEST),
        "URML_MCP_ENVELOPE": str(ENVELOPE),
        "URML_MCP_PROFILES": "home",
        "URML_MCP_POLICY": "none",
        "URML_MCP_EVIDENCE_LOG": str(log),
        **extra,
    }
    return tools.load_pinned(environ, [])


# --- loading the pin ------------------------------------------------------------


def test_the_env_var_sets_the_log(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    pins = tools.load_pinned({"URML_MCP_EVIDENCE_LOG": str(log)}, [])
    assert pins.evidence_log == log.resolve()
    assert not log.exists()  # created on the first record, not at startup
    # It is operator configuration, not a constraint the agent must leave out.
    assert pins.names == ()


def test_the_flag_wins_over_the_env_var(tmp_path: Path) -> None:
    flag = tmp_path / "flag.jsonl"
    pins = tools.load_pinned(
        {"URML_MCP_EVIDENCE_LOG": str(tmp_path / "env.jsonl")}, ["--evidence-log", str(flag)]
    )
    assert pins.evidence_log == flag.resolve()


def test_blank_means_no_log() -> None:
    assert tools.load_pinned({"URML_MCP_EVIDENCE_LOG": "  "}, []).evidence_log is None
    assert tools.load_pinned({}, []).evidence_log is None


def test_a_directory_stops_the_server_at_startup(tmp_path: Path) -> None:
    with pytest.raises(tools.PinnedConfigError, match="URML_MCP_EVIDENCE_LOG"):
        tools.load_pinned({"URML_MCP_EVIDENCE_LOG": str(tmp_path)}, [])


def test_no_tool_takes_the_log_as_an_argument() -> None:
    for tool in (tools.get_contract, tools.validate_program, tools.execute_program, tools.describe_manifest):
        assert not any("evidence" in name for name in inspect.signature(tool).parameters)


# --- validate_program -------------------------------------------------------------


def test_validate_records_each_verdict(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    pins = _pins(log)
    assert tools.validate_program(str(PROGRAM), pinned=pins)["accepted"] is True
    assert tools.validate_program(str(GRASP_4N), pinned=pins)["accepted"] is False
    accepted, refused = read_records(log)
    assert (accepted.surface, accepted.stage, accepted.verdict) == ("mcp", "validation", "accepted")
    assert (refused.verdict, refused.codes) == ("refused", ["envelope.force_exceeded"])
    assert refused.program == _load(GRASP_4N)
    assert refused.manifest_digest == content_digest(_load(MANIFEST))
    assert refused.envelope_digest == content_digest(_load(ENVELOPE))
    assert (refused.policy, refused.profiles) == ("none", ["home"])


def test_no_log_means_no_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    tools.validate_program(str(GRASP_4N), str(MANIFEST), str(ENVELOPE), ["home"])
    assert list(tmp_path.iterdir()) == []


# --- execute_program --------------------------------------------------------------


def test_execute_records_a_refusal_before_anything_is_built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _refuse(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("_build_runtime was called")

    monkeypatch.setattr(tools, "_build_runtime", _refuse)
    log = tmp_path / "evidence.jsonl"
    with pytest.raises(ValidationRejectedError, match="envelope.force_exceeded"):
        tools.execute_program(str(GRASP_4N), pinned=_pins(log))
    (record,) = read_records(log)
    assert (record.surface, record.stage, record.verdict) == ("mcp", "validation", "refused")
    assert record.as_of is not None


def test_execute_hands_the_log_to_the_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[dict[str, Any]] = []

    def _build(adapter: str, **kwargs: Any) -> tuple[Any, list[Any]]:
        built.append(kwargs)
        return URMLRuntime(MockROSAdapter(), **kwargs), []

    monkeypatch.setattr(tools, "_build_runtime", _build)
    log = tmp_path / "evidence.jsonl"
    pins = _pins(log)
    assert tools.execute_program(str(PROGRAM), pinned=pins)["success"] is True
    assert built == [{"evidence_log": pins.evidence_log}]
    (record,) = read_records(log)  # the runtime adds no verdict of its own for a program it runs
    assert (record.surface, record.verdict) == ("mcp", "accepted")


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


def test_execute_links_its_run_to_its_verdict(tmp_path: Path) -> None:
    """The link rule (RFC-0715, Draft): the run's record and the acceptance share a program digest."""
    log = tmp_path / "evidence.jsonl"
    out = tools.execute_program(str(PROGRAM), pinned=_pins(log))
    assert out["success"] is True and out["evidence_log_error"] is None
    verdict, run = read_log(log)
    assert isinstance(verdict, ValidationRecord) and isinstance(run, ExecutionRecord)
    assert (verdict.surface, verdict.verdict) == ("mcp", "accepted")
    assert (run.surface, run.outcome) == ("mcp", "completed")
    assert run.steps_executed == out["steps_executed"] == len(run.steps)
    assert run.program_digest == verdict.program_digest == content_digest(_load(PROGRAM))
    assert run.manifest_digest == verdict.manifest_digest
    assert _unlinked(log) == []
    assert verify_log(log).intact


def test_a_program_passed_as_a_mapping_links_too(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    tools.execute_program(_load(PROGRAM), pinned=_pins(log))
    assert len(read_log(log)) == 2 and _unlinked(log) == []


def test_a_refused_program_gets_no_execution_record(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    with pytest.raises(ValidationRejectedError):
        tools.execute_program(str(GRASP_4N), pinned=_pins(log))
    assert [type(record) for record in read_log(log)] == [ValidationRecord]


def test_a_run_whose_record_cannot_be_written_keeps_its_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The verdict was written and the program ran. Only the run's own record
    fails, so the result comes back as it is, with the reason beside it."""

    def _no_space(*args: Any, **kwargs: Any) -> Any:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(execution_record, "append_record", _no_space)
    log = tmp_path / "evidence.jsonl"
    pins = _pins(log)
    out = tools.execute_program(str(PROGRAM), pinned=pins)
    assert out["success"] is True and out["steps_executed"] == 5
    assert out["evidence_log_error"] == (
        f"the evidence log {pins.evidence_log} was not written: [Errno 28] No space left on device"
    )
    assert [type(record) for record in read_log(log)] == [ValidationRecord]


def test_the_mock_runtime_is_built_with_the_log(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    runtime, cleanup = tools._build_runtime("mock", evidence_log=log)
    assert cleanup == []
    with pytest.raises(ValidationRejectedError):
        runtime.execute(_load(GRASP_4N), _load(MANIFEST), _load(ENVELOPE), ("home",), policy=None)
    (record,) = read_records(log)
    assert (record.surface, record.stage) == ("runtime", "revalidation")
