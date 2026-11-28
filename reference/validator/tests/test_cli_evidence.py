"""`--evidence-log` on `urml validate`, `execute`, `run` and `translate`, and `urml evidence log`.

Every verdict a command makes lands in the log as one validation record, and
every run as one execution record (RFC-0715, Draft). Turning the log on
changes nothing the command prints or returns. `urml evidence log` checks the
chain that links the lines. Hermetic: the echo provider stands in for the
model and the mock adapter for the robot.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from urml_validator.cli import main
from urml_validator.errors import ValidationResult
from urml_validator.evidence import (
    ExecutionRecord,
    ValidationRecord,
    content_digest,
    read_log,
    read_records,
    reverify,
    verify_log,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
HOME = REPO_ROOT / "examples" / "home"
PROGRAM = HOME / "red-mug.urml.yaml"
GRASP_4N = HOME / "red-mug.grasp-4n.urml.yaml"
MANIFEST = HOME / "red-mug.manifest.yaml"
CN_MANIFEST = HOME / "red-mug.cn-critical.manifest.yaml"
ENVELOPE = HOME / "red-mug.envelope.yaml"
DOC = REPO_ROOT / "docs" / "evidence" / "validation-records.md"
FIXTURES = Path(__file__).parent / "fixtures"
REGISTRY_FILE = REPO_ROOT / "registry" / "evidence" / "gopigo3-example-adapter" / "validation-records.jsonl"

REQUEST = "Pick up the mug and squeeze it hard."


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _same_with_and_without_the_log(
    argv: list[str], log: Path, capsys: pytest.CaptureFixture[str]
) -> int:
    """Run ``argv`` without, then with, ``--evidence-log``: exit code and output match."""
    plain = _run(argv, capsys)
    assert not log.exists()
    logged = _run([*argv, "--evidence-log", str(log)], capsys)
    assert logged == plain
    return logged[0]


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


def _execute_argv(program: Path, *extra: str) -> list[str]:
    return [
        "execute", str(program), "-m", str(MANIFEST), "-e", str(ENVELOPE),
        "--profile", "home", "--no-policy", "--adapter", "mock", *extra,
    ]


def _no_space(*args: Any, **kwargs: Any) -> Any:
    raise OSError(28, "No space left on device")


def _use_adapter(monkeypatch: pytest.MonkeyPatch, adapter: Any) -> None:
    """Make `--adapter mock` hand the runtime this adapter."""
    import urml_validator.cli as cli

    monkeypatch.setattr(cli, "_build_execute_adapter", lambda args, cleanup: adapter)


def _blocked_adapter() -> Any:
    from urml_ros2_runtime import MockROSAdapter, NavigationResult

    adapter = MockROSAdapter()
    adapter.set_navigation_result(NavigationResult(success=False, reason="path_blocked"))
    return adapter


def _echo(tmp_path: Path, *programs: dict[str, Any]) -> Path:
    """An echo-response file: one scripted emission per bridge attempt."""
    path = tmp_path / "echo.json"
    path.write_text(json.dumps(list(programs)), encoding="utf-8")
    return path


def _bridge_argv(command: str, echo: Path, *extra: str) -> list[str]:
    return [
        command, REQUEST,
        "--manifest", str(MANIFEST),
        "--envelope", str(ENVELOPE),
        "--profile", "home",
        "--no-policy",
        "--provider", "echo",
        "--echo-response-file", str(echo),
        *extra,
    ]


# ---------------------------------------------------------------------------
# urml validate
# ---------------------------------------------------------------------------


def test_validate_records_a_refusal(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    log = tmp_path / "evidence.jsonl"
    argv = [
        "validate", str(GRASP_4N), "-m", str(MANIFEST), "-e", str(ENVELOPE),
        "--profile", "home", "--no-policy",
    ]
    assert _same_with_and_without_the_log(argv, log, capsys) == 1
    (record,) = read_records(log)
    assert (record.surface, record.stage, record.verdict) == ("validate", "validation", "refused")
    assert record.codes == ["envelope.force_exceeded"]
    assert record.program == _load(GRASP_4N)
    assert record.program_digest == content_digest(_load(GRASP_4N))
    assert record.manifest_digest == content_digest(_load(MANIFEST))
    assert record.envelope_digest == content_digest(_load(ENVELOPE))
    assert record.robot_id == "turtlebot4_red_mug"
    assert record.policy == "none"
    assert record.profiles == ["home"]
    assert record.default_rulebooks is True and record.rulebooks == []
    assert record.as_of is None  # validate lets the validator pick today's date
    assert (record.request, record.attempts, record.attempt_codes) == (None, None, None)
    check = reverify(record, manifest=_load(MANIFEST), envelope=_load(ENVELOPE), policy=None)
    assert check.reproduced, check.problems


def test_validate_records_an_acceptance(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    log = tmp_path / "evidence.jsonl"
    argv = ["validate", str(PROGRAM), "-m", str(MANIFEST), "-e", str(ENVELOPE), "--profile", "home", "--json"]
    assert _same_with_and_without_the_log(argv, log, capsys) == 0
    (record,) = read_records(log)
    assert record.verdict == "accepted" and record.codes == []
    assert record.policy == "default"
    assert record.result == json.loads(_run(argv, capsys)[1])


def test_validate_appends_one_line_per_verdict(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    log = tmp_path / "nested" / "evidence.jsonl"
    common = ["-m", str(MANIFEST), "-e", str(ENVELOPE), "--profile", "home", "--evidence-log", str(log)]
    assert _run(["validate", str(PROGRAM), *common], capsys)[0] == 0
    assert _run(["validate", str(GRASP_4N), *common], capsys)[0] == 1
    assert [r.verdict for r in read_records(log)] == ["accepted", "refused"]
    assert len(log.read_text(encoding="utf-8").splitlines()) == 2


def test_no_flag_writes_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    assert _run(["validate", str(GRASP_4N), "-m", str(MANIFEST), "-e", str(ENVELOPE)], capsys)[0] == 1
    assert list(tmp_path.iterdir()) == []


def test_a_log_that_cannot_be_written_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, err = _run(
        ["validate", str(PROGRAM), "-m", str(MANIFEST), "--evidence-log", str(tmp_path)], capsys
    )
    assert code == 2
    assert out == ""
    assert "cannot write the evidence log" in err


# ---------------------------------------------------------------------------
# urml execute
# ---------------------------------------------------------------------------


def test_execute_records_the_pre_check_refusal(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    log = tmp_path / "evidence.jsonl"
    argv = [
        "execute", str(GRASP_4N), "-m", str(MANIFEST), "-e", str(ENVELOPE),
        "--profile", "home", "--no-policy", "--adapter", "mock",
    ]
    assert _same_with_and_without_the_log(argv, log, capsys) == 1
    (record,) = read_records(log)
    assert (record.surface, record.stage, record.verdict) == ("execute", "validation", "refused")
    assert record.codes == ["envelope.force_exceeded"]
    assert record.as_of is not None  # execute validates twice on one date


def test_execute_records_one_verdict_when_it_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import urml_ros2_runtime

    seen: list[dict[str, Any]] = []
    real = urml_ros2_runtime.URMLRuntime

    class _Spy(real):  # type: ignore[misc,valid-type]
        def __init__(self, adapter: Any, **kwargs: Any) -> None:
            seen.append(kwargs)
            super().__init__(adapter, **kwargs)

    monkeypatch.setattr(urml_ros2_runtime, "URMLRuntime", _Spy)
    log = tmp_path / "evidence.jsonl"
    argv = [
        "execute", str(PROGRAM), "-m", str(MANIFEST), "-e", str(ENVELOPE),
        "--profile", "home", "--no-policy", "--adapter", "mock",
    ]
    assert _same_with_and_without_the_log(argv, log, capsys) == 0
    (record,) = read_records(log)
    assert (record.surface, record.verdict) == ("execute", "accepted")
    # The runtime gets the log, so its own refusals would land there too, and
    # it is told which command is calling, for the execution record's surface.
    assert seen == [
        {"evidence_log": None, "evidence_surface": "execute"},
        {"evidence_log": log, "evidence_surface": "execute"},
    ]


def test_execute_runtime_refusal_is_recorded_by_the_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A pre-check that lets the program through leaves the runtime's own check to refuse it."""
    import urml_validator.cli as cli

    monkeypatch.setattr(cli, "validate", lambda *args, **kwargs: ValidationResult(accepted=True))
    log = tmp_path / "evidence.jsonl"
    code, out, err = _run(
        [
            "execute", str(GRASP_4N), "-m", str(MANIFEST), "-e", str(ENVELOPE),
            "--profile", "home", "--no-policy", "--adapter", "mock", "--evidence-log", str(log),
        ],
        capsys,
    )
    assert code == 64 and "runtime rejected a pre-validated program" in err
    assert "URML execute:" not in out
    pre_check, runtime = read_records(log)
    assert (pre_check.surface, pre_check.verdict) == ("execute", "accepted")
    assert (runtime.surface, runtime.stage, runtime.verdict) == ("runtime", "revalidation", "refused")
    assert runtime.codes == ["envelope.force_exceeded"]
    assert runtime.as_of == pre_check.as_of


def test_a_runtime_refusal_whose_record_could_not_be_written_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The runtime attaches a note to its refusal when the refusal's record fails.
    The CLI used to print the refusal and drop the note."""
    import urml_ros2_runtime.runtime as runtime_module

    import urml_validator.cli as cli

    monkeypatch.setattr(cli, "validate", lambda *args, **kwargs: ValidationResult(accepted=True))
    monkeypatch.setattr(runtime_module, "append_record", _no_space)
    log = tmp_path / "evidence.jsonl"
    code, out, err = _run(_execute_argv(GRASP_4N, "--evidence-log", str(log)), capsys)
    assert code == 64 and "URML execute:" not in out
    first, second = err.splitlines()
    assert "runtime rejected a pre-validated program" in first
    assert second == f"urml: the evidence log {log} was not written: [Errno 28] No space left on device"
    (pre_check,) = read_log(log)  # the command's own verdict was written before the runtime ran
    assert isinstance(pre_check, ValidationRecord)


# ---------------------------------------------------------------------------
# urml translate and urml run
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", ["translate", "run"])
def test_a_bridge_refusal_is_recorded(
    command: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    grasp = _load(GRASP_4N)
    log = tmp_path / "evidence.jsonl"
    argv = _bridge_argv(command, _echo(tmp_path, grasp, grasp), "--max-revisions", "1")
    if command == "run":
        argv += ["--adapter", "mock"]
    assert _same_with_and_without_the_log(argv, log, capsys) == 1
    (record,) = read_records(log)
    assert (record.surface, record.stage, record.verdict) == (command, "bridge", "refused")
    assert record.request == REQUEST
    assert record.attempts == 2
    assert record.attempt_codes == [["envelope.force_exceeded"], ["envelope.force_exceeded"]]
    assert record.codes == ["envelope.force_exceeded"]
    assert record.program == grasp  # the parsed emission the final verdict judged
    assert (record.as_of is not None) is (command == "run")
    check = reverify(record, manifest=_load(MANIFEST), envelope=_load(ENVELOPE), policy=None)
    assert check.reproduced, check.problems


@pytest.mark.parametrize("command", ["translate", "run"])
def test_a_bridge_acceptance_is_recorded(
    command: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import urml_ros2_runtime

    seen: list[dict[str, Any]] = []
    real = urml_ros2_runtime.URMLRuntime

    class _Spy(real):  # type: ignore[misc,valid-type]
        def __init__(self, adapter: Any, **kwargs: Any) -> None:
            seen.append(kwargs)
            super().__init__(adapter, **kwargs)

    monkeypatch.setattr(urml_ros2_runtime, "URMLRuntime", _Spy)
    program = _load(PROGRAM)
    log = tmp_path / "evidence.jsonl"
    argv = _bridge_argv(command, _echo(tmp_path, program))
    if command == "run":
        argv += ["--adapter", "mock"]
    assert _same_with_and_without_the_log(argv, log, capsys) == 0
    record, *later = read_records(log)
    assert (record.surface, record.stage, record.verdict) == (command, "bridge", "accepted")
    assert record.program == program  # as judged, before the request is copied into it
    assert (record.request, record.attempts, record.attempt_codes) == (REQUEST, 1, [[]])
    if command == "translate":
        assert later == []
        return
    # `run` goes on to execute. It validates the program as it will run, with
    # the request copied into its description, and records that verdict too
    # (RFC-0715, Draft). The runtime adds no verdict of its own.
    (check,) = later
    assert (check.surface, check.stage, check.verdict) == ("run", "validation", "accepted")
    assert check.program == {**program, "description": REQUEST}
    assert (check.request, check.attempts, check.attempt_codes) == (None, None, None)
    assert check.as_of == record.as_of
    assert seen == [
        {"evidence_log": None, "evidence_surface": "run"},
        {"evidence_log": log, "evidence_surface": "run"},
    ]


def test_a_policy_refusal_through_the_bridge_is_recorded(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log = tmp_path / "evidence.jsonl"
    argv = [
        "translate", REQUEST, "--manifest", str(CN_MANIFEST), "--profile", "home",
        "--provider", "echo", "--echo-response-file", str(_echo(tmp_path, _load(PROGRAM))),
    ]
    assert _same_with_and_without_the_log(argv, log, capsys) == 1
    (record,) = read_records(log)
    assert record.verdict == "refused" and record.policy == "default"
    assert record.codes and all(code.startswith("policy.") for code in record.codes)
    assert record.attempts == 1


def test_a_provider_error_writes_no_record(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The bridge ended without a verdict (the model stopped answering), so nothing is recorded."""
    log = tmp_path / "evidence.jsonl"
    argv = _bridge_argv(
        "translate", _echo(tmp_path, _load(GRASP_4N)), "--max-revisions", "1", "--evidence-log", str(log)
    )
    code, _, err = _run(argv, capsys)
    assert code == 1 and "provider error" in err
    assert not log.exists()


# ---------------------------------------------------------------------------
# Execution records and the link to a verdict (RFC-0715, Draft)
# ---------------------------------------------------------------------------


def test_execute_links_its_run_to_its_verdict(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The link rule: an execution record and an acceptance in the same log share a program digest."""
    log = tmp_path / "evidence.jsonl"
    assert _run(_execute_argv(PROGRAM, "--evidence-log", str(log)), capsys)[0] == 0
    verdict, run = read_log(log)
    assert isinstance(verdict, ValidationRecord) and isinstance(run, ExecutionRecord)
    assert (verdict.surface, verdict.verdict) == ("execute", "accepted")
    assert (run.surface, run.outcome, run.steps_executed) == ("execute", "completed", 5)
    assert run.program_digest == verdict.program_digest == content_digest(_load(PROGRAM))
    assert _unlinked(log) == []
    assert verify_log(log).intact


def test_run_links_its_run_to_its_verdict(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """`urml run` executes the bridge's program with the request added as its
    description, so the bridge's verdict is on another digest. The verdict of
    the check before execution is the one the run links to."""
    program = _load(PROGRAM)
    log = tmp_path / "evidence.jsonl"
    argv = [*_bridge_argv("run", _echo(tmp_path, program)), "--adapter", "mock", "--evidence-log", str(log)]
    assert _run(argv, capsys)[0] == 0
    bridge, check, run = read_log(log)
    assert isinstance(bridge, ValidationRecord) and isinstance(check, ValidationRecord)
    assert isinstance(run, ExecutionRecord)
    executed = {**program, "description": REQUEST}
    assert run.program_digest == check.program_digest == content_digest(executed)
    assert bridge.program_digest == content_digest(program) != run.program_digest
    assert (run.surface, run.outcome) == ("run", "completed")
    assert _unlinked(log) == []
    assert verify_log(log).intact


def test_run_links_when_the_model_wrote_its_own_description(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A description the model emitted is kept, so all three records share one digest."""
    program = {**_load(PROGRAM), "description": "Fetch the red mug."}
    log = tmp_path / "evidence.jsonl"
    argv = [*_bridge_argv("run", _echo(tmp_path, program)), "--adapter", "mock", "--evidence-log", str(log)]
    assert _run(argv, capsys)[0] == 0
    assert len({record.program_digest for record in read_log(log)}) == 1
    assert _unlinked(log) == []


def test_run_refuses_before_rehearsal_and_adapter_and_records_the_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The bridge has no manifest directory, so an HBOM-content rule can only
    warn there. The check before execution reads the HBOM and refuses."""
    import urml_validator.cli as cli

    def _never(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("an adapter was built for a refused program")

    monkeypatch.setattr(cli, "_build_execute_adapter", _never)
    program = {
        "profile": "home",
        "behavior": {
            "type": "sequence",
            "on_error": "abort_and_report",
            "steps": [{"move_to": {"location": "kitchen"}}],
        },
    }
    log = tmp_path / "evidence.jsonl"
    code, out, err = _run(
        [
            "run", "Go to the kitchen.",
            "--manifest", str(FIXTURES / "manifests" / "provenance_hbom_cn_chip.yaml"),
            "--policy", str(FIXTURES / "policies" / "hbom_no_cn_components.yaml"),
            "--profile", "home", "--provider", "echo", "--echo-response-file", str(_echo(tmp_path, program)),
            "--rehearse", "--adapter", "mock", "--evidence-log", str(log),
        ],
        capsys,
    )
    assert code == 1 and "URML execute:" not in out
    assert "execution refused: the validator rejected the program as it would run" in err
    assert "gate:" not in err  # refused before the rehearsal, as in `urml execute`
    bridge, check = read_log(log)
    assert isinstance(bridge, ValidationRecord) and isinstance(check, ValidationRecord)
    assert (bridge.stage, bridge.verdict) == ("bridge", "accepted")
    assert (check.surface, check.stage, check.verdict) == ("run", "validation", "refused")
    assert check.codes == ["policy.hbom_component_country_denied"]


def test_execute_records_a_failed_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _use_adapter(monkeypatch, _blocked_adapter())
    log = tmp_path / "evidence.jsonl"
    code, out, _ = _run(_execute_argv(PROGRAM, "--evidence-log", str(log)), capsys)
    assert code == 1 and "RESULT: FAILURE" in out
    _, run = read_log(log)
    assert isinstance(run, ExecutionRecord)
    assert (run.outcome, run.error, run.steps_executed) == ("failed", "path_blocked", 1)
    assert [(step.primitive, step.outcome, step.error) for step in run.steps] == [("move_to", "failed", "path_blocked")]
    assert _unlinked(log) == []


def test_execute_records_a_run_that_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from urml_ros2_runtime import MockROSAdapter

    class _LinkLost(MockROSAdapter):
        def send_navigation_goal(self, *args: Any, **kwargs: Any) -> Any:
            raise ConnectionError("link lost")

    _use_adapter(monkeypatch, _LinkLost())
    log = tmp_path / "evidence.jsonl"
    code, _, err = _run(_execute_argv(PROGRAM, "--evidence-log", str(log)), capsys)
    assert code == 64
    assert err == "urml: internal error: ConnectionError: link lost\n"
    _, run = read_log(log)
    assert isinstance(run, ExecutionRecord)
    assert (run.outcome, run.error) == ("failed", "ConnectionError: link lost")


@pytest.mark.parametrize("as_json", [False, True])
def test_execute_exits_2_when_the_run_finished_and_its_record_could_not_be_written(
    as_json: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The verdict before the run is written. The run happens. Only then does
    the log fail, so the result is printed as usual and the exit code is 2."""
    from urml_ros2_runtime import execution_record

    plain = _run(_execute_argv(PROGRAM, *(["--json"] if as_json else [])), capsys)
    monkeypatch.setattr(execution_record, "append_record", _no_space)
    log = tmp_path / "evidence.jsonl"
    code, out, err = _run(_execute_argv(PROGRAM, "--evidence-log", str(log), *(["--json"] if as_json else [])), capsys)
    assert code == 2
    reason = f"the evidence log {log} was not written: [Errno 28] No space left on device"
    assert err == f"urml: the run finished (success), but its execution record is missing: {reason}\n"
    if as_json:
        payload, expected = json.loads(out), json.loads(plain[1])
        assert payload["result"].pop("evidence_log_error") == reason
        assert expected["result"].pop("evidence_log_error") is None
        assert payload == expected
    else:
        assert out == plain[1]
        assert "RESULT: SUCCESS (5 step(s) executed)" in out
    assert [type(record) for record in read_log(log)] == [ValidationRecord]


def test_run_exits_2_when_the_run_finished_and_its_record_could_not_be_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from urml_ros2_runtime import execution_record

    monkeypatch.setattr(execution_record, "append_record", _no_space)
    log = tmp_path / "evidence.jsonl"
    argv = [*_bridge_argv("run", _echo(tmp_path, _load(PROGRAM))), "--adapter", "mock", "--evidence-log", str(log)]
    code, out, err = _run(argv, capsys)
    assert code == 2 and "RESULT: SUCCESS" in out
    assert err.splitlines()[-1] == (
        "urml: the run finished (success), but its execution record is missing: "
        f"the evidence log {log} was not written: [Errno 28] No space left on device"
    )
    assert [record.stage for record in read_records(log)] == ["bridge", "validation"]
    assert len(read_log(log)) == 2


def test_a_failed_run_without_its_record_still_says_it_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from urml_ros2_runtime import execution_record

    monkeypatch.setattr(execution_record, "append_record", _no_space)
    _use_adapter(monkeypatch, _blocked_adapter())
    code, out, err = _run(_execute_argv(PROGRAM, "--evidence-log", str(tmp_path / "evidence.jsonl")), capsys)
    assert code == 2
    assert "RESULT: FAILURE" in out
    assert err.startswith("urml: the run finished (failure), but its execution record is missing: ")


def test_a_run_that_raised_without_its_record_says_both(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The exception keeps its exit code. The missing record is a second line, never dropped."""
    from urml_ros2_runtime import MockROSAdapter, execution_record

    class _LinkLost(MockROSAdapter):
        def send_navigation_goal(self, *args: Any, **kwargs: Any) -> Any:
            raise ConnectionError("link lost")

    monkeypatch.setattr(execution_record, "append_record", _no_space)
    _use_adapter(monkeypatch, _LinkLost())
    log = tmp_path / "evidence.jsonl"
    code, _, err = _run(_execute_argv(PROGRAM, "--evidence-log", str(log)), capsys)
    assert code == 64
    assert err.splitlines() == [
        "urml: internal error: ConnectionError: link lost",
        f"urml: the evidence log {log} was not written: [Errno 28] No space left on device",
    ]


# ---------------------------------------------------------------------------
# urml evidence log
# ---------------------------------------------------------------------------


def _digest(line: bytes) -> str:
    return "sha256:" + hashlib.sha256(line).hexdigest()


def _a_refusal_then_a_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    """Three lines: a refused verdict, an accepted verdict, and the run it allowed."""
    log = tmp_path / "evidence.jsonl"
    refused = ["validate", str(GRASP_4N), "-m", str(MANIFEST), "-e", str(ENVELOPE), "--profile", "home", "--no-policy"]
    assert _run([*refused, "--evidence-log", str(log)], capsys)[0] == 1
    assert _run(_execute_argv(PROGRAM, "--evidence-log", str(log)), capsys)[0] == 0
    return log


def test_evidence_log_exits_0_for_an_intact_chain(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    log = _a_refusal_then_a_run(tmp_path, capsys)
    before = log.read_bytes()
    code, out, err = _run(["evidence", "log", str(log)], capsys)
    assert (code, err) == (0, "")
    assert out.splitlines()[:5] == [
        f"Evidence log: {log}",
        "  records: 3 on 3 lines (2 validation, 1 execution)",
        "  chain:   starts at line 1",
        "  intact:  yes",
        f"  head:    seq 3 {_digest(before.splitlines()[-1])}",
    ]
    assert out.splitlines()[5].startswith("  note:    an intact chain cannot show a cut-off end")
    assert log.read_bytes() == before  # read-only


def test_evidence_log_exits_1_and_names_the_line_where_the_chain_breaks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log = _a_refusal_then_a_run(tmp_path, capsys)
    first, _, third = log.read_bytes().splitlines(keepends=True)
    log.write_bytes(first + third)  # the accepted verdict removed
    code, out, err = _run(["evidence", "log", str(log)], capsys)
    assert (code, err) == (1, "")
    lines = out.splitlines()
    assert lines[1] == "  records: 2 on 2 lines (1 validation, 1 execution)"
    assert lines[3] == "  intact:  no, 2 problems"
    assert lines[4] == "    line 2: seq is 3, expected 2"
    assert lines[5].startswith("    line 2: prev is ")
    assert not any(line.startswith("  note:") for line in lines)


def test_evidence_log_exits_2_when_the_file_cannot_be_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, err = _run(["evidence", "log", str(tmp_path / "no-such.jsonl")], capsys)
    assert (code, out) == (2, "") and "evidence log not found" in err
    code, out, err = _run(["evidence", "log", str(tmp_path)], capsys)
    assert (code, out) == (2, "") and "evidence log not found" in err
    with pytest.raises(SystemExit) as usage:
        main(["evidence", "log"])
    assert usage.value.code == 2


def test_evidence_log_says_when_a_file_has_no_chain(capsys: pytest.CaptureFixture[str]) -> None:
    """A committed format 1 file: nothing to break, and the output does not call it intact."""
    code, out, _ = _run(["evidence", "log", str(REGISTRY_FILE)], capsys)
    assert code == 0
    lines = out.splitlines()
    assert lines[1] == "  records: 6 on 6 lines (6 validation, 0 execution)"
    assert lines[2].startswith("  chain:   none")
    assert lines[3] == "  intact:  nothing to check"
    assert lines[4] == f"  head:    line 6 (no seq) {_digest(REGISTRY_FILE.read_bytes().splitlines()[-1])}"
    assert len(lines) == 5


def test_evidence_log_shows_where_an_older_log_was_continued(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log = tmp_path / "evidence.jsonl"
    shutil.copyfile(REGISTRY_FILE, log)
    argv = ["validate", str(PROGRAM), "-m", str(MANIFEST), "-e", str(ENVELOPE), "--profile", "home", "--no-policy"]
    assert _run([*argv, "--evidence-log", str(log)], capsys)[0] == 0
    assert log.read_bytes().startswith(REGISTRY_FILE.read_bytes())
    code, out, _ = _run(["evidence", "log", str(log)], capsys)
    assert code == 0
    lines = out.splitlines()
    assert lines[1] == "  records: 7 on 7 lines (7 validation, 0 execution)"
    assert lines[2].startswith("  chain:   starts at line 7; lines 1 to 6 were written before the chain")
    assert lines[3] == "  intact:  yes"
    assert lines[4].startswith("  head:    seq 7 sha256:")


# ---------------------------------------------------------------------------
# The documented example is a real, replayable record
# ---------------------------------------------------------------------------


def _documented_line(first_key: str) -> str:
    """The one record line on the page whose first (sorted) key is `first_key`."""
    text = DOC.read_text(encoding="utf-8")
    lines: list[str] = re.findall(r"^\{\"" + first_key + r"\".*\}$", text, flags=re.MULTILINE)
    assert len(lines) == 1, f"the page shows exactly one record line starting with {first_key}"
    return lines[0]


def _documented_record() -> ValidationRecord:
    return ValidationRecord.model_validate(json.loads(_documented_line("as_of")))


def test_the_documented_record_replays() -> None:
    record = _documented_record()
    assert (record.surface, record.verdict, record.codes) == ("validate", "refused", ["envelope.force_exceeded"])
    assert record.program == _load(GRASP_4N)
    assert (record.format, record.seq, record.prev) == ("urml.validation-record/2", 1, None)
    check = reverify(record, manifest=_load(MANIFEST), envelope=_load(ENVELOPE), policy=None)
    assert check.reproduced, check.problems


def test_the_documented_execution_record_is_the_run_of_the_example() -> None:
    """The page's line 3: the run of red-mug.urml.yaml, linked to the page's other numbers."""
    text = DOC.read_text(encoding="utf-8")
    line = _documented_line("adapter")
    record = ExecutionRecord.model_validate(json.loads(line))
    # The example runs on the mock, and the record says so.
    assert record.adapter == "urml_ros2_runtime.substrate.mock.MockROSAdapter"
    assert (record.format, record.surface, record.outcome, record.seq) == (
        "urml.execution-record/1", "execute", "completed", 3,
    )
    assert record.program_digest == content_digest(_load(PROGRAM))
    assert record.manifest_digest == content_digest(_load(MANIFEST)) == _documented_record().manifest_digest
    assert record.envelope_digest == content_digest(_load(ENVELOPE))
    steps = _load(PROGRAM)["behavior"]["steps"]
    assert [(step.path, step.primitive, step.outcome) for step in record.steps] == [
        (["behavior", "steps", str(index)], next(iter(step)), "ok") for index, step in enumerate(steps)
    ]
    assert record.steps_executed == len(steps)
    # The `urml evidence log` output on the page shows this line as the head.
    assert f"  head:    seq 3 {_digest(line.encode('utf-8'))}" in text
    # The broken-chain example hashes the page's line 1, and the head check greps for line 2's digest.
    assert f"but line 1 hashes to {_digest(_documented_line('as_of').encode('utf-8'))}" in text
    assert f"grep -c '\"prev\":\"{record.prev}\"' evidence.jsonl" in text
