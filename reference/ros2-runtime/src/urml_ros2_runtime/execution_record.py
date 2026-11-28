"""Execution records: what one run dispatched, kept in the evidence log (RFC-0715, Draft).

`URMLRuntime.execute` makes one `ExecutionRecorder` for each run that got past
re-validation. The recorder notes every step at the one place the runtime
dispatches a step, and writes one execution record when the run ends, whether
it completed, failed or raised. With no evidence log it does nothing.

The record says what the runtime sent to the adapter and what the adapter
reported back. It does not say what the robot physically did.

A record that cannot be written never changes the run's result and is never
silent. `finished` returns the reason, which `execute` puts in
`RuntimeResult.evidence_log_error`. `raised` adds the reason as a note to the
exception that is on its way out.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from urml_validator.evidence import (
    ExecutedStep,
    RunOutcome,
    RuntimeInfo,
    Surface,
    append_record,
    build_execution_record,
    content_digest,
)

from urml_ros2_runtime._version import __version__
from urml_ros2_runtime.primitives import PrimitiveOutcome

__all__ = ["ExecutionRecorder", "adapter_name", "validator_path"]

_NO_STEP_REASON = "the adapter reported failure and gave no reason"
_NO_RUN_REASON = "the run failed and its last outcome gave no reason"


def validator_path(path: Sequence[str]) -> list[str]:
    """A step's path as validation errors write it.

    The runtime numbers the attempts of a retry (`attempt`, `0`). The
    validator names the retried behavior once (`behavior`). Every other
    segment is the same in both, so a step inside a retry keeps one path
    across its attempts.
    """
    out: list[str] = []
    segments = iter(path)
    for segment in segments:
        if segment == "attempt":
            next(segments, None)
            out.append("behavior")
        else:
            out.append(segment)
    return out


def adapter_name(adapter: object) -> str:
    """An adapter's class as `module.Class`, the form an execution record holds."""
    cls = type(adapter)
    return f"{cls.__module__}.{cls.__qualname__}"


def _describe(exc: BaseException) -> str:
    text = str(exc)
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


class ExecutionRecorder:
    """Notes the steps of one run and writes the run's execution record."""

    def __init__(
        self,
        log: Path | None,
        *,
        surface: Surface = "runtime",
        adapter: object = None,
        program: Mapping[str, Any] | BaseModel | None = None,
        manifest: Mapping[str, Any] | BaseModel | None = None,
        envelope: Mapping[str, Any] | BaseModel | None = None,
    ) -> None:
        """Start the record of one run. With `log` None every method does nothing.

        The digests are taken here, before the first step, so they name the
        program the gate accepted and not whatever the objects hold later.
        """
        self._log = log
        self._surface: Surface = surface
        self._adapter = adapter_name(adapter)
        # One entry per dispatch: the runtime's path, the primitive, the error
        # (None for a step that came back ok), and the seconds it took.
        self._steps: list[tuple[list[str], str, str | None, float]] = []
        self._answered = 0
        self._program_digest = ""
        self._manifest_digest = ""
        self._envelope_digest: str | None = None
        self._robot_id: str | None = None
        if log is None:
            return
        self._program_digest = content_digest(program)
        self._manifest_digest = content_digest(manifest)
        self._envelope_digest = content_digest(envelope) if envelope is not None else None
        robot_id = manifest.get("robot_id") if isinstance(manifest, Mapping) else getattr(manifest, "robot_id", None)
        self._robot_id = robot_id if isinstance(robot_id, str) else None

    def dispatch(
        self, primitive: str, path: Sequence[str], call: Callable[[], PrimitiveOutcome]
    ) -> PrimitiveOutcome:
        """Make one step's call and note what came back.

        `call` is the runtime's one dispatch of a step, so a step is noted
        once for each time it is dispatched. The outcome is returned as it
        came. An exception is noted as a failed step and raised again as it
        was, a Ctrl-C included.
        """
        if self._log is None:
            return call()
        started = time.perf_counter()
        try:
            outcome = call()
        except BaseException as exc:
            self._steps.append((list(path), primitive, _describe(exc), time.perf_counter() - started))
            raise
        self._answered += 1
        error = None if outcome.success else outcome.reason or _NO_STEP_REASON
        self._steps.append((list(path), primitive, error, time.perf_counter() - started))
        return outcome

    def finished(self, *, success: bool, reason: str | None) -> str | None:
        """Write the record of a run that returned a result.

        `reason` is the last outcome's reason, kept as the run's error when
        the run failed. Returns None when the record was written or no log is
        set, and otherwise why the record is missing.
        """
        if success:
            return self._write("completed", None)
        return self._write("failed", reason or _NO_RUN_REASON)

    def raised(self, exc: BaseException) -> None:
        """Write the record of a run that ended in an exception.

        When the record cannot be written, the reason is added to `exc` as a
        note. The caller raises `exc` again either way.
        """
        problem = self._write("failed", _describe(exc))
        if problem is not None:
            exc.add_note(problem)

    def _write(self, outcome: RunOutcome, error: str | None) -> str | None:
        if self._log is None:
            return None
        try:
            record = build_execution_record(
                surface=self._surface,
                tool=RuntimeInfo(name="urml-ros2-runtime", version=__version__),
                adapter=self._adapter,
                robot_id=self._robot_id,
                program_digest=self._program_digest,
                manifest_digest=self._manifest_digest,
                envelope_digest=self._envelope_digest,
                outcome=outcome,
                steps=[
                    ExecutedStep(
                        path=validator_path(path),
                        primitive=primitive,
                        outcome="ok" if step_error is None else "failed",
                        error=step_error,
                        duration_s=round(seconds, 3),
                    )
                    for path, primitive, step_error, seconds in self._steps
                ],
                steps_executed=self._answered,
                error=error,
            )
            append_record(self._log, record)
        except Exception as exc:
            # The run is over and its result stands. Whatever stopped the
            # record, a full disk or a fault in this module, the caller is
            # told instead of losing the result to a second exception.
            detail = str(exc) if isinstance(exc, OSError) else _describe(exc)
            return f"the evidence log {self._log} was not written: {detail}"
        return None
