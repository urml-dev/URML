---
rfc: 0708
title: URML-Certified becomes a paid validation service, on public criteria
author: Ido Yahalomi
state: Accepted
created: 2026-11-25
updated: 2026-11-25
amends: RFC-0705, MANIFESTO.md (Non-Goals)
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

# RFC-0708: URML-Certified becomes a paid validation service, on public criteria

Kind: Governance and spec. This RFC amends the Manifesto's non-goal on certification, amends [RFC-0705](0705-urml-certified.md) so the Licensor charges a fee for the certification run, and publishes the change in a new conformance specification version, `conformance@0.2.2`. The criteria, the checker and the registry format do not change.

## Summary

A runtime maker who wants **URML-Certified** pays the Licensor (Yahalomik Ltd., [RFC-0704](0704-licensor-yahalomik.md)) a fee for the certification run: the Licensor's reproduction of the conformance suite from the public package, in a clean, offline environment. The fee is listed with the other paid validation services in [`COMMERCIAL.md`](../../COMMERCIAL.md#validation-services) and quoted per certification.

The fee pays for the run, not for the result. The criteria stay public and machine-checked, a run that fails keeps its fee and grants nothing, and no amount of money changes a verdict or the order of the queue. Everything else stays free: the conformance suite, the self-reported tier, and listing in the registry.

## Motivation

RFC-0705 made certification free because the Manifesto said URML "will never sell certification." That kept the mark clean, but it left the Licensor doing real work for nothing: every certification is an install, an offline run of the full suite with a third party's adapter, a report, and a review of the attestation. That work repeats for every version and at least once a year, and it grows with every runtime that applies. Unpaid, it competes with everything else the sole maintainer does, and the queue gets slower exactly when the program succeeds.

Certification is also where the value to a runtime maker is most direct. A maker certifies to sell into buyers who ask for an independent conformance claim. Paying for the work that produces that claim is ordinary for conformance programs (USB-IF, Bluetooth SIG, the Wi-Fi Alliance and Thread Group all charge), and it is a revenue line that fits the [strategic posture](../../CLAUDE.md#strategic-posture): it grows with adoption and charges the party that profits from it.

The Manifesto's worry is real: a mark that can be bought tells a buyer less than one that cannot. This RFC keeps the parts of RFC-0705 that answer that worry and changes only who pays for the run.

## Proposal

### What the fee buys

One certification run: the Licensor installs the exact runtime version from its public source, turns the network off, runs the suite for the claimed profiles with the submitter's adapter, commits the reproduction report, and reviews the entry against the criteria. A renewal or a new version is a new run and a new fee.

### What the fee does not buy

- **The result.** The mark is granted only when the criteria in [`spec/conformance/v0.2.2.md`](../../spec/conformance/v0.2.2.md) section 3 are met and the registry check passes. A run that fails is still a completed run: its fee is not refunded, and the entry stays at the self-reported tier or is withdrawn.
- **Speed.** Paid requests are run in the order they are paid. There is no expedited tier.
- **A different standard.** The criteria, the fixtures and the checker are the same for every submitter, and every reproduction report is committed where anyone can re-run it.
- **Anything about safety or compliance.** The mark still certifies conformance to the URML specification and nothing else.

### How the fee is set

Quoted per certification, from the scope of the run only: the number of profiles claimed, and whether the adapter runs against a simulator, a recorded substrate or hardware the submitter provides. The quote never depends on who the submitter is, whether it holds a commercial license, or what result is expected. A commercial license is not required to apply, and holding one does not change the fee or the outcome.

The fee is not published as a fixed price yet. Per [`CLAUDE.md`](../../CLAUDE.md#public-commitments-are-deferred-until-measured), a number goes on the page once the first certifications show what a run actually costs.

### What stays free

- The conformance suite, to run as often as anyone likes.
- The self-reported URML-compatible tier and a registry listing at that tier.
- Reading, re-running and challenging any committed reproduction report.

### What the Licensor still does not do

It does not certify the URML project's own runtimes (RFC-0705). It does not sell a certification that skips the reproduction, and it does not sell certification of safety, regulatory compliance, or NDAA status, which the mark never covered.

### Payment stays out of the registry

A registry entry records no fee, invoice or payment state. The entry shows the criteria and the evidence; the commercial side lives in the order form. This keeps the registry a record of conformance, and keeps billing data out of a public repository.

### The Manifesto

The non-goal "It will never sell certification. It will offer it, and the certification process will be public" becomes: "Its certification will always run on public criteria. The Licensor charges for the certification run, never for the result, and no payment changes a verdict."

## Alternatives considered

1. **Keep certification free (RFC-0705).** Rejected by the founder: the reproduction is real, repeating work, and a free queue gets slower as the program grows.
2. **A paid readiness engagement, with the mark free.** A consultancy that prepares a team for the free run. It earns less, and it pays the Licensor to help a team pass a test the Licensor then grades for free, which mixes the roles more than a flat fee for the run does.
3. **A published fixed fee from day one.** Clearer, and the eventual goal. Deferred until measured, so the first number is one the Licensor can hold.
4. **Charge only for the mark's use (a trademark license fee), with a free run.** Separates the fee from the verdict even further, but every runtime that passes would owe a recurring fee for words on a box, and enforcement becomes the product. A fee for work done is simpler to explain and to audit.
5. **Hand certification to a third-party lab that charges.** Better neutrality, but no lab knows URML yet. The process stays written so a lab or a future foundation can take over the Licensor's role, and the fee, unchanged.

## Prior art

- USB-IF, Bluetooth SIG, the Wi-Fi Alliance, Thread Group: paid certification on published test specifications. The fee model followed here.
- Kubernetes Certified (CNCF): free, public, pull-request based. The process model RFC-0705 followed and this RFC keeps.
- NRTL product listings (UL, Intertek, CSA): the maker pays the lab for testing, and a failed test is still billed. The "fee for the run, not the result" rule followed here.

## Implementation plan

In the pull request that carries this RFC:

- `MANIFESTO.md`: the Non-Goals sentence above.
- `spec/conformance/v0.2.2.md`: section 3 states the fee rules above; v0.2.1 and earlier stay as the record. `spec/conformance/README.md` points to v0.2.2.
- `conformance/src/urml_conformance/registry.py`: accepts `conformance_spec: "0.2.2"`; the regenerated `registry/entry.schema.json`. No rule changes.
- `COMMERCIAL.md`: URML-Certified joins the Validation services, quoted per certification.
- `TRADEMARK.md`, `GOVERNANCE.md`, `CLAUDE.md`, `docs/glossary.md`, `docs/registry/SUBMISSION.md`, `registry/README.md`, `conformance/README.md`, `conformance/CONFORMANCE_KIT.md`, `docs/manufacturers/README.md` and the standards directory: every sentence that called certification free.
- RFC-0705 records that it is amended by this RFC.

## Regulatory alignment

None changes. A URML-Certified runtime is no more NDAA-compliant than an uncertified one.

## Open questions

1. **Fee waivers.** Should runs for university research groups, teaching platforms and non-commercial runtimes be waived or reduced, to keep the free tier generous where adoption starts?
2. **Published price.** When the first certifications are done, publish a fee schedule by scope in `COMMERCIAL.md`.
3. **Registration.** As in RFC-0705: register URML-Certified as a certification mark before the first grant. A paid mark makes this more pressing, because a mark that earns money is a mark worth copying.
4. **Hand-over.** When a foundation exists, the reproduction role and its fee move to it together.

## Process note

The sole maintainer is a director of Yahalomik Ltd., which now both certifies and is paid to certify. The conflict is recorded here and limited by design: the fee is owed whatever the result, the criteria are public, and every reproduction report is committed where anyone can re-run it and challenge a grant. [`GOVERNANCE.md`](../../GOVERNANCE.md) asks for a non-conflicted reviewer on such RFCs once a steering committee exists; none exists yet.

This RFC reverses a sentence in the Manifesto that had been public since Phase 0. It says so plainly rather than reinterpreting the old sentence. Like RFC-0703 through RFC-0705, it is accepted on merge, without the seven-day comment window RFC-0001 sets. The maintainer may hold the merge for that window.
