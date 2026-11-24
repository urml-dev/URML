# Evidence report: arducopter_delivery_quad

> Evidence of declared intent and its checks. Not a safety assessment, a certification or a compliance determination.

As of 2026-11-24 · urml-validator VERSION · profiles: drone · policy: bundled

## Summary

| Status | Items | Meaning |
|---|---|---|
| `checked` | 14 | The validator checks this before a program runs. |
| `declared` | 2 | Someone states this; URML records who and does not verify it. |
| `runtime` | 6 | The runtime must enforce this while a program runs. |
| `missing` | 4 | Something a rule, the policy or the envelope needs is absent. |
| `outside` | 12 | URML cannot see this; someone else must cover it. |

Gaps: 5 (4 missing, 1 failed check).

## Gaps

- **Provenance** `provenance.absent` (missing): The manifest declares no provenance, so no component origin is on record and the policy's provenance rules (critical_country_denylist, critical_final_assembly_denylist, covered_vendor_denylist, hbom_required_for_critical, attestation_floor) have nothing to check.
- **Rules** `rule.us_faa_part107.remote_identification` (missing): Remote identification by one of the means of 14 CFR Part 89. The deployment declares no remote_id; every program is refused until it does.
- **Programs** `validated.too-high` (checked, fail): Program too-high.urml.yaml is refused, 2 errors. envelope.altitude_exceeded: move_to.pose.z (80.0 m) exceeds the strictest altitude cap (60.0 m); envelope.geofence_violation: move_to.pose (50.0, 40.0, alt=80.0) is inside the footprint of a declared geofence but outside its altitude band (['delivery_corridor']).
- **Conformance** `conformance.failures` (missing): 1 fixture failed: drone/return_to_home_on_link_loss.
- **Conformance** `registry.tier` (missing): URML-Certified for drone expired on 2026-06-30. It certifies conformance to URML, not safety or compliance.

## Robot

| Status | Item | What the report knows |
|---|---|---|
| `checked` | `capability.mobility` | Mobility (multirotor), up to 10 m/s. The validator refuses steps faster than this or the envelope's limit. No evidence tag: the claim's source is not recorded. |
| `checked` | `capability.sensor.battery` | Sensor battery (voltage). No evidence tag: the claim's source is not recorded. |

## Provenance

| Status | Item | What the report knows |
|---|---|---|
| `missing` | `provenance.absent` | The manifest declares no provenance, so no component origin is on record and the policy's provenance rules (critical_country_denylist, critical_final_assembly_denylist, covered_vendor_denylist, hbom_required_for_critical, attestation_floor) have nothing to check. |

## Envelope

| Status | Item | What the report knows |
|---|---|---|
| `checked` | `limit.max_velocity` | The envelope limits speed to 10 m/s. The manifest allows 10 m/s; the stricter, 10 m/s, applies. |
| `checked` | `limit.max_altitude` | The envelope limits altitude to 60 m. The manifest allows 120 m; the stricter, 60 m, applies. |
| `checked` | `limit.max_payload` | The envelope limits payload to 1.5 kg. The manifest allows 1.5 kg; the stricter, 1.5 kg, applies. |
| `checked` | `limit.max_drop_height` | The envelope limits drop height to 5 m. |
| `checked` | `geofence.delivery_corridor` | Geofence delivery_corridor (frame agl, 4 vertices). Every place a program names must lie inside a declared geofence. |
| `checked` | `people_zone.footpath` | People-occupancy zone footpath (frame agl). Programs may not target places inside it. |
| `runtime` | `weather` | Weather limits are on record. The validator cannot see the weather; the runtime or the operator must check conditions before and during a run. |
| `runtime` | `link_loss.0` | On losing the command_link link, the robot must return_to_home. The validator checks the policy against the declared links; acting on a loss happens at run time. |
| `runtime` | `runtime.start_position` | Where the robot starts. The runtime must not start a program while the robot is outside every geofence, or inside a people-occupancy zone that does not allow an override. |
| `runtime` | `runtime.paths` | The path between two checked places. The runtime must keep it inside the geofences and out of the people-occupancy zones. |
| `runtime` | `runtime.unstated_speed` | The speed of a step that states none. The runtime must keep it at or below the strictest speed limit. |
| `runtime` | `runtime.emergency_stop` | On an emergency stop reported by the substrate, the runtime must stop dispatching and stop every motion it commands. The emergency stop itself is a function of the machine. |

## Rules

| Status | Item | What the report knows |
|---|---|---|
| `checked` | `rule.us_faa_part107.altitude_400ft_agl` | Maximum altitude 400 feet (121.92 m) above ground level. Checked against every program (cap). |
| `checked` | `rule.us_faa_part107.groundspeed_100mph` | Maximum groundspeed 87 knots (100 miles per hour); the stricter 44.704 m/s is used. Checked against every program (cap). |
| `checked` | `rule.us_faa_part107.over_human_beings` | No flight over human beings unless the operation meets a Subpart D category. Checked against every program (forbid_over_people). |
| `checked` | `rule.us_faa_part107.one_aircraft_per_pilot` | One unmanned aircraft at a time per remote pilot in command. Checked against every program (max_concurrent_aircraft). |
| `missing` | `rule.us_faa_part107.remote_identification` | Remote identification by one of the means of 14 CFR Part 89. The deployment declares no remote_id; every program is refused until it does. |
| `outside` | `obligation.us_faa_part107.remote_pilot_certificate` | A remote pilot certificate with a small UAS rating. The remote pilot in command holds a remote pilot certificate with a small UAS rating. Anyone else at the flight controls is under the direct supervision of that pilot, who can take direct control immediately. |
| `outside` | `obligation.us_faa_part107.visual_line_of_sight` | Visual line of sight for the whole flight. The remote pilot in command, the person at the controls and any visual observer are able to see the aircraft throughout the flight with vision unaided by any device other than corrective lenses, and either the two pilots or a visual observer keep watching it. |
| `outside` | `obligation.us_faa_part107.night_and_twilight_lighting` | Anti-collision lighting at night and in civil twilight. At night, the remote pilot in command has completed an initial knowledge test or training under 107.65 after April 6, 2021, and the aircraft shows lighted anti-collision lighting visible for at least 3 statute miles. The same lighting is required during civil twilight. |
| `outside` | `obligation.us_faa_part107.controlled_airspace_authorization` | ATC authorization in controlled airspace. Operations in Class B, Class C or Class D airspace, or within the lateral boundaries of the surface area of Class E airspace designated for an airport, have prior authorization from Air Traffic Control. |
| `outside` | `obligation.us_faa_part107.flight_visibility` | Flight visibility of at least 3 statute miles. The minimum flight visibility, observed from the control station, is at least 3 statute miles. |
| `outside` | `obligation.us_faa_part107.cloud_clearance` | At least 500 feet below and 2,000 feet horizontally from clouds. The aircraft stays at least 500 feet below clouds and at least 2,000 feet horizontally from them. |
| `outside` | `obligation.us_faa_part107.people_outside_declared_zones` | People and flight paths the validator cannot see. URML checks flight targets against the people-occupancy zones the deployment declares. People outside those zones, and the path the aircraft flies between targets, are for the remote pilot in command to watch. |

## Programs

| Status | Item | What the report knows |
|---|---|---|
| `checked, pass` | `validated.parcel-delivery` | Program parcel-delivery.urml.yaml is accepted. 1 warning: rule.declaration_missing. |
| `checked, fail` | `validated.too-high` | Program too-high.urml.yaml is refused, 2 errors. envelope.altitude_exceeded: move_to.pose.z (80.0 m) exceeds the strictest altitude cap (60.0 m); envelope.geofence_violation: move_to.pose (50.0, 40.0, alt=80.0) is inside the footprint of a declared geofence but outside its altitude band (['delivery_corridor']). |

## Conformance

| Status | Item | What the report knows |
|---|---|---|
| `declared` | `conformance.run` | The conformance report says adapter example_vendor_runtime:ExampleAdapter ran 3 fixtures: 2 passed, 1 failed. |
| `missing` | `conformance.failures` | 1 fixture failed: drone/return_to_home_on_link_loss. |
| `declared` | `registry.entry` | Registry entry example-vendor-quadrotor (listed) lists example-vendor-runtime 1.2.0 for profiles drone, last verified 2025-07-01. |
| `missing` | `registry.tier` | URML-Certified for drone expired on 2026-06-30. It certifies conformance to URML, not safety or compliance. |

## Outside URML

| Status | Item | What the report knows |
|---|---|---|
| `outside` | `outside.safety_control` | The robot's safety-related control and its safety functions (stops, speed and separation monitoring, power and force limiting), designed and validated outside URML. |
| `outside` | `outside.below_substrate` | Firmware, controllers and drivers below the substrate. |
| `outside` | `outside.site` | Wiring, guarding and the physical site. |
| `outside` | `outside.declarations` | Whether any declared item in this report is true. |
| `outside` | `outside.unmediated` | Anything a program does through a path that does not pass through a URML runtime. |

## By standard

| Standard | checked | declared | runtime | missing | outside |
|---|---|---|---|---|---|
| 14 CFR Part 107 | 4 | 0 | 0 | 0 | 7 |
| 14 CFR Part 89 | 0 | 0 | 0 | 1 | 0 |

## Inputs

| Role | Id | File | Digest |
|---|---|---|---|
| manifest | arducopter_delivery_quad | parcel-delivery.manifest.yaml | `sha256:2be728c3130b9a6a210fed037964bbf39901bb673c9e9c2fb8287d6428a85383` |
| envelope | parcel_delivery_test | parcel-delivery.envelope.yaml | `sha256:35081612e6f9ddde40144f5a918c64f248a7f89d9bd8946ea04b86a5342a5c01` |
| policy | urml_us_federal_default | bundled | `sha256:281e91ec5795a8d27cf029bb641704642eb8fb9e6dbb258ebbe2879ff960c4aa` |
| rulebook | us_faa_part107 | bundled | `sha256:031f6907896cf0f898826e21636fe071e8c88f2e78b3d4b7a8191b16c4d563f1` |
| program |  | parcel-delivery.urml.yaml | `sha256:eaa34c716aa5fea7afd850335ee302504e3968f19078ff958a8ffb031900a8ee` |
| program |  | too-high.urml.yaml | `sha256:5aa895e48e03f4276cc59ccf4642882e366330dd1662f0de680aca18f58c0424` |
| conformance_report | example_vendor_runtime:ExampleAdapter | conformance-report.json | `sha256:b902c8e6947bec44a3389363679d4186a0863ac5c4b23acc8d034248f3977c21` |
| registry_entry | example-vendor-quadrotor | registry-entry.yaml | `sha256:704d862df5761d12d503c2511efeea3930ff98761e38fe3d2d3560c75eee21a5` |

Rebuild this report from the same files with `urml evidence build` and the same `--as-of` date, and compare digests.
