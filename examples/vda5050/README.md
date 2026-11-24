<p align="center">
  <a href="https://urml.dev"><img src="https://urml.dev/favicon.svg" alt="URML" width="72" height="72"></a>
</p>

# URML intent to VDA 5050 orders

The warehouse example program ([`examples/warehouse/pick-to-conveyor.urml.yaml`](../warehouse/pick-to-conveyor.urml.yaml): pick a tote from shelf A3, put it on conveyor A, report), run on a VDA 5050 mobile robot. The program and its manifest are unchanged. The only VDA 5050-specific file is the adapter config.

```
python examples/vda5050/run_demo.py
```

1. **Validate** the program against its manifest with the warehouse profile and the default policy. Nothing goes to the vehicle until the validator accepts it.
2. **Execute** it through `Vda5050Adapter` (`reference/vda5050-runtime`), which acts as fleet control for one vehicle. Each dispatch step becomes one VDA 5050 `order`.
3. **Print** every order as the vehicle received it.

Three URML steps become five orders: drive to the shelf, `detectObject`, `pick`, drive to the conveyor, `drop`. The `report` step stays local.

The vehicle here is the package's `SimulatedVehicle` on an in-memory broker, so the demo needs no robot, broker or network. To drive a real vehicle, set `broker_host` in `vda5050_adapter.yaml`, install the `[mqtt]` extra, and leave out the simulator.

The committed [`demo-output.txt`](demo-output.txt) is the recorded output. The run is deterministic and a test asserts the two are identical, so the example cannot drift from the tool.

## Files

- `vda5050_adapter.yaml`: vehicle identity, broker, the route graph (URML location name to VDA 5050 node), and the vehicle's action set.
- `run_demo.py`: the demo.
- `demo-output.txt`: its recorded output.
