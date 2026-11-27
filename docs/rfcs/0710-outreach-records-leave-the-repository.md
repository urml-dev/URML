---
rfc: 0710
title: Outreach and distribution records leave the repository
author: Ido Yahalomi
state: Accepted
created: 2026-11-27
updated: 2026-11-27
amends: RFC-0275 (withdrawn), CLAUDE.md, AGENTS.md
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

# RFC-0710: Outreach and distribution records leave the repository

Kind: Governance. This RFC changes what this repository contains. It changes no schema, no primitive, no validator behavior and no license term.

## Summary

Since May 2026 this repository has carried the working files of URML's outreach next to the specification: 597 request-for-comment documents addressed to other projects, 72 ledgers that recorded what was sent and what came back, post drafts, a dashboard, and the scripts and tests around them. This RFC moves all of it into a private archive kept by the Licensor.

The files stay in this repository's history. They are no longer in the tree a visitor reads. After the move `docs/rfcs/` holds 104 documents where it held 700, and every one of them is about URML.

## Motivation

The outreach RFCs were letters, not decisions. Each one proposed a mapping from URML to another project's adapter, manifest or API. None changed the specification, and most said so in a fixed sentence: "No spec change is proposed here". They sat in the directory that [RFC-0001](0001-rfc-process.md) defines as the decision history, where they outnumbered the decisions about six to one. A reader who wanted to know why a primitive exists had to step around 597 documents that decide nothing.

The record can no longer be followed. Those documents and the ledgers link to 571 threads in other projects' repositories. On 2026-11-27, 562 of them were looked up through the GitHub API, and all 562 returned Not Found. The other nine are organization-level discussions, which the API cannot look up. A public record that cannot be traced to its source has stopped doing the work of a public record.

Names on the project's own pages read as relationships. The demo directory was called `lighthouses` and described a "lighthouse program" of sixteen vendors. No vendor joined a program. [`TRADEMARK.md`](../../TRADEMARK.md) asks others not to imply "URML endorsement, sponsorship, or affiliation when none exists". The project owes the same care in the other direction, and it owes it before a certification mark is enforced ([RFC-0705](0705-urml-certified.md), [RFC-0708](0708-paid-certification.md)).

Who was contacted, and what they answered, is the Licensor's working data. Nobody needs it to learn, evaluate or implement URML.

## Proposal

### What leaves

| What | Where it was | Files |
|---|---|---|
| Outreach RFCs (539 indexed as Outreach, 58 never indexed) | `docs/rfcs/` | 597 |
| Outreach ledgers | `examples/lighthouses/outreach*.yaml` | 72 |
| Post drafts, founder notes and research notes | `examples/lighthouses/` | 79 |
| Distribution ledger and citability prompt panel | `examples/lighthouses/distribution.yaml`, `prompt-panel.yaml` | 2 |
| Outreach dashboard, its scripts and its dev requirements | `tools/outreach_app/`, seven scripts in `tools/scripts/`, two files in `tools/` | 25 |
| Tests of the ledgers and of those scripts | `conformance/tests/` | 4 |
| The ledger schema check and two scheduled jobs that polled outreach threads | `.github/workflows/` | 3 |
| Outreach planning pages | `docs/launch/` | 5 |
| **Total** | | **787** |

That is 787 of 2,538 tracked files and about 108,000 of 326,000 lines.

The archive is a private repository that keeps every file at the path it had here, so the dashboard and the scripts run there unchanged. It was taken from commit `6fd8f24`.

### What stays

Every Spec and Governance RFC stays. Thirty-three of them (in the range 0250 to 0285) were never listed in the index. The index lists them now, with the state their own header gives.

[RFC-0275](0275-outreach-ledger-schema-v2.md), the ledger schema, stays as a record. Its subject is no longer in this repository, so its state becomes Withdrawn and it carries a dated note.

The vendor-shaped manifests and their conformance fixtures stay. They are test inputs that the URML project wrote from public documentation.

The demo runner that exercises those fixtures stays under a new name. `examples/lighthouses/` becomes [`examples/vendor-manifests/`](../../examples/vendor-manifests/). The runner loses the column that read the ledger and the two entries that had no fixture behind them. Its README says in the first paragraph that no vendor named there has reviewed, supplied or endorsed the manifests.

Examples and runtimes that grew out of an exchange with another project stay, with the account of that exchange in their README.

The release playbooks for the MCP server and the agent skill stay. They describe how the project publishes its own packages.

### The RFC index

[`docs/rfcs/README.md`](README.md) drops the Outreach kind, the 539 Outreach rows and the per-wave commentary. It keeps one table, in number order, with two kinds: Spec and Governance. One paragraph says where the outreach RFCs went and why.

### Numbers are not reused

The numbers the outreach RFCs used, all between 0023 and 0697, stay retired. A new RFC takes the next number after the highest ever assigned. Reusing a number would make old citations point at the wrong document.

### References from documents that stay

A document that stays and links to a file that left keeps the reference as plain text. The same holds for a link to an outreach thread that no longer resolves. The sentences around those links are left as written: they record where an example or a spec change came from.

This touches 173 links in 88 files: 127 to removed files and 46 to threads. On 2026-11-27 the remaining documents carried links to 31 distinct threads on other projects. Thirty are issues or repository discussions; each was checked against the GitHub API and returned Not Found. One is an organization-level discussion, which the API cannot check, and it is treated the same.

Conformance fixtures are not edited. Their bytes are pinned by the suite hash that a certification run reproduces ([RFC-0705](0705-urml-certified.md)), so four industrial fixtures keep a description line that names the old program, and `fleet/06_engaged_partners_choreography_positive` keeps its name, until the next conformance release.

### Rules from now on

[`CLAUDE.md`](../../CLAUDE.md) and [`AGENTS.md`](../../AGENTS.md) state them:

- This repository holds no outreach state and no distribution state. No ledger, no post draft and no per-target request for comment is added here.
- An RFC is filed for a change to the specification or to governance. A proposal to another project is correspondence, and it lives with the Licensor's records.
- Contact with a maintainer or a company is one message at a time, sent by the founder. No batches. An AI assistant does not open or answer a thread on another project's tracker.
- A page of this project names a company as a partner, adopter or program member only when that company has agreed to it in writing.

### Public numbers that change

| Where | Before | After |
|---|---|---|
| README badge | "RFCs: 63 Spec + 630 Outreach" | removed |
| README, Status | "63 Spec RFCs are filed (8 accepted, 48 implemented, 6 draft, 1 open)" | "97 Spec RFCs are on `main` (9 accepted, 49 implemented, 38 draft, 1 open) and 6 Governance RFCs" |
| README, capability table | "24 primitives" | "28 primitives" (the 24, plus `drive` and `turn` from RFC-0630 and `look_at` and `gesture` from RFC-0698) |
| README, runtime row | brand lists with no statement of what a name means | the same lists, with one sentence: a name says which public driver, SDK or interface an adapter targets, and unless the table says otherwise no adapter has run on that hardware and no maker has reviewed or endorsed one |
| `docs/launch/claims-audit.md` | "Spec vs Outreach RFCs" paragraph, 693 documents; "24 primitives" | one paragraph on the two kinds that remain; "28 primitives" |
| `conformance/tests`, as measured | 1,210 tests, 443 of them checks of the outreach ledgers | 786 tests |
| `VIBE.md` | names "the outreach RFC log" and "~100 outreach RFCs" | names neither |
| Files in `docs/rfcs/` | 700 | 104 |

The Spec count moves from 63 to 97 for two reasons that have nothing to do with outreach: three Spec RFCs were filed after the README line was written, and 32 drafts that were never indexed are counted now. One indexed draft, RFC-0696, is on a branch and not on `main`; its row stays, without a link, and is not counted.

The primitive count was stale. The validator's list has 28 names. A 29th verb, `call_program`, has an executor but its RFC (0015) is still Open, so it stays out of the count as before.

The audit table in `claims-audit.md` is the 2026-09-28 measurement and is not re-transcribed here. A dated note under it records the conformance figure above.

## What is lost

The outreach RFCs held the longest written account of how URML's primitives map onto other stacks. A few of them are also the design record of a runtime that shipped: ArduPilot (0041), Boston Dynamics Spot (0043), Petoi (0062), Robotical Marty (0073), VDA 5050 (0297) and Project Chrono (0328). Each runtime's README, and its `SPEC-GAPS.md` where it has one, carries the mapping that shipped. The request-for-comment text does not stay.

The ledgers were public. Anyone could see what the outreach had reached and what it had not. That view closes. The project's measured state stays public in [`docs/launch/claims-audit.md`](../launch/claims-audit.md) and the [registry](../../registry/README.md).

Commitments made to maintainers in those threads stand. The list of them moves with the ledgers.

## Alternatives considered

- **Fix the index and leave the files.** The directory listing is what a visitor sees first, and 597 files would still fill it.
- **Move the outreach RFCs to another directory here.** They would still be on the project's public face, with links that do not resolve.
- **Delete without an archive.** The ledgers say who has been contacted already. Losing that invites writing to the same people twice.
- **Rewrite history so the files never existed.** It breaks every clone and every tag, and the aim is the tree a visitor reads, not secrecy. The history keeps the full record for anyone who wants it.
- **Keep the distribution ledger public, since it is not outreach.** It is the same kind of working state. One rule, no ledgers here, is easier to keep than two.
- **Rename the fixtures in the same change.** That changes the conformance suite and belongs to a conformance release.

## Prior art

- [PEP 1](https://peps.python.org/pep-0001/) sorts Python's proposals into Standards Track, Informational and Process. All three kinds are about Python.
- The [Rust RFC repository](https://github.com/rust-lang/rfcs) holds proposals for changes to Rust, Cargo, crates.io and the RFC process itself.

Neither keeps its correspondence with other projects in the proposal series.

## Implementation plan

In the pull request that carries this RFC:

- The 787 files listed above are removed from the tree.
- `docs/rfcs/README.md` is rebuilt as described, and gains this RFC's row.
- RFC-0275 gets its status note and the state Withdrawn.
- `examples/lighthouses/` becomes `examples/vendor-manifests/`, with a rewritten README, a runner without the ledger column, and a test that runs every listed fixture.
- Links to removed files and to threads that no longer resolve become plain text.
- `CLAUDE.md`, `AGENTS.md`, `README.md`, `VIBE.md`, `docs/launch/claims-audit.md`, `Makefile`, `.gitignore`, the MCP server's README and playbook, and two workflow comments are brought in line. `.gitignore` gains the old ledger paths, so a stale checkout cannot add them back by accident.
- `CHANGELOG.md` gains an entry under Unreleased. Entries for past releases keep their text; their links to removed files become plain text.

In a separate pull request to `urml-dev/urml-website`: the Partners page becomes a Directory page. It stops listing vendors under a program they did not join, says who wrote each entry, and stops linking to documents that are no longer in this repository.

Outside both pull requests, the Licensor stops the scheduled jobs that read the ledgers or wrote to them.

## Regulatory alignment

None changes.

## Open questions

1. **Fixture names.** Four fixture descriptions and one fixture name still carry the old wording. They change in the next conformance release.
2. **Named people.** About thirty files that stay credit a design input to a named maintainer of another project, in a thread that can no longer be read. The text is left as written. Whether to keep the names is the maintainer's call.
3. **Runtime design notes.** If the mapping tables for the six runtimes named above should be public, each belongs in that runtime's own documentation, written as a design note.
4. **The newly indexed drafts.** At least two of them, RFC-0250 and RFC-0251, are implemented in the validator while their headers say Draft. The rest were never reviewed. A later RFC should mark each one implemented, or withdraw it.

## Process note

`CLAUDE.md` and `AGENTS.md` say that a substantive change to them needs an RFC. This is that RFC.

Like RFC-0703, RFC-0704, RFC-0708 and RFC-0709, this RFC is accepted on merge, without the seven-day comment window RFC-0001 sets. The maintainer may hold the merge for that window.
