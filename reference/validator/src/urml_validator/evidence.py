"""The evidence log: an opt-in, local file of what the gate decided and what ran.

A validation record captures one verdict of the URML validator, `accepted` or
`refused`, together with a content digest of every input it judged: the
program, the manifest, the envelope, the compliance policy and the rulebooks.
An execution record captures one run: the steps the runtime dispatched and
what the adapter reported back for each. Records are appended, one JSON
object per line, to a file the operator names.

The chain (RFC-0715, Draft). Every line `append_record` writes carries `seq`,
its line number in the file, and `prev`, the digest of the bytes of the line
before it. `verify_log` walks a file and names the first line where that
stops holding, so a line that was removed, edited or moved shows to anyone
who holds a later line or the head digest. The chain has no secret: it does
not stop someone who rewrites the whole file, and a file whose end was cut
off still checks. Note the head somewhere else to cover both.

Why keep them. A refused program is the evidence that the gate held: what a
model or a person asked the robot to do, which declared limit it broke, and
which validator version said no. An accepted program is the other half of the
same ledger. The URML registry (`registry/`) re-validates committed records to
show that a listed robot's recorded verdicts still reproduce.

Privacy. Nothing is recorded unless the operator turns the log on (the CLI's
`--evidence-log PATH`, `URMLRuntime(evidence_log=...)`, the MCP server's
`URML_MCP_EVIDENCE_LOG`, or the ROS action server's `evidence_log` parameter).
The log is a local file. It holds the program and, for a bridge verdict
(`urml run`, `urml translate`, a sentence goal on the action server), the
natural-language request, because those are the command being judged. URML
adds no user, host or network identifier, and nothing is sent anywhere. An
execution record holds no program and no request; a failed step's `error` is
the adapter's own text, so it can name what that text names. See
`docs/evidence/validation-records.md`.

Digests of inputs are `sha256:` over canonical JSON (sorted keys, no
whitespace), so the same content hashes the same whether it came from a YAML
file, a JSON file or memory, and whatever the file's formatting. The chain's
`prev` is `sha256:` over the exact bytes of a line, without its newline.
"""

from __future__ import annotations

import errno
import hashlib
import io
import json
import os
import stat
import sys
import threading
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from urml_validator._version import __version__
from urml_validator.errors import ValidationResult

__all__ = [
    "EXECUTION_RECORD_FORMAT",
    "RECORD_FORMAT",
    "ExecutedStep",
    "ExecutionRecord",
    "LogVerification",
    "Reverification",
    "RuntimeInfo",
    "ValidationRecord",
    "append_record",
    "build_execution_record",
    "build_record",
    "canonical_json",
    "content_digest",
    "read_log",
    "read_records",
    "reverify",
    "verify_log",
]

#: The format tag a writer puts on a validation record. Format 2 is format 1
#: plus the chain fields `seq` and `prev`. A reader accepts both.
RECORD_FORMAT: Literal["urml.validation-record/2"] = "urml.validation-record/2"

#: The format urml-validator wrote up to 0.5.3: no `seq`, no `prev`. Still read
#: and replayed. It is also the tag inside every `record_id`: the identity of
#: a verdict did not change with format 2, so its inputs did not either.
_FORMAT_1: Literal["urml.validation-record/1"] = "urml.validation-record/1"

#: The format tag of an execution record.
EXECUTION_RECORD_FORMAT: Literal["urml.execution-record/1"] = "urml.execution-record/1"

Surface = Literal[
    "api", "validate", "execute", "run", "translate", "runtime", "mcp", "action_server"
]
Stage = Literal["validation", "revalidation", "bridge"]
Verdict = Literal["accepted", "refused"]
StepOutcome = Literal["ok", "failed"]
RunOutcome = Literal["completed", "failed"]

_SEQ = (
    "This record's line number in its log, counting every line from 1. Set by "
    "`append_record`; None on a record that has not been appended."
)
_PREV = (
    "`sha256:` over the bytes of the line before this one, without its newline. "
    "None on the first line of a log."
)


def canonical_json(value: Any) -> str:
    """Sorted keys, no whitespace, UTF-8 characters kept: the form every digest uses."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _plain(value: Any) -> Any:
    """A JSON-ready form of a dict or a pydantic model, as the caller supplied it."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_unset=True, by_alias=True)
    return json.loads(json.dumps(value, default=str))


def content_digest(value: Any) -> str:
    """`sha256:<hex>` of the canonical JSON of a dict, list or pydantic model."""
    data = canonical_json(_plain(value)).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


class RulebookRef(BaseModel):
    """One caller-supplied rulebook, by id and content digest."""

    model_config = ConfigDict(extra="forbid")

    rulebook_id: str | None = None
    digest: str


class ToolInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Literal["urml-validator"] = "urml-validator"
    version: str


class ValidationRecord(BaseModel):
    """One verdict of the validator, with digests of everything it judged."""

    model_config = ConfigDict(extra="forbid")

    format: Literal["urml.validation-record/1", "urml.validation-record/2"] = RECORD_FORMAT
    record_id: str = Field(
        ...,
        description=(
            "sha256 over the record's identity: verdict, input digests, profiles, "
            "codes and tool version. Two runs that judged the same inputs the same "
            "way share an id; recorded_at, seq and prev are not part of it."
        ),
    )
    recorded_at: str = Field(..., description="UTC time the verdict was recorded, to the second.")
    tool: ToolInfo
    surface: Surface = Field(..., description="Which entry point produced the verdict.")
    stage: Stage = Field(
        ...,
        description=(
            "`validation`: the first check. `revalidation`: the runtime's own check "
            "before its first adapter call. `bridge`: the LLM bridge's final verdict."
        ),
    )
    verdict: Verdict
    robot_id: str | None = None
    program: dict[str, Any] | None = Field(
        None,
        description=(
            "The program as judged. None only for a bridge refusal whose exception did "
            "not carry the parsed program (a urml-llm-bridge older than `last_program`)."
        ),
    )
    program_digest: str | None = None
    manifest_digest: str
    envelope_digest: str | None = None
    policy: str = Field(
        ..., description="`none`, `default` (the bundled policy), or the content digest of a custom policy."
    )
    rulebooks: list[RulebookRef] = Field(default_factory=list)
    default_rulebooks: bool = True
    as_of: str | None = Field(None, description="The date rulebook effective dates were judged against.")
    profiles: list[str] = Field(default_factory=list)
    codes: list[str] = Field(default_factory=list, description="Error codes, in emission order.")
    warning_codes: list[str] = Field(default_factory=list)
    result: dict[str, Any] = Field(..., description="The ValidationResult, as `urml validate --json` prints it.")
    request: str | None = Field(None, description="The natural-language request, for a bridge verdict.")
    attempts: int | None = Field(None, description="How many emissions the bridge validated, for a bridge verdict.")
    attempt_codes: list[list[str]] | None = Field(
        None, description="Error codes of each bridge attempt, in order."
    )
    seq: int | None = Field(None, ge=1, description="Format 2. " + _SEQ)
    prev: str | None = Field(None, description="Format 2. " + _PREV)

    @model_validator(mode="after")
    def _format_1_has_no_chain(self) -> ValidationRecord:
        if self.format == _FORMAT_1 and (self.seq is not None or self.prev is not None):
            raise ValueError("a format 1 record has no seq and no prev; the chain starts with format 2")
        return self


class RuntimeInfo(BaseModel):
    """The runtime that dispatched a run, by package name and version."""

    model_config = ConfigDict(extra="forbid")

    name: str
    version: str


class ExecutedStep(BaseModel):
    """One step the runtime dispatched, and what came back for it."""

    model_config = ConfigDict(extra="forbid")

    path: list[str] = Field(
        ...,
        description=(
            "Where the step sits in the program, written as validation errors write "
            "paths. A step inside a retry appears once per attempt, with the same path."
        ),
    )
    primitive: str
    outcome: StepOutcome = Field(
        ..., description="`ok` when the adapter reported success. `failed` when it reported failure or raised."
    )
    error: str | None = Field(None, description="Why the step failed, in the adapter's or the runtime's words.")
    duration_s: float = Field(
        ..., ge=0, description="Seconds from the dispatch to the answer, on the host's clock, to the millisecond."
    )

    @model_validator(mode="after")
    def _error_goes_with_failure(self) -> ExecutedStep:
        if self.outcome == "failed" and self.error is None:
            raise ValueError("a failed step carries an error")
        if self.outcome == "ok" and self.error is not None:
            raise ValueError("an ok step carries no error")
        return self


class ExecutionRecord(BaseModel):
    """One run of an accepted program: what the runtime dispatched, step by step.

    It records what the runtime sent to the adapter and what the adapter
    reported back. It does not record what the robot physically did: an
    adapter can report success for a motion that slipped, stalled or never
    happened, and nothing in URML sees the difference.
    """

    model_config = ConfigDict(extra="forbid")

    format: Literal["urml.execution-record/1"] = EXECUTION_RECORD_FORMAT
    record_id: str = Field(
        ...,
        description=(
            "sha256 over the run's identity: program digest, manifest digest, adapter, "
            "outcome and the steps without their durations. recorded_at, seq and prev "
            "are not part of it."
        ),
    )
    recorded_at: str = Field(..., description="UTC time the run ended and was recorded, to the second.")
    tool: RuntimeInfo
    surface: Surface = Field(
        ..., description="The entry point that called the runtime, or `runtime` when the runtime was not told."
    )
    adapter: str = Field(
        ...,
        description=(
            "The class of the adapter the runtime dispatched to, as `module.Class`. It tells "
            "a run on a mock adapter from a run on a robot. A wrapper names itself, not "
            "what it wraps."
        ),
    )
    robot_id: str | None = None
    program_digest: str = Field(
        ..., description="Content digest of the program that ran. An accepted validation record carries the same one."
    )
    manifest_digest: str
    envelope_digest: str | None = None
    outcome: RunOutcome = Field(
        ..., description="`completed` when the runtime reported success, `failed` when it did not or it raised."
    )
    steps_executed: int = Field(..., ge=0, description="How many dispatched steps the adapter answered.")
    steps: list[ExecutedStep] = Field(..., description="Every step dispatched, in dispatch order.")
    error: str | None = Field(None, description="Why the run failed. None for a completed run.")
    seq: int | None = Field(None, ge=1, description=_SEQ)
    prev: str | None = Field(None, description=_PREV)

    @model_validator(mode="after")
    def _error_goes_with_failure(self) -> ExecutionRecord:
        if self.outcome == "failed" and self.error is None:
            raise ValueError("a failed run carries an error")
        if self.outcome == "completed" and self.error is not None:
            raise ValueError("a completed run carries no error")
        return self


def _policy_label(policy: Any) -> str:
    if policy is None:
        return "none"
    if isinstance(policy, str) and policy == "DEFAULT":
        return "default"
    return content_digest(policy)


def _rulebook_refs(rulebooks: Sequence[Any]) -> list[RulebookRef]:
    refs: list[RulebookRef] = []
    for rulebook in rulebooks:
        plain = _plain(rulebook)
        rulebook_id = plain.get("rulebook_id") if isinstance(plain, Mapping) else None
        refs.append(RulebookRef(rulebook_id=rulebook_id, digest=content_digest(plain)))
    return refs


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_record(
    *,
    surface: Surface,
    stage: Stage,
    result: ValidationResult,
    program: Mapping[str, Any] | BaseModel | None,
    manifest: Mapping[str, Any] | BaseModel,
    envelope: Mapping[str, Any] | BaseModel | None = None,
    policy: Any = "DEFAULT",
    rulebooks: Sequence[Any] = (),
    default_rulebooks: bool = True,
    as_of: date | None = None,
    profiles: Sequence[str] = (),
    request: str | None = None,
    attempts: int | None = None,
    attempt_codes: Sequence[Sequence[str]] | None = None,
    recorded_at: str | None = None,
) -> ValidationRecord:
    """Build the record for one verdict. Pure: it reads nothing and writes nothing."""
    program_plain: dict[str, Any] | None = _plain(program) if program is not None else None
    manifest_plain = _plain(manifest)
    robot_id = manifest_plain.get("robot_id") if isinstance(manifest_plain, Mapping) else None
    codes = [str(e.code) for e in result.errors]
    verdict: Verdict = "accepted" if result.accepted else "refused"
    program_digest = content_digest(program_plain) if program_plain is not None else None
    manifest_digest = content_digest(manifest_plain)
    envelope_digest = content_digest(envelope) if envelope is not None else None
    policy_label = _policy_label(policy)
    rulebook_refs = _rulebook_refs(rulebooks)
    as_of_text = as_of.isoformat() if as_of is not None else None
    identity = {
        "format": _FORMAT_1,
        "verdict": verdict,
        "program_digest": program_digest,
        "manifest_digest": manifest_digest,
        "envelope_digest": envelope_digest,
        "policy": policy_label,
        "rulebooks": [ref.model_dump() for ref in rulebook_refs],
        "default_rulebooks": default_rulebooks,
        "as_of": as_of_text,
        "profiles": list(profiles),
        "codes": codes,
        "tool_version": __version__,
    }
    return ValidationRecord(
        record_id=content_digest(identity),
        recorded_at=recorded_at or _now(),
        tool=ToolInfo(version=__version__),
        surface=surface,
        stage=stage,
        verdict=verdict,
        robot_id=robot_id if isinstance(robot_id, str) else None,
        program=program_plain,
        program_digest=program_digest,
        manifest_digest=manifest_digest,
        envelope_digest=envelope_digest,
        policy=policy_label,
        rulebooks=rulebook_refs,
        default_rulebooks=default_rulebooks,
        as_of=as_of_text,
        profiles=list(profiles),
        codes=codes,
        warning_codes=[str(w.code) for w in result.warnings],
        result=result.model_dump(mode="json"),
        request=request,
        attempts=attempts,
        attempt_codes=[list(c) for c in attempt_codes] if attempt_codes is not None else None,
    )


def build_execution_record(
    *,
    surface: Surface,
    tool: RuntimeInfo,
    adapter: str,
    robot_id: str | None,
    program_digest: str,
    manifest_digest: str,
    envelope_digest: str | None,
    outcome: RunOutcome,
    steps: Sequence[ExecutedStep],
    steps_executed: int,
    error: str | None = None,
    recorded_at: str | None = None,
) -> ExecutionRecord:
    """Build the record for one run. Pure: it reads nothing and writes nothing.

    The digests are the caller's, taken with `content_digest` before the first
    step, so they name the program the gate accepted.
    """
    step_list = list(steps)
    identity = {
        "format": EXECUTION_RECORD_FORMAT,
        "program_digest": program_digest,
        "manifest_digest": manifest_digest,
        "adapter": adapter,
        "outcome": outcome,
        "steps": [step.model_dump(mode="json", exclude={"duration_s"}) for step in step_list],
    }
    return ExecutionRecord(
        record_id=content_digest(identity),
        recorded_at=recorded_at or _now(),
        tool=tool,
        surface=surface,
        adapter=adapter,
        robot_id=robot_id,
        program_digest=program_digest,
        manifest_digest=manifest_digest,
        envelope_digest=envelope_digest,
        outcome=outcome,
        steps_executed=steps_executed,
        steps=step_list,
        error=error,
    )


# ---------------------------------------------------------------------------
# The log file: one writer at a time, every line chained to the one before
# ---------------------------------------------------------------------------

RecordT = TypeVar("RecordT", ValidationRecord, ExecutionRecord)

#: How long `append_record` waits for another writer before it gives up.
_LOCK_WAIT_S = 10.0
_LOCK_POLL_S = 0.005
#: The last line is found by reading backwards in blocks of this size.
_BLOCK = 65536
#: `verify_log` lists this many problems and counts the rest.
_MAX_PROBLEMS = 50

#: Threads of one process take turns here. The file lock is for other processes.
_THREADS = threading.Lock()

if sys.platform == "win32":
    import msvcrt

    #: A Windows lock is mandatory: a locked byte cannot be read through another
    #: handle. The lock sits on one byte far past the end of any log, so a
    #: reader is never turned away while a writer holds it.
    _LOCK_BYTE = 1 << 62

    def _try_lock(handle: io.FileIO) -> bool:
        """Take the exclusive lock if it is free. False when another writer holds it."""
        handle.seek(_LOCK_BYTE)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EDEADLK):
                return False
            raise
        return True

    def _unlock(handle: io.FileIO) -> None:
        handle.seek(_LOCK_BYTE)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _try_lock(handle: io.FileIO) -> bool:
        """Take the exclusive lock if it is free. False when another writer holds it."""
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True

    def _unlock(handle: io.FileIO) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def _exclusive(handle: io.FileIO, path: Path) -> Iterator[None]:
    """Hold a log for one append. The wait is bounded; running out of it is a TimeoutError."""
    deadline = time.monotonic() + _LOCK_WAIT_S
    gave_up = f"gave up after {_LOCK_WAIT_S:g} s waiting for the lock on {path}; another writer holds it"
    if not _THREADS.acquire(timeout=_LOCK_WAIT_S):
        raise TimeoutError(gave_up)
    try:
        while not _try_lock(handle):
            if time.monotonic() >= deadline:
                raise TimeoutError(gave_up)
            time.sleep(_LOCK_POLL_S)
        try:
            yield
        finally:
            _unlock(handle)
    finally:
        _THREADS.release()


def _line_digest(line: bytes) -> str:
    """`sha256:<hex>` of one line's bytes, without its newline: what the next line's `prev` holds."""
    return "sha256:" + hashlib.sha256(line).hexdigest()


def _parse_record(line: bytes) -> ValidationRecord | ExecutionRecord:
    """The record one line holds. Raises ValueError when the line is neither kind."""
    data = json.loads(line.decode("utf-8"))
    if isinstance(data, dict) and data.get("format") == EXECUTION_RECORD_FORMAT:
        return ExecutionRecord.model_validate(data)
    return ValidationRecord.model_validate(data)


def _read_at(handle: io.FileIO, start: int, length: int) -> bytes:
    """Exactly `length` bytes from `start`."""
    handle.seek(start)
    parts: list[bytes] = []
    remaining = length
    while remaining:
        part = handle.read(remaining)
        if not part:
            raise OSError(errno.EIO, "the evidence log got shorter while it was being read")
        parts.append(part)
        remaining -= len(part)
    return b"".join(parts)


def _last_line(handle: io.FileIO, size: int) -> tuple[bytes, bool]:
    """The last line of a log that is not empty, and whether a newline ends it."""
    terminated = _read_at(handle, size - 1, 1) == b"\n"
    end = size - 1 if terminated else size
    pieces: list[bytes] = []
    while end > 0:
        start = max(0, end - _BLOCK)
        block = _read_at(handle, start, end - start)
        cut = block.rfind(b"\n")
        if cut != -1:
            pieces.append(block[cut + 1 :])
            break
        pieces.append(block)
        end = start
    return b"".join(reversed(pieces)), terminated


def _count_lines(handle: io.FileIO, size: int) -> int:
    """How many lines a log holds. A last line with no newline counts as one."""
    count = 0
    last = b"\n"
    start = 0
    while start < size:
        block = _read_at(handle, start, min(_BLOCK, size - start))
        count += block.count(b"\n")
        last = block[-1:]
        start += len(block)
    return count if last == b"\n" else count + 1


def _chained_seq(line: bytes) -> int | None:
    """The `seq` of a line that is a chained record, else None."""
    try:
        return _parse_record(line).seq
    except ValueError:
        return None


def _write_all(handle: io.FileIO, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = handle.write(view)
        if not written:
            raise OSError(errno.EIO, "the evidence log took no bytes")
        view = view[written:]


def append_record(path: Path | str, record: RecordT) -> RecordT:
    """Append one record as one chained line of canonical JSON, and return it as written.

    Creates the file and its folder. Under an exclusive lock it reads the last
    line, sets `seq` to this line's number and `prev` to the digest of the
    line before, writes the line, and calls `fsync` before it lets go. The
    record it was given is not changed. A validation record is always written
    as format 2.

    The lock holds off other threads and other processes, on POSIX (`flock`)
    and on Windows (`msvcrt.locking`). A writer that cannot get it within ten
    seconds raises TimeoutError. That and every other failure to write is an
    OSError, which callers treat as "the record was not written".

    The last line gives the count when it is a chained record. Otherwise the
    file is read once to count its lines, which happens on the first append
    to a log an older version began. A last line with no newline is left as
    it is and the new record starts on a line of its own.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a+b", buffering=0) as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise OSError(errno.EINVAL, "an evidence log must be a regular file", str(target))
        with _exclusive(handle, target):
            size = handle.seek(0, os.SEEK_END)
            seq, prev, lead = 1, None, b""
            if size:
                last, terminated = _last_line(handle, size)
                count = _chained_seq(last)
                if count is None:
                    count = _count_lines(handle, size)
                seq, prev = count + 1, _line_digest(last)
                lead = b"" if terminated else b"\n"
            update: dict[str, Any] = {"seq": seq, "prev": prev}
            if isinstance(record, ValidationRecord):
                update["format"] = RECORD_FORMAT
            written = record.model_copy(update=update)
            line = canonical_json(written.model_dump(mode="json")).encode("utf-8")
            _write_all(handle, lead + line + b"\n")
            os.fsync(handle.fileno())
    return written


def read_log(path: Path | str) -> list[ValidationRecord | ExecutionRecord]:
    """Every record in a log, validation and execution, in order.

    A line ends at a newline and nowhere else. A blank line is skipped. Any
    other line that is not a record raises ValueError naming it. This reads
    records and does not check the chain: `verify_log` does that.
    """
    records: list[ValidationRecord | ExecutionRecord] = []
    lines = Path(path).read_bytes().split(b"\n")
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            records.append(_parse_record(line))
        except ValueError as exc:
            raise ValueError(f"{path}:{number}: not a validation record or an execution record: {exc}") from exc
    return records


def read_records(path: Path | str) -> list[ValidationRecord]:
    """Every validation record in a log, in order, format 1 and format 2.

    Execution records are skipped. A malformed line raises ValueError naming it.
    """
    return [record for record in read_log(path) if isinstance(record, ValidationRecord)]


class LogVerification(BaseModel):
    """What `verify_log` found in one evidence log."""

    model_config = ConfigDict(extra="forbid")

    lines: int = Field(..., description="Lines in the file, records or not.")
    records: int = Field(..., description="Lines that are records.")
    validation_records: int
    execution_records: int
    chain_start: int | None = Field(
        None,
        description=(
            "The line of the first record that carries `seq`. None when no line does: "
            "the file holds only format 1 records, or nothing."
        ),
    )
    intact: bool = Field(
        ...,
        description=(
            "True when no problem was found. With `chain_start` None there is no chain, "
            "and this says only that every line is a record."
        ),
    )
    problems: list[str] = Field(
        default_factory=list, description="The first problems found, in file order, each naming its line."
    )
    problem_count: int = Field(0, description="How many problems were found, listed or not.")
    head_seq: int | None = Field(None, description="The last line's `seq`. None when it has none.")
    head_digest: str | None = Field(
        None, description="`sha256:` over the last line's bytes: what the next record's `prev` will be."
    )


def _first_error(exc: ValidationError) -> str:
    errors = exc.errors(include_url=False, include_context=False, include_input=False)
    first = errors[0]
    where = ".".join(str(part) for part in first["loc"]) or "record"
    more = f", and {len(errors) - 1} more" if len(errors) > 1 else ""
    return f"{where}: {first['msg']}{more}"


def verify_log(path: Path | str) -> LogVerification:
    """Check an evidence log line by line and report where its chain breaks.

    The rules, for a line at line number N:

    - every line is a record;
    - the first record that carries `seq` starts the chain, and its `seq` is N;
    - from there on every line carries `seq`, one more than the line before;
    - `prev` is the digest of the bytes of line N - 1, or null on line 1;
    - before the chain starts, only format 1 validation records are allowed.

    After a break the check carries on from the `seq` it found, so one removed
    line is reported once and not again on every line after it.

    What an intact result does not show: that the file still has its end (a
    cut-off tail checks), that the last line is unchanged (nothing after it
    holds its digest), or that the file was not rewritten as a whole. Compare
    `head_seq` and `head_digest` with a head noted somewhere else for those.
    Raises OSError when the file cannot be read.
    """
    problems: list[str] = []
    found = 0

    def problem(text: str) -> None:
        nonlocal found
        found += 1
        if len(problems) < _MAX_PROBLEMS:
            problems.append(text)

    lines = validation = execution = 0
    chain_start: int | None = None
    expected = 0
    before: bytes | None = None
    head_seq: int | None = None

    with Path(path).open("rb") as handle:
        for raw in handle:
            line = raw[:-1] if raw.endswith(b"\n") else raw
            lines += 1
            record: ValidationRecord | ExecutionRecord | None = None
            if not line.strip():
                problem(f"line {lines}: not a record (empty line)")
            else:
                try:
                    record = _parse_record(line)
                except UnicodeDecodeError:
                    problem(f"line {lines}: not a record (not UTF-8)")
                except json.JSONDecodeError:
                    problem(f"line {lines}: not a record (not JSON)")
                except ValidationError as exc:
                    problem(f"line {lines}: not a record ({_first_error(exc)})")
            if isinstance(record, ValidationRecord):
                validation += 1
            elif record is not None:
                execution += 1

            seq = record.seq if record is not None else None
            if record is not None and seq is not None:
                if chain_start is None:
                    chain_start, expected = lines, lines
                if seq != expected:
                    problem(f"line {lines}: seq is {seq}, expected {expected}")
                if before is None:
                    if record.prev is not None:
                        problem(f"line {lines}: prev is {record.prev}, but nothing comes before the first line")
                elif record.prev != _line_digest(before):
                    problem(
                        f"line {lines}: prev is {record.prev or 'null'}, "
                        f"but line {lines - 1} hashes to {_line_digest(before)}"
                    )
                expected = seq + 1
            else:
                if chain_start is not None:
                    if record is not None:
                        problem(f"line {lines}: no seq, after the chain started at line {chain_start}")
                    expected += 1
                elif record is not None and not (isinstance(record, ValidationRecord) and record.format == _FORMAT_1):
                    problem(f"line {lines}: no seq; only a format 1 validation record is written without one")
            before, head_seq = line, seq

    return LogVerification(
        lines=lines,
        records=validation + execution,
        validation_records=validation,
        execution_records=execution,
        chain_start=chain_start,
        intact=found == 0,
        problems=problems,
        problem_count=found,
        head_seq=head_seq,
        head_digest=_line_digest(before) if before is not None else None,
    )


class Reverification(BaseModel):
    """The outcome of re-running the validator on a recorded program."""

    model_config = ConfigDict(extra="forbid")

    record_id: str
    reproduced: bool
    problems: list[str] = Field(default_factory=list)


def reverify(
    record: ValidationRecord,
    *,
    manifest: Mapping[str, Any] | BaseModel,
    envelope: Mapping[str, Any] | BaseModel | None = None,
    policy: Any = "DEFAULT",
    rulebooks: Sequence[Any] = (),
    manifest_base_dir: Path | None = None,
) -> Reverification:
    """Re-validate a recorded program and compare the verdict and error codes.

    The caller supplies the inputs; each must hash to the digest the record
    carries, so a record can only be re-verified against what it judged.
    A record with no program (the bridge produced none) cannot be replayed.
    """
    from urml_validator.validator import validate

    problems: list[str] = []
    if record.program is None:
        return Reverification(
            record_id=record.record_id,
            reproduced=False,
            problems=["the record has no program to replay"],
        )
    if content_digest(record.program) != record.program_digest:
        problems.append("the program does not match its recorded digest")
    if content_digest(manifest) != record.manifest_digest:
        problems.append("the manifest supplied does not match the recorded manifest digest")
    envelope_digest = content_digest(envelope) if envelope is not None else None
    if envelope_digest != record.envelope_digest:
        problems.append("the envelope supplied does not match the recorded envelope digest")
    if _policy_label(policy) != record.policy:
        problems.append("the policy supplied does not match the recorded policy")
    if [ref.digest for ref in _rulebook_refs(rulebooks)] != [ref.digest for ref in record.rulebooks]:
        problems.append("the rulebooks supplied do not match the recorded rulebooks")
    if problems:
        return Reverification(record_id=record.record_id, reproduced=False, problems=problems)

    result = validate(
        record.program,
        _plain(manifest),
        _plain(envelope) if envelope is not None else None,
        profiles=tuple(record.profiles),
        policy=policy,
        manifest_base_dir=manifest_base_dir,
        rulebooks=[_plain(r) for r in rulebooks],
        default_rulebooks=record.default_rulebooks,
        as_of=date.fromisoformat(record.as_of) if record.as_of else None,
    )
    verdict = "accepted" if result.accepted else "refused"
    if verdict != record.verdict:
        problems.append(f"verdict: recorded {record.verdict}, now {verdict}")
    codes = [str(e.code) for e in result.errors]
    if codes != record.codes:
        problems.append(f"codes: recorded {record.codes}, now {codes}")
    return Reverification(record_id=record.record_id, reproduced=not problems, problems=problems)
