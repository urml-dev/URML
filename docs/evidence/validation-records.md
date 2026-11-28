<p align="center">
  <a href="https://urml.dev"><img src="https://urml.dev/favicon.svg" alt="URML" width="72" height="72"></a>
</p>

<p align="center">
  A small, opinionated, human-readable language for describing robot intent.
</p>

<p align="center">
  <a href="https://urml.dev"><b>urml.dev</b></a>
</p>

---

# Validation records and the evidence log

The URML validator decides whether a program may run on a robot. A validation record is the written trace of one of those decisions: the verdict, the program that was judged, a content digest of every input it was judged against (manifest, envelope, compliance policy, rulebooks), the error codes, and the validator version. An execution record is the trace of one run of an accepted program: the steps the runtime dispatched and what the adapter reported back for each.

Both kinds go to the evidence log, a local file you name, one JSON object per line. The log is opt-in. When you turn it on, each entry point appends one validation record per verdict, accepted or refused, and the runtime appends one execution record per run.

A refused program is the evidence that the gate held: what a person or a model asked the robot to do, and the declared limit that stopped it. An accepted program is the other half of the same ledger, and its execution record says what was then sent to the robot. Because the inputs are recorded as digests, anyone who holds the same manifest, envelope, policy and rulebooks can run the validator again on a recorded program and check that the verdict comes out the same.

Every line carries its line number and the digest of the line before it, so a line that was removed, edited or moved can be found. [What the chain shows and what it does not](#what-the-chain-shows-and-what-it-does-not) says how far that goes. The formats are defined in [RFC-0715](../rfcs/0715-validation-record-chain.md) (Draft).

## Turn it on

| Entry point | Setting | Records |
|---|---|---|
| `urml validate` | `--evidence-log PATH` | its verdict |
| `urml execute` | `--evidence-log PATH` | the verdict of its check before execution, the runtime's refusal if the runtime's own check refuses, and the run |
| `urml translate` | `--evidence-log PATH` | the LLM bridge's final verdict, with the request and each attempt's error codes |
| `urml run` | `--evidence-log PATH` | the bridge's final verdict as for `translate`, the verdict of its check before execution, the runtime's refusal, and the run |
| Python runtime | `URMLRuntime(adapter, evidence_log=PATH)` | refusals at its re-validation, and the run |
| MCP server | `URML_MCP_EVIDENCE_LOG=PATH`, or `--evidence-log PATH` (the flag wins) | the verdict of every `urml_validate` and `urml_execute` call, the runtime's refusals, and each run |
| ROS 2 action server | node parameter `evidence_log` (empty, the default, is off) | the bridge's verdict for a sentence goal, the validator's verdict for every goal, the runtime's refusals, and each run |

For example, `ros2 run urml_ros2_runtime urml-ros2-action-server --ros-args -p evidence_log:=/var/log/urml/evidence.jsonl`.

"The run" is one execution record, written by the runtime when the run ends, whether it completed, failed or raised. A program the runtime refuses at its own check gets a refusal and no execution record, because nothing ran.

The runtime records refusals and runs. It does not record an acceptance: every program it runs was accepted first by the entry point that called it, and that entry point recorded the acceptance. The MCP server and the action server take the log from the operator when they start, and an agent calling a tool or sending a goal cannot change it.

An execution record and the acceptance that allowed it carry the same `program_digest`, and the acceptance comes first in the file. `urml run` executes the bridge's program with the request copied into its `description`, which changes the digest. So `urml run` validates that program once more, before it rehearses or builds an adapter, and records the verdict. That verdict, not the bridge's, is the one the run matches.

Code that drives `URMLRuntime` directly gets the execution record and no acceptance, since no entry point validated first. To have the pair on file, validate the program yourself and append the verdict with `build_record` and `append_record` before you call `execute`.

Some outcomes write no record because there is no verdict to record. A provider error is one: the model's reply was not a JSON object, or the provider call failed. It ends the translation without a verdict, even when an earlier attempt in the same translation was refused. A clarifying question that ends the command (clarify mode, RFC-0700) is another, as are usage errors and goals the action server turns away before validation. Fleet programs are not recorded yet: a record holds one manifest digest, and a fleet has one manifest per member. `FleetRuntime` writes no execution record either.

`urml` prints nothing about the log. Output and exit codes are the same with and without `--evidence-log`. A log that cannot be written stops the command with exit code 2 before the verdict is printed or acted on. The MCP server fails the call and the action server refuses the goal, so nothing runs in either case. The Python runtime still raises its refusal, with a note that the record was not written.

The execution record is written after the run, so a log that fails at that point cannot stop anything. The run's result stands, and each entry point says that the record is missing:

| Entry point | When the run finished and its record could not be written |
|---|---|
| `urml execute`, `urml run` | print the result as usual, say on stderr that the execution record is missing, and exit 2 |
| Python runtime | returns the result with `success` unchanged and the reason in `evidence_log_error`. A run that raised raises the same exception, with the reason as a note |
| MCP server | returns the result with `success` unchanged and the reason in `evidence_log_error`, and prints one line on stderr for the operator |
| ROS 2 action server | returns the result with `success` unchanged and the reason in `reason` |

## An example

The red-mug example has a variant, [`red-mug.grasp-4n.urml.yaml`](../../examples/home/red-mug.grasp-4n.urml.yaml), that grasps the mug at 4 N. The gripper allows 5 N and the deployment envelope caps the grip at 3 N, so the envelope refuses it:

```bash
cd examples/home
urml validate red-mug.grasp-4n.urml.yaml -m red-mug.manifest.yaml \
  -e red-mug.envelope.yaml --profile home --no-policy --evidence-log evidence.jsonl
```

The command prints the refusal and exits 1, as it does without the flag, and appends this line to `evidence.jsonl`:

```json
{"as_of":null,"attempt_codes":null,"attempts":null,"codes":["envelope.force_exceeded"],"default_rulebooks":true,"envelope_digest":"sha256:660c42e847de58644fe3767120097571adadb112f404ff888672e716898f466b","format":"urml.validation-record/2","manifest_digest":"sha256:7227344fdec067d4a854f7f3ec87ebc631de132e33731b2f2b4568cf71117699","policy":"none","prev":null,"profiles":["home"],"program":{"behavior":{"on_error":"abort_and_report","steps":[{"detect":{"object":"mug","store_as":"target"}},{"grasp":{"force":4.0,"target":"$target"}}],"type":"sequence"},"profile":"home"},"program_digest":"sha256:1932ce0821d9f81fb8c9ded1e3d5c04dac2ac9ce316217da4ea2e5afc4be2ba2","record_id":"sha256:9ac68ebdfe1e075d2b9d697b4e18a1d26c1e242794c71d49fac7661d9e731ad2","recorded_at":"2026-11-28T10:09:52Z","request":null,"result":{"accepted":false,"errors":[{"code":"envelope.force_exceeded","detail":null,"field":"force","message":"grasp.force (4.0 N) exceeds the strictest declared force cap (3.0 N).","path":["behavior","steps","1"],"primitive":"grasp","severity":"error","suggestion":"Reduce the grasp force to at most 3.0 N."}],"warnings":[]},"robot_id":"turtlebot4_red_mug","rulebooks":[],"seq":1,"stage":"validation","surface":"validate","tool":{"name":"urml-validator","version":"0.5.3"},"verdict":"refused","warning_codes":[]}
```

It is the first line of the file, so its `seq` is 1 and its `prev` is null.

Now run the program that stays inside the envelope, on the mock adapter:

```bash
urml execute red-mug.urml.yaml -m red-mug.manifest.yaml \
  -e red-mug.envelope.yaml --profile home --no-policy --adapter mock --evidence-log evidence.jsonl
```

It appends two lines. Line 2 is the acceptance, a validation record like the one above with `"verdict":"accepted"`. Line 3 is the execution record:

```json
{"envelope_digest":"sha256:660c42e847de58644fe3767120097571adadb112f404ff888672e716898f466b","error":null,"format":"urml.execution-record/1","manifest_digest":"sha256:7227344fdec067d4a854f7f3ec87ebc631de132e33731b2f2b4568cf71117699","outcome":"completed","prev":"sha256:88dc48fc3455dab735b5c620c281c9e7d5fd4e0d63ad8457772b672835fcc502","program_digest":"sha256:855b8d1326e39a784cf6da3296b261a2501a8be630184894be57f81ba8225116","record_id":"sha256:35df4dbeeb670696ab88a6dfec6ca2d244c443690c133948f0a41308a6ab1413","recorded_at":"2026-11-28T10:09:53Z","robot_id":"turtlebot4_red_mug","seq":3,"steps":[{"duration_s":0.0,"error":null,"outcome":"ok","path":["behavior","steps","0"],"primitive":"move_to"},{"duration_s":0.0,"error":null,"outcome":"ok","path":["behavior","steps","1"],"primitive":"detect"},{"duration_s":0.0,"error":null,"outcome":"ok","path":["behavior","steps","2"],"primitive":"grasp"},{"duration_s":0.0,"error":null,"outcome":"ok","path":["behavior","steps","3"],"primitive":"move_to"},{"duration_s":0.0,"error":null,"outcome":"ok","path":["behavior","steps","4"],"primitive":"release"}],"steps_executed":5,"surface":"execute","tool":{"name":"urml-ros2-runtime","version":"0.5.3"}}
```

Its `prev` is the digest of line 2, and its `program_digest` is the one line 2 carries. The durations are zero because the mock adapter answers at once.

To read a log by eye, `python -m json.tool --json-lines evidence.jsonl` prints each record indented.

## Validation record fields

| Field | Meaning |
|---|---|
| `format` | `urml.validation-record/2`. A reader also accepts `urml.validation-record/1`, the format urml-validator wrote up to 0.5.3. Format 1 has every field below except `seq` and `prev`. |
| `record_id` | `sha256:` over the verdict, the input digests, the profiles, the error codes and the validator version. Two runs that judged the same inputs the same way share an id; `recorded_at`, `seq` and `prev` are not part of it. |
| `recorded_at` | UTC time of the verdict, to the second, by the host's clock. |
| `tool` | The validator's name (`urml-validator`) and version. |
| `surface` | The entry point that made the verdict: `validate`, `execute`, `run`, `translate`, `runtime`, `mcp` or `action_server`, or `api` for a record your own code builds with `build_record`. |
| `stage` | `validation` for an entry point's own check, `revalidation` for the runtime's check before its first adapter call, `bridge` for the LLM bridge's final verdict. |
| `verdict` | `accepted` or `refused`. |
| `robot_id` | The manifest's `robot_id`. |
| `program` | The program as judged. For a bridge verdict it is the model's final emission as the bridge parsed it, before `urml translate` and `urml run` copy the request into its `description`. Null only for a bridge refusal from a `urml-llm-bridge` too old to attach the parsed program; such a record cannot be replayed. |
| `program_digest` | Content digest of `program`. |
| `manifest_digest` | Content digest of the manifest. |
| `envelope_digest` | Content digest of the envelope, or null when there was none. |
| `policy` | `none` (the compliance pass was off), `default` (the bundled US-federal policy), or the content digest of a policy file. |
| `rulebooks` | The operator's rulebooks in the order they applied, each as its `rulebook_id` and content digest. The bundled rulebooks are not listed. |
| `default_rulebooks` | Whether the bundled rulebooks applied. |
| `as_of` | The date rulebook effective dates were judged against, when the entry point fixed one (`execute`, `run`, the runtime, the MCP execute tool, the action server's own check). Null means the validator used the current UTC date, which is the date in `recorded_at`. |
| `profiles` | The profiles the program was judged under. |
| `codes` | The error codes, in the order the validator emitted them. Empty for an acceptance. |
| `warning_codes` | The warning codes, in order. |
| `result` | The full verdict as `urml validate --json` prints it, with each error's path, message and suggestion. |
| `request` | The natural-language request, for a bridge verdict. Null otherwise. |
| `attempts` | How many emissions the bridge validated. Bridge verdicts only. |
| `attempt_codes` | The sorted error codes of each bridge attempt, in order. The last entry belongs to the final verdict, and an accepted attempt has none. Bridge verdicts only. |
| `seq` | Format 2. The line's number in the file, counting every line from 1. |
| `prev` | Format 2. `sha256:` over the bytes of the line before this one, without its newline. Null on the first line of a file. |

A content digest is `sha256:` over canonical JSON (sorted keys, no whitespace), so the same content hashes the same whether it came from a YAML file, a JSON file or memory, however the file is formatted.

## Execution record fields

An execution record says what the runtime sent to the adapter and what the adapter reported back. It does not say what the robot physically did. An adapter can report success for a motion that slipped, stalled or never happened, and URML cannot see the difference. A run on the mock adapter writes the same kind of record as a run on a robot; the record does not name the adapter.

| Field | Meaning |
|---|---|
| `format` | `urml.execution-record/1`. |
| `record_id` | `sha256:` over the program digest, the manifest digest, the outcome and the steps without their durations. `recorded_at`, `seq` and `prev` are not part of it. |
| `recorded_at` | UTC time the run ended and the record was written, to the second, by the host's clock. |
| `tool` | The runtime's package name (`urml-ros2-runtime`) and version. |
| `surface` | The entry point that called the runtime: `execute`, `run`, `mcp` or `action_server`. `runtime` when the runtime was not told, as when your own code drives it. |
| `robot_id` | The manifest's `robot_id`. |
| `program_digest` | Content digest of the program that ran. An accepted validation record earlier in the same log carries the same one. |
| `manifest_digest` | Content digest of the manifest. |
| `envelope_digest` | Content digest of the envelope, or null when there was none. |
| `outcome` | `completed` when the runtime reported success. `failed` when it reported failure or the run raised. |
| `steps_executed` | How many dispatched steps the adapter answered. It is the number the runtime's result reports. |
| `steps` | Every step dispatched, in order. Each has `path` (where the step sits in the program, written as validation errors write paths), `primitive`, `outcome` (`ok` or `failed`), `error` (set when the step failed: the adapter's reason, or the exception it raised), and `duration_s` (seconds from dispatch to answer, to the millisecond). |
| `error` | Why the run failed: the last outcome's reason, or the exception. Null for a completed run. |
| `seq`, `prev` | As in a validation record. |

A step inside a `retry` appears once for each attempt, with the same path. A run can complete with a failed step in its list, when the program's `on_error` let it carry on. A step the envelope shield stopped before dispatch is not in the list, since nothing was sent, and the shield's reason is the run's `error`.

## The chain

`seq` is a line's number in the file. `prev` is the digest of the bytes of the line before it. A reader that holds line N can check line N - 1 byte for byte, and from there back to the first line.

The writer takes an exclusive lock on the file for each line, so two commands, two threads, or a server and a command can share one log. Under the lock it reads the last line, writes the new one, and calls `fsync` before it lets go. It waits up to ten seconds for the lock. A log that cannot be locked or written is the same error as any other log that cannot be written.

The log has to be a regular file on a file system that can lock one. A pipe or a device cannot hold a chain, because the writer reads the line before the one it writes.

A log begun by urml-validator 0.5.3 or older holds format 1 lines, with no `seq` and no `prev`. A newer version continues the same file. The chain starts at the first format 2 line, whose `seq` is its line number and whose `prev` is the digest of the format 1 line before it. The format 1 lines are not rewritten. They are covered by their number, and the last of them by its digest. Do not let an older version write to a log after a newer one has: its lines carry no `seq`, and the check reports each of them.

## Check a log

```bash
urml evidence log evidence.jsonl
```

```text
Evidence log: evidence.jsonl
  records: 3 on 3 lines (2 validation, 1 execution)
  chain:   starts at line 1
  intact:  yes
  head:    seq 3 sha256:a482585fd5c66db7123bc97a2cffd9266fcd5b488f6f020352f6bd76aada3b80
  note:    an intact chain cannot show a cut-off end or a file rewritten as a whole; compare the head with one noted somewhere else
```

The command reads the file and changes nothing. It exits 0 when it found no break, 1 when it found one, and 2 when it cannot read the file. The head is the last line's `seq` and digest.

On a break it names the line. With line 2 of the example removed:

```text
  intact:  no, 2 problems
    line 2: seq is 3, expected 2
    line 2: prev is sha256:88dc48fc3455dab735b5c620c281c9e7d5fd4e0d63ad8457772b672835fcc502, but line 1 hashes to sha256:9e74b37133876a2b1db2e4149c0bd512babeeb82af726068725e241bdcf25d09
```

A file that holds only format 1 lines has no chain. The command says so, checks that every line is a record, and exits 0.

Check a log while nothing is writing to it, or check a copy. A line that is half written at the moment the check reads it is reported as not a record.

From Python, `verify_log(path)` in `urml_validator.evidence` returns the same facts: `lines`, `records`, `validation_records`, `execution_records`, `chain_start`, `intact`, `problems`, `problem_count`, `head_seq` and `head_digest`.

## What the chain shows and what it does not

The chain shows a removed line, an edited line and lines in another order, to anyone who holds a later line or the head digest. Remove a line and the next line's `seq` is one too high. Edit a line and the next line's `prev` no longer matches it. The check names the line where the file stops agreeing with itself.

It does not stop someone who rewrites the whole file. The chain holds no secret. Whoever can write the file can drop a record, compute every `seq` and `prev` again, and get a file that checks. What exposes a rewrite is a head noted somewhere that person cannot reach.

It does not show that the end was cut off. A file that lost its last ten lines is a shorter file that checks. The last line is in the same position: no later line holds its digest, so an edit to it shows only in the head.

So note the head somewhere else, at an interval that suits the deployment: a ticket, a second machine, a shift report. A noted head is checked against a later log like this. If the log still ends at that `seq`, its head is the noted one. If it has grown and is intact, the line after it carries the noted digest as its `prev`:

```bash
grep -c '"prev":"sha256:88dc48fc3455dab735b5c620c281c9e7d5fd4e0d63ad8457772b672835fcc502"' evidence.jsonl
```

That prints 1 for the example, where the noted head was line 2.

The time in `recorded_at` is the host's clock. Nothing checks it against another clock, so it is as right as that machine's time was.

Keeping the file is the operator's job. URML appends to it and never deletes, rotates or copies it. Some rules ask for records like these to be kept for a year, or for five: plan the storage, the backups and who can reach them as for any other record of that kind. To start a new file, move the old one while nothing is writing to it and note its head. The next record starts a new chain at `seq` 1.

## Privacy

The log is off unless the operator names a file. URML writes records to that path and sends nothing anywhere. There is no telemetry.

A validation record holds the command being judged: the program, and for a bridge verdict the natural-language request, because they are what the gate decided about. If a deployment's requests can hold something you do not want kept, leave the log off there, or treat the file like any other log that holds user input.

A record adds no user name, host name, network address or account. The manifest, envelope, policy and rulebooks appear only as digests, and `robot_id` is the identifier the manifest gives the robot. The `result` field is the validator's report exactly as printed, so it carries what the validator reports. One case names a local file: when a policy's HBOM content rule (RFC-0005) cannot find the HBOM file, the error's `detail.resolved` holds the absolute path it looked for.

An execution record holds no program and no request. It holds digests, step paths, primitive names, outcomes and durations. A failed step's `error` is the adapter's own text, or the text of the exception it raised, so it can name what that text names, for example an address the adapter could not reach.

## Read and replay

```python
import yaml
from urml_validator.evidence import read_records, reverify

def load(path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)

record = read_records("evidence.jsonl")[0]
check = reverify(
    record,
    manifest=load("red-mug.manifest.yaml"),
    envelope=load("red-mug.envelope.yaml"),
    policy=None,
)
print(check.reproduced, check.problems)
```

`read_records` returns every validation record in the file, format 1 and format 2, in order, and skips execution records. `read_log` returns both kinds. Each raises `ValueError` naming the first line that is not a record. Neither checks the chain: `verify_log` does that.

`reverify` runs the validator again on the recorded program and compares the verdict and the error codes. The inputs you pass must hash to the digests in the record: `policy=None` for `none`, `"DEFAULT"` for `default`, the parsed policy file for a digest, and the operator's rulebooks in their original order. When an input differs, the record does not reproduce and `problems` names the input. A policy with HBOM content rules (RFC-0005) reads files next to the manifest, so pass `manifest_base_dir` for those.

## The registry

The URML registry (`registry/`) re-verifies committed records with `reverify`, to show that a listed robot's recorded verdicts still reproduce under the current validator. A record there shows what one version of the validator decided about one program under one set of declared inputs, and nothing about the robot beyond that.

The files committed there are format 1 and stay as they are. Each entry pins its file's sha256, and a format 1 file reads and replays as it did.
