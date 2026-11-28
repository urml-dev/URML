---
rfc: 0715
title: A chained evidence log, and a record of what ran
author: Ido Yahalomi (greenvh@gmail.com)
state: Draft
created: 2026-11-28
updated: 2026-11-28
supersedes: none
superseded-by: none
---

<p align="center">
  <a href="https://urml.dev"><img src="https://urml.dev/favicon.svg" alt="URML" width="72" height="72"></a>
</p>

<p align="center">
  The standard language for robot intent.
</p>

<p align="center">
  <a href="https://urml.dev"><b>urml.dev</b></a>
</p>

---

# RFC-0715: A chained evidence log, and a record of what ran

Kind: Spec (tooling). This RFC defines the two record formats of the evidence log, the local file a validator and a runtime write to when an operator names one, and adds one CLI command. It changes no layer, no primitive and no validation rule. The log stays opt-in, and nothing about when it is on changes here.

## Summary

The evidence log gains three things.

Every line is chained to the one before it. Validation record format 2 adds two fields: `seq`, the line's number in the file, and `prev`, the digest of the bytes of the line before. The writer takes an exclusive lock for each line and calls `fsync` before it lets go.

The runtime writes an execution record, `urml.execution-record/1`, at the end of every run that got past its re-validation: which steps it dispatched and what the adapter reported back for each.

A checker reads a log and names the first line where the chain breaks: `verify_log` in Python and `urml evidence log FILE` on the command line.

Format 1 records are still read and replayed, and a log an older version began is continued in place. The validation record shipped without an RFC, so this document also states format 1 in full.

## Motivation

The validation record shipped in 0.5.0 with a user page ([`docs/evidence/validation-records.md`](../evidence/validation-records.md)) and no RFC. The registry replays committed records in CI, and the rulebooks for the EU Machinery Regulation and the EU Cyber Resilience Act name the records as something a manufacturer can put in its file of evidence ([`examples/rulebooks/eu-machinery-regulation.yaml`](../../examples/rulebooks/eu-machinery-regulation.yaml), obligation `rule_changes_go_through_the_risk_assessment`).

A review of the log for that use found three weaknesses.

**A line can go missing without a trace.** The log was a plain file opened for append. Remove the refusal from last Tuesday, or change `refused` to `accepted` in it, and nothing in the file disagrees. A record that cannot show it was left alone is weak evidence that a gate held.

**Nothing says what ran.** A record says a program was accepted. It does not say whether the program then ran, how far it got, or which step failed. `RuntimeResult` returns the step count and, for the mock adapter, a call log; nothing keeps them. An integrator looking into an incident can show what the robot was allowed to do at 14:02 and not what the runtime sent it.

**There is no tool to check a log.** `read_records` parses a file and `reverify` replays one verdict. Neither says whether the file is whole.

Two smaller faults came out of the same reading. Nothing locked the file, so two commands writing to one log were kept apart only by the operating system's append. And `read_records` split a file with `str.splitlines`, which also breaks at U+2028 and U+0085: a natural-language request holding one of those characters could be written and never read back.

## Detailed design

### The file

An evidence log is a UTF-8 text file with one record per line. A line ends at a newline byte (`0x0A`) and nowhere else. Each line is canonical JSON: keys sorted, no whitespace between tokens, non-ASCII characters kept as they are (`json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`).

Two digests are used. A content digest is `sha256:` followed by the lowercase hex SHA-256 of the canonical JSON of a value. A line digest is `sha256:` followed by the lowercase hex SHA-256 of a line's bytes, without its newline.

A reader refuses a record with a field this RFC does not name.

### Validation record, format 1

Format 1 is what urml-validator wrote up to 0.5.3. It has these fields and no others.

| Field | Type | Meaning |
|---|---|---|
| `format` | string | `urml.validation-record/1` |
| `record_id` | string | The content digest of the identity (below) |
| `recorded_at` | string | UTC time of the verdict, `YYYY-MM-DDTHH:MM:SSZ`, by the host's clock |
| `tool` | object | `name` (`urml-validator`) and `version` |
| `surface` | string | `api`, `validate`, `execute`, `run`, `translate`, `runtime`, `mcp` or `action_server` |
| `stage` | string | `validation`, `revalidation` or `bridge` |
| `verdict` | string | `accepted` or `refused` |
| `robot_id` | string or null | The manifest's `robot_id` |
| `program` | object or null | The program as judged. Null only for a bridge refusal that carried no parsed program |
| `program_digest` | string or null | Content digest of `program` |
| `manifest_digest` | string | Content digest of the manifest |
| `envelope_digest` | string or null | Content digest of the envelope |
| `policy` | string | `none`, `default`, or the content digest of a policy file |
| `rulebooks` | array | The operator's rulebooks in order, each `rulebook_id` (string or null) and `digest` |
| `default_rulebooks` | boolean | Whether the bundled rulebooks applied |
| `as_of` | string or null | The date rulebook dates were judged against, `YYYY-MM-DD` |
| `profiles` | array of strings | The profiles the program was judged under |
| `codes` | array of strings | Error codes, in emission order |
| `warning_codes` | array of strings | Warning codes, in order |
| `result` | object | The `ValidationResult`, as `urml validate --json` prints it |
| `request` | string or null | The natural-language request, for a bridge verdict |
| `attempts` | integer or null | How many emissions the bridge validated |
| `attempt_codes` | array or null | The error codes of each bridge attempt, in order |

The identity is the object below, and `record_id` is its content digest. `tool_version` is `tool.version`.

```json
{"format": "urml.validation-record/1", "verdict": "...", "program_digest": "...",
 "manifest_digest": "...", "envelope_digest": "...", "policy": "...",
 "rulebooks": [{"rulebook_id": "...", "digest": "..."}], "default_rulebooks": true,
 "as_of": null, "profiles": ["..."], "codes": ["..."], "tool_version": "..."}
```

### Validation record, format 2

Format 2 is format 1 with `format` set to `urml.validation-record/2` and two more fields.

| Field | Type | Meaning |
|---|---|---|
| `seq` | integer, 1 or more | The line's number in the file, counting every line from 1 |
| `prev` | string or null | The line digest of the line before. Null on the first line of a file |

`record_id` keeps its meaning and its inputs. The identity object is the one above, tag included: it still reads `urml.validation-record/1`, because the identity of a verdict did not change. `seq`, `prev` and `recorded_at` are not part of it, so the same verdict has the same id wherever and whenever it is written.

A writer always writes format 2. A record with format 1 that carries `seq` or `prev` is not a record.

### Execution record

`urml.execution-record/1` is one run of an accepted program.

| Field | Type | Meaning |
|---|---|---|
| `format` | string | `urml.execution-record/1` |
| `record_id` | string | The content digest of the identity (below) |
| `recorded_at` | string | UTC time the run ended and the record was written, by the host's clock |
| `tool` | object | The runtime's package `name` and `version` |
| `surface` | string | The entry point that called the runtime, from the list above, or `runtime` when the runtime was not told |
| `adapter` | string | The class of the adapter the runtime dispatched to, as `module.Class`. It tells a run on the mock adapter from a run on a robot. A wrapper names itself, not what it wraps |
| `robot_id` | string or null | The manifest's `robot_id` |
| `program_digest` | string | Content digest of the program that ran |
| `manifest_digest` | string | Content digest of the manifest |
| `envelope_digest` | string or null | Content digest of the envelope |
| `outcome` | string | `completed` when the runtime reported success. `failed` when it reported failure or the run raised |
| `steps_executed` | integer | How many dispatched steps the adapter answered |
| `steps` | array | Every step dispatched, in dispatch order |
| `error` | string or null | Why the run failed. Null for a completed run, set for a failed one |
| `seq`, `prev` | | As in validation record format 2 |

Each entry of `steps` has these fields.

| Field | Type | Meaning |
|---|---|---|
| `path` | array of strings | Where the step sits in the program, as validation errors write paths (`["behavior", "steps", "1"]`) |
| `primitive` | string | The primitive's name |
| `outcome` | string | `ok` when the adapter reported success. `failed` when it reported failure or raised |
| `error` | string or null | Set for a failed step: the adapter's reason, or the exception. Null for an ok step |
| `duration_s` | number | Seconds from the dispatch to the answer, to the millisecond |

The identity is the format tag, `program_digest`, `manifest_digest`, `adapter`, `outcome`, and `steps` with each entry's `path`, `primitive`, `outcome` and `error`. Durations, the time and the chain fields are not part of it.

A step inside a `retry` is listed once for each attempt, under one path. A run that carried on after a failed step (`on_error: continue`) can be `completed` with a `failed` entry in its list. A step the envelope shield stopped before dispatch is not listed, since nothing was sent, and the shield's reason is the run's `error`.

**What it does not record.** The record holds what the runtime sent to the adapter and what the adapter said back. It does not hold what the robot physically did. An adapter can report success for a motion that slipped or stalled, and URML has no way to know.

### The chain

For a line at line number N:

1. the line is a record;
2. the first line that carries `seq` starts the chain, and its `seq` is N;
3. from there on every line carries `seq`, one more than the line before;
4. `prev` is the line digest of line N - 1, and null when N is 1;
5. before the chain starts, only format 1 validation records appear.

A log an older version began is therefore valid when a newer one continues it. The chain starts at the first format 2 line, whose `seq` is its line number and whose `prev` covers the last format 1 line. The format 1 lines are not rewritten. Their number is covered by the first `seq`, and the bytes of the last of them by the first `prev`.

### Writing a line

`append_record(path, record)` creates the file and its folder as before, and then:

1. opens the file and refuses anything that is not a regular file;
2. takes an exclusive lock, `flock` on POSIX and `msvcrt.locking` on Windows, behind a lock that keeps the threads of one process in turn. It waits up to ten seconds and then raises `TimeoutError`;
3. reads the last line backwards from the end of the file. When that line is a chained record its `seq` is the line count. When it is not, the file is read once to count its lines;
4. writes one line with `seq` and `prev` set, and with format 2 for a validation record;
5. calls `fsync`, and releases the lock.

It returns the record as written and leaves the one it was given unchanged. Every failure is an `OSError`, as it was, so every entry point keeps its behavior: a log that cannot be written stops the command before anything runs.

A last line with no newline, which a write that stopped half way leaves behind, is kept as it is. The new record starts on its own line and its `prev` covers the torn one. The check then reports the torn line.

On Windows a lock on a byte stops other handles from reading it, so the lock sits on one byte far past the end of the file, where a reader never looks.

### Who writes what

Each entry point that makes a verdict records it, as before. `URMLRuntime.execute` records a refusal at its re-validation, as before, and now writes one execution record at the end of a run that got past it, whether the run completed, failed, raised or was interrupted. The steps are noted at the one place the runtime dispatches a step. The adapter is not wrapped.

The runtime is told which entry point is calling it (`evidence_surface`), and writes that into `surface`.

**The link rule.** For every execution record a shipped entry point causes, an accepted validation record with the same `program_digest` comes earlier in the same log. `urml execute`, the MCP server and the action server validate and record the program they then hand to the runtime, so the digests match. `urml run` did not: it recorded the bridge's verdict on the model's emission and executed that program with the request copied into its `description`. `urml run` now validates the program as it will run, with the manifest's directory in view, records that verdict, and refuses before it rehearses or builds an adapter, as `urml execute` does. The runtime's own check stays behind it.

**A record that cannot be written after a run.** The run has happened, so the failure changes no result and is never silent. The runtime returns its result with `success` unchanged and the reason in a new field, `RuntimeResult.evidence_log_error`; when the run raised, the same exception goes on with the reason attached as a note. `urml execute` and `urml run` print the result, say on stderr that the record is missing, and exit 2. The MCP server returns the result with the field set and prints a line for the operator. The action server returns the result with the reason in `reason`.

**Not recorded.** Fleet programs get neither kind of record: a record holds one manifest digest, and a fleet has one manifest per member. A rehearsal is a simulation and writes nothing.

### Reading and checking

`read_records(path)` returns the validation records of a log, both formats, in order, and skips execution records, so the registry checker reads a mixed log as it read a format 1 file. `read_log(path)` returns both kinds. Both split lines at newline bytes only.

`verify_log(path)` applies the five rules above and returns the number of lines and of records by kind, the line where the chain starts, whether it found no problem, the first fifty problems with a count of all of them, and the head: the last line's `seq` and line digest. After a break it carries on from the `seq` it found, so one removed line is reported once.

`urml evidence log FILE` prints the same facts. It exits 0 when no problem was found, 1 when one was, and 2 when the file cannot be read. A file with no chain exits 0, and the output says there is no chain. `log` sits beside `evidence build` and `evidence verify`; `verify` already means checking a signed evidence report ([RFC-0707](0707-evidence-report.md)), so the log command does not use the word.

### What an intact chain shows

A removed line, an edited line or lines in another order show to anyone who holds a later line or the head.

A rewritten file does not. The chain holds no secret, so whoever can write the file can drop a record and compute every `seq` and `prev` again. A cut-off end does not either: a shorter file checks. The last line is in the same position, since no later line holds its digest. All three show only against a head noted somewhere the writer of the file cannot reach, and the user page says how to compare one.

`recorded_at` is the host's clock. Keeping the file, for however long the operator's rules ask, is the operator's job: URML appends to it and never deletes, rotates or copies it.

### Spec changes

None to a layer document or a profile. The record formats are defined in this RFC and described for users in [`docs/evidence/validation-records.md`](../evidence/validation-records.md). They have no JSON Schema file (see Unresolved questions).

### Validator changes

No validation rule changes. In `urml_validator.evidence`: `RECORD_FORMAT` becomes `urml.validation-record/2`; `ValidationRecord` accepts both formats and gains `seq` and `prev`; `ExecutionRecord`, `ExecutedStep`, `RuntimeInfo`, `build_execution_record`, `read_log`, `verify_log` and `LogVerification` are new; `append_record` chains, locks and syncs, and returns the record; `read_records` skips execution records. In the CLI: `urml evidence log`, the extra validation in `urml run`, and exit code 2 for a run whose record could not be written.

### Reference runtime changes

`urml-ros2-runtime`: a new module, `execution_record.py`; `URMLRuntime` takes `evidence_surface` and writes the execution record; `RuntimeResult` gains `evidence_log_error`; the action server passes its surface and reports a missing record in `reason`. `urml-mcp-server` passes its surface and reports a missing record on stderr. The other reference runtimes run through `URMLRuntime` and write execution records when their caller sets an evidence log. No adapter changes, and the substrate Protocol does not change.

### Conformance suite changes

None. Writing an evidence log is not a conformance clause, and this RFC does not make it one.

## Backward compatibility

Measured on the branch that implements this RFC.

**Format 1 files.** The three committed registry files (`registry/evidence/*/validation-records.jsonl`, written in September 2026, with `tool.version` 0.4.0) are byte for byte unchanged, their pinned sha256 values match, and `conformance/tests/test_registry.py` passes without an edit: every record parses, replays and reproduces. `registry.py` is not changed.

**Format 2 files and older readers.** A 0.5.3 reader refuses a format 2 line, because it accepts only the tag `urml.validation-record/1` and no unknown field, and it refuses an execution record for the same reason. A log written by this version needs this version or newer to read. A registry entry whose records are format 2 needs a checker at this version.

**Mixed writers.** An older version appending to a log after a newer one writes lines with no `seq`, and the check reports each. It also takes no lock.

**Record ids.** Unchanged for the same validator version: the identity keeps its inputs.

**Python API.** `append_record` returned None and now returns the record. `ValidationRecord.model_dump()` has two more keys. `RuntimeResult` has one more field, so `urml execute --json`, `urml run --json` and the MCP `urml_execute` result carry `evidence_log_error` (null when there is nothing to report). `URMLRuntime` takes one more keyword argument, which the CLI passes: a validator at this version needs a runtime at this version, as with every release since the family moved in lockstep.

**`urml run`.** It validates once more before execution. A program the bridge accepted and the check with the manifest's directory refuses (an HBOM-content rule) is now refused before a rehearsal runs or an adapter is built, where it was refused by the runtime after both. The exit code is 1 in both cases and the message changed. With a log, `run` writes one more validation record per run.

**A log on a pipe or a device.** Refused, because the writer reads the line before the one it writes. The same goes for a file system that cannot lock a file.

**Tests that changed.** Eight existing tests, each for a reason above:

- `test_evidence.py::test_records_hold_no_identifiers`: the field set gained `seq` and `prev`.
- `test_evidence.py::test_append_and_read_back`: a written line carries `seq` and `prev`, so it is compared with the record `append_record` returns.
- `test_cli_evidence.py::test_execute_records_one_verdict_when_it_runs` and `test_action_server_evidence.py::test_the_runtime_gets_the_log`: the runtime is also handed `evidence_surface`.
- `test_cli_evidence.py::test_a_bridge_acceptance_is_recorded` (the `run` case): `run` records a second verdict, on the program as it runs.
- `test_cli_evidence.py::test_the_documented_record_replays`: the page's example line is format 2.
- `test_cli_run.py::test_run_refuses_when_the_runtime_check_rejects`, renamed `..._the_check_before_execution_rejects`: same assertions, the refusal now comes one step earlier.
- `test_runtime_evidence.py::test_an_accepted_program_is_not_recorded_by_the_runtime`, renamed `test_the_runtime_records_the_run_and_not_the_acceptance`: the log now holds one execution record and still no acceptance.

## Drawbacks

**The chain does not stop a full rewrite.** It has no key. It raises the cost of a quiet edit from one line to the whole file, and makes any change visible against a noted head. An operator who notes no head gets less than the word "chain" suggests, which is why the command prints that limit with every intact result.

**Format 2 is refused by a 0.5.3 reader.** There is no way to add fields to a format whose readers refuse unknown fields without that.

**The adapter is named by its class, and a class name is not proof.** The record tells a mock run from a real one by the adapter's class. A wrapper around an adapter names itself, and code that drives the runtime can pass any object. The field says what the runtime was given, in the same way the rest of the record says what the adapter reported.

**Every line now costs a lock and an `fsync`.** Measured on one macOS host, 0.14 ms per append against 0.05 ms for the 0.5.3 writer. `fsync` on macOS does not wait for the drive, so expect more on Linux.

**The Windows lock has no test run behind it.** The branch is type-checked for Windows and follows the documented behavior of `msvcrt.locking`. The repository's CI runs on Linux, so nothing has executed it.

**`urml run` validates three times.** The bridge, the command and the runtime each check. The third check is the price of a verdict on the program that runs.

**Code that drives `URMLRuntime` directly gets a run with no acceptance on file.** The runtime records refusals and runs, and leaves the acceptance to the entry point. A caller with no entry point has to record its own verdict.

## Alternatives considered

**Sign each record with an operator key.** A signature would stop a rewrite by anyone without the key, which the chain does not. It was rejected for this step. The key would live on the robot's host, next to the file it protects, so whoever can rewrite the file can often read the key. Custody that is worth having (a hardware token, a second machine) is a deployment project, and the validator has no signer: it verifies OpenSSH signatures for evidence reports and leaves signing to `ssh-keygen`. Signing the head at intervals, outside the robot, gets most of the value and can be added on top of this format without changing it.

**A second file for execution records.** It would leave the validation log's format alone. It was rejected because the order of a verdict and its run across two files rests on two clocks, a reader has two chains to check and two files to keep together, and the link rule ("the acceptance comes earlier in the same log") could not be stated.

**A keyed chain (HMAC).** Same custody problem as signing, with a shared secret in place of a key pair, and a checker would need the secret.

**A Merkle tree with signed tree heads**, as Certificate Transparency uses. It answers "is this record in the log" without the whole file, for many readers of one large log. A robot's log is a local file with a few readers, and a linear chain is enough.

**Record the adapter's call log in the execution record.** The mock adapter keeps one and real adapters mostly do not. Its entries are adapter-specific, can be large, and can hold coordinates. The record keeps to what every runtime knows: the step, its outcome and its duration.

**Have the runtime record its own acceptance.** It would make the link rule hold for any caller, with one more line per run on every surface. It is left as an unresolved question because it changes what the runtime has recorded since 0.5.0.

## Prior art

- **Git.** A commit names the hash of its parent, so history cannot change without every later hash changing. The same idea, one line at a time.
- **Certificate Transparency (RFC 6962).** An append-only log whose signed tree head lets an outside party hold it to its past. The "head noted somewhere else" is the unsigned, manual form of that.
- **systemd journal sealing** (Forward Secure Sealing). The journal is sealed at intervals with a key that moves forward, and checked with a key kept off the machine. It shows what a keyed scheme needs.
- **Signed syslog (RFC 5848).** Signature blocks over groups of messages, sent with the log.
- **JSON Lines.** One record per line, appended, readable with any tool.
- **[RFC-0707](0707-evidence-report.md)**, which describes a deployment before anything runs and says that what ran is a second question with its own record. This is the record; a report built from it is still to come.
- **[RFC-0638](0638-execution-lifecycle-and-run-report.md)** (Draft), which proposes cancel, pause, progress events and a run report as a return value. It stays the place for lifecycle and progress. This RFC takes only the persisted per-step record, and its step entry (a path, an outcome, a duration) is the smallest shape that proposal's report would also need.

## Unresolved questions

1. **JSON Schema files.** The evidence report has a schema under `spec/evidence/`. The two record formats have none; this RFC defines them in prose and in the pydantic models. Should `spec/evidence/` hold `validation-record` and `execution-record` schemas, exported from the models and guarded for freshness like the registry schema?
2. **The adapter in the execution record.** *Resolved 2026-11-28: the record names the adapter's class.* A mock run would otherwise read as a real one.
3. **The runtime's own acceptance.** Should `URMLRuntime` record an accepted re-validation, so the link rule holds for code that calls it directly?
4. **Checking a noted head.** Should `urml evidence log` take the noted `seq` and digest and say whether the log still passes through them, in place of the `grep` on the user page?
5. **A file with no chain.** `urml evidence log` exits 0 for a format 1 file. Should it exit 1 once format 1 logs are rare?
6. **Chaining in the registry.** Should the registry checker run `verify_log` on a committed file that carries a chain? The entry already pins the file's sha256, so the chain adds nothing there today.

## Implementation note

One pull request carries the formats, the writer, the runtime's record, the command, the tests and the user page. It changes no default.

The validator's CLI passes a new keyword to the runtime, and the runtime imports new names from the validator. The next release raises the `urml-validator` floor in `urml-ros2-runtime`, `urml-mcp-server` and `urml-conformance` to that release, as the lockstep bump does.

This RFC does not turn the log on anywhere, and adds no rule that requires it. The log stays off unless the operator names a file, as the maintainer confirmed on 2026-11-28. A rulebook rule that requires the log is not proposed here or in RFC-0714, which lists it as a question for later.

Once this RFC is Accepted, the questions above are settled in follow-up changes that keep `urml.execution-record/1` if they add nothing a reader would refuse, and move to `/2` if they do.

## Self-review (Phase 0)

- [x] The Summary alone tells a reader what is being proposed.
- [x] The Motivation is grounded in a concrete use case, not hypothetical needs.
- [x] The Detailed design names every affected spec document and reference component.
- [x] At least one alternative is genuinely considered (not a strawman).
- [x] Drawbacks are listed; at least one of them is a real downside, not a humblebrag.
- [x] Backward compatibility is honest about what breaks.
- [x] If this RFC adds a Layer-2 primitive, both ROS-2 and non-ROS implementation sketches are present (substrate-neutrality acid test). Not applicable: no primitive is added. The record formats name no substrate.
- [x] The implementation note explains how this lands, not just what.
- [x] The author has re-read [`CLAUDE.md`](../../CLAUDE.md) §What Claude Should Never Do and confirmed this proposal does not violate it. The log stays opt-in and local, and nothing is sent anywhere.
