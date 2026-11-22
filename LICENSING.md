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

# URML Licensing

URML is source-available under the **Business Source License 1.1** (BSL). The binding text is [`LICENSE`](LICENSE). This page explains it in plain terms. If this page and `LICENSE` disagree, `LICENSE` controls.

## The short version

| You want to | License needed? |
|---|---|
| Read the spec and the code | No |
| Learn, teach, or run a university course with URML | No |
| Research, including published papers and benchmarks | No |
| Evaluate URML, build a proof of concept, run it in simulation | No |
| Develop and test your own robot software against URML | No |
| Run the conformance suite against your runtime | No |
| Use URML on a personal robot that you don't sell or offer to others | No |
| Operate robots with URML in a commercial or business setting | **Yes** |
| Ship URML inside a robot, controller, or product you sell | **Yes** (OEM) |
| Offer URML as a hosted or managed service | **Yes** |

Commercial licenses: **sales@urml.dev**

## Every release opens up after two years

Each version of URML converts automatically to the **Apache License 2.0** two years after it is first publicly released. The BSL applies only during that window.

## Earlier releases stay Apache 2.0

URML was released under the Apache License 2.0 up to and including **v0.4.x** (all source published before 2026-11-22). Those releases, and any copy of them, remain under Apache 2.0 permanently. The change applies to new versions only. The reasons are recorded in [RFC-0703](docs/rfcs/0703-bsl-relicense.md).

One correction: `urml-av-runtime` 0.4.0 was published to PyPI on 2026-11-22 with BSL metadata by mistake. Like every 0.4.x release, it is licensed under Apache 2.0. It has been yanked; use 0.5.0.

## Third-party code

Code contributed by others before the change keeps its original license. `examples/gopigo3/` is Apache 2.0, with its own [`LICENSE`](examples/gopigo3/LICENSE).

URML's optional dependencies (ROS 2, PX4, pymavlink, asyncua and others) keep their own licenses. URML's BSL does not change them.

## What counts as production

Production use is about what the robots do, not who owns them.

| Situation | License needed? |
|---|---|
| A pilot of up to 5 robots for up to 90 days in total, even if they do real work | No |
| A university teaching or research lab | No |
| Robots doing real work for a company, a non-profit or a public body | Yes |
| A university hospital's delivery fleet | Yes |
| An integrator deploying URML on a customer's robots | The customer, who operates the robots |
| Simulated robots, and spares that never run | Not counted |

**One robot** is one physical machine whose actuators are commanded by a program URML validated, translated or executed. Each drone in a swarm counts. The count is the highest number in production on any day of the month.

Not sure where your use falls? Email sales@urml.dev and describe it before you buy.

## Commercial license tiers

| Tier | Price | For |
|---|---|---|
| **Production** | $4 per robot per month | Any company running URML on robots in production. Only robots in service count. |
| **Enterprise lifetime** | $225,000 one time, plus $10,000 per year support | Perpetual license for up to 1,000 robots in service, extra robots $225 each one time; every release while support is paid; audited policy files |
| **Enterprise half** | $112,500 one time, plus $5,000 per year support | The same, for up to 500 robots. On request |
| **OEM** | Per unit, on request | Robot and controller makers embedding URML in products they ship, with redistribution rights |

Licenses: sales@urml.dev.

## Contributing

Contributions are accepted under the [Contributor License Agreement](CLA.md), which lets the Licensor offer URML under both the BSL and commercial licenses. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Trademark

The URML name and marks are covered separately by [`TRADEMARK.md`](TRADEMARK.md). The BSL grants no trademark rights.
