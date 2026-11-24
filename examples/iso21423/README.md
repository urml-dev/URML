<p align="center">
  <a href="https://urml.dev"><img src="https://urml.dev/favicon.svg" alt="URML" width="72" height="72"></a>
</p>

# URML intent to ISO 21423 requests

> **Status: validation in progress.** The ISO 21423 runtime is built from public material based on the ISO/FDIS 21423 draft. We are validating it against the published ISO 21423:2026; until that is done it makes no claim of conformance.

A warehouse program ([`aisle-run.urml.yaml`](aisle-run.urml.yaml): go to shelf A3, then the conveyor, then dock to charge, and report), run on a mobile robot that speaks ISO 21423. The robot's manifest is the repository's warehouse example, unchanged.

```
python examples/iso21423/run_demo.py
```

1. **Validate** the program against the manifest with the warehouse profile and the default policy. Nothing goes to the robot until the validator accepts it.
2. **Execute** it through `Iso21423Adapter` (`reference/iso21423-runtime`). Each dispatch step becomes one ISO 21423 request, published to the robot's request topic.
3. **Print** each request and the robot's final request status.

Four URML steps become three requests: two `move` requests and a `dock` request with the CHARGE station action. The `report` step stays local.

The robot is the package's `SimulatedImr` on an in-memory broker, so the demo needs no robot or broker. To drive a real robot, set `broker_host` and the UUIDs in `iso21423_adapter.yaml` and install the `[mqtt]` extra.

The committed [`demo-output.txt`](demo-output.txt) is the recorded output; a test asserts the two are identical.

## Files

- `iso21423_adapter.yaml`: the adapter's and the robot's entity UUIDs (random), the Common Coordinate System, each place's point in it, the docks and the dock services.
- `aisle-run.urml.yaml`: the program.
- `run_demo.py`, `demo-output.txt`: the demo and its recorded output.
