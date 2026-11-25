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

# Submitting to the URML registry

This page is for anyone who wants a robot listed in the [URML registry](../../registry/README.md): a robot maker, a runtime author, or a user with a recorded run. URML is in Phase 1 and takes outside contributions ([CONTRIBUTING.md](../../CONTRIBUTING.md)). A submission is one pull request that adds one entry file and one evidence folder.

Read [TRADEMARK.md](../../TRADEMARK.md) first. A listing grants no mark. You may call a runtime "URML-compatible" only if it passes the unmodified, current public conformance suite, and "URML-Certified" only once the entry is certified ([Applying for URML-Certified](#applying-for-urml-certified), below).

## What an entry needs

A capability manifest for the robot, committed in this repository. If it is not already under `examples/`, put it in the entry's evidence folder.

At least one piece of evidence: a recorded run with public sources (`hardware_run` or `simulation_run`), validation records, or a conformance report produced with your runtime's own adapter. The [registry README](../../registry/README.md) explains each kind and what the checker verifies.

Limits: at least one sentence on what your evidence does not show. Every entry has them. A reader trusts an entry that says where it stops.

## Step by step

### 1. Fork and branch

Fork `urml-dev/URML` and create a branch. Pick an id: lowercase words joined by hyphens, naming the robot and the runtime (`acme-rover-ros2`). The id is the entry's file name.

### 2. Add the evidence folder

Create `registry/evidence/<id>/` with what your entry points at: the manifest (unless it is already in the repository), any envelope, policy or rulebook your validation records use, `validation-records.jsonl`, and `conformance-report.json` if you claim the self-reported tier.

### 3. Run the conformance suite against your own adapter (optional)

Skip this step unless you claim the self-reported URML-compatible tier. The report must come from your runtime's own adapter; a report from the built-in mock describes the mock, and the checker refuses it.

```bash
pip install -e reference/validator -e reference/ros2-runtime -e conformance
urml conformance run --adapter your_pkg.substrate:YourAdapter --profile <profile> \
    --output registry/evidence/<id>/conformance-report.json
```

`python -m urml_conformance --adapter your_pkg.substrate:YourAdapter --profile <profile> --report <path>` writes the same report. A claim covers a whole profile: `--profile` (repeatable) runs every fixture that lists that profile, wherever it lives in the suite, and the checker refuses a claim whose report skips any of them. A runtime that serves only part of a profile (a flight controller with no camera, for example) does not claim that profile; it lists recorded runs as field evidence instead, as the PX4 entry does. The report records the profiles, the number of fixtures, and a sha256 over the fixture files. Do not edit the report or the fixtures. The checker requires `all_passed: true`, your `runtime.adapter` as the report's adapter, and the urml-conformance version of this repository.

### 4. Produce validation records (optional)

Validate the programs you ran on the robot, plus a few refusal cases a reader grasps at once (an altitude above the manifest ceiling, a speed above the declared maximum, a primitive the robot does not declare), against the listed manifest:

```bash
urml validate program.urml.yaml -m registry/evidence/<id>/robot.manifest.yaml \
    --profile <profile> --no-policy --evidence-log registry/evidence/<id>/validation-records.jsonl
```

Use the same manifest, envelope, policy and rulebooks the entry's `validation_records.inputs` declare; the [registry README](../../registry/README.md#validation-records) shows the Python calls as well. The checker replays every record, so a record is evidence only while it still reproduces.

### 5. Write the entry

Create `registry/entries/<id>.yaml`. Quote every date, or YAML reads it as a date object and the checker refuses it.

```yaml
registry_version: "1"
id: acme-rover-ros2
title: Acme Rover through the Acme URML runtime
status: listed
listed: "2026-10-01"
last_verified: "2026-10-01"
submitted_by: Acme Robotics
robot:
  name: Acme Rover
  class: four-wheel ground robot
  maker: Acme Robotics
  manifest: registry/evidence/acme-rover-ros2/acme-rover.manifest.yaml
runtime:
  package: acme-urml-runtime
  version: "1.2.0"
  adapter: acme_urml.substrate:AcmeAdapter
  substrate: ROS 2 Jazzy with Nav2
profiles: [home]
compatibility:
  tier: self_reported
  profiles: [home]
  report:
    path: registry/evidence/acme-rover-ros2/conformance-report.json
    sha256: <sha256 of the report file>
field_evidence:
  - kind: hardware_run
    date: "2026-09-30"
    by: Acme Robotics
    summary: What ran, on which robot, and what happened, in the words of the sources.
    sources:
      - https://github.com/acme/rover/blob/v1.2.0/docs/urml-run.md
validation_records:
  path: registry/evidence/acme-rover-ros2/validation-records.jsonl
  sha256: <sha256 of the records file>
  summary: How and when the records were produced, and what they show.
  inputs:
    manifest: registry/evidence/acme-rover-ros2/acme-rover.manifest.yaml
    policy: none
limits:
  - What the evidence does not show.
```

`sha256` is the hex digest of the file's bytes: `sha256sum <file>` on Linux, `shasum -a 256 <file>` on macOS, `Get-FileHash <file>` in PowerShell (lowercase the result). Write names, never email addresses. Sources are repository paths or `https://` links a reader can open without an account; link a commit or a tagged release rather than a moving branch where you can. The schema is [`registry/entry.schema.json`](../../registry/entry.schema.json).

### 6. Check and export

```bash
python -m urml_conformance.registry check
python -m urml_conformance.registry export
```

`check` must print no problems. `export` rewrites `registry/registry.json`; commit it with your entry, because CI compares it with fresh output.

### 7. Open the pull request

Sign off every commit (`git commit -s`, the DCO), push, and open a pull request with the registry template: add `?template=registry-submission.md` to the new pull request URL. The template's acknowledgements are part of the review.

## What happens next

The `registry-check` workflow runs the checker and the registry tests on the pull request. The maintainer then reviews for completeness only: the check passes, the sources open and say what the summary says, the limits are stated, and the acknowledgements are ticked. The maintainer does not re-run your hardware, run your runtime, or judge your robot.

## Applying for URML-Certified

Certification follows [RFC-0705](../rfcs/0705-urml-certified.md) and is a paid certification run ([RFC-0708](../rfcs/0708-paid-certification.md), [COMMERCIAL.md](../../COMMERCIAL.md#urml-certified-runtime-makers)). It needs everything the self-reported tier needs (step 3), plus:

- `runtime.package` is a distribution anyone can install and `runtime.version` is one exact release. The URML project's own `urml-*` runtimes cannot be certified.
- In the entry, set `compatibility.tier: certified` and add a `certification` block with `conformance_spec: "0.2.3"` and an `attestation`: your statement that the runtime meets the six clauses of the [conformance contract](../../spec/conformance/v0.2.3.md), in particular that no path actuates without validation. Leave `certified_on`, `expires` and `reproduction` to the Licensor.
- Email sales@urml.dev for a quote for the run (free for a non-commercial runtime: one not sold, not licensed for a fee and not part of a paid product or service), then open the pull request and say in it that you are applying for URML-Certified.

The Licensor then installs that exact version from its public source in a clean environment, turns the network off, runs the same suite with your adapter, and commits the reproduction report and the dates to your pull request. The run is public code, `python -m urml_conformance.reproduce registry/entries/<id>.yaml`, so you can run it yourself first and see exactly what the Licensor will see:

```yaml
compatibility:
  tier: certified
  profiles: [home]
  report:
    path: registry/evidence/acme-rover-ros2/conformance-report.json
    sha256: <sha256 of your report>
  certification:
    conformance_spec: "0.2.3"
    certified_on: "2026-12-01"
    expires: "2027-12-01"
    attestation: The runtime meets the six clauses of the conformance contract; nothing actuates without validation.
    reproduction:
      report:
        path: registry/evidence/acme-rover-ros2/reproduction-report.json
        sha256: <sha256 of the reproduction>
      by: Yahalomik Ltd. (URML Licensor)
      date: "2026-11-30"
      environment: acme-urml-runtime 1.2.0 from PyPI, Python 3.12 on Linux, network off after install.
```

When the registry check passes, the pull request merges and the entry is certified. Requests are run in the order they are paid or waived. The fee pays for the run, never for the result: a run that fails keeps its fee and the entry stays self-reported. The certification lasts at most 366 days and ends earlier at the next urml-conformance release. Renew it with a new self-report and reproduction. Free text in an entry never says "certified": the `tier` field says it.

## Keeping an entry current

Re-verify when URML releases a new version. A release can change a validator verdict, which makes a record stop reproducing, and it moves the urml-conformance version, which a compatibility report must match. Either one fails the check. Produce the records or the report again, update the pinned sha256 values and `last_verified`, run `export`, and open a pull request. If you cannot, withdraw the entry.

## Withdrawing an entry

Open a pull request that sets `status: withdrawn` and says why. No questions asked. A withdrawn entry stays in `registry.json` with that status, so links to it keep resolving and git keeps the history.

## If something goes wrong

Open an issue or start a thread in [GitHub Discussions](https://github.com/urml-dev/URML/discussions). The conformance suite and the checker are free to run for testing, so anyone can re-run them and settle a disagreement about what passes.
