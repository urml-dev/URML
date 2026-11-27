---
rfc: 0709
title: The BSL Change Date moves from two years to four
author: Ido Yahalomi
state: Accepted
created: 2026-11-27
updated: 2026-11-27
amends: RFC-0703, MANIFESTO.md (License Direction note)
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

# RFC-0709: The BSL Change Date moves from two years to four

Kind: Governance. This RFC amends [RFC-0703](0703-bsl-relicense.md). It changes one parameter of URML's Business Source License 1.1, the Change Date, for versions released from now on. It changes no code and no price.

## Summary

A URML version first publicly released after this RFC is merged converts to the Apache License 2.0 four years after its release. Until now the window was two years.

Nothing already published changes. Versions 0.5.0, 0.5.1 and 0.5.2, and all source published in this repository from 2026-11-22 until this RFC is merged, were released with a two-year Change Date and keep it. Releases up to v0.4.x are Apache 2.0 already and stay so.

The other parameters stay as RFC-0703 and [RFC-0704](0704-licensor-yahalomik.md) set them: the Licensor is Yahalomik Ltd., non-production use is free, and the Change License is Apache 2.0.

## Motivation

The Change Date decides how long a version needs a commercial license for production use. After it, that version is Apache 2.0 for everyone, permanently. The Licensor cannot take a version back once it has converted.

RFC-0703 chose two years on 2026-11-22. Two things weigh against that choice. Conversion is one-way, so a short window hands each release over early and for good. And the window sets what a company gets without a license: under two years it is a version two years old, under four it is a version four years old.

The maintainer's judgment is that URML carries enough work to be paid for during the whole period the license allows. Four years is that period. Whatever date a licensor names, the BSL 1.1 converts a version on "the fourth anniversary of the first publicly available distribution of a specific version of the Licensed Work".

## Proposal

### The parameter

`LICENSE`, and its copy in `plugins/urml/LICENSE`, change from

> Change Date: Two years from the date each version of the Licensed Work is first publicly released.

to

> Change Date: Four years from the date each version of the Licensed Work is first publicly released.

followed by a sentence that keeps the two-year date for everything published with it.

### What each version gets

| Published | License now | Becomes Apache 2.0 |
|---|---|---|
| Up to v0.4.x, and source before 2026-11-22 | Apache 2.0 | Already is |
| 0.5.0, 0.5.1 and 0.5.2, and source from 2026-11-22 until this RFC is merged | BSL 1.1 | Two years after each was first published |
| Every version first released after this RFC is merged | BSL 1.1 | Four years after it is first released |

### Why the earlier versions keep two years

Each of those versions was offered to the public with a two-year Change Date in `LICENSE`, and copies of them are out. The BSL says it "applies separately for each version of the Licensed Work and the Change Date may vary for each version of the Licensed Work released by Licensor". A later version can carry a later date. A version already released cannot have its date pushed out, and this RFC does not try.

In practice the repository as it stands on the day of the merge becomes Apache 2.0 in full two years later. The four-year window covers what is written after that day.

### What does not change

The Additional Use Grant stays: research, teaching, evaluation, development, testing, simulation and personal projects are free. The Change License stays Apache 2.0. The prices and tiers in [`COMMERCIAL.md`](../../COMMERCIAL.md) and the pilot allowance in [`LICENSING.md`](../../LICENSING.md#what-counts-as-production) stay as they are.

### Package metadata

No change. The packages declare `BUSL-1.1`, an identifier that carries no Change Date. The parameters for a version are the ones in this repository's `LICENSE` at that version's release.

## Trust being spent

RFC-0703 asked what trust a license change spends, and the question applies again. This is the second change to URML's license terms in a week. On 2026-11-22 the project said each release would open after two years. Five days later the number for new releases is four. Nobody loses a right they were given, because everything published under the two-year text keeps it. What is spent is confidence that the stated terms hold still.

One fact limits how far this can go. Four years is the BSL's ceiling, so this parameter cannot be lengthened again under this license.

## Alternatives considered

- **Keep two years.** It is the friendlier term and the one announced. Rejected by the maintainer: it opens each release early, and conversion cannot be undone.
- **Three years.** A middle value with no argument of its own. The reasons for a longer window apply up to the license's limit.
- **Four years with a copyleft Change License.** The BSL allows any Change License compatible with GPL 2.0 or later. Rejected for the reason RFC-0703 gave against AGPL: robot makers ship embedded software, and copyleft terms would keep them away from converted versions too.
- **A license that never converts.** It would no longer be the BSL, and it would end the promise that every version becomes open in time. Not proposed.
- **A later date for 0.5.0 to 0.5.2 as well.** Not available. Those versions were released with two years.

## Prior art

- HashiCorp's BSL sets the Change Date at four years from publication, with MPL 2.0 as the Change License.
- CockroachDB adopted the BSL in 2019 with a three-year window and Apache 2.0 as the Change License.
- The BSL 1.1 text caps every Change Date at the fourth anniversary of a version's first public distribution.

## Implementation plan

In the pull request that carries this RFC:

- `LICENSE` and `plugins/urml/LICENSE`: the Change Date parameter.
- `LICENSING.md`: the section on conversion, with the versions that keep two years.
- `COMMERCIAL.md`, `README.md`, `reference/README.md` and `CLAUDE.md`: the sentence that states the window.
- `MANIFESTO.md` (License Direction note) and `ANNOUNCE.md`: a dated update line. The announcement itself stays as published.
- `CHANGELOG.md`: an entry under Unreleased.
- RFC-0703 records that it is amended by this RFC, and the RFC index gains this row.

In a separate pull request to `urml-dev/urml-website`: the FAQ, the pricing page and the home page, which each state the window.

## Regulatory alignment

None changes.

## Open questions

1. **Counsel review.** The sentence in `LICENSE` that keeps the two-year date for earlier versions is the maintainer's wording. Counsel should read it together with the commercial agreement.
2. **Release order.** A version released before this RFC merges carries two years. The 0.5.3 release should follow the merge if it is meant to be the first four-year version.

## Process note

The sole maintainer is a director of Yahalomik Ltd., the Licensor, which benefits from a longer window. [`GOVERNANCE.md`](../../GOVERNANCE.md) asks for a non-conflicted reviewer on such RFCs once a steering committee exists. None exists yet, so the conflict is recorded here.

Like RFC-0703, RFC-0704, RFC-0705 and RFC-0708, this RFC is accepted on merge, without the seven-day comment window RFC-0001 sets. The maintainer may hold the merge for that window.
