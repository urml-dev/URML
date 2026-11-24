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

# URML Commercial Licensing

Status: in force from 2026-11-22.
Authority: [RFC-0703](docs/rfcs/0703-bsl-relicense.md), [RFC-0704](docs/rfcs/0704-licensor-yahalomik.md). Commercial licenses are granted by Yahalomik Ltd. (Israel). Summarizes [`LICENSE`](LICENSE) and [`LICENSING.md`](LICENSING.md) for companies. `LICENSE` controls.

## Who needs a commercial license

Any organization that uses URML in production. That means operating robots with URML in a commercial or business setting, shipping URML inside a product, or offering it as a service.

Research, teaching, evaluation, development, testing, simulation and personal projects are free under the [Business Source License 1.1](LICENSE). Each release converts to Apache 2.0 two years after it ships.

## What a commercial license includes

- The right to run URML in production on the robots and sites the license covers.
- The validator, every reference runtime, the LLM bridge and MCP server, and the conformance suite.
- The bundled US-federal default compliance policy.
- Email support. Enterprise tiers add priority email support.

## Tiers

| Tier | Price | Includes |
|---|---|---|
| **Production** | **$4 per robot per month** | Any company running URML on robots in production. Only robots in service count. Email support |
| **Enterprise lifetime** | **$225,000 one time**, plus **$10,000 per year** support | Perpetual license for up to 1,000 robots in service; extra robots $225 each, one time; every release while support is paid; audited policy files; priority email support |
| **Enterprise half** | **$112,500 one time**, plus **$5,000 per year** support | The same, for up to 500 robots. On request. Upgrade to lifetime by paying the difference |
| **OEM** | Per unit, on request | Robot and controller makers: redistribution rights in shipped products, directory listing |

What counts as production, and what counts as one robot, is in [`LICENSING.md`](LICENSING.md#what-counts-as-production). Prices may change. The signed order form sets the price.

## How to buy

**You don't need a license to try URML.** Evaluate it, build the proof of concept, run it in simulation, test it on your own robots in the lab. You need a license once URML runs robots in production.

**Not sure your use counts as production?** Email sales@urml.dev and describe it before you buy.

**Online payment is coming soon.** Until then, email sales@urml.dev and we send you an order form and an invoice.

### Production

1. Email sales@urml.dev with your company name, the number of robots that will run URML, and where they operate.
2. You receive an order form under the URML Commercial License Agreement, naming your company and the number of robots it covers.
3. Once both sides sign and the first payment is made, the license is active.
4. When your fleet grows or shrinks, email the new count. You pay only for robots in service.

### Enterprise lifetime and Enterprise half

Both are a signed contract rather than an order form. Email sales@urml.dev with your company name and the number of robots you plan to cover.

### OEM

OEM pricing depends on the product and the volume. Email sales@urml.dev with the product that will ship URML and the number of units you expect to ship each year.

## Validation services

Paid engagements, priced per engagement. Email sales@urml.dev with your site or vehicle and we send a scope and a quote.

### Fleet validation (operators)

For a site that will run AMRs or AGVs over VDA 5050. Before go-live we validate the deployment against URML:

- your URML programs against each robot's manifest, safety envelope and the active policy, including the cross-robot checks;
- the route graph and station mapping in the adapter config against the vehicles' factsheets;
- a run of the programs through `urml-vda5050-runtime` against your vehicles or your vendor's VDA 5050 simulator.

You receive a written validation report: what was checked, what passed, what was refused and why, pinned to the URML commit and the config files used. Running URML on those robots in production afterwards needs a production license; the engagement does not include one.

### Vehicle validation (AMR and AGV makers)

For a maker whose vehicle speaks VDA 5050. We run your vehicle, or your VDA 5050 simulator, against `urml-vda5050-runtime` and the conformance suite and give you:

- a written report of which URML primitives your vehicle carries out and where it diverges from VDA 5050 as URML uses it;
- the URML manifest for the vehicle, which you can ship to your customers.

This is a validation run and a report, not a certification. The **URML-Certified** mark is reserved for the Phase 4 program ([`TRADEMARK.md`](TRADEMARK.md)) and is not granted by this engagement.

A validation report records what was tested on the dates it was tested. It is not a safety assessment or a compliance determination; site safety stays with the integrator and its risk assessment.

## Other commercial offerings

- **URML-Certified** conformance program and mark (planned; see [`TRADEMARK.md`](TRADEMARK.md)).
- **Audited policy files** with third-party legal attestation, kept current.
- **Hosted services**: validation, LLM bridge, simulation. URML always runs fully offline; hosting is optional.
- **Training and certification** for teams.

## Contact

sales@urml.dev
