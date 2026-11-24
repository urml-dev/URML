---
rfc: 0707
title: The evidence report, one reproducible picture of a robot deployment
author: Ido Yahalomi (ido@beamdesk.space)
state: Draft
created: 2026-11-24
updated: 2026-11-24
supersedes: none
amends: RFC-0702 (an optional `standard` field on `cite`)
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

# RFC-0707: The evidence report, one reproducible picture of a robot deployment

Kind: Spec (tooling). This RFC adds a report format and one CLI command, `urml evidence`. It changes no layer, no primitive and no validation rule. Everything the report says, the validator already knows; the RFC puts it in one place, in a fixed vocabulary, so that a reader who did not build the robot can see, like an X-ray, what was checked, what was only declared, and what URML cannot see at all.

## Summary

`urml evidence` reads the files that describe one robot deployment (the capability manifest, the safety envelope, the compliance policy, the rulebooks and their declarations, and optionally a set of programs and a conformance report) and writes one report. The report has a JSON form, fixed by a schema and byte-for-byte deterministic, and a human form rendered from it.

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
urml evidence build --manifest robot.manifest.yaml \
                    --envelope site.envelope.yaml \
                    [--policy PATH | --no-policy] \
                    [--rulebook PATH]... [--no-default-rulebooks] \
                    [--program PATH]... \
                    [--conformance-report PATH] [--registry-entry PATH] \
                    --as-of 2026-11-24 \
                    [--redact] \
                    [--format json|md|html] [--out PATH]

urml evidence verify report.json report.json.sig
```

`build` writes a report; `verify` checks a signed one (see Signing).

Input flags mean exactly what they mean for `urml validate`, so a deployment's evidence report uses the same files its validation does. `--as-of` is required: the report states the date it describes, and expiry checks (conformance, certification, rulebook review dates) use that date, never the clock. The command runs offline, reads only the files it is given, and sends nothing anywhere.

Exit codes follow `urml validate`: `0` when the report was written and nothing is `missing` and no check failed; `1` when the report was written and at least one item is `missing` or one check failed (a policy rule a manifest breaks, or, once programs are added, a refused program); `2` when an input could not be read. The report is written in both of the first two cases. A CI job can gate on the exit code without parsing the report.

### The report

The JSON report has these sections, in this order. Each section is a list of items; each item has an `id`, a `status` from the table above, a human `text`, and a `source` naming the input file and the field it came from.

1. **Inputs.** Every input file with its sha256, the URML spec versions in force, the validator package and version, the policy id, the loaded rulebook ids, and the `--as-of` date. Anyone holding the same files can rebuild the report and compare hashes.

2. **Robot.** From the manifest: identity, profiles, `manifest_attestation`, and one item per capability. A capability's status is `checked` when the validator uses it to refuse programs (a joint limit, a payload, a reach), and its RFC-0631 evidence tag (`inferred`, `declared`, `derived`, `verified`) and reference are printed beside it. A capability with no evidence tag says so.

3. **Provenance.** The compliance policy's result for the manifest and its hardware bill of materials: each component, its declared origin, and the policy rule that accepted or refused it. Origins are `declared`; the policy check over them is `checked`. With `--no-policy`, the section says the policy was off and lists nothing as checked.

4. **Envelope.** One item per limit in the envelope, with its status taken from the split [RFC-0701](0701-envelope-completeness.md) already makes: a static check is `checked`, a runtime obligation is `runtime`. A limit the envelope leaves unset is shown with what the validator uses instead: the manifest's value (`checked` against that) or nothing, which is `missing`. This section is the deployment-specific view of [`docs/safety/envelope-coverage.md`](../safety/envelope-coverage.md).

5. **Rules.** One item per rule in each loaded rulebook ([RFC-0702](0702-rulebooks.md)): its kind, its `cite`, and its status (`checked` for every rule kind the validator enforces). Each `require_declared` rule shows the declared value, the deployment rulebook it came from and its issuer, as `declared`, or `missing` when absent or not in the allowed list. Each obligation is `outside`, with its cite. Exceptions are listed with their cited basis.

6. **By standard.** The same rules and obligations regrouped by the standard their `cite` names (ISO 10218-1:2025, ISO 3691-4:2023, IEC 61508:2010, 14 CFR Part 107, and so on). For each standard: rules checked, declarations on record, obligations outside URML. The grouping key is the cite's `standard` field (below) when it is present, and the cite text up to the clause when it is not, so the view works for any rulebook, including ones written before the field existed.

7. **Programs.** When `--program` is given, one item per program: accepted or refused, and every issue the validator raised, with its code and the rule or limit behind it. Without programs, the section says none were given; the rest of the report stands without it.

8. **Conformance.** When `--conformance-report` is given: the adapter it ran against, the fixture count and set, passes and failures. A run against the hermetic mock adapter, a filtered run, a failed fixture and a deployment profile the run did not select are each `missing`. When `--registry-entry` is given: the runtime package and exact version, the registry tier (`self_reported` or `certified`, [RFC-0705](0705-urml-certified.md)), a certification's expiry against `--as-of`, whether the entry pins the given report's sha256, and the profiles its claim covers. Both read through the `urml-conformance` package, so the evidence report applies the registry's own rules rather than a copy of them.

9. **Outside URML.** Always present, always the same opening items, whatever the inputs:
   - the robot's safety-related control and its safety functions (stops, monitoring, limiting), designed and validated outside URML;
   - firmware, controllers and drivers below the substrate;
   - wiring, guarding and the physical site;
   - whether any `declared` item is true;
   - anything a program does through a substrate path that does not pass through a URML runtime.

   Then every rulebook obligation and every `runtime` item again, so the list of what someone else must cover is complete in one place.

10. **Counts.** Items per status, per section. Counts only: no ratio, no grade.

The human form (`md` or `html`) renders the same sections from the JSON and adds nothing the JSON lacks. The HTML is one static file with inline styles and no scripts, generated by Python's standard library, so it opens offline and can be attached to an audit file. Every page of it carries the same one-line header: "Evidence of declared intent and its checks. Not a safety assessment, a certification or a compliance determination."

### Determinism and reproduction

Same inputs, same `--as-of`, same validator version: byte-identical JSON. Lists are sorted by a stated key, floats are printed in one fixed form, and no wall-clock time, hostname, user name or absolute path enters the report. A reader who wants to trust a report does not trust its author: they rerun `urml evidence build` on the same files and compare the sha256. This is the trust model [RFC-0705](0705-urml-certified.md) already uses for certification reproduction, applied to one deployment.

### A `standard` field on rulebook cites

This RFC amends the rulebook format ([RFC-0702](0702-rulebooks.md)) with one optional field. A `cite` keeps its free `text` and `url`, and may add `standard`: the identifier of the standard or regulation it comes from, with its edition, and nothing else.

```yaml
cite:
  text: "ISO 3691-4:2023, clause FILL_IN"
  standard: "ISO 3691-4:2023"
```

A cite that draws on more than one standard lists them:

```yaml
cite:
  text: "ISO 13849-1:2023, IEC 62061:2021 or IEC 61508:2010, clause FILL_IN"
  standard: ["ISO 13849-1:2023", "IEC 62061:2021", "IEC 61508:2010"]
```

The field changes no validation result. It exists so that two rulebooks naming one standard land in one group in the By standard section, whatever their `text` says. It is optional, so every existing rulebook stays valid; the bundled FAA rulebook and the safety-standard templates gain it in the same change that adds it to the schema.

### Redaction

A report names locations, zones, geofences and their coordinates: the layout of a site, which an operator may not want to hand to a buyer or an insurer. `--redact` writes a report fit to share outside the site. It is one flag with one behavior, not a menu:

- every coordinate, polygon, altitude band and frame transform is removed, and each removed value is replaced by its sha256;
- names (of locations, zones, rules, capabilities) stay, because without them the rules cannot be read;
- every status, rule, cite, declaration and count stays, so the redacted report says as much about what was checked as the full one;
- the report records `redacted: true`, the list of field paths it redacted, and the sha256 of the full report built from the same inputs.

Redaction is deterministic like the rest of the report. A recipient who is later shown the full report, under whatever agreement the parties have, can check that it matches the hash the redacted one carries.

### Signing

Anyone can build an evidence report, and a report anyone builds is trusted by reproduction, not by signature. A report the Licensor has reproduced and reviewed, as part of the paid validation services, is also signed, so that the recipient can tell it came from the Licensor without rerunning it.

- The signature is a detached Ed25519 signature over the exact bytes of the JSON report, in a file next to it (`report.json.sig`). The human forms are not signed; they are renderings of the JSON.
- The Licensor's public key is committed to this repository and published on urml.dev. Key rotation is recorded in the repository, with the old key kept so old signatures still verify.
- `urml evidence verify report.json report.json.sig` checks the signature offline, against the keys in the installed package. No network, no service, no account.
- A signature means one thing: the Licensor rebuilt this report from inputs with these hashes and reviewed it. It is not a certification and does not say the robot is safe or compliant. The signed report's first line says so, like every other report.
- Redacted and full reports are signed separately; each carries its own signature.

The private key is held by the Licensor on a hardware token and never enters CI. The choice of tool (OpenSSH signatures, minisign, or a small Ed25519 implementation in the validator) is an implementation detail, decided in step 4 of the plan, as long as verification needs nothing but the package.

### What actually ran is a second report

This report describes a deployment before anything runs. What a robot actually did (audit trails, run reports under [RFC-0638](0638-execution-lifecycle-and-run-report.md)) is a different question with different inputs, a different retention story and different readers. It gets its own report, in a later RFC, reusing this report's status vocabulary, determinism and signing rules so the two read alike.

### What is normative

The report schema (`spec/evidence/v0.1.0/report.schema.json`), the status vocabulary, the redaction rules and the signature format are normative: another tool may produce an evidence report, and it is a URML evidence report when it validates against the schema and assigns statuses by the rules above. The CLI flags and the human rendering are not normative.

### Naming

The command and the report are called **evidence**, because that is what they produce: evidence a certification body, a buyer or an integrator weighs, not a finding of their own. "X-ray" describes the idea in conversation, and the report's first line says what it is. The name avoids regulated words on purpose: "inspection" is what accredited inspection bodies do under ISO/IEC 17020, "certification" is what certification bodies do under ISO/IEC 17065, and "audit" implies an independent auditor. The command does none of those.

## Alternatives considered

**A score or grade.** A single number travels well and is what OpenSSF Scorecard does for repositories. Rejected: a score turns "this many things were declared and not verified" into "8.2 out of 10", which a reader will take as a safety rating. Counts per status give the same overview without the implication.

**An overall pass or fail.** Rejected for the same reason. The exit code distinguishes "something required is missing" from "nothing required is missing", which is a fact about the files, not a judgment about the robot.

**URML as the certifier.** Considered and rejected in the discussion that led to this RFC. Safety certification needs accreditation, carries liability one Licensor cannot hold, and would mean the Licensor certifying against its own standard while selling licenses for it. URML-Certified stays a conformance mark; the evidence report stays evidence.

**URML as the holder of the standards' content.** A complete machine-readable library of ISO and IEC requirements would make the report richer. The text and values are copyrighted, and the templates carry none of them for that reason. Public law (US federal regulation) can be encoded in full, as the bundled FAA Part 107 rulebook is. Licensed content from a standards body remains possible later, by agreement, without changing this format: a licensed rulebook is a rulebook.

**Extending `urml validate --json`.** The validator's output answers "may this program run?". The evidence report answers "what is known about this deployment?", which holds without any program. Folding the second into the first would make the validator's output larger for every caller who only wants the first answer.

**A hosted dashboard.** Out of scope for this repository: hosted services live outside it and reference runtimes take no cloud dependency. A hosted product can read the same JSON later.

## Prior art

- **Software bills of materials** (SPDX, CycloneDX): a machine-readable inventory, produced by tools, read by buyers. The report's provenance section plays the same role for a robot's components.
- **SLSA provenance and reproducible builds**: trust by reproduction, not by the producer's word.
- **Compliance as code** (Chef InSpec, Open Policy Agent): rules in files, a report of which rules a system meets, each with its source control or regulation.
- **Safety cases** (UL 4600 for autonomous products, Goal Structuring Notation): an argument with evidence for each claim. The evidence report is not a safety case; a safety case can cite it, and each item's status says how strong that evidence is.
- **Lighthouse reports** (web performance): one command, one self-contained HTML file, every finding linked to its rule. The evidence report borrows the shape and drops the score.

## Licensing and commercial fit

`urml evidence` ships in the validator package under the same terms as `urml validate` ([`LICENSING.md`](../../LICENSING.md)): free for evaluation, development, testing, research and teaching, with production use under a commercial license. The report format is part of the specification.

The paid fleet and vehicle validation services in [`COMMERCIAL.md`](../../COMMERCIAL.md#validation-services) gain a concrete deliverable: an evidence report reproduced by the Licensor, with the reviewer's notes, signed (see Signing). That is a service, not a certification, and it says so.

## Implementation plan

1. **Schema and core sections.** The optional `standard` field on `cite` in the rulebook schema and spec, filled in the bundled FAA rulebook and the safety-standard templates. `spec/evidence/v0.1.0/report.schema.json`; `urml evidence` producing JSON for Inputs, Robot, Provenance, Envelope, Rules, By standard, Outside URML and Counts. Golden reports for `examples/warehouse` and `examples/industrial/simple-pick-and-place` with each safety-standard template filled in, as the template tests already do. A determinism test runs the command twice and compares bytes, and a schema test validates every golden report.
2. **Programs and conformance.** The Programs and Conformance sections, reusing the registry checker for tier and expiry.
3. **Human form.** Markdown and static HTML rendered from the JSON with the standard library only. A test asserts that every item in the JSON appears in the rendering, so the human form cannot drop a finding.
4. **Redaction and signing.** `--redact`, with a test that no coordinate survives it and that the full report's hash matches. `urml evidence verify`, the Licensor's public key in the package, and a test that verifies a committed signed fixture offline and rejects a report altered by one byte.
5. **Example and docs.** `examples/evidence/` with one committed, byte-asserted report and a README written for an auditor who has never seen URML. A section in `docs/safety/safety-model.md`.
6. **Website.** A page on urml.dev showing an example report, after steps 1 to 5 ship.

Each step lands with its tests. No step changes validation results.

## Decisions

Settled by the founder on 2026-11-24:

1. **Signing.** Licensor-reviewed reports are signed, as described under Signing. Reports anyone builds stay unsigned and are trusted by reproduction.
2. **Run-time evidence.** What actually ran is a second report, in a later RFC.
3. **Redaction.** `--redact` exists, with the single behavior described under Redaction.
4. **The name.** `urml evidence`, and "evidence report".
5. **Grouping by standard.** Rulebook cites gain an optional `standard` field, as described above.

## Open questions

1. **Key custody beyond one person.** One Licensor key on one hardware token is enough while there is one maintainer. When a foundation holds the standard, who holds the key, and does a reviewed report need two signatures?
