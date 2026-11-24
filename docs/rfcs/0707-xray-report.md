---
rfc: 0707
title: The X-ray report, one reproducible picture of a robot deployment
author: Ido Yahalomi (ido@beamdesk.space)
state: Draft
created: 2026-11-24
updated: 2026-11-24
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

# RFC-0707: The X-ray report, one reproducible picture of a robot deployment

Kind: Spec (tooling). This RFC adds a report format and one CLI command, `urml xray`. It changes no layer, no primitive and no validation rule. Everything the report says, the validator already knows; the RFC puts it in one place, in a fixed vocabulary, so that a reader who did not build the robot can see what was checked, what was only declared, and what URML cannot see at all.

## Summary

`urml xray` reads the files that describe one robot deployment (the capability manifest, the safety envelope, the compliance policy, the rulebooks and their declarations, and optionally a set of programs and a conformance report) and writes one report. The report has a JSON form, fixed by a schema and byte-for-byte deterministic, and a human form rendered from it.

Every item in the report carries one status from a closed list:

| Status | Meaning |
|---|---|
| `checked` | The validator checks this before a program runs. The report names the check and, where programs were given, the result. |
| `declared` | Someone states this and URML records who, on what basis, and with what evidence reference. URML does not verify it. |
| `runtime` | The runtime must enforce this while the program runs. No static check covers it. |
| `missing` | Something a loaded rule, policy or the envelope requires is absent. |
| `outside` | URML cannot see this. It is listed so the reader knows to look elsewhere. |

The report gives no verdict, no score and no pass mark. It never says "safe" or "compliant". It says what is known about a deployment and how it is known.

## Motivation

A robot deployment is described today by a manifest, an envelope, a policy file, rulebooks and declarations, conformance reports and validation output. Each is precise. Together they are hard to read: an auditor, a buyer or an insurer has to know URML to find out what the validator enforces for this robot and what it leaves to someone else.

Three readers need that picture and cannot get it now.

**The integrator before commissioning.** They want one document that lists every limit in force, every rule loaded, every declaration on record, and every gap, before the robot moves on site.

**A certification body or auditor.** TÜV, UL, exida and similar bodies certify safety. URML does not and will not ([`docs/safety/iec-61508.md`](../safety/iec-61508.md), [RFC-0705](0705-urml-certified.md)). What URML can do is hand those bodies evidence in a form they can check: what the intent layer refuses, cited to the standard each rule came from, and a plain list of what it leaves to the safety-related control. The body stays the certifier; the report is one input to its work.

**A buyer or procurement officer.** They want the robot's declared provenance against the policy in force (NDAA Section 889, the FCC Covered List), the conformance tier of its runtime, and whether the maker's claims carry evidence ([RFC-0631](0631-capability-evidence-traceability.md)), without reading YAML.

There is a fourth reason, about URML itself. The project has said in many places what URML is not: not a safety function, not a certifier, not a compliance determination. Those statements are scattered across documents a reader may never open. A report that always prints its own blind spots puts the limit next to the claim, every time.

## Proposal

### The command

```bash
urml xray --manifest robot.manifest.yaml \
          --envelope site.envelope.yaml \
          [--policy PATH | --no-policy] \
          [--rulebook PATH]... [--no-default-rulebooks] \
          [--program PATH]... \
          [--conformance-report PATH] \
          --as-of 2026-11-24 \
          [--format json|md|html] [--out PATH]
```

Input flags mean exactly what they mean for `urml validate`, so a deployment's X-ray uses the same files its validation does. `--as-of` is required: the report states the date it describes, and expiry checks (conformance, certification, rulebook review dates) use that date, never the clock. The command runs offline, reads only the files it is given, and sends nothing anywhere.

Exit codes: `0` when the report was written and nothing is `missing` and no given program was refused; `2` when the report was written and at least one item is `missing` or one program was refused; `1` when the report could not be built (an input failed to load). The report is written in both of the first two cases. A CI job can gate on `2` without parsing the report.

### The report

The JSON report has these sections, in this order. Each section is a list of items; each item has an `id`, a `status` from the table above, a human `text`, and a `source` naming the input file and the field it came from.

1. **Inputs.** Every input file with its sha256, the URML spec versions in force, the validator package and version, the policy id, the loaded rulebook ids, and the `--as-of` date. Anyone holding the same files can rebuild the report and compare hashes.

2. **Robot.** From the manifest: identity, profiles, `manifest_attestation`, and one item per capability. A capability's status is `checked` when the validator uses it to refuse programs (a joint limit, a payload, a reach), and its RFC-0631 evidence tag (`inferred`, `declared`, `derived`, `verified`) and reference are printed beside it. A capability with no evidence tag says so.

3. **Provenance.** The compliance policy's result for the manifest and its hardware bill of materials: each component, its declared origin, and the policy rule that accepted or refused it. Origins are `declared`; the policy check over them is `checked`. With `--no-policy`, the section says the policy was off and lists nothing as checked.

4. **Envelope.** One item per limit in the envelope, with its status taken from the split [RFC-0701](0701-envelope-completeness.md) already makes: a static check is `checked`, a runtime obligation is `runtime`. A limit the envelope leaves unset is shown with what the validator uses instead: the manifest's value (`checked` against that) or nothing, which is `missing`. This section is the deployment-specific view of [`docs/safety/envelope-coverage.md`](../safety/envelope-coverage.md).

5. **Rules.** One item per rule in each loaded rulebook ([RFC-0702](0702-rulebooks.md)): its kind, its `cite`, and its status (`checked` for every rule kind the validator enforces). Each `require_declared` rule shows the declared value, the deployment rulebook it came from and its issuer, as `declared`, or `missing` when absent or not in the allowed list. Each obligation is `outside`, with its cite. Exceptions are listed with their cited basis.

6. **By standard.** The same rules and obligations regrouped by the standard their `cite` names (ISO 10218-1:2025, ISO 3691-4:2023, IEC 61508:2010, 14 CFR Part 107, and so on). For each standard: rules checked, declarations on record, obligations outside URML. The grouping key is the cite text up to the clause, so it works for any rulebook, including ones this repository has never seen. This is the view a certification body reads first.

7. **Programs.** When `--program` is given, one item per program: accepted or refused, and every issue the validator raised, with its code and the rule or limit behind it. Without programs, the section says none were given; the rest of the report stands without it.

8. **Conformance.** When `--conformance-report` is given: the runtime package and exact version, the report's sha256, the profiles covered, and the registry tier (`self-reported` or `certified`, [RFC-0705](0705-urml-certified.md)) with its expiry against `--as-of`. A report from the mock adapter is shown and marked as such.

9. **Outside URML.** Always present, always the same opening items, whatever the inputs:
   - the robot's safety-related control and its safety functions (stops, monitoring, limiting), designed and validated outside URML;
   - firmware, controllers and drivers below the substrate;
   - wiring, guarding and the physical site;
   - whether any `declared` item is true;
   - anything a program does through a substrate path that does not pass through a URML runtime.

   Then every rulebook obligation and every `runtime` item again, so the list of what someone else must cover is complete in one place.

10. **Counts.** Items per status, per section. Counts only: no ratio, no grade.

The human form (`md` or `html`) renders the same sections from the JSON and adds nothing the JSON lacks. The HTML is one static file with inline styles and no scripts, generated by Python's standard library, so it opens offline and can be attached to an audit file. Every page of it carries the same one-line header: "An X-ray of declared intent and its checks. Not a safety assessment, a certification or a compliance determination."

### Determinism and reproduction

Same inputs, same `--as-of`, same validator version: byte-identical JSON. Lists are sorted by a stated key, floats are printed in one fixed form, and no wall-clock time, hostname, user name or absolute path enters the report. A reader who wants to trust a report does not trust its author: they rerun `urml xray` on the same files and compare the sha256. This is the trust model [RFC-0705](0705-urml-certified.md) already uses for certification reproduction, applied to one deployment.

### What is normative

The report schema (`spec/xray/v0.1.0/report.schema.json`) and the status vocabulary are normative: another tool may produce an X-ray report, and it is a URML X-ray report when it validates against the schema and assigns statuses by the rules above. The CLI flags and the human rendering are not normative.

### Naming

"X-ray" is a picture, not a finding. The name is chosen to avoid regulated words: "inspection" is what accredited inspection bodies do under ISO/IEC 17020, "certification" is what certification bodies do under ISO/IEC 17065, and "audit" implies an independent auditor. The command does none of those, and its name should not suggest it does.

## Alternatives considered

**A score or grade.** A single number travels well and is what OpenSSF Scorecard does for repositories. Rejected: a score turns "this many things were declared and not verified" into "8.2 out of 10", which a reader will take as a safety rating. Counts per status give the same overview without the implication.

**An overall pass or fail.** Rejected for the same reason. The exit code distinguishes "something required is missing" from "nothing required is missing", which is a fact about the files, not a judgment about the robot.

**URML as the certifier.** Considered and rejected in the discussion that led to this RFC. Safety certification needs accreditation, carries liability one Licensor cannot hold, and would mean the Licensor certifying against its own standard while selling licenses for it. URML-Certified stays a conformance mark; the X-ray stays evidence.

**URML as the holder of the standards' content.** A complete machine-readable library of ISO and IEC requirements would make the report richer. The text and values are copyrighted, and the templates carry none of them for that reason. Public law (US federal regulation) can be encoded in full, as the bundled FAA Part 107 rulebook is. Licensed content from a standards body remains possible later, by agreement, without changing this format: a licensed rulebook is a rulebook.

**Extending `urml validate --json`.** The validator's output answers "may this program run?". The X-ray answers "what is known about this deployment?", which holds without any program. Folding the second into the first would make the validator's output larger for every caller who only wants the first answer.

**A hosted dashboard.** Out of scope for this repository: hosted services live outside it and reference runtimes take no cloud dependency. A hosted product can read the same JSON later.

## Prior art

- **Software bills of materials** (SPDX, CycloneDX): a machine-readable inventory, produced by tools, read by buyers. The X-ray's provenance section plays the same role for a robot's components.
- **SLSA provenance and reproducible builds**: trust by reproduction, not by the producer's word.
- **Compliance as code** (Chef InSpec, Open Policy Agent): rules in files, a report of which rules a system meets, each with its source control or regulation.
- **Safety cases** (UL 4600 for autonomous products, Goal Structuring Notation): an argument with evidence for each claim. The X-ray is not a safety case; it is evidence a safety case can cite, with each item's status saying how strong it is.
- **Lighthouse reports** (web performance): one command, one self-contained HTML file, every finding linked to its rule. The X-ray borrows the shape and drops the score.

## Licensing and commercial fit

`urml xray` ships in the validator package under the same terms as `urml validate` ([`LICENSING.md`](../../LICENSING.md)): free for evaluation, development, testing, research and teaching, with production use under a commercial license. The report format is part of the specification.

The paid fleet and vehicle validation services in [`COMMERCIAL.md`](../../COMMERCIAL.md#validation-services) gain a concrete deliverable: an X-ray report reproduced by the Licensor, with the reviewer's notes. That is a service, not a certification, and it says so.

## Implementation plan

1. **Schema and core sections.** `spec/xray/v0.1.0/report.schema.json`; `urml xray` producing JSON for Inputs, Robot, Provenance, Envelope, Rules, By standard, Outside URML and Counts. Golden reports for `examples/warehouse` and `examples/industrial/simple-pick-and-place` with each safety-standard template filled in, as the template tests already do. A determinism test runs the command twice and compares bytes, and a schema test validates every golden report.
2. **Programs and conformance.** The Programs and Conformance sections, reusing the registry checker for tier and expiry.
3. **Human form.** Markdown and static HTML rendered from the JSON with the standard library only. A test asserts that every item in the JSON appears in the rendering, so the human form cannot drop a finding.
4. **Example and docs.** `examples/xray/` with one committed, byte-asserted report and a README written for an auditor who has never seen URML. A section in `docs/safety/safety-model.md`.
5. **Website.** A page on urml.dev showing an example report, after steps 1 to 4 ship.

Each step lands with its tests. No step changes validation results.

## Open questions

1. **Signing.** Reproduction gives trust without keys. Should the Licensor's reviewed reports also be signed (Sigstore, or a plain detached signature), and with what key custody?
2. **Run-time evidence.** A later version could take audit trails and run reports ([RFC-0638](0638-execution-lifecycle-and-run-report.md)) and show what actually ran. Is that one report or a second one?
3. **Sensitive content.** A report names locations, zones and site layout. Is a `--redact` option for sharing outside the site worth its cost, or should the integrator share the report as they would the envelope itself?
4. **Grouping by standard.** Grouping on cite text is simple and works for any rulebook, but two rulebooks may spell one standard differently. Is a short normalization table needed, or a `standard` field on `cite`, which would be a rulebook format change?
5. **The name.** `xray` is short and clear in English. Does it read well in the other languages URML's natural-language layer supports, or is `urml evidence` better for an international audience?
