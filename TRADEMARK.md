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

# URML Trademark Policy

Status: policy. The URML-Certified sections are in force from [RFC-0705](docs/rfcs/0705-urml-certified.md) (2026-11-24); the rest is the interim policy from Phase 0.
Authority: refines [GOVERNANCE.md §Trademark Policy](GOVERNANCE.md#trademark-policy). Licensing terms are in [LICENSE](LICENSE) and [LICENSING.md](LICENSING.md).

## The marks

URML has two marks.

The word mark **URML** identifies the specification and its reference implementations.

The conformance mark **URML-Certified** says that one exact version of a runtime passed the public conformance suite for named profiles, and that the Licensor reproduced the result. It is granted on public criteria, through the [registry](registry/README.md), after a paid certification run ([RFC-0708](docs/rfcs/0708-paid-certification.md)). It says nothing about safety, regulatory compliance, or fitness for any purpose.

## Ownership

Both marks are held by Yahalomik Ltd., the URML Licensor ([RFC-0704](docs/rfcs/0704-licensor-yahalomik.md)). Neither is registered yet. They stay assignable to a future URML foundation, and no decision here may block that assignment.

## What anyone can do

Use the word "URML" as a factual descriptor. Statements like "this library implements the URML specification" or "URML is a specification for natural-language robot control" are fine. You don't need permission.

Describe a runtime, library, or tool as "URML-compatible" if it passes the unmodified, current public [conformance test suite](conformance/) for the profiles and URML spec versions it claims.

Submit a robot and its runtime to the [registry](registry/README.md) by following [docs/registry/SUBMISSION.md](docs/registry/SUBMISSION.md). A listing is a factual record of the evidence submitted, not an endorsement.

Submit a robot or product for listing in the [Manufacturer & Product Directory](docs/manufacturers/directory.md) by following [docs/manufacturers/SUBMISSION.md](docs/manufacturers/SUBMISSION.md). Same posture: a factual record, not an endorsement.

State, factually, that a specific manifest "validates clean under URML's open US-federal default compliance policy at URML commit `<hash>`" if it does and you pin the commit. This is a reproducible self-report, not a certification. The exact permitted and forbidden phrasing is in [docs/manufacturers/FEDERAL-VALIDATION-SELF-REPORT.md](docs/manufacturers/FEDERAL-VALIDATION-SELF-REPORT.md).

## URML-Certified

### Who can get it

Anyone whose runtime is one exact version of a distribution the public can install. The Licensor does not certify runtimes the URML project publishes itself (the `urml-*` packages and the in-repository examples); they stay at the self-reported tier.

### The criteria

The criteria are in [`spec/conformance/v0.2.3.md`](spec/conformance/v0.2.3.md) section 3, and the registry checker enforces all but the attestation:

1. A self-report: the full suite for each claimed profile, run with the runtime's own adapter, every fixture passed.
2. A reproduction: the Licensor installs that exact version from its public source into a clean environment, turns the network off, runs the same suite with the same adapter, and gets a pass on every fixture over the same fixture set.
3. An attestation by the submitter that the runtime meets the six clauses of the conformance contract, in particular that no path actuates without validation.

### Cost and order

The Licensor charges a fee for each certification run, listed with the validation services in [COMMERCIAL.md](COMMERCIAL.md#urml-certified-runtime-makers). The fee is waived for a non-commercial runtime, one that is not sold, not licensed for a fee and not part of a paid product or service. The fee pays for the run, never for the result: a run that fails keeps its fee and grants nothing. Requests are run in the order they are paid or waived, with no expedited tier, and no fee, license or other service affects whether certification is granted.

### How long it lasts

At most 366 days from the grant, and never past the next urml-conformance release. After either, the registry check fails for the entry until it is renewed or moved back to the self-reported tier.

### Using the mark

Use "URML-Certified" only:

- while the registry entry is listed with `tier: certified` and the registry check passes for it;
- together with its scope, in this form or one that carries the same facts: "URML-Certified (conformance 0.2.0): profiles warehouse; acme-urml-runtime 1.2.0", with a link to the registry entry;
- for the certified version, not for later versions, other products, or the company as a whole.

Never use it to claim, or in a way that suggests, safety certification, regulatory compliance (including "NDAA compliant by URML"), or fitness for any purpose. Never alter the mark or combine it with another word to make a new mark.

### Withdrawal

The Licensor withdraws a certification when the registry check fails for it, when a later reproduction fails, when the attestation proves false, or when the mark is used outside these rules. Withdrawal is a public commit to the registry entry that states the reason. No right to use the mark survives it.

## What is off limits

Using "URML-Certified" for anything that is not a currently certified registry entry, or outside the rules above.

Implying URML endorsement, sponsorship, or affiliation when none exists. Neither a listing nor a certification is an endorsement of the product.

Using the URML name in a product name that suggests official status (e.g., "URML Pro", "URML Cloud", "URML Enterprise") without written permission. Product names that make the relationship factual (e.g., "Foo Robotics URML Adapter") are fine.

Modifying the URML conformance suite and continuing to claim conformance against the modified suite. "URML-compatible" and "URML-Certified" both mean passing the unmodified suite.

## What listing does not grant

A listing in the registry, [docs/compatible-runtimes.md](docs/compatible-runtimes.md), or the [Manufacturer & Product Directory](docs/manufacturers/directory.md) grants no license to use the URML or URML-Certified marks beyond the factual descriptor use above. It does not indicate URML has audited, endorsed, sponsored, or assumed responsibility for the listed product, and it does not indicate fitness for production, safety-critical, or regulated deployment. The conformance suite tests specification conformance, not fitness for any particular purpose. A validator passing a manifest under the bundled default policy is a reproducible factual result, not a certification or a compliance determination. No rights persist after delisting.

## Still to come

- Registration of the marks, starting with URML-Certified as a certification mark. Trademark counsel reviews this policy before the first certification is granted.
- A formal dispute-resolution procedure for trademark misuse.
- Hand-over of the Licensor's certification role to a foundation or steering committee once one exists.

## Reporting trademark concerns

Open an issue in the URML repository or contact the maintainer per [CONTRIBUTING.md](CONTRIBUTING.md). The maintainer commits to responding within 30 days.

## Changing this document

Material changes follow the RFC process in [docs/rfcs/0001-rfc-process.md](docs/rfcs/0001-rfc-process.md). Typo and clarification fixes go through ordinary PRs.
