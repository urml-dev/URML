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

# `examples/vendor-manifests/`: vendor manifest demo runner

The conformance suite carries capability manifests shaped like real industrial products. This directory has one script that picks one of them and runs its conformance fixture on the mock adapter. No ROS, no hardware, no network.

**The URML project wrote every manifest here from the vendor's public documentation. No vendor named on this page has reviewed, supplied or endorsed its manifest, and none is a partner of the project.** A name says which product a manifest is shaped like. A vendor that wants its entry corrected or removed can open an issue.

## The fourteen entries

| Kind | Vendors |
|---|---|
| Arms | Yaskawa, Universal Robots, KUKA, Stäubli, Mitsubishi MELFA, FANUC, Kawasaki, Denso |
| Parts (declared in the manifest, not driven) | SCHUNK, Ouster, SICK, Festo, Zivid, Hokuyo |

The suite holds more vendor-shaped fixtures than these fourteen. They are in [`conformance/fixtures/industrial/`](../../conformance/fixtures/industrial/), and `urml conformance run` exercises all of them.

## Quick start

```bash
# Set PYTHONPATH so the validator, conformance and runtime packages resolve.
# Windows PowerShell:
$env:PYTHONPATH = "reference/validator/src;reference/ros2-runtime/src;conformance/src"
# Linux / macOS:
export PYTHONPATH=reference/validator/src:reference/ros2-runtime/src:conformance/src

# List the entries:
python examples/vendor-manifests/demo.py --list

# Run the conformance fixture for one of them:
python examples/vendor-manifests/demo.py --vendor yaskawa
python examples/vendor-manifests/demo.py --vendor ur
python examples/vendor-manifests/demo.py --vendor ouster
```

With the packages installed (`python bootstrap.py`), the `PYTHONPATH` line is not needed.

## What a run shows

Each run loads the named fixture from `conformance/fixtures/industrial/`, resolves its manifest from the `MANIFEST_REGISTRY`, runs the validator and the executor through `ConformanceRunner` against `MockROSAdapter`, and prints the audit trace. A passing run means three things.

1. The manifest validates against the schema.
2. The validator's passes accept the program under the bundled US-federal default policy ([RFC-0004](../../docs/rfcs/0004-compliance-policy.md)). Each manifest declares provenance that the policy allows.
3. The same mock adapter that runs the rest of the suite runs this fixture, with no vendor-specific code path.

## What a run does not show

- It does not exercise the vendor's driver or SDK, and it is not a hardware claim. The project has not run URML on any of these products.
- It does not certify anything. Certification is a separate, opt-in path that a runtime's maintainer starts ([RFC-0014](../../docs/rfcs/0014-substrate-conformance.md), [RFC-0705](../../docs/rfcs/0705-urml-certified.md)).
- It says nothing about a relationship between URML and the vendor. There is none.
