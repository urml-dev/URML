# Evidence report: warehouse_amr_1

> Evidence of declared intent and its checks. Not a safety assessment, a certification or a compliance determination.

As of 2026-11-24 · urml-validator 0.5.3 · profiles: warehouse · policy: bundled

## Summary

| Status | Items | Meaning |
|---|---|---|
| `checked` | 21 | The validator checks this before a program runs. |
| `declared` | 9 | Someone states this; URML records who and does not verify it. |
| `runtime` | 4 | The runtime must enforce this while a program runs. |
| `missing` | 1 | Something a rule, the policy or the envelope needs is absent. |
| `outside` | 15 | URML cannot see this; someone else must cover it. |

Gaps: 2 (1 missing, 1 failed check).

## Gaps

- **Rules** `rule.hall_2_safety.speed_monitoring_declared` (missing): Safety-rated speed monitoring is declared and meets its requirement. The deployment declares no speed_monitoring_safety_level; every program is refused until it does.
- **Programs** `validated.pick-to-conveyor` (checked, fail): Program pick-to-conveyor.urml.yaml is refused, 1 error. rule.declaration_missing: ISO 13849-1:2023, IEC 62061:2021 or IEC 61508:2010, clause n.n (from a licensed copy); the machine's risk assessment: safety-rated speed monitoring is declared and meets its requirement. The deployment declares no speed_monitoring_safety_level (allowed: PLd, PLe, SIL2, SIL3, SIL4).

## Robot

| Status | Item | What the report knows |
|---|---|---|
| `checked` | `capability.mobility` | Mobility (differential), up to 1.5 m/s. The validator refuses steps faster than this or the envelope's limit. No evidence tag: the claim's source is not recorded. |
| `checked` | `capability.gripper.robotiq_2f85` | Gripper robotiq_2f85 (servo_electric), 1 to 235 N. The validator refuses grasps above the maximum or the envelope's limit. No evidence tag: the claim's source is not recorded. |
| `checked` | `capability.camera.front_rgbd` | Camera front_rgbd. Capture steps must name a declared camera. No evidence tag: the claim's source is not recorded. |
| `checked` | `capability.sensor.front_lidar` | Sensor front_lidar (distance). No evidence tag: the claim's source is not recorded. |
| `checked` | `capability.sensor.battery` | Sensor battery (voltage). No evidence tag: the claim's source is not recorded. |

## Provenance

| Status | Item | What the report knows |
|---|---|---|
| `declared` | `provenance.attestation` | Manifest attestation: self_declared. |
| `declared` | `component.amr_base` | Component amr_base (critical): vendor clearpath, origin CA, final assembly CA. |
| `declared` | `component.arm_controller` | Component arm_controller (critical): vendor universal_robots, origin DK, final assembly DK. |
| `declared` | `component.gripper` | Component gripper (non_critical): vendor robotiq, origin CA, final assembly CA. |
| `declared` | `component.head_camera` | Component head_camera (critical): vendor intel, origin US, final assembly US. |
| `declared` | `component.front_lidar` | Component front_lidar (critical): vendor ouster, origin US, final assembly US. |
| `checked, pass` | `policy_rule.critical_country_denylist` | Policy rule critical_country_denylist: passed. |
| `checked, pass` | `policy_rule.critical_final_assembly_denylist` | Policy rule critical_final_assembly_denylist: passed. |
| `checked, pass` | `policy_rule.covered_vendor_denylist` | Policy rule covered_vendor_denylist: passed. |
| `checked, pass` | `policy_rule.hbom_required_for_critical` | Policy rule hbom_required_for_critical: passed. |
| `checked, pass` | `policy_rule.attestation_floor` | Policy rule attestation_floor: 1 finding (warning). Self-declared provenance accepted in v0.1 but flagged. v0.2 will promote this to an error; deployments should arrange third-party attestation now. |

## Envelope

| Status | Item | What the report knows |
|---|---|---|
| `checked` | `limit.max_velocity` | The envelope limits speed to 1 m/s. The manifest allows 1.5 m/s; the stricter, 1 m/s, applies. |
| `checked` | `limit.max_payload` | The envelope limits payload to 50 kg. |
| `checked` | `limit.max_grip_force_n` | The envelope sets no grip force limit; the manifest's 235 N applies. |
| `checked` | `geofence.hall_2` | Geofence hall_2 (frame site, 4 vertices). Every place a program names must lie inside a declared geofence. |
| `checked` | `people_zone.break_area` | People-occupancy zone break_area (frame site). Programs may not target places inside it. |
| `runtime` | `runtime.start_position` | Where the robot starts. The runtime must not start a program while the robot is outside every geofence, or inside a people-occupancy zone that does not allow an override. |
| `runtime` | `runtime.paths` | The path between two checked places. The runtime must keep it inside the geofences and out of the people-occupancy zones. |
| `runtime` | `runtime.unstated_speed` | The speed of a step that states none. The runtime must keep it at or below the strictest speed limit. |
| `runtime` | `runtime.emergency_stop` | On an emergency stop reported by the substrate, the runtime must stop dispatching and stop every motion it commands. The emergency stop itself is a function of the machine. |

## Rules

| Status | Item | What the report knows |
|---|---|---|
| `checked` | `rule.hall_2_amr_rules.max_travel_speed` | Maximum travel speed a program may request. Checked against every program (cap). |
| `checked` | `rule.hall_2_amr_rules.outside_operating_zones` | Programs never send a robot outside its operating zones. Checked against every program (forbid_zone_entry). |
| `checked` | `rule.hall_2_amr_rules.load_handling_at_stations_only` | Loads are picked and placed only at designated stations. Checked against every program (forbid_primitive). |
| `checked` | `rule.hall_2_amr_rules.validated_programs_only` | Only robot programs covered by the risk assessment run. Checked against every program (forbid_primitive). |
| `checked` | `rule.hall_2_amr_rules.safety_outputs_untouched` | Programs never write safety-related output lines. Checked against every program (forbid_primitive). |
| `outside` | `obligation.hall_2_amr_rules.risk_assessment` | A current risk assessment for the mobile robot system. The site has a risk assessment that covers every route, station and task these programs use, repeated whenever the layout, the fleet or the tasks change. |
| `outside` | `obligation.hall_2_amr_rules.safety_rated_functions` | Personnel detection and stopping in safety-rated control. Personnel detection, speed control near people, braking and emergency stop run in the robot's safety-rated hardware and software, at the performance levels the standards require, not in URML and not in the fleet manager. |
| `outside` | `obligation.hall_2_amr_rules.zones_marked_and_declared` | Operating and restricted zones are marked on site and match the manifest. The zones the risk assessment defines are marked on the floor or otherwise identified, and the declared_areas in each robot's manifest are drawn to match them. |
| `outside` | `obligation.hall_2_amr_rules.system_validation` | The installed system is verified and validated before use. The integrator verifies and validates the safety functions of the installed mobile robot system before the site runs production programs. |
| `outside` | `obligation.hall_2_amr_rules.users_trained` | People who work near the robots are trained and informed. The site operator trains the people who work with or near the robots, keeps the information for use current, and keeps zones clear as the risk assessment requires. |
| `declared` | `rule.hall_2_safety.emergency_stop_declared` | The emergency stop's safety level is declared and meets its requirement. Declared emergency_stop_safety_level: PLd, by hall_2_safety_declarations. URML checks the declaration is there and allowed, not that it is true. |
| `declared` | `rule.hall_2_safety.protective_stop_declared` | The protective stop's safety level is declared and meets its requirement. Declared protective_stop_safety_level: SIL2, by hall_2_safety_declarations. URML checks the declaration is there and allowed, not that it is true. |
| `missing` | `rule.hall_2_safety.speed_monitoring_declared` | Safety-rated speed monitoring is declared and meets its requirement. The deployment declares no speed_monitoring_safety_level; every program is refused until it does. |
| `declared` | `rule.hall_2_safety.safety_validation_on_record` | The safety functions' validation is on record. Declared safety_validation_record: VAL-2026-017, by hall_2_safety_declarations. URML checks the declaration is there and allowed, not that it is true. |
| `outside` | `obligation.hall_2_safety.urml_is_not_a_safety_function` | Nothing in URML counts toward a performance level or a SIL. The URML validator and runtimes are not safety-related parts of the control system. They are left out of every performance level and safety integrity level calculation, and no safety function depends on them. |
| `outside` | `obligation.hall_2_safety.urml_cannot_interfere` | URML cannot interfere with safety-related software. If URML runs on hardware that also runs safety-related software, the integrator shows that URML cannot interfere with it, or treats URML as safety-related, which URML does not support. The simpler design keeps URML on separate hardware. |
| `outside` | `obligation.hall_2_safety.safety_functions_designed` | Each safety function is designed to its required level. Each safety function the risk assessment calls for is specified, designed and implemented in safety-related control to reach its required performance level or safety integrity level. |
| `outside` | `obligation.hall_2_safety.safety_functions_validated` | Each safety function is validated. The safety functions are validated before use, and again after any change to the safety-related control, and the validation record is kept. |
| `outside` | `obligation.hall_2_safety.declarations_kept_true` | The declarations match the validation records. The operator keeps the deployment rulebook's declarations in line with the current validation records, and updates them when the safety functions or their validation change. |

## Programs

| Status | Item | What the report knows |
|---|---|---|
| `checked, fail` | `validated.pick-to-conveyor` | Program pick-to-conveyor.urml.yaml is refused, 1 error. rule.declaration_missing: ISO 13849-1:2023, IEC 62061:2021 or IEC 61508:2010, clause n.n (from a licensed copy); the machine's risk assessment: safety-rated speed monitoring is declared and meets its requirement. The deployment declares no speed_monitoring_safety_level (allowed: PLd, PLe, SIL2, SIL3, SIL4). |

## Conformance

No conformance report or registry entry was given.

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
| ANSI/A3 R15.08-1-2020 | 0 | 0 | 0 | 0 | 1 |
| ANSI/A3 R15.08-2-2023 | 5 | 0 | 0 | 0 | 3 |
| ANSI/A3 R15.08-3-2026 | 0 | 0 | 0 | 0 | 1 |
| IEC 61508-3:2010 | 0 | 0 | 0 | 0 | 1 |
| IEC 61508:2010 | 0 | 3 | 0 | 1 | 4 |
| IEC 62061:2021 | 0 | 3 | 0 | 1 | 4 |
| ISO 13849-1:2023 | 0 | 2 | 0 | 1 | 2 |
| ISO 13849-2 | 0 | 1 | 0 | 0 | 2 |
| ISO 3691-4:2023 | 4 | 0 | 0 | 0 | 5 |

## Inputs

| Role | Id | File | Digest |
|---|---|---|---|
| manifest | warehouse_amr_1 | manifest.yaml | `sha256:b54b3c140d171ebf5a7797e31f5756f3823e3ad81c8866735e9f45f67bf27e98` |
| envelope | warehouse_hall_2 | envelope.yaml | `sha256:3ed0e01427fc9a2fa85266877740468fac599b2470f8d562f4f1645197dbaf3a` |
| policy | urml_us_federal_default | bundled | `sha256:281e91ec5795a8d27cf029bb641704642eb8fb9e6dbb258ebbe2879ff960c4aa` |
| rulebook | hall_2_amr_rules | amr-rules.yaml | `sha256:2552e2a9e448e7e1695f8142cd6fdf492ab9a9dc33368824ce38c7825155ace7` |
| rulebook | hall_2_safety | functional-safety.yaml | `sha256:f6eeab13e8445e02df9d7d414803d05f6b049594228afe2aa355ae766718ae52` |
| rulebook | hall_2_safety_declarations | declarations.yaml | `sha256:bc6bce8c42e810a4dd90d7b4c56c49b3b95baa201a9c23a3a0347c4e1ee05f10` |
| program |  | pick-to-conveyor.urml.yaml | `sha256:ea3d21520cfe0bffac6a8218b725bee0f33fc3c8cc48a0fa1194ad483e5a8364` |

Rebuild this report from the same files with `urml evidence build` and the same `--as-of` date, and compare digests.
