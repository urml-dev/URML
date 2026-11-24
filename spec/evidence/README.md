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

# The evidence report

This directory holds the format of the evidence report, proposed by [RFC-0707](../../docs/rfcs/0707-evidence-report.md). It is a Draft: it becomes normative when RFC-0707 is accepted. The reference validator implements it as `urml evidence build`.

An evidence report describes one robot deployment: what URML checks before a program runs, what is only declared, what the runtime must enforce, what is missing, and what URML cannot see. It is not a safety assessment, a certification or a compliance determination, and every report says so in its `notice`.

## Files

| File | What it is |
|---|---|
| [`v0.1.0/report.schema.json`](v0.1.0/report.schema.json) | JSON Schema (draft 2020-12) of the report, format `urml.evidence-report/0.1` |

## Statuses

Every item carries exactly one status.

| Status | Meaning |
|---|---|
| `checked` | The validator checks this before a program runs. An item judged without a program also carries `result`: `pass` or `fail`. |
| `declared` | Someone states this, and the report records who. URML does not verify it. |
| `runtime` | The runtime must enforce this while a program runs. No static check covers it. |
| `missing` | Something a rule, the policy or the envelope needs is absent. |
| `outside` | URML cannot see this. Someone else must cover it. |

## Rules a producer follows

1. **Sections**, in this order: `robot`, `provenance`, `envelope`, `rules`, `programs`, `conformance`, `outside`. Every section is present. One with no items carries a `note` saying why, for example that no program was given. The `outside` section always opens with the same five items: safety-related control, what lies below the substrate, the physical site, the truth of declarations, and paths that do not pass through a URML runtime.
2. **Provenance.** Without a provenance block in the manifest, the policy's provenance rules have nothing to judge. They are not listed as passed; the `provenance.absent` item names them instead.
3. **Programs.** Each program given is validated against the deployment's own manifest, envelope, policy and rulebooks, on the report's `as_of` date. It is a `checked` item whose `result` is `pass` when the validator accepts it and `fail` when it refuses it, with every issue in its detail.
4. **Conformance.** A conformance report and a registry entry are what their authors state, so their items are `declared`. A run against the hermetic mock adapter, a filtered run, a failed fixture, a profile the run or the claim does not cover, an expired certification, a withdrawn entry and a report the entry does not pin are each `missing`.
5. **By standard.** Every item that carries a cite is grouped under each standard its cite names in `standard`, or, without that field, under the cite text up to the clause. Items without a cite are not grouped.
6. **Counts.** `gaps` is the number of `missing` items plus the number of `checked` items whose `result` is `fail`. There is no score, no grade and no overall verdict.
7. **Determinism.** The same inputs, `as_of` date and producer version give the same bytes: keys sorted, two-space indent, one trailing newline, no wall-clock time, host, user or absolute path. Input digests are `sha256` over canonical JSON (sorted keys, no whitespace), as in validation records, so a YAML file and its JSON equivalent hash alike.

## Not yet in this version

## Redaction

A redacted copy carries a `redaction` block: `removed`, the paths of the values it removed, and `full_report_sha256`, the sha256 of the full report's canonical JSON. A producer replaces every geofence and zone vertex list, every altitude band and every validator message on a program with the marker `[redacted]`, never with a hash of the value. Everything else stays, so the copy's statuses, results, counts and by-standard groups equal the full report's.

## Signatures

A signed report is the JSON file plus an OpenSSH signature of its exact bytes (SSHSIG, namespace `evidence-report@urml.dev`, Ed25519 key, plain or FIDO). A verifier accepts it only from a key in its allowed-signers file that is valid on the report's `as_of` date. See [`docs/evidence/signing.md`](../../docs/evidence/signing.md).

## Human forms

`urml evidence build --format md` and `--format html` render the JSON report for people. They are not normative and add nothing the JSON lacks: each opens with the notice, and each carries every item's id, status and text, every cited standard and every input digest. The HTML is one static file with inline styles, no scripts and no external requests, so it opens offline and can be attached to an audit file. Only the JSON is meant to be signed.
