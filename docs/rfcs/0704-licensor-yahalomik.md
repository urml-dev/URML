---
rfc: 0704
title: Yahalomik Ltd. becomes the URML Licensor
author: Ido Yahalomi (ido@beamdesk.space)
state: Accepted
created: 2026-11-22
updated: 2026-11-22
amends: RFC-0703
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

# RFC-0704: Yahalomik Ltd. becomes the URML Licensor

Kind: Governance. This RFC amends [RFC-0703](0703-bsl-relicense.md). Ido Yahalomi assigns all rights in URML to Yahalomik Ltd., an Israeli company, which becomes the Licensor under the Business Source License 1.1 and the party to every commercial license. No user loses any right.

## Summary

- **New Licensor:** Yahalomik Ltd., incorporated in Israel, company number 517379111.
- **Mechanism:** a written IP assignment from Ido Yahalomi to Yahalomik Ltd., approved by its sole director and sole shareholder under the Israeli Companies Law. The assignment is made without payment, as a contribution to the company's capital.
- **Effective:** 2026-11-22, the date the assignment was signed and the approving resolution adopted.
- **Unchanged:** the BSL parameters from RFC-0703 (non-production use free, two-year Change Date, Apache 2.0 as Change License), the Apache 2.0 status of every release up to v0.4.x, and the prices in [`COMMERCIAL.md`](../../COMMERCIAL.md).

## Motivation

RFC-0703 named Ido Yahalomi personally as Licensor. That leaves one person as the seller of every commercial license and the defendant in any claim about software that commands physical machines. A company is the normal holder for both roles. It can sign contracts, carry insurance, hold the trademark and later assign the standard to a foundation without a personal estate in the chain.

## What this RFC changes

1. [`LICENSE`](../../LICENSE): the Licensor and the copyright line name Yahalomik Ltd. The Licensed Work's name is corrected from "Universal Robot Markup Language" to "Universal Robot Language", the name used everywhere else.
2. [`CLA.md`](../../CLA.md): "Licensor" means Yahalomik Ltd. and any entity it assigns URML to. Agreements already signed stay valid, because they already covered assignees of Ido Yahalomi.
3. [`COMMERCIAL.md`](../../COMMERCIAL.md) and [`LICENSING.md`](../../LICENSING.md): commercial licenses are granted by Yahalomik Ltd.
4. [`GOVERNANCE.md`](../../GOVERNANCE.md): the disclosed-affiliations line names Yahalomik Ltd. and the maintainer's role in it.
5. [`CLAUDE.md`](../../CLAUDE.md): the structural-separation paragraph records that URML's rights, including its unregistered trademark rights, are held by Yahalomik Ltd. and stay assignable to a future foundation.

## Existing grants

Every license granted before the assignment survives it, and Yahalomik Ltd. honors each one as Licensor:

| Release | License | After this RFC |
|---|---|---|
| Up to v0.4.x, and `urml-av-runtime` 0.4.0 | Apache 2.0 | Unchanged, permanent |
| v0.5.0, Licensor Ido Yahalomi in its `LICENSE` | BSL 1.1 | Same terms and Change Date. Yahalomik Ltd. holds the Licensor's rights by assignment |
| Releases after the assignment | BSL 1.1 | Name Yahalomik Ltd. as Licensor |

## Alternatives considered

- **Keep the founder as Licensor.** This keeps personal liability for every commercial license and makes a later transfer to a foundation depend on one person.
- **A Delaware C-corporation.** It fits the US-domiciled foundation target in [`CLAUDE.md`](../../CLAUDE.md) and US investors. Yahalomik Ltd. exists today. A later move to a US parent company stays possible and would be its own RFC.

## Regulatory alignment

The Licensor's domicile does not change URML's regulatory alignment. The bundled default policy stays aligned with enacted US federal law under [RFC-0003](0003-us-alignment.md).

## Trust being spent

None for users: no right under Apache 2.0, the BSL or a commercial license is narrowed. The change is disclosed here and in `GOVERNANCE.md` so readers can see who holds the project.

## Process note

The sole maintainer is also a director of Yahalomik Ltd., so this RFC benefits a maintainer's commercial entity. [`GOVERNANCE.md`](../../GOVERNANCE.md) requires a non-conflicted reviewer for such RFCs once a steering committee exists. None exists yet, so this conflict is recorded here.
