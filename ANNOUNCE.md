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

# URML is now commercially licensed

Starting with v0.5.0, URML is licensed under the Business Source License 1.1, with a commercial license for production use. The source stays public. Learning, research, evaluation, development and simulation stay free. Running URML on robots in production now needs a commercial license, which starts at $4 per robot per month.

## What URML is

URML is a small, human-readable language for robot intent. You write down what should happen, and URML checks the program against what the robot can actually do before anything moves. Ask a 100 N gripper for a 250 N grasp, or send a waypoint outside the geofence, and the program is refused on paper. The error that comes back is specific enough for a language model to fix its own program.

URML sits above ROS 2, PX4, OPC UA and vendor SDKs, and runs on whichever one your robot already uses.

## What changed

| | Up to v0.4.x | v0.5.0 and later |
|---|---|---|
| License | Apache 2.0 | BSL 1.1 |
| Source code | Public | Public |
| Research, teaching, evaluation, development, simulation | Free | Free |
| Production use by a business | Free | Commercial license |
| Becomes Apache 2.0 | Already is | Two years after each release |

Every release up to v0.4.x stays Apache 2.0 permanently. If you depend on one of them, nothing changes for you.

The repository also moved, from `URML-MARS/URML` to [`urml-dev/URML`](https://github.com/urml-dev/URML).

## Why

URML has one maintainer: me. The companies that get the most out of it are robot makers and fleet operators running it in production, and what they run is the core: the validator, the reference runtimes and the compliance policy. Charging those companies for production use is the most direct way to keep that core maintained.

This breaks a promise. The Core Commitment said the spec, the validator, the ROS 2 and PX4 runtimes and the default policy would stay Apache 2.0 forever. For new releases, that is no longer true. [RFC-0703](docs/rfcs/0703-bsl-relicense.md) records the decision, the alternatives I rejected and the trust it costs. Two things limit the damage: earlier releases keep their Apache license, and every new release turns into Apache 2.0 two years after it ships.

I also looked at AGPL with a commercial option. Robot makers ship embedded software, and AGPL obligations would stop them from adopting URML at all. Going fully proprietary would end public review of the validator, and URML's safety claims depend on that review.

## Do you need a license?

If you operate robots with URML in a commercial or business setting, ship URML inside a product, or offer it as a service: yes.

If you are learning, teaching, researching, evaluating, building a proof of concept, testing, simulating, or running a personal robot you don't sell: no. The full table is in [`LICENSING.md`](LICENSING.md).

| Tier | Price |
|---|---|
| Production | $4 per robot per month, counting only robots in service |
| Enterprise lifetime | $225,000 once for up to 1,000 robots, plus $10,000 per year for support |
| OEM | Per unit, on request |

[How to buy](COMMERCIAL.md#how-to-buy) is a short email to sales@urml.dev.

## Try it

No license, no API key, no robot:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install urml-validator urml-llm-bridge
urml init my-robot --profile home && cd my-robot
urml validate program.urml.yaml \
    --manifest manifest.yaml --envelope envelope.yaml --profile home --no-policy
```

`--no-policy` skips the US-federal compliance pass so you see the language on its own. Drop the flag to turn the compliance pass back on.

## Contributing

Contributions now come in under a [Contributor License Agreement](CLA.md), which you sign once. It lets the project offer both the BSL and commercial licenses. Everything else in [`CONTRIBUTING.md`](CONTRIBUTING.md) is unchanged.

Questions about the change go in [GitHub Discussions](https://github.com/urml-dev/URML/discussions). Questions about a license go to sales@urml.dev.

Ido Yahalomi
