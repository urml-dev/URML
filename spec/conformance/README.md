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

# Substrate Conformance

**Status:** Normative. The current specification is [`v0.2.0.md`](v0.2.0.md):
the six-clause contract a runtime MUST satisfy to be **URML-compatible**, the two
conformance tiers (self-reported and URML-Certified), and the normative
spec-gap loop. Specified by [RFC-0014](../../docs/rfcs/0014-substrate-conformance.md); the
certified tier by [RFC-0705](../../docs/rfcs/0705-urml-certified.md). [`v0.1.0.md`](v0.1.0.md) is
the previous version.

## Purpose

Layers 1–4 define what URML *is*; this layer defines what it means for a
*runtime* to correctly run it. "URML-compatible" was previously folklore — a
runtime felt compatible if it resembled the ROS 2 reference runtime. This
document makes the contract explicit and testable, so the universality claim is
provable and the *URML-Certified* mark has a specification to certify against.

## The two halves

- **The written contract** is [`v0.2.0.md`](v0.2.0.md) (this directory): the
  rationale and the human-readable obligations.
- **The executable contract** is the [conformance suite](../../conformance/):
  the freely runnable tests whose passing is clause 6 of the contract. Both are
  BSL 1.1 (see [`LICENSING.md`](../../LICENSING.md)); running them is free.

A runtime declares the spec versions and profiles it passes in its own
`CONFORMANCE.md` (the self-reported tier).
