---
rfc: 0705
title: URML-Certified, a free conformance certification on public criteria
author: Ido Yahalomi (ido@beamdesk.space)
state: Accepted
created: 2026-11-24
updated: 2026-11-24
amends: RFC-0014
superseded-by: none
amended-by: RFC-0708 (the certification run is paid)
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

# RFC-0705: URML-Certified, a free conformance certification on public criteria

Kind: Spec and governance. This RFC starts the URML-Certified program that [`MANIFESTO.md`](../../MANIFESTO.md) puts in Phase 4 and [RFC-0014](0014-substrate-conformance.md) defined only as a bar. It amends the conformance specification (new version `conformance@0.2.0`), replaces the URML-Certified parts of [`TRADEMARK.md`](../../TRADEMARK.md), and adds a `certified` tier to the [registry](../../registry/README.md).

## Summary

A runtime earns **URML-Certified** for a set of profiles when it passes the full public conformance suite for those profiles with its own adapter, and the Licensor (Yahalomik Ltd., [RFC-0704](0704-licensor-yahalomik.md)) reproduces that result from the publicly released package in a clean, offline environment. Both reports are committed to the registry, pinned by sha256, and re-checked by `python -m urml_conformance.registry check` on every change. Certification is free as accepted here; [RFC-0708](0708-paid-certification.md) makes the run paid, and the fee pays for the run, never for the result. It certifies conformance to the URML specification and nothing else: not safety, not regulatory compliance, not fitness for any purpose.

## Motivation

Two things have been true at once. The Manifesto says URML "will never sell certification. It will offer it, and the certification process will be public." Other documents ([`CLAUDE.md`](../../CLAUDE.md), [`COMMERCIAL.md`](../../COMMERCIAL.md), [`conformance/README.md`](../../conformance/README.md), [`CONTRIBUTING.md`](../../CONTRIBUTING.md), [`GOVERNANCE.md`](../../GOVERNANCE.md), the glossary) described URML-Certified as a future paid program and a commercial moat. The Manifesto ranks first in the precedence order, so the paid reading was never available. This RFC settles it in the Manifesto's favor and writes it down everywhere.

The self-reported tier has a gap a certification closes: nobody but the submitter has run the suite. A buyer comparing two "URML-compatible" vehicles has to trust each maker's report. A reproduction by a party that did not build the runtime, from the package a customer would install, is the smallest step that makes the claim independent.

The registry already has the machinery: pinned conformance reports, a checker that refuses reports from the mock adapter or from another adapter, and whole-profile coverage. Certification adds one more report and a few rules, not a parallel system.

## Proposal

### What is certified

A **(runtime package, version, adapter, profiles, conformance spec version)** tuple, recorded in one registry entry. Certification attaches to that exact package version. A new version needs its own reproduction.

### Criteria

All of them are public and all but the attestation are checked by machine:

1. **Self-report.** Everything the self-reported tier requires today: a `urml.conformance-report/1` report from the runtime's own adapter, every fixture of each claimed profile, all passed, from this repository's urml-conformance version.
2. **Public package.** `runtime.package` is a distribution anyone can install, and `runtime.version` is one exact version. A repository-path example cannot be certified.
3. **Reproduction.** The Licensor installs that version from its public source into a clean environment with the network off after installation, runs the same suite with the same adapter, and commits the report. It must pass on every fixture and cover the same fixture set (equal `fixtures_sha256`) as the self-report.
4. **Attestation.** The submitter states in the entry that the runtime meets the six clauses of the conformance contract, in particular that it has no path that actuates without validation. The suite cannot prove a negative; the attestation is the submitter's word, and a false one is grounds for revocation.
5. **Limits.** The entry states what the certification does not show, as every registry entry already must.

### Validity

A certification is valid until the earlier of its `expires` date (at most 366 days after `certified_on`) and the next urml-conformance release. The checker already refuses a report from an older urml-conformance version, so a release ends every certification and self-report until it is re-run. The checker also refuses an expired certification. An entry whose certification lapses goes back to the self-reported tier or is withdrawn.

### Process

1. The submitter opens a pull request that adds or updates a registry entry with `tier: certified`, the self-report, and the attestation.
2. The Licensor reproduces the run and adds the reproduction report and the dates to the same pull request.
3. The registry check passes and the entry merges. That merge is the grant of the mark.

Requests are handled in the order they arrive. There is no fee for any step, and no paid service can buy or speed up the outcome: a validation engagement ([`COMMERCIAL.md`](../../COMMERCIAL.md#validation-services)) can help a team get ready, and the certification decision rests only on the criteria above.

### What the Licensor does not certify

Its own runtimes. Packages published by the URML project (the `urml-*` distributions and the in-repository examples) stay at the self-reported tier. A certifier grading its own work proves nothing, and a certification mark holder using the mark on its own goods would weaken the mark.

### Use of the mark

The full rules are in [`TRADEMARK.md`](../../TRADEMARK.md). In short: the mark is used only with its scope ("URML-Certified, conformance 0.2.0, profiles warehouse, acme-urml-runtime 1.2.0"), only while the registry entry is listed and unexpired, and never as a claim about safety, regulatory compliance, NDAA status or fitness for a purpose.

### Revocation

The Licensor withdraws a certification when the registry check fails for it, when a later reproduction fails, when the attestation proves false, or when the mark is used outside its rules. Withdrawal is a commit to the entry with the reason in its limits, so it is as public as the grant.

## Alternatives considered

1. **A paid program.** Rejected: the Manifesto forbids selling certification, and a mark that can be bought tells a buyer less than one that cannot. Revenue stays with licenses and the validation engagements.
2. **Certification by a third-party lab.** Better neutrality, but no lab knows URML yet and none would do it for free. The process here is written so a lab or a future foundation can take over the Licensor's role unchanged.
3. **Keep waiting for Phase 4.** The bar has been specified since RFC-0014 and the registry checker exists. Waiting leaves the self-reported tier as the only signal buyers get.
4. **Certify robots instead of runtimes.** A robot's behavior under URML is its runtime plus its manifest. The registry entry already pairs the two, so certification attaches to the entry; the manifest is checked as part of it.

## Prior art

- Kubernetes Certified (CNCF): free to apply, public conformance tests, results submitted by pull request and reproducible. The model followed here.
- OpenStack Powered: trademark use tied to passing a published test set.
- USB-IF and Bluetooth SIG: paid certification run by an industry body. The model rejected here.

## Implementation plan

In the pull request that carries this RFC:

- `spec/conformance/v0.2.0.md`: section 3 describes the certified tier as above; v0.1.0 stays as the record.
- `conformance/src/urml_conformance/registry.py`: the `certified` tier, its reproduction report and dates, the public-package and not-first-party rules, expiry; tests; the regenerated `registry/entry.schema.json`.
- `TRADEMARK.md`: the URML-Certified policy replaces the Phase 4 stub.
- `registry/README.md`, `docs/registry/SUBMISSION.md`, `conformance/README.md`, `COMMERCIAL.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`, the glossary and the other pages that called the program future or paid.

## Regulatory alignment

None changes. A URML-Certified runtime is no more NDAA-compliant than an uncertified one; the federal self-report rules in [`FEDERAL-VALIDATION-SELF-REPORT.md`](../../docs/manufacturers/FEDERAL-VALIDATION-SELF-REPORT.md) stand.

## Open questions

1. **Registration.** URML's marks are unregistered. Registering URML-Certified as a certification mark (USPTO, and the Israel Patent Office) gives the policy teeth. Trademark counsel should review `TRADEMARK.md` before the first certification is granted.
2. **Hand-over.** When a foundation or steering committee exists, the Licensor's reproduction role moves to it. The registry format does not change.

## Process note

The sole maintainer is a director of Yahalomik Ltd., which this RFC names as the certifier. [`GOVERNANCE.md`](../../GOVERNANCE.md) asks for a non-conflicted reviewer on such RFCs once a steering committee exists; none exists yet, so the conflict is recorded here. The conflict is limited by design: the mark is free, the criteria are public, and every reproduction report is committed where anyone can re-run it.

Like RFC-0703 and RFC-0704, this RFC is accepted on merge, without the seven-day comment window RFC-0001 sets. The maintainer may hold the merge for that window.
