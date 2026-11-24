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

# urml-iso21423-runtime

**ISO 21423 reference runtime for URML.** `Iso21423Adapter` drives industrial mobile robots that speak ISO 21423:2026 (Robotics, Industrial mobile robots, Communications and interoperability) over MQTT. No ROS 2 dependency.

> **Status: validation in progress.** This runtime is built from public material based on the **ISO/FDIS 21423** draft, not from the published ISO 21423:2026 text. We are validating it against the published standard. Until that is done, it makes **no claim of conformance to ISO 21423**, and field names or behaviour may change.

## What it does

In ISO 21423 every participant is an entity: robots (IMR), fleet managers (IMRFM) and site equipment. Each publishes its identity, capabilities and status on one MQTT broker, and any entity may send another a **request**: an ordered list of actions such as `move` or `dock`. The receiver answers with request status messages until the request SUCCEEDED, was CANCELED or ABORTED.

`Iso21423Adapter` makes URML such an entity. The URML runtime calls it only after the validator has accepted the program. Each dispatch step then becomes one request, sent to the robot or to the fleet manager that manages it. A step succeeds only when the robot's own request status says SUCCEEDED for every action.

```
URML program --validate--> URMLRuntime --> Iso21423Adapter --request (QoS 2, retained)--> robot or fleet manager
                                                 ^-------request status, identity, status, battery, odometry--'
```

## Method coverage

| URML primitive | ISO 21423 request |
|---|---|
| `move_to` | `move` to the place's point in the facility's Common Coordinate System |
| `dock` | `dock` with the service's station actions (`charge` is CHARGE, `park` is none); `until: full` waits on `batteryStatus` |
| `grasp` / `release` | `dock` with PICK / DROP at the station the robot is at |
| `measure` | battery charge, voltage, current and position from what the robot publishes |
| `call_program` | a configured vendor action, under the vendor's own format name (RFC-0015) |
| `wait` | local sleep |
| `report` | local record, no cloud |

Returned as not supported, with a reason: `detect` (so `pick_from` cannot run), `wait_for`, `scan`, `capture`, `speak`, `listen`, release `hand_to_user`. The drone trio returns `not_applicable_iso21423`.

A `move` request carries no speed limit. A step that asks for a speed runs only when the robot's rated speed, from its identity, is already within it; otherwise it is refused.

**Before a request** the adapter refuses to send if the robot has not published its identity and status, does not list the action among the requests it accepts, is not in `MODE_AUTO` or `MODE_SEMIAUTO`, reports a stop category, `LOST`, `OFFLINE` or `WAIT_FOR_RESET`, or has dropped off the broker (its `LOST_CONNECTION` will). **After sending**, a rejection comes back with the robot's own reason (for example `ACTION_NOT_IMPLEMENTED`). A request that does not finish within `request_timeout_seconds` is canceled, and every retained request the adapter sent is cleared.

## Configuration

The robot or fleet manager to address, the Common Coordinate System, where each URML location sits in it, the docks and the dock services are deployment facts. They go in an `iso21423_adapter.yaml`; see [`examples/iso21423/iso21423_adapter.yaml`](../../examples/iso21423/iso21423_adapter.yaml). To go through a fleet manager, set `target_type: IMRFM`, `target_id` to the fleet manager and `robot_id` to the robot.

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
pip install -e reference/iso21423-runtime           # hermetic: simulated robot, in-memory broker
pip install -e "reference/iso21423-runtime[mqtt]"   # real broker via paho-mqtt
python examples/iso21423/run_demo.py                # a warehouse program as ISO 21423 requests
```

## Tested

- **Hermetic suite** (`tests/`): the adapter against `SimulatedImr` on an in-memory broker that keeps retained messages. Covers every primitive, the preflight refusals, rejection reasons, timeout and cancel, disconnection through the will, a fleet manager in between, and a URML program run end to end through the validator and `URMLRuntime`.
- **Live broker** (`tests/integration/test_live_broker.py`, `URML_ISO21423_BROKER=host:port`): adapter and simulated robot on separate `paho-mqtt` connections to a real broker; a client killed outright, with the broker publishing its will. Run against Mosquitto weekly by [`iso21423-integration.yml`](../../.github/workflows/iso21423-integration.yml).
- **TLS broker** (`tests/integration/test_tls_broker.py`, `URML_MQTT_TLS_DIR`): the same checks over TLS as for the VDA 5050 runtime: a round trip, a wrong password, an untrusted CA and a wrong host name refused at connect, mutual TLS. Run by the same workflow.
- **Cross-check** (`tests/integration/test_openrobops_schemas.py`, `URML_ISO21423_SCHEMA_CHECK=1`): every message the adapter and the simulated robot publish is checked against the JSON Schemas OpenRobOps publishes for ISO 21423, downloaded at a pinned commit. This shows URML's reading of the message model agrees with another implementer's reading of the same draft. It is not validation against the published standard.
- **Not yet:** a check against the published ISO 21423:2026 text, a real robot, or a vendor's fleet manager.

## Sources

The message model was taken from public descriptions of ISO 21423: the explanatory guide and the Apache-2.0 SDK in [OpenRobOps/iso21423](https://github.com/OpenRobOps/iso21423) (InOrbit), which state that they are based on ISO/FDIS 21423, and trade press on the published standard. URML's code is its own. This repository contains no text, schema or figure from the ISO standard or its drafts, and none from the OpenRobOps schema files, which the cross-check downloads rather than copies.

## Scope

The adapter is a requester for one robot. It does not run a fleet manager, publish a robot's telemetry, do traffic management, or calibrate a Common Coordinate System from reference points: the CCS id and the coordinates of each place come from the config. Open questions are in [`SPEC-GAPS.md`](SPEC-GAPS.md).

## License

Business Source License 1.1: free for non-production use, commercial license for production (see [`LICENSING.md`](../../LICENSING.md)). `paho-mqtt` (EPL-2.0 or EDL-1.0) is an optional extra, imported lazily.

## Related

- [`/reference/vda5050-runtime/`](../vda5050-runtime/): the VDA 5050 sibling, for fleets that use a central fleet control.
- [RFC-0022](../../docs/rfcs/0022-warehouse-domain-profile.md): the warehouse profile; no new primitives were needed.
- [`examples/rulebooks/amr-template.yaml`](../../examples/rulebooks/amr-template.yaml): a site's mobile-robot safety rules (ISO 3691-4, ANSI/A3 R15.08). ISO 21423 itself contains no safety requirements.
