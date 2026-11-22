---
rfc: 0703
title: Relicense URML under the Business Source License 1.1
author: Ido Yahalomi (ido@beamdesk.space)
state: Accepted
created: 2026-11-22
updated: 2026-11-22
supersedes: CORE_COMMITMENT.md, RFC-0672
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

# RFC-0703: Relicense URML under the Business Source License 1.1

Kind: Governance. This RFC changes the license of new URML versions from Apache 2.0 to the Business Source License 1.1, retires the Core Commitment, and moves the project to the `urml-dev` GitHub organization.

## Summary

From 2026-11-22, new URML source and every release after v0.4.x are licensed under the **Business Source License 1.1**:

- **Licensor:** Ido Yahalomi.
- **Additional Use Grant:** non-production use is free, including research, teaching, evaluation, development, testing, simulation and personal projects.
- **Change Date:** two years after each version is first publicly released.
- **Change License:** Apache License 2.0.

Production use by an organization requires a commercial license (sales@urml.dev). Releases up to and including v0.4.x stay Apache 2.0 permanently.

## Motivation

URML needs a sustainable maintainer. The Core Commitment assumed revenue would come from services around an Apache-2.0 core, with a foundation taking over the standard later. In practice, the companies that gain the most from URML are robot makers and fleet operators running it in production, and the core is exactly what they use. Paying for the core is the clearest way to fund the validator, the runtimes and the compliance policy work that those companies depend on.

The BSL keeps the source public, keeps research and evaluation free, and returns every release to Apache 2.0 after two years.

## What this RFC changes

1. `LICENSE` becomes the BSL 1.1 text with the parameters above. [`LICENSING.md`](../../LICENSING.md) explains it in plain terms.
2. [`CORE_COMMITMENT.md`](../../CORE_COMMITMENT.md) is superseded. It stays in the repository, marked superseded, as a record.
3. [`COMMERCIAL.md`](../../COMMERCIAL.md) describes the commercial license tiers instead of the earlier open-core boundary (RFC-0672).
4. Contributions move from DCO-only to a [Contributor License Agreement](../../CLA.md). DCO sign-off remains as a record of provenance.
5. Package metadata (`pyproject.toml`, `package.xml`, `setup.py`) declares `BUSL-1.1`.
6. The canonical repository moves from `URML-MARS/URML` (the earlier organization) to `urml-dev/URML`.

## Alternatives considered

- **Keep Apache 2.0 and sell only services.** This leaves the core that production users depend on without a funding source.
- **AGPL plus a commercial license.** Robot makers ship embedded software, and AGPL obligations would block adoption more than a time-limited BSL.
- **Fully proprietary.** This would end public review of the validator, which URML's safety claims rely on.

## Trust being spent

The Core Commitment asked that any removal RFC state what community trust it spends. This change reverses a public promise that the spec, conformance suite, ROS 2 and PX4 runtimes, validator, prompt contract and default policy would stay Apache 2.0 forever. Anyone who relied on that promise keeps every release up to v0.4.x under Apache 2.0. New releases become Apache 2.0 two years after they ship.

## Contributions from others

At the time of this RFC, one external contributor had merged code: two commits to `examples/gopigo3/gopigo3_adapter.py`. That directory stays Apache 2.0 under its own `LICENSE`.

## Process note

[`CORE_COMMITMENT.md`](../../CORE_COMMITMENT.md) set a 30-day public draft period for changes. The sole maintainer accepted this RFC without that period, as part of moving the project to a new organization. This is recorded here so the decision history stays accurate.
