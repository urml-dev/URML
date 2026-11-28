---
rfc: 0711
title: A URML-Certified certificate a buyer can ask for
author: Ido Yahalomi
state: Draft
created: 2026-11-27
updated: 2026-11-27
amends: RFC-0705, RFC-0708
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

# RFC-0711: A URML-Certified certificate a buyer can ask for

Kind: Governance and spec. This RFC amends [RFC-0705](0705-urml-certified.md) and [RFC-0708](0708-paid-certification.md) and publishes the change in a new conformance specification version, `conformance@0.3.1`. It follows RFC-0712 ([pull request #116](https://github.com/urml-dev/URML/pull/116)), which defines what a compatibility claim covers and takes `conformance@0.3.0`. It adds fields to the registry entry, a certificate file and a public list of withdrawals. It changes no clause of the conformance contract and no fixture.

This is a draft. The implementation listed at the end lands in the same pull request before the RFC is accepted.

## Summary

URML-Certified names a software package and a version. A company that buys robots needs a certificate it can match to the model and software on a quote, check without a developer, and read without knowing URML.

This RFC keeps the one mark and the public criteria and changes six things:

1. The certificate names the product: who submitted it, the robot maker and models, and the controller software the run met.
2. It states where the Licensor repeated the run: on the robot or on a simulator.
3. The certified run includes the goal-line lane, so "a refused program sends nothing" is tested and no longer rests on the attestation alone.
4. Each certificate gets an ID, one fixed plain text, a file signed by the Licensor and a page at urml.dev/verify.
5. A certificate stays valid for its term against the suite version it names.
6. The fee becomes yearly per product family and covers the runs for new software versions.

No criterion gets easier. The fee still pays for the run and never for the result.

## Motivation

The registry has no certified entry. That makes this the cheapest moment to fix the shape of the certificate, because nothing already granted changes meaning.

The program was designed from the runtime maker's side. Read from a buyer's side it has six gaps.

**The unit is a package.** A certification attaches to a runtime package, a version, an adapter, a profile set and a conformance specification version. A purchasing department compares robot models and software releases. Nothing on the certificate tells it whether the robot on the quote is the thing that was tested.

**The run can happen without a robot.** The suite records what the runtime asked the adapter to do, and the specification says that this "does not show that the robot moved" ([`spec/conformance/v0.2.3.md`](../../spec/conformance/v0.2.3.md), clause 6). A reproduction against a recorded substrate and one against the robot lead to the same grant, and a buyer will assume the robot was there. A conformance report names the adapter and says nothing about what stood behind it.

**The refusal is not in the certified run.** The main run stops a rejected fixture at the validator. Only the goal-line lane ([`conformance/CONFORMANCE_KIT.md`](../../conformance/CONFORMANCE_KIT.md)) hands rejected programs to the runtime and checks that the adapter saw zero calls. That lane writes no report and is not a criterion. The claim a buyer cares about most is the one a certificate supports with an attestation only.

**A certificate rarely stays current.** It ends when the package version changes and when any urml-conformance version is released. Three urml-conformance versions were released between 2026-11-22 and 2026-11-25. A maker that ships firmware every quarter would hold a current certificate for a few days at a time, and would pay for a run each time.

**Nobody outside the repository can check one.** The grant is a merge. There is no certificate number, no signed file and no page a buyer can open, and the Licensor has published no signing key.

**The text is for developers.** "URML-Certified (conformance 0.2.0): profiles warehouse; acme-urml-runtime 1.2.0" is exact, and a buyer cannot tell what it promises.

A buyer that cannot ask for the certificate gives a maker no reason to pay for one. RFC-0708 already says who a maker certifies for: "buyers who ask for an independent conformance claim". This RFC builds the half of the program those buyers use.

## Proposal

### One mark, two tiers, as before

Nothing here adds a tier, a level or a second mark. Section 3 of the conformance specification keeps its two tiers and its sentence "There are no numeric levels, scores, or star ratings." What changes is what a certified entry records and what the Licensor publishes for it.

### The certificate names a product

A certified entry gains a `product` block under `certification`:

- `submitter`: who publishes the package, makes the attestation, and pays for the run or receives the waiver.
- `maker` and `model`: the robot maker and the model name as they appear on a quote. One entry is one model with its manifest.
- `controller`: the name and version of the software the adapter drives, as the robot or the simulator reported it during the reproduction.

Entries that share a package, a version, an adapter, a profile set and one reproduction form a **product family** and carry the same certificate. Under RFC-0712 each model's manifest selects the fixtures that apply to it, so one run for a family covers every fixture that applies to any of its models. Each model keeps its own entry, manifest, claim scope and validation records.

The submitter and the maker can differ. A university lab can certify its adapter for a commercial arm. The certificate says who attests, and a buyer that wants the maker's own word asks for a certificate whose submitter is the maker. A certificate held by a third party is not a statement by the robot's maker.

The package stays public, as RFC-0705 requires. A maker whose controller firmware is closed publishes the layer that speaks URML, usually its adapter package, and keeps the controller behind it closed. The certificate records the controller version the run met. A package that builds on a URML-project runtime with the maker's own adapter is a third party's package and can be certified. The Licensor still never certifies a package it publishes itself.

### The certificate says where the run happened

`certification.reproduction` gains `substrate`, with one of two values:

- `hardware`: the Licensor's run drove the robot itself.
- `simulator`: it drove a simulator of the robot or of its controller.

These are the backend kinds RFC-0712 accepts, which the submitter declares in the self-report and the Licensor's run confirms. RFC-0712 refuses the other two kinds for every claim: a replay of responses captured earlier, and a test double that answers without a model of the robot.

The values describe what happened. The registry does not rank them, as it does not rank the kinds of field evidence today. A buyer decides which it accepts, and the certificate, the scope line and the verify page all state the value.

A `hardware` reproduction also records `observed`: how the Licensor confirmed motion through a channel the adapter does not write, such as telemetry read by a separate listener or the Licensor's own observation at the robot. The files are pinned in the entry's evidence folder. The registry already records why this matters: the first PX4 gate test passed on command acknowledgements while the vehicle never armed ([`registry/README.md`](../../registry/README.md)).

A hardware run takes place on a unit in the Licensor's hands, or at the submitter's site with the Licensor running the suite from its own machine.

### The goal line joins the certified run

A certified entry's self-report and reproduction both include the goal-line lane for the claimed profiles. Every rejected fixture is handed to the runtime through the recording proxy, and a case passes only when the runtime refuses, the refusal carries the expected error codes, and the adapter saw zero calls.

The lane runs through the entry point the product ships. The entry gains an optional `runtime.factory` (`module:attribute`, the form `--runtime` takes today). When the package has no runtime of its own, the lane runs the reference runtime with the entry's adapter.

The conformance report gains a `goal_line` section with its own counts and fixture digest, so the registry check can refuse a certified entry that lacks it.

### An ID, a file, a signature, a text, a page

**ID.** `URML-C-<year>-<four digits>`, assigned at the grant and never reused.

**File.** `registry/certificates/<ID>.json`, format `urml.certificate/1`. The registry tool generates it from the entries and the two reports. Nobody writes it by hand, and it does not change after the grant. It holds the product blocks of the family, the package, its version and the sha256 of the distribution the Licensor installed, the adapter, the profiles, the conformance specification and urml-conformance versions, the fixture counts and digests of both lanes, the sha256 of both reports, the reproduction's date, substrate and environment, the attestation and the name and role of the person who made it, the two dates, the limits, and the registry commit.

**Signature.** An OpenSSH signature by the Licensor's key, made the way [`docs/evidence/signing.md`](../evidence/signing.md) describes, in a new namespace `certificate@urml.dev`. The separate namespace keeps a signature on an evidence report from passing as a certificate. Verification runs offline.

**Text.** Every certificate renders one fixed text from its fields. No free text is added. Draft, for counsel to review before the first grant:

> Certificate [ID], valid until [date].
>
> [Package] [version], published by [submitter], drives the [maker] [models] (controller [name and version]).
>
> It passed all [N] public URML conformance tests that apply to it in the [profiles] profile (conformance [version]): [the scope statement of RFC-0712, which says what the product served, what the test companion served and what did not apply]. All [M] programs that the specification says must be refused were refused, and nothing was sent to the robot.
>
> Yahalomik Ltd. repeated the run on [the robot itself, model X | a simulator] on [date].
>
> [Submitter] attests that every command entering through URML is checked before the robot acts on it.
>
> This certificate covers the URML interface only. It does not certify safety, regulatory compliance or fitness for any purpose, and it says nothing about other ways of commanding the robot.

**Page.** `urml.dev/verify` is a static page built from the certificate files and the withdrawal list. A reader types an ID and sees whether the certificate is valid, expired or withdrawn, reads the fixed text, and can download the file and its signature to verify offline. The page needs no account and records nothing about who looked. An ID the page does not know is not a certificate.

**Withdrawals.** `registry/certificates/withdrawn.yaml` lists the ID, the date and the reason. A certificate file is never edited or deleted, so a withdrawn certificate stays readable with its status.

### Validity

A certificate is valid from `certified_on` to `expires`, at most 366 days, for the urml-conformance version it names. A later urml-conformance release no longer ends it. A renewal runs on the suite that is current at renewal.

Each urml-conformance release records its fixture-set digests in the repository, so the check can verify an older report against the set it ran.

The Licensor may repeat a certified run on a newer suite at its own cost. If that run fails, the withdrawal rule of RFC-0705 applies.

The self-reported tier keeps today's rule. A self-report is free to re-run, so it must come from the current urml-conformance version.

### Fee

Every rule of RFC-0708 stays: the quote comes from the scope of the run alone, the fee pays for the run and never for the result, a failed run keeps its fee, requests run in the order they are paid or waived, there is no expedited tier, the waiver for non-commercial runtimes holds, and no commercial license is needed to apply.

The unit changes. The fee is yearly, per product family. It covers the first run and the runs for new software versions of that family during the year, up to the number the quote states. Each version still gets its own reproduction and its own certificate. No version is certified without a run.

The scope a quote is built from is the number of profiles, the substrate, and the number of runs in the year. A hardware run adds the cost of travel or shipping.

No price is published yet. RFC-0708 deferred it until the first certifications show what a run costs, and that still holds.

### Using the mark

The scope line that [`TRADEMARK.md`](../../TRADEMARK.md) requires gains the product, the substrate and the ID:

> URML-Certified (conformance 0.3.1): Acme A6, controller AcmeOS 4.2.1, acme-urml-adapter 1.2.0, profile industrial, reproduced on hardware. Certificate URML-C-2027-0001, urml.dev/verify.

Where space is short, such as a nameplate or a datasheet footer, "URML-Certified, certificate URML-C-2027-0001" is enough, because the ID leads to everything else.

The mark is used for the models and the software version the certificate names, and for nothing else the company makes.

### What a buyer checks

Three facts, each on the verify page: the ID is valid, it names the model and the software version being offered, and it states the substrate the buyer requires.

Documents that help a buyer write this into a request for quotation are planned for after the third certificate. They are documentation, not criteria.

## What the certificate still does not show

**Safety, compliance or fitness.** Unchanged from RFC-0705.

**That the manifest is true.** The maker declares the robot's limits. The suite runs on the public test manifests, not on the model's own. The entry's validation records show the validator's verdicts on the model's manifest, and they are the submitter's records, replayed by the check.

**Other ways of commanding the robot.** A teach pendant, a vendor API or a fieldbus can move the robot without URML. The certificate covers commands that enter through URML.

**An independent implementation.** The suite drives the reference runtime with the submitter's adapter, or a runtime factory that follows the reference runtime's interface. A validator or runtime written from the specification in another language has no lane yet.

**The deployed site.** Which envelope applies and which programs run there is the subject of the evidence report ([RFC-0707](0707-evidence-report.md)), which the operator or integrator builds for its own cell.

## Backward compatibility

No certified entry exists, so no grant changes. `conformance_spec` gains the value `0.3.1`, and a certified entry names `0.3.1` or later. Self-reported entries and listings without a claim are unchanged. The conformance report format stays `urml.conformance-report/1`: the `goal_line` section is an optional addition that only a certified entry must carry. The registry entry format stays `registry_version: "1"`, with new optional fields.

RFC-0708 said: "A renewal or a new version is a new run and a new fee." The first half stands. The yearly family fee replaces the second half.

## Drawbacks

Each grant gets heavier. The Licensor generates a file, signs it with a hardware key and publishes it, and a hardware run needs a robot in the room. The Licensor is one person today.

A certificate that names a robot model will be read as a statement about the robot, whatever the fixed text says. The text and the "does not show" list limit that risk and do not remove it.

Two robots can both be certified against different suite versions. The certificate states the version, and a buyer that wants the current suite has to ask for it.

A yearly fee that includes several runs commits the Licensor to work it has not measured yet. The quote caps the number of runs for that reason.

For a package that uses the reference runtime, the goal-line result is a property of the reference runtime in the certified configuration: that runtime refuses before it touches any adapter. The lane says most when a package ships a runtime of its own.

The Licensor is paid to certify and now also signs the certificate. The conflict that RFC-0708 recorded is unchanged: the fee is owed whatever the result, the criteria are public, and every report is committed where anyone can re-run it.

## Alternatives considered

1. **A second mark or a product tier.** For example "URML-Certified Product", or levels for hardware and simulator. Rejected: the specification keeps two tiers on purpose, and a second mark is a second thing to register and police. One mark with a stated scope says the same with less.
2. **Certify closed builds delivered privately.** It would fit controller firmware that never becomes public. Not now: a reproduction that nobody else can repeat rests on the Licensor's word, and avoiding that is what the mark was built for. The question comes back when a maker asks and a second party can reproduce.
3. **Keep ending certificates at every urml-conformance release and re-run them all.** The Licensor could do that for simulator runs. It cannot for hardware runs, and the load grows with every certificate and every release.
4. **Keep the fee per run.** A maker with quarterly firmware pays four times a year or stays uncertified for most of it. A yearly fee per family is a line a product manager can budget.
5. **A hosted verification service.** Rejected: a static page and an offline signature check answer the same question with nothing to operate and nothing collected about who asks.
6. **Refusal tests written against each model's own manifest.** The Licensor would hand the runtime programs that exceed that model's declared limits. It ties the certificate to the product's own numbers and needs new suite machinery. Left as an open question.

## Prior art

- Wi-Fi CERTIFIED and Bluetooth qualification: every certified product has a public identifier and a public lookup. The identifier is what a buyer checks.
- NRTL listings (UL, Intertek, CSA): a file number that resolves in the lab's public directory.
- VDA 5050: vehicle buyers in the VDA wrote the interface together with the makers in the VDMA, and the VDA describes it as the standard its members ask for when they tender AGV systems. A standard that buyers ask for is one makers implement.
- Kubernetes Certified: the public, pull-request based process RFC-0705 followed and this RFC keeps.

## Implementation plan

In the pull request that carries this RFC, before it is accepted:

- `spec/conformance/v0.3.1.md`: section 3 as above, on top of RFC-0712's v0.3.0. Earlier versions stay as the record, and `spec/conformance/README.md` points to v0.3.1.
- `conformance/src/urml_conformance/`: the goal-line lane writes its section of the report (`goal_line.py`, `report.py`); the registry model gains `product`, `reproduction.substrate` and `observed`, `runtime.factory` and the certificate ID, plus the certificate export, the withdrawal list, the new validity rule and the per-release fixture digests (`registry.py`); the reproduction runs the goal line, records the substrate and the distribution digest, and lets the offline guard allow one robot address for a hardware run (`reproduce.py`). Tests for each, and the regenerated `registry/entry.schema.json`.
- `docs/evidence/signing.md` and the validator's verifier: the `certificate@urml.dev` namespace.
- `TRADEMARK.md`, `COMMERCIAL.md`, `registry/README.md`, `docs/registry/SUBMISSION.md`, `conformance/README.md`, `conformance/CONFORMANCE_KIT.md`, `docs/glossary.md`: the product scope, the substrate, the ID, the validity rule and the yearly fee.
- RFC-0705 and RFC-0708 record that they are amended by this RFC.

Outside this repository: the `urml.dev/verify` page in the website repository, and the Licensor's public key, published in a reviewed commit once the key exists on a hardware token.

After the third certificate: the buyer documents.

## Regulatory alignment

None changes. A certificate is not a declaration of conformity under the EU Machinery Regulation or any other law, and a URML-Certified product is no more NDAA-compliant than an uncertified one.

## Open questions

1. **A real robot cannot hold a whole profile today.** A claim covers every fixture that lists a profile, and no registry entry carries even a self-report. Measured on 2026-11-27 at commit 6fd8f24: apart from the mock, no adapter passes a whole profile on a real backend. The two passes found are empty ones: `research`, whose one fixture never reaches the adapter, and `av`, with one executing fixture, on a fake. With every fixture location mapped and the mock standing in for perception, the UR adapter reaches 71 of 77 industrial fixtures and the PX4 adapter 48 of 49 drone fixtures, both on fakes. Three things stand in the way by design. Most executing fixtures need perception that an arm or an autopilot does not have. Fixtures name places that exist only in the fixture world. Fleet fixtures need other robots. The measurement also showed that an adapter which fails every call still passes 27 of the 77 industrial fixtures, because those stop at the validator. The scope of a claim therefore gets its own RFC before this one is accepted, because a certificate nobody can earn helps no buyer. That RFC is RFC-0712, in draft as [pull request #116](https://github.com/urml-dev/URML/pull/116).
2. **Closed builds.** Alternative 2. The proposal keeps the public package as the only route.
3. **The model's own limits.** Alternative 6. Should the run also hand the runtime refused programs written against the model's manifest?
4. **Runs per year.** How many runs the yearly fee includes, to be set with the price after the first three certifications.
5. **Counsel.** The fixed text, the scope line, the registration of URML-Certified as a certification mark, and the rules for naming a label in a public tender in the EU and the US. `TRADEMARK.md` already asks for a counsel review before the first grant.
6. **Key custody.** One hardware token and one backup, and who holds the backup.
7. **Remote hardware runs.** Whether a run at the submitter's site that the Licensor operates over a remote session counts as `hardware`.
8. **A buyers' group.** A group of robot buyers is planned. Its role in changing the criteria is a separate RFC.

## Process note

The sole maintainer is a director of Yahalomik Ltd., which certifies, is paid to certify, and under this RFC signs each certificate. The conflict is recorded here as it was in RFC-0705 and RFC-0708.

RFC-0703 through RFC-0709 were accepted on merge. This one takes the comment window that [RFC-0001](0001-rfc-process.md) sets: it stays open for at least seven days before it is accepted. The readers it is written for are buyers and makers outside the project, and nothing forces the date.
