"""The evidence log's chain: written, checked, and honest about its limits (RFC-0715, Draft).

Every line `append_record` writes carries `seq`, its line number, and `prev`,
the digest of the line before it. `verify_log` walks the file and names the
first line where that stops holding. These tests show each kind of break
being found, and they also pin what the chain does not find: a tail that was
cut off, an edit to the last line, and a file somebody rewrote from scratch.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

import pytest
import yaml

from urml_validator import evidence, validate
from urml_validator.evidence import (
    EXECUTION_RECORD_FORMAT,
    RECORD_FORMAT,
    ExecutedStep,
    ExecutionRecord,
    RuntimeInfo,
    ValidationRecord,
    append_record,
    build_execution_record,
    build_record,
    canonical_json,
    content_digest,
    read_log,
    read_records,
    reverify,
    verify_log,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
HOME = REPO_ROOT / "examples" / "home"
REGISTRY_FILE = REPO_ROOT / "registry" / "evidence" / "gopigo3-example-adapter" / "validation-records.jsonl"
FORMAT_1 = "urml.validation-record/1"


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


MANIFEST = _load(HOME / "red-mug.manifest.yaml")
ENVELOPE = _load(HOME / "red-mug.envelope.yaml")
SAFE = _load(HOME / "red-mug.urml.yaml")
GRASP_4N = _load(HOME / "red-mug.grasp-4n.urml.yaml")


def _record(program: dict[str, Any] = GRASP_4N, **extra: Any) -> ValidationRecord:
    result = validate(program, MANIFEST, ENVELOPE, profiles=("home",), policy=None)
    return build_record(
        surface="api",
        stage="validation",
        result=result,
        program=program,
        manifest=MANIFEST,
        envelope=ENVELOPE,
        policy=None,
        profiles=("home",),
        recorded_at="2026-11-28T08:00:00Z",
        **extra,
    )


def _execution(**extra: Any) -> ExecutionRecord:
    fields: dict[str, Any] = {
        "surface": "runtime",
        "tool": RuntimeInfo(name="urml-ros2-runtime", version="0.0.0"),
        "adapter": "urml_ros2_runtime.substrate.mock.MockROSAdapter",
        "robot_id": "turtlebot4_red_mug",
        "program_digest": content_digest(SAFE),
        "manifest_digest": content_digest(MANIFEST),
        "envelope_digest": content_digest(ENVELOPE),
        "outcome": "completed",
        "steps": [
            ExecutedStep(path=["behavior", "steps", "0"], primitive="move_to", outcome="ok", duration_s=0.25),
        ],
        "steps_executed": 1,
        "recorded_at": "2026-11-28T08:00:05Z",
    }
    fields.update(extra)
    return build_execution_record(**fields)


def _digest(line: bytes) -> str:
    """The chain's digest of one line, computed here from the rule and not from the module."""
    return "sha256:" + hashlib.sha256(line).hexdigest()


def _lines(log: Path) -> list[bytes]:
    data = log.read_bytes()
    assert data.endswith(b"\n")
    return data[:-1].split(b"\n")


def _write(log: Path, lines: list[bytes]) -> None:
    log.write_bytes(b"".join(line + b"\n" for line in lines))


def _format_1_line(record: ValidationRecord) -> bytes:
    """The line urml-validator 0.5.3 wrote for this verdict: format 1, no seq, no prev."""
    data = record.model_dump(mode="json")
    del data["seq"], data["prev"]
    data["format"] = FORMAT_1
    return canonical_json(data).encode("utf-8")


def _log_of(tmp_path: Path, count: int) -> Path:
    log = tmp_path / "evidence.jsonl"
    for index in range(count):
        append_record(log, _record(SAFE if index % 2 else GRASP_4N))
    return log


# ---------------------------------------------------------------------------
# Writing the chain
# ---------------------------------------------------------------------------


def test_each_line_carries_its_number_and_the_digest_of_the_line_before(tmp_path: Path) -> None:
    log = tmp_path / "nested" / "evidence.jsonl"
    built = _record()
    written = [append_record(log, built) for _ in range(3)]
    lines = _lines(log)
    assert [json.loads(line)["seq"] for line in lines] == [1, 2, 3]
    assert [json.loads(line)["prev"] for line in lines] == [None, _digest(lines[0]), _digest(lines[1])]
    assert [json.loads(line)["format"] for line in lines] == [RECORD_FORMAT] * 3
    assert RECORD_FORMAT == "urml.validation-record/2"
    # append_record returns what it wrote, and leaves the record it was given alone.
    assert [(w.seq, w.prev) for w in written] == [(1, None), (2, _digest(lines[0])), (3, _digest(lines[1]))]
    assert lines[1] == canonical_json(written[1].model_dump(mode="json")).encode("utf-8")
    assert (built.seq, built.prev) == (None, None)


def test_the_record_id_does_not_depend_on_the_place_in_the_log(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    built = _record()
    first, second = append_record(log, built), append_record(log, built)
    assert (first.seq, second.seq) == (1, 2)
    assert first.record_id == second.record_id == built.record_id


def test_the_record_id_inputs_are_the_format_1_inputs() -> None:
    """Format 2 added the chain and left the identity alone: same inputs, same tag."""
    record = _record()
    identity = {
        "format": FORMAT_1,
        "verdict": record.verdict,
        "program_digest": record.program_digest,
        "manifest_digest": record.manifest_digest,
        "envelope_digest": record.envelope_digest,
        "policy": record.policy,
        "rulebooks": [ref.model_dump() for ref in record.rulebooks],
        "default_rulebooks": record.default_rulebooks,
        "as_of": record.as_of,
        "profiles": record.profiles,
        "codes": record.codes,
        "tool_version": record.tool.version,
    }
    assert record.format == RECORD_FORMAT
    assert record.record_id == content_digest(identity)
    # A record committed to the registry before 0.5.0 (its tool version reads 0.4.0) has an id built the same way.
    committed = read_records(REGISTRY_FILE)[2]
    identity.update(
        verdict=committed.verdict,
        program_digest=committed.program_digest,
        manifest_digest=committed.manifest_digest,
        envelope_digest=committed.envelope_digest,
        policy=committed.policy,
        rulebooks=[ref.model_dump() for ref in committed.rulebooks],
        default_rulebooks=committed.default_rulebooks,
        as_of=committed.as_of,
        profiles=committed.profiles,
        codes=committed.codes,
        tool_version=committed.tool.version,
    )
    assert committed.record_id == content_digest(identity)


def test_each_append_is_flushed_to_disk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    synced: list[int] = []
    real = os.fsync

    def _fsync(fd: int) -> None:
        synced.append(fd)
        real(fd)

    monkeypatch.setattr(evidence.os, "fsync", _fsync)
    log = _log_of(tmp_path, 2)
    assert len(synced) == 2
    assert verify_log(log).intact


def test_a_last_line_longer_than_one_read_block_is_still_chained(tmp_path: Path) -> None:
    """The writer finds the last line by reading backwards; a long line spans several blocks."""
    log = tmp_path / "evidence.jsonl"
    long_request = "bring the mug. " * 20_000  # about 300 kB, several 64 kB blocks
    append_record(log, _record(request=long_request))
    append_record(log, _record(request=long_request))
    append_record(log, _record())
    lines = _lines(log)
    assert len(lines[0]) > 4 * 65536
    assert [json.loads(line)["prev"] for line in lines] == [None, _digest(lines[0]), _digest(lines[1])]
    assert verify_log(log).intact


def test_line_separators_inside_a_request_do_not_split_a_record(tmp_path: Path) -> None:
    """U+2028 and U+0085 stay raw in canonical JSON. Only a newline ends a line.

    Before the chain, `read_records` split a log with `str.splitlines`, which
    also breaks at these characters, so a request holding one could be written
    and never read back.
    """
    log = tmp_path / "evidence.jsonl"
    request = "bring the mug\u2028then stop\u0085and wait\u2029here"
    append_record(log, _record(request=request))
    append_record(log, _record())
    assert len(_lines(log)) == 2
    first, second = read_records(log)
    assert first.request == request and second.seq == 2
    check = verify_log(log)
    assert check.intact and check.lines == 2


@pytest.mark.skipif(sys.platform == "win32", reason="needs a POSIX device file")
def test_a_log_must_be_a_regular_file() -> None:
    """The chain reads the line before it writes the next, so a device or a pipe cannot hold one."""
    with pytest.raises(OSError, match="regular file"):
        append_record(os.devnull, _record())


def test_a_directory_is_still_an_os_error(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        append_record(tmp_path, _record())


# ---------------------------------------------------------------------------
# Checking the chain
# ---------------------------------------------------------------------------


def test_an_intact_log_verifies(tmp_path: Path) -> None:
    log = _log_of(tmp_path, 4)
    append_record(log, _execution())
    check = verify_log(log)
    assert check.intact and check.problems == [] and check.problem_count == 0
    assert (check.lines, check.records) == (5, 5)
    assert (check.validation_records, check.execution_records) == (4, 1)
    assert check.chain_start == 1
    assert (check.head_seq, check.head_digest) == (5, _digest(_lines(log)[-1]))


def test_an_empty_log_has_no_chain_and_no_head(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    log.write_bytes(b"")
    check = verify_log(log)
    assert check.intact and check.lines == 0 and check.records == 0
    assert (check.chain_start, check.head_seq, check.head_digest) == (None, None, None)


def test_a_missing_log_is_an_os_error(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        verify_log(tmp_path / "no-such.jsonl")


def test_an_edited_line_is_found_by_the_line_after_it(tmp_path: Path) -> None:
    log = _log_of(tmp_path, 4)
    lines = _lines(log)
    lines[1] = lines[1].replace(b'"verdict":"accepted"', b'"verdict":"refused"')
    assert lines[1] != _lines(log)[1]
    _write(log, lines)
    check = verify_log(log)
    assert not check.intact
    (problem,) = check.problems
    assert problem.startswith("line 3: prev is ") and "line 2" in problem
    assert check.chain_start == 1 and check.head_seq == 4


def test_a_removed_line_is_found_where_the_gap_is(tmp_path: Path) -> None:
    log = _log_of(tmp_path, 5)
    lines = _lines(log)
    del lines[2]
    _write(log, lines)
    check = verify_log(log)
    assert not check.intact
    assert check.problems[0] == "line 3: seq is 4, expected 3"
    assert check.problems[1].startswith("line 3: prev is ")
    # One gap, reported once: the lines after it follow on from the line they follow.
    assert check.problem_count == 2
    assert check.head_seq == 5 and check.lines == 4


def test_a_removed_first_line_is_found(tmp_path: Path) -> None:
    log = _log_of(tmp_path, 3)
    _write(log, _lines(log)[1:])
    check = verify_log(log)
    assert not check.intact
    assert check.problems[0] == "line 1: seq is 2, expected 1"
    assert check.problems[1].startswith("line 1: prev is ")
    assert "nothing comes before the first line" in check.problems[1]


def test_swapped_lines_are_found(tmp_path: Path) -> None:
    log = _log_of(tmp_path, 4)
    lines = _lines(log)
    lines[1], lines[2] = lines[2], lines[1]
    _write(log, lines)
    check = verify_log(log)
    assert not check.intact
    assert check.problems[0] == "line 2: seq is 3, expected 2"
    assert any(problem.startswith("line 2: prev is ") for problem in check.problems)
    assert any(problem == "line 3: seq is 2, expected 4" for problem in check.problems)


def test_a_repeated_line_is_found(tmp_path: Path) -> None:
    log = _log_of(tmp_path, 3)
    lines = _lines(log)
    _write(log, [lines[0], lines[1], lines[1], lines[2]])
    check = verify_log(log)
    assert not check.intact
    assert check.problems[0] == "line 3: seq is 2, expected 3"


def test_a_line_that_is_not_a_record_is_found(tmp_path: Path) -> None:
    log = _log_of(tmp_path, 3)
    lines = _lines(log)
    for garbage in (b"not json", b'{"format":"something-else/9"}', b"", b"\xff\xfe"):
        _write(log, [lines[0], garbage, lines[2]])
        check = verify_log(log)
        assert not check.intact
        assert check.problems[0].startswith("line 2: not a record")
        assert check.lines == 3 and check.records == 2


def test_an_unchained_line_after_the_chain_started_is_found(tmp_path: Path) -> None:
    """A format 1 line in the middle of a chain was not written by a format 2 writer."""
    log = _log_of(tmp_path, 2)
    lines = _lines(log)
    _write(log, [lines[0], _format_1_line(_record()), lines[1]])
    check = verify_log(log)
    assert not check.intact
    assert check.problems[0] == "line 2: no seq, after the chain started at line 1"
    assert check.chain_start == 1


def test_a_format_2_record_without_seq_is_found(tmp_path: Path) -> None:
    """Only a format 1 record is written without a place in the chain."""
    log = tmp_path / "evidence.jsonl"
    unchained = canonical_json(_record().model_dump(mode="json")).encode("utf-8")
    _write(log, [unchained, canonical_json(_execution().model_dump(mode="json")).encode("utf-8")])
    check = verify_log(log)
    assert not check.intact and check.chain_start is None
    assert check.problems == [
        "line 1: no seq; only a format 1 validation record is written without one",
        "line 2: no seq; only a format 1 validation record is written without one",
    ]


def test_only_the_first_problems_are_listed(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    _write(log, [b"not json"] * 80)
    check = verify_log(log)
    assert check.problem_count == 80
    assert len(check.problems) == 50
    assert check.problems[0].startswith("line 1: not a record")


# ---------------------------------------------------------------------------
# What the chain does not show
# ---------------------------------------------------------------------------


def test_a_cut_off_tail_is_not_detected(tmp_path: Path) -> None:
    """Nothing in a shorter file says it was longer. Only a head noted elsewhere does."""
    log = _log_of(tmp_path, 5)
    noted = verify_log(log)
    _write(log, _lines(log)[:3])
    check = verify_log(log)
    assert check.intact and check.problems == []
    assert (check.head_seq, check.lines) == (3, 3)
    assert (check.head_seq, check.head_digest) != (noted.head_seq, noted.head_digest)


def test_an_edit_to_the_last_line_is_only_visible_in_the_head(tmp_path: Path) -> None:
    """No later line holds the last line's digest, so the chain alone cannot see it change."""
    log = _log_of(tmp_path, 3)
    noted = verify_log(log)
    lines = _lines(log)
    lines[2] = lines[2].replace(b'"verdict":"refused"', b'"verdict":"accepted"')
    assert lines[2] != _lines(log)[2]
    _write(log, lines)
    check = verify_log(log)
    assert check.intact
    assert check.head_seq == noted.head_seq and check.head_digest != noted.head_digest


def test_a_rewritten_file_is_not_detected(tmp_path: Path) -> None:
    """The chain has no secret. Whoever rebuilds every line gets a chain that checks."""
    log = _log_of(tmp_path, 4)
    noted = verify_log(log)
    forged = tmp_path / "forged.jsonl"
    kept = [record for record in read_log(log) if record.seq != 2]
    for record in kept:
        append_record(forged, record)
    check = verify_log(forged)
    assert check.intact and check.lines == 3
    assert check.head_digest != noted.head_digest


# ---------------------------------------------------------------------------
# Format 1: still read, still replayed, and continued
# ---------------------------------------------------------------------------


def test_the_test_helper_writes_what_0_5_3_wrote() -> None:
    committed = json.loads(REGISTRY_FILE.read_bytes().split(b"\n")[0])
    assert set(json.loads(_format_1_line(_record()))) == set(committed)
    assert committed["format"] == FORMAT_1


def test_a_format_1_log_is_read_and_replayed(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    _write(log, [_format_1_line(_record(GRASP_4N)), _format_1_line(_record(SAFE))])
    refused, accepted = read_records(log)
    assert (refused.format, refused.seq, refused.prev) == (FORMAT_1, None, None)
    assert (refused.verdict, accepted.verdict) == ("refused", "accepted")
    for record in (refused, accepted):
        check = reverify(record, manifest=MANIFEST, envelope=ENVELOPE, policy=None)
        assert check.reproduced, check.problems


def test_a_committed_format_1_file_has_no_chain_and_no_problem() -> None:
    before = REGISTRY_FILE.read_bytes()
    records = read_records(REGISTRY_FILE)
    assert len(records) == 6
    assert {(record.format, record.seq, record.prev) for record in records} == {(FORMAT_1, None, None)}
    check = verify_log(REGISTRY_FILE)
    assert check.intact and check.chain_start is None
    assert (check.lines, check.validation_records, check.execution_records) == (6, 6, 0)
    assert (check.head_seq, check.head_digest) == (None, _digest(before.split(b"\n")[5]))
    assert REGISTRY_FILE.read_bytes() == before


def test_a_format_1_record_with_a_chain_field_is_refused() -> None:
    data = json.loads(_format_1_line(_record()))
    assert ValidationRecord.model_validate(data).seq is None
    with pytest.raises(ValueError, match="format 1"):
        ValidationRecord.model_validate({**data, "seq": 1})
    with pytest.raises(ValueError, match="format 1"):
        ValidationRecord.model_validate({**data, "prev": "sha256:" + "0" * 64})


def test_a_format_1_log_is_continued_by_format_2(tmp_path: Path) -> None:
    """The chain starts at the first format 2 line and reaches back one line."""
    log = tmp_path / "evidence.jsonl"
    old = [_format_1_line(_record(GRASP_4N)), _format_1_line(_record(SAFE)), _format_1_line(_record(GRASP_4N))]
    _write(log, old)
    fourth = append_record(log, _record(SAFE))
    fifth = append_record(log, _record(GRASP_4N))
    assert (fourth.format, fourth.seq, fourth.prev) == (RECORD_FORMAT, 4, _digest(old[2]))
    assert (fifth.seq, fifth.prev) == (5, _digest(_lines(log)[3]))
    assert _lines(log)[:3] == old  # the old lines are not touched
    check = verify_log(log)
    assert check.intact and check.chain_start == 4
    assert (check.lines, check.head_seq) == (5, 5)
    assert [record.format for record in read_records(log)] == [FORMAT_1] * 3 + [RECORD_FORMAT] * 2
    for record in read_records(log):
        assert reverify(record, manifest=MANIFEST, envelope=ENVELOPE, policy=None).reproduced


def test_the_format_1_lines_before_the_chain_are_covered_by_their_number(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    old = [_format_1_line(_record(GRASP_4N)), _format_1_line(_record(SAFE)), _format_1_line(_record(GRASP_4N))]
    _write(log, old)
    append_record(log, _record(SAFE))
    chained = _lines(log)[3]

    _write(log, [old[0], old[2], chained])  # one format 1 line removed
    assert verify_log(log).problems == ["line 3: seq is 4, expected 3"]

    edited_last = old[2].replace(b'"verdict":"refused"', b'"verdict":"accepted"')
    _write(log, [old[0], old[1], edited_last, chained])  # the last format 1 line edited
    (problem,) = verify_log(log).problems
    assert problem.startswith("line 4: prev is ") and "line 3" in problem

    edited_first = old[0].replace(b'"verdict":"refused"', b'"verdict":"accepted"')
    _write(log, [edited_first, old[1], old[2], chained])  # an earlier format 1 line edited
    assert verify_log(log).intact, "nothing covers the bytes of a format 1 line that is not the last one"


def test_appending_a_format_1_record_writes_it_as_format_2(tmp_path: Path) -> None:
    """A writer always writes format 2, also for a record it read from an old log."""
    old_log, new_log = tmp_path / "old.jsonl", tmp_path / "new.jsonl"
    _write(old_log, [_format_1_line(_record())])
    (old,) = read_records(old_log)
    written = append_record(new_log, old)
    assert (written.format, written.seq, written.prev) == (RECORD_FORMAT, 1, None)
    assert written.record_id == old.record_id
    assert verify_log(new_log).intact


# ---------------------------------------------------------------------------
# A tail that is not a clean line
# ---------------------------------------------------------------------------


def test_a_torn_last_line_is_kept_and_the_next_record_starts_a_new_line(tmp_path: Path) -> None:
    log = _log_of(tmp_path, 2)
    intact = log.read_bytes()
    torn = b'{"as_of":null,"attempt_codes":nu'
    log.write_bytes(intact + torn)  # a write that stopped half way, with no newline
    third = append_record(log, _record())
    lines = _lines(log)
    assert lines[2] == torn
    assert (third.seq, third.prev) == (4, _digest(torn))
    check = verify_log(log)
    assert not check.intact
    assert check.problems == ["line 3: not a record (not JSON)"]
    assert (check.lines, check.records, check.head_seq) == (4, 3, 4)


def test_a_last_line_without_a_newline_gets_one_before_the_next_record(tmp_path: Path) -> None:
    log = _log_of(tmp_path, 2)
    log.write_bytes(log.read_bytes()[:-1])  # the same two records, the final newline stripped
    third = append_record(log, _record())
    assert third.seq == 3
    assert len(_lines(log)) == 3
    assert verify_log(log).intact


def test_a_blank_line_is_reported_and_counted(tmp_path: Path) -> None:
    log = _log_of(tmp_path, 1)
    first = _lines(log)[0]
    log.write_bytes(first + b"\n\n")
    second = append_record(log, _record())
    assert (second.seq, second.prev) == (3, _digest(b""))
    check = verify_log(log)
    assert check.problems == ["line 2: not a record (empty line)"]
    assert len(read_records(log)) == 2  # reading skips it, as it always did


# ---------------------------------------------------------------------------
# Two writers
# ---------------------------------------------------------------------------

_WRITER = """
import sys
from pathlib import Path
from urml_validator.evidence import ValidationRecord, append_record

record = ValidationRecord.model_validate_json(Path(sys.argv[2]).read_text(encoding="utf-8"))
for _ in range(int(sys.argv[3])):
    append_record(sys.argv[1], record)
"""


def test_two_processes_appending_at_once_leave_an_intact_chain(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    template = tmp_path / "record.json"
    template.write_text(_record().model_dump_json(), encoding="utf-8")
    each = 60
    writers = [
        subprocess.Popen([sys.executable, "-c", _WRITER, str(log), str(template), str(each)])
        for _ in range(2)
    ]
    for writer in writers:
        assert writer.wait(timeout=120) == 0
    check = verify_log(log)
    assert check.intact, check.problems
    assert (check.lines, check.records, check.head_seq) == (2 * each, 2 * each, 2 * each)
    assert [json.loads(line)["seq"] for line in _lines(log)] == list(range(1, 2 * each + 1))


def test_threads_appending_at_once_leave_an_intact_chain(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    record = _record()
    failures: list[BaseException] = []

    def _append() -> None:
        try:
            for _ in range(20):
                append_record(log, record)
        except BaseException as exc:
            failures.append(exc)

    threads = [threading.Thread(target=_append) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)
    assert failures == []
    check = verify_log(log)
    assert check.intact, check.problems
    assert check.lines == 80


def test_a_log_held_by_another_writer_times_out_and_is_left_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The wait for the lock is bounded, and running out of time is an OSError like any other."""
    log = _log_of(tmp_path, 1)
    before = log.read_bytes()
    monkeypatch.setattr(evidence, "_LOCK_WAIT_S", 0.2)
    with log.open("a+b", buffering=0) as other:
        assert evidence._try_lock(other)
        try:
            with pytest.raises(TimeoutError, match="lock"):
                append_record(log, _record())
            assert issubclass(TimeoutError, OSError)
            assert log.read_bytes() == before
        finally:
            evidence._unlock(other)
    assert append_record(log, _record()).seq == 2


# ---------------------------------------------------------------------------
# Execution records share the log
# ---------------------------------------------------------------------------


def test_read_log_returns_both_kinds_and_read_records_only_verdicts(tmp_path: Path) -> None:
    log = tmp_path / "evidence.jsonl"
    accepted = append_record(log, _record(SAFE))
    ran = append_record(log, _execution())
    refused = append_record(log, _record(GRASP_4N))
    assert read_log(log) == [accepted, ran, refused]
    assert read_records(log) == [accepted, refused]
    assert isinstance(ran, ExecutionRecord)
    assert (ran.format, ran.seq, ran.prev) == (EXECUTION_RECORD_FORMAT, 2, _digest(_lines(log)[0]))
    assert EXECUTION_RECORD_FORMAT == "urml.execution-record/1"


def test_read_log_names_the_bad_line(tmp_path: Path) -> None:
    log = _log_of(tmp_path, 1)
    with log.open("ab") as handle:
        handle.write(b'{"format":"urml.execution-record/1","outcome":"completed"}\n')
    with pytest.raises(ValueError, match=r"evidence\.jsonl:2:"):
        read_log(log)
    with pytest.raises(ValueError, match=r"evidence\.jsonl:2:"):
        read_records(log)


def test_an_execution_record_holds_these_fields_and_no_others() -> None:
    record = _execution()
    assert set(record.model_dump()) == {
        "format", "record_id", "recorded_at", "tool", "surface", "adapter", "robot_id", "program_digest",
        "manifest_digest", "envelope_digest", "outcome", "steps_executed", "steps", "error", "seq", "prev",
    }
    assert set(record.steps[0].model_dump()) == {"path", "primitive", "outcome", "error", "duration_s"}
    assert record.tool.model_dump() == {"name": "urml-ros2-runtime", "version": "0.0.0"}
    assert record.recorded_at == "2026-11-28T08:00:05Z"
    assert build_execution_record(
        surface="runtime",
        tool=RuntimeInfo(name="urml-ros2-runtime", version="0.0.0"),
        adapter="urml_ros2_runtime.substrate.mock.MockROSAdapter",
        robot_id=None,
        program_digest=content_digest(SAFE),
        manifest_digest=content_digest(MANIFEST),
        envelope_digest=None,
        outcome="completed",
        steps=[],
        steps_executed=0,
    ).recorded_at.endswith("Z")


def test_an_execution_record_id_is_the_run_not_the_moment() -> None:
    def step(duration: float, outcome: str = "ok", error: str | None = None) -> ExecutedStep:
        return ExecutedStep(
            path=["behavior", "steps", "0"], primitive="move_to", outcome=outcome, error=error, duration_s=duration
        )

    base = _execution(steps=[step(0.25)])
    identity = {
        "format": EXECUTION_RECORD_FORMAT,
        "program_digest": base.program_digest,
        "manifest_digest": base.manifest_digest,
        "adapter": "urml_ros2_runtime.substrate.mock.MockROSAdapter",
        "outcome": "completed",
        "steps": [{"path": ["behavior", "steps", "0"], "primitive": "move_to", "outcome": "ok", "error": None}],
    }
    assert base.record_id == content_digest(identity)
    # Not the time, not the durations, not the place in the log.
    assert _execution(steps=[step(9.5)], recorded_at="2027-01-01T00:00:00Z").record_id == base.record_id
    assert base.model_copy(update={"seq": 7, "prev": "sha256:" + "0" * 64}).record_id == base.record_id
    # The outcome, the steps and the program are.
    failed = _execution(outcome="failed", error="path_blocked", steps=[step(0.25, "failed", "path_blocked")])
    assert failed.record_id != base.record_id
    assert _execution(program_digest=content_digest(GRASP_4N)).record_id != base.record_id


def test_an_execution_record_keeps_its_own_rules() -> None:
    path = ["behavior", "steps", "0"]
    with pytest.raises(ValueError, match="failed step"):
        ExecutedStep(path=path, primitive="move_to", outcome="failed", duration_s=0.1)
    with pytest.raises(ValueError, match="ok step"):
        ExecutedStep(path=path, primitive="move_to", outcome="ok", error="path_blocked", duration_s=0.1)
    with pytest.raises(ValueError, match="failed run"):
        _execution(outcome="failed")
    with pytest.raises(ValueError, match="completed run"):
        _execution(error="path_blocked")
    with pytest.raises(ValueError):
        ExecutionRecord.model_validate({**_execution().model_dump(mode="json"), "host": "robot-7"})
