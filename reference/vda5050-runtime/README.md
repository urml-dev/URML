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

# urml-vda5050-runtime

**VDA 5050 reference runtime for URML.** `Vda5050Adapter` drives AMRs and AGVs that speak [VDA 5050](https://github.com/VDA5050/VDA5050), the open interface between a fleet control and mobile robots, over MQTT. No ROS 2 dependency.

## What it does

In VDA 5050 the fleet control owns the route graph. It sends each vehicle an `order` (a path of nodes and edges, with actions on them) and reads progress from the vehicle's `state`. This adapter plays the fleet control for one vehicle. The URML runtime calls it only after the validator has accepted the program; each dispatch step then becomes one order. A step succeeds only when the vehicle's own state says the order reached its last node and every action is `FINISHED`.

```
URML program --validate--> URMLRuntime --> Vda5050Adapter --order / instantActions--> vehicle
                                                 ^------------------state---------------'
```

It targets VDA 5050 **3.0.0** (2026-03-18). `protocol_version` and `interface_name` in the config set the topic prefix for 2.x vehicles; the message shape is 3.0.0's, which 2.x vehicles have not been tested against.

## Method coverage

| URML primitive | VDA 5050 |
|---|---|
| `move_to` | an order along the shortest configured route from the vehicle's `lastNodeId`; URML `speed` caps each edge's `maximumSpeed` |
| `dock` | an order to the station ending in the service's action (`charge` is `startCharging`, `park` is none); `until: full` waits on `powerSupply.stateOfCharge` |
| `grasp` / `release` (and so `pick_from` / `place_at`) | `pick` / `drop` at the current node, with its `stationName` / `stationType` and the object class as `loadType` |
| `detect` | `detectObject` at the current node, when the vehicle declares it |
| `measure` | a fresh `state`: `battery`, `voltage`, `current`, `position` |
| `call_program` | a configured vendor action (RFC-0015) |
| `wait` | local sleep (the vehicle holds at its node) |
| `report` | local record, no cloud |

Returned as not supported, with a reason: `wait_for` (the vehicle interface carries no external events), `scan`, `capture`, `speak`, `listen`, release `hand_to_user`. The drone trio returns `not_applicable_vda5050`.

**Before every order** the adapter asks for a fresh state (`stateRequest`) and refuses to send if the vehicle is not in an operating mode that accepts orders, has an active emergency stop, reports an `URGENT` / `CRITICAL` / `FATAL` error, is still running an order, or stands on a node the config does not know. (A vehicle that ignores `stateRequest` still works, but each step then waits `state_timeout_seconds` before the adapter falls back to the last state it received.) **After sending** it reports a vehicle rejection with the vehicle's own error type (for example `INVALID_ORDER_ACTION`). When an order does not finish within `order_timeout_seconds`, it sends `cancelOrder` before reporting the failure.

## Configuration

Node ids, edges, stations and the vehicle's action set are deployment facts, so they live in a `vda5050_adapter.yaml` next to the URML artifacts, not in the program or manifest. See [`examples/vda5050/vda5050_adapter.yaml`](../../examples/vda5050/vda5050_adapter.yaml) for a commented example. `supported_actions` is the vehicle factsheet's `protocolFeatures.agvActions`; an action outside it is refused before anything is sent.

### Broker security

To reach a broker that is not on this machine, give the connection TLS and credentials in the adapter config:

```yaml
broker_host: broker.site.example
broker_port: 8883
broker_tls:
  ca_file: certs/broker-ca.pem       # omit to trust the system store
  client_cert_file: certs/urml.pem   # optional: mutual TLS, give both or neither
  client_key_file: certs/urml.key
broker_username: urml-fleet
broker_password_env: URML_BROKER_PASSWORD   # the variable that holds the password
```

TLS is 1.2 or newer, and the broker's certificate and host name are always checked; there is no switch to turn either off. The password is read from the named environment variable when the adapter connects and never appears in the config. Relative certificate paths resolve against the config file's folder. The adapter connects only once the broker accepts: a wrong password or a failed certificate check is a `ConnectionError` at connect, not a later timeout. Without `broker_tls`, a connection to a broker on another host still works, in clear text, with a warning. Where this fits in a site's IEC 62443 zones and conduits: [`docs/security/iec-62443.md`](../../docs/security/iec-62443.md).

## Install and run

```bash
pip install -e reference/vda5050-runtime          # hermetic: simulated vehicle, in-memory broker
pip install -e "reference/vda5050-runtime[mqtt]"  # real broker via paho-mqtt
python examples/vda5050/run_demo.py               # the warehouse example as VDA 5050 orders
```

```python
from urml_vda5050_runtime import Vda5050Adapter, load_vda5050_config

config = load_vda5050_config("vda5050_adapter.yaml")
with Vda5050Adapter(config) as amr:          # connects to config.broker_host
    print(amr.send_navigation_goal(location="shelf_a3"))
```

## Tested

- **Hermetic suite** (`tests/`): the adapter against `SimulatedVehicle` on an `InMemoryBroker`. Every message either side publishes is validated against the official VDA 5050 JSON schemas for 3.0.0, as upstream maintains them on its `main` branch ([`tests/vda5050_schemas/`](tests/vda5050_schemas/), MIT, pinned to a commit). Includes the repository's unchanged warehouse example run end to end through the validator and `URMLRuntime`, and a validator rejection that sends nothing to the vehicle.
- **Live broker** (`tests/integration/`, `URML_VDA5050_BROKER=host:port`): adapter and simulated vehicle on separate `paho-mqtt` connections to a real Mosquitto 2.0 broker. Run weekly by [`vda5050-integration.yml`](../../.github/workflows/vda5050-integration.yml).
- **TLS broker** (`tests/integration/test_tls_broker.py`, `URML_MQTT_TLS_DIR`): against a broker with TLS and a password and with client certificates: a message round trip, a wrong password refused at connect, a broker signed by another CA refused, a host name the certificate does not carry refused, mutual TLS with and without a client certificate. Run by the same workflow, with certificates from [`mqtt_tls_fixture.sh`](../../tools/scripts/mqtt_tls_fixture.sh).
- **Not yet:** a real vendor vehicle, or a vendor's VDA 5050 simulator. The vehicle on the other side of every test is this package's own simulator, which follows the protocol rules a fleet control depends on but is not a vehicle model.

## Scope

One order per dispatch step, fully released, no horizon. That is enough to drive a vehicle through a URML program; it is not traffic management. Multi-vehicle deconfliction, horizon streaming and order updates belong to a fleet manager (openTCS, Open-RMF, a vendor fleet manager). URML's own cross-robot checks (RFC-0286, RFC-0291) run in the validator before anything is sent, and a site's mobile-robot rules (after ISO 3691-4 and ANSI/A3 R15.08) load as a rulebook: start from [`examples/rulebooks/amr-template.yaml`](../../examples/rulebooks/amr-template.yaml). Open questions are recorded in [`SPEC-GAPS.md`](SPEC-GAPS.md).

**ISO 21423:2026** (industrial mobile robot communications and interoperability) has its own runtime, [`iso21423-runtime`](../iso21423-runtime/), because its model differs: every participant publishes its own state and any one may send another a request. That runtime is built from public material based on the standard's draft, and its validation against the published standard is in progress.

## License

Business Source License 1.1: free for non-production use, commercial license for production (see [`LICENSING.md`](../../LICENSING.md)). `paho-mqtt` (EPL-2.0 or EDL-1.0) is an optional extra, imported lazily. The VDA 5050 schemas in `tests/vda5050_schemas/` are MIT-licensed test fixtures and are not shipped in the wheel.

## Related

- [RFC-0022](../../docs/rfcs/0022-warehouse-domain-profile.md): the warehouse profile; no new primitives were needed.
- [`/reference/opcua-runtime/`](../opcua-runtime/): the zero-ROS sibling whose structure this mirrors.
