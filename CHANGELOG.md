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

# Changelog

All notable changes to URML are recorded in this file.

The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and URML versioning is per-artifact semantic versioning (see [`MANIFESTO.md`](MANIFESTO.md) §License Direction and [`CONTRIBUTING.md`](CONTRIBUTING.md) — each spec layer, profile, and reference implementation versions independently; this top-level changelog records *project-level* milestones).

## [Unreleased]

### Added: rulebooks

- A rulebook can require a site limit ([RFC-0714](docs/rfcs/0714-rulebook-requires-a-limit.md), Draft). The new rule kind `require_envelope` lists safety-envelope fields, such as `geofences` or `max_velocity`. A deployment that loads the rulebook and leaves a listed limit unset has every program refused with the new code `rule.limit_missing`. Without such a rule a limit nobody set is not checked and the program is accepted, which stays the default. The evidence report shows the rule as `checked` or `missing` under the standard it cites. `examples/rulebooks/example-site-standard.yaml` is a fictional company's site standard that uses it. No government rulebook or template gains a rule.

## [0.5.3] - 2026-11-27

The family is bumped in lockstep to 0.5.3 so the work merged since 0.5.2 reaches PyPI: the evidence report's Markdown, HTML, redacted and signed forms, the EU and UL rulebooks, the certification reproduction tool and its fee rules, and the release SBOMs. 0.5.2 on PyPI was built from the v0.5.2 tag, and a re-run skips versions that already exist, so none of it could ship without a new version.

0.5.3 is the first version under the four-year Change Date ([RFC-0709](docs/rfcs/0709-change-date-four-years.md)): it converts to Apache 2.0 four years after its release, where 0.5.0 to 0.5.2 convert after two. It carries the corrected legal sources of the default compliance policy, and it is the first version published since the outreach records left the repository ([RFC-0710](docs/rfcs/0710-outreach-records-leave-the-repository.md)). `urml-marine-runtime` reaches PyPI for the first time with this version; PyPI's limit on new projects held it back at 0.5.2.

### Changed: release

- The Claude Code plugin bundle (`plugins/urml`) pins `urml-mcp-server==0.5.3`, in lockstep with `server.json`. Until 0.5.3 is on PyPI, a plugin installed from `main` cannot start its server, so the release run follows the merge.
- `registry/registry.json` and the committed evidence report example are regenerated: both record the validator version.
- The evidence report golden test masks a redacted report's `full_report_sha256` along with the version. That digest hashes the full report, version included, so every bump staled the golden file; `test_evidence_sign` still checks the digest against the full report.
- Every package now ships the license text it is released under. Wheels and source archives up to 0.5.2 carried only the identifier `BUSL-1.1` in their metadata, which does not state the Change Date or the Additional Use Grant. Each package directory now holds a copy of `LICENSE`, the build puts it into the wheel (`.dist-info/licenses/LICENSE`) and the source archive, and `conformance/tests/test_package_licenses.py` keeps the copies identical to the repository's file.
- The fleet example and conformance fixture that were called "engaged partners" are renamed, the change [RFC-0710](docs/rfcs/0710-outreach-records-leave-the-repository.md) left for the next conformance release: `fleet/06_four_robot_roll_call_positive`, `examples/fleet/four_robot_roll_call.fleet.yaml`, `run_roll_call_demo.py` and `run_nl_roll_call_demo.py`. Four industrial fixture descriptions no longer name a "lighthouse" program, and three fixture descriptions no longer give the FCC Covered List as the source of the vendor denylist. No fixture changes what it tests; the suite hash (`fixtures_sha256`) changes with the text.

### Changed: repository

- Outreach and distribution records left the repository ([RFC-0710](docs/rfcs/0710-outreach-records-leave-the-repository.md)). `docs/rfcs/` holds Spec and Governance RFCs only, and its index lists every one of them. `examples/lighthouses/` became `examples/vendor-manifests/`. The `make outreach-*` targets are gone. No schema, primitive, validator behavior or license term changes.
- `README.md` states 28 primitives, measured from the validator. It said 24: `drive`, `turn`, `look_at` and `gesture` had shipped without the number moving. The RFC badge is removed, and the runtime row says what a brand name in it means.

### Changed: license

- The BSL Change Date moves from two years to four for new versions ([RFC-0709](docs/rfcs/0709-change-date-four-years.md)). A version first publicly released after this change converts to Apache 2.0 four years after its release. Versions 0.5.0, 0.5.1 and 0.5.2, and source published from 2026-11-22 until this change, keep two years. The Additional Use Grant, the Change License and the prices are unchanged.

### Fixed: default compliance policy

- The bundled default policy (`us_federal_default.yaml`) cited law that does not say what the file claimed. It named the American Security Robotics Act, a bill that is not enacted, as the source of the Unitree entry. It placed the LiDAR restriction in "FY26 NDAA §164", which is a KC-46 provision; the restriction is section 164 of the FY2025 NDAA, amended by section 162 of the FY2026 NDAA. It gave section 889 of the FY2019 NDAA, which covers telecommunications and video surveillance equipment, as the source of the country rules. It gave two NIST publications that set no hardware bill of materials requirement as the source of the HBOM rule. Every citation now in the file was read in the primary text on 2026-11-27, and the header says where each rule reaches further than its source: all four vendors are on the Department of Defense list of Chinese military companies (91 FR 35189), and the country list is the covered foreign country list of the Department of Defense statutes for unmanned aircraft and LiDAR. The violation messages no longer say that federal procurement of the robot is prohibited; they say the rule is a screen and not a legal determination. No verdict changes: rule ids, selectors, lists, codes and severities are the same. The policy's content digest changes, so an evidence report built from this release records a new digest for the bundled policy. `tests/test_default_policy_sources.py` keeps every citation in the file on a checked list and keeps pending bills out. The README, the policy specification, the drone and home profiles, the compliance walkthrough, tutorial 4 and the manufacturers guide repeat the corrected sources, and RFC-0003 and RFC-0004 carry a dated correction note.

### Added: conformance

- The reproduction run (`python -m urml_conformance.reproduce`) records how long each step took (`plan`, `install`, `run`, `check`) in the reproduction report's new optional `timing` field, and prints the times. RFC-0708 defers a published certification fee until runs show what one costs; this is the measurement. A report without `timing`, such as every self-report, still parses.

### Added

- One CycloneDX SBOM per URML package: `tools/scripts/build_sboms.py` builds every wheel in the release's build list (read from `release.yml`, so the two cannot drift), installs each into a fresh environment with its dependencies, and records it with `cyclonedx-py`. The new `sbom` workflow runs it after every successful release run and on demand, read-only, and uploads the `sboms` artifact; `release.yml` is unchanged. SECURITY.md says where to find them. For robot makers listing URML in a product SBOM (EU Cyber Resilience Act, Annex I, Part II, point (1)).
- URML-Certified runs are free for non-commercial runtimes (RFC-0708 open question 1, resolved): a runtime not sold, not licensed for a fee and not part of a paid product or service, such as a university research group's or a teaching platform's. The waiver follows the runtime, not the submitter, and changes nothing else. [`spec/conformance/v0.2.3.md`](spec/conformance/v0.2.3.md) adds it to section 3 (v0.2.2 stays as the record), the registry accepts `conformance_spec: "0.2.3"`, and COMMERCIAL, TRADEMARK, SUBMISSION and the standards directory say so.
- `SECURITY.md`: Code of Conduct reports go to sales@urml.dev with "Conduct" in the subject, replacing the last placeholder address.
- `SECURITY.md`: implementation vulnerabilities are reported privately through GitHub's private vulnerability reporting, now enabled on the repository, instead of the placeholder address. It is the single point of contact for vulnerabilities in URML, including for makers who find one in a URML package built into their product, and published advisories are listed on the repository's advisories page.
- IEC 61800-5-1:2022 (electrical safety of drives) in `examples/rulebooks/machinery-safety-template.yaml`, as an obligation next to the electrical verification, and in the standards directory. The home template and the ISO 13482 directory entry record that the new edition (for service robots) was under publication, stage 60.00, on 2026-11-25; the cites stay on ISO 13482:2014 until it is published. IEC 61508 edition 3 is still unpublished; the functional-safety template's note stands.
- `examples/rulebooks/eu-cyber-resilience-act.yaml`: a government rulebook (jurisdiction EU) for the Cyber Resilience Act, Regulation (EU) 2024/2847, which applies from 11 December 2027; its Article 14 reporting duty has applied since 11 September 2026. Seven `require_declared` rules: the product class (`default`, `important_class_I`, `important_class_II`, `critical`), the conformity procedure (`module_A`, `module_B_C`, `module_H`, `eu_cybersecurity_certification`), the cybersecurity risk assessment, the software bill of materials, the end of the support period, the vulnerability contact and the EU declaration of conformity. Five obligations: reporting exploited vulnerabilities within 24 hours, integrating URML as a third-party component with due diligence, connections secure by default (TLS and broker credentials on the MQTT runtimes, protected rulebooks and manifests), security updates during the support period, and recording security-relevant activity. Opt-in. The standards directory gains the entry.
- `examples/rulebooks/eu-ai-act.yaml`: a government rulebook (jurisdiction EU) for the AI Act, Regulation (EU) 2024/1689, as amended by the Digital Omnibus on AI, Regulation (EU) 2026/1744 (OJ 24.7.2026). For a robot whose programs an AI system proposes. Three `require_declared` rules: the safety-component assessment (`not_a_safety_component` or `safety_component`, Article 6(1a) and (1b)), how people are told they deal with an AI system (Article 50(1)) and the AI literacy measures (Article 4). Four obligations: no proposed program skips the validator; a high-risk AI safety component of machinery goes through the Machinery Regulation, since the Omnibus moved machinery to Annex I, Section B (AI requirements in its Annex III by 2 August 2028); no emotion inference at work or in education (Article 5(1)(f)); the model provider meets Article 53. `ai_system_in_use: false` switches it off. The EU Machinery Regulation rulebook notes the Omnibus amendments, none of which touch what it cites. The standards directory gains the entry.
- IEC 61800-5-2:2016 (safety functions of drives) in `examples/rulebooks/functional-safety-template.yaml`: three rules, the drive stop function on record (for example STO or SS1, from the list the site accepts), a speed cap below the drives' safely limited speed (SLS) so no program trips it, and no `set_output` on the lines wired to the drives' safety inputs; two obligations, the drives' safety functions configured, protected and validated, and the cap recalculated when the drive's limits change. The cap is a convenience, not protection: the drive enforces SLS. The standards directory gains the IEC 61800-5-2 entry.
- ANSI/A3 R15.06-2025 in `examples/rulebooks/industrial-template.yaml`: R15.06-2025 adopts ISO 10218-1:2025 and -2:2025 in full and replaces R15.06-2012, so every ISO 10218 citation now names it too and an evidence report groups the rules under both. Two obligations come from ANSI/A3 R15.06-3-2025 (Use of Industrial Robot Cells), which has no ISO counterpart: the user runs the cell as validated and has changes (including to rulebooks, envelope and manifest) assessed, and everyone who works with the cell is trained, including on what URML does not stop. The standards directory names R15.06-2025 in the ISO 10218 entry.
- `examples/rulebooks/eu-machinery-regulation.yaml`: a government rulebook (jurisdiction EU) for Regulation (EU) 2023/1230 on machinery, which applies from 20 January 2027 (as corrected in OJ L 169, 4.7.2023). EU law is free to reuse, so it cites articles and annex sections exactly and needs no FILL_IN. Six `require_declared` rules: the risk assessment, the substantial-modification check for integrating URML (`not_a_substantial_modification` or `substantial_modification_reassessed`), the conformity procedure (`module_A`, `module_B_C`, `module_H`, `module_G`), the EU declaration of conformity, the technical file and the safety-software inventory. Six obligations, among them that no safety function relies on URML (Annex II, point 18, lists software ensuring safety functions as a safety component), that the manufacturer assesses self-evolving behaviour (Annex I, Part A, points 5 and 6), and that URML never prevents a stop. Opt-in; the US-federal defaults are unchanged. The standards directory gains the entry, a *Ready rulebook* support kind, a *Notified body* role and a *CE marking* term.
- The standards directory shows the *Evidence report* badge on every entry that has a rulebook template (13 more: ISO 12100, ISO 13855, ISO 14119, IEC 60204-1, IEC 61496, ISO/TS 15066, ISO 3691-4 and R15.08, ISO 13482, ISO 13849, IEC 62061, IEC 61508, IEC 62443 and the UL listings). `urml evidence build` already grouped their rules by the standard each cites; the directory now says so. A test keeps every template entry badged and checks each linked template cites a standard.
- `python -m urml_conformance.reproduce`: the Licensor's URML-Certified run as public code (RFC-0705, RFC-0708). It reads a submitted registry entry and refuses early what cannot be certified (a first-party `urml-*` package, a repository path, a version range, the mock adapter, no attestation, a self-report that does not match its pin), installs exactly `<package>==<version>` and the matching urml-conformance into a fresh virtual environment, runs the claimed profiles with the entry's adapter while refusing every network connection and lookup except loopback, and checks the reproduction against the self-report (all passed, same adapter, same `fixtures_sha256`, same profiles). It writes the reproduction report and, with `--write`, fills `certified_on`, `expires` and `reproduction` into the entry and sets `last_verified`, keeping the submitter's comments. `--run-prefix` runs the suite under an OS sandbox as well. A failed run keeps its report and grants nothing. The standards directory gains a *Registry check* support kind, and URML-Certified now shows it.
- [RFC-0708](docs/rfcs/0708-paid-certification.md): URML-Certified becomes a paid validation service in [`COMMERCIAL.md`](COMMERCIAL.md#urml-certified-runtime-makers). The Licensor charges per certification run, quoted from its scope; the fee pays for the run, never for the result, a failed run keeps its fee, and requests run in the order they are paid. The criteria, the checker and the registry are unchanged, and the conformance suite and the self-reported tier stay free. Amends the Manifesto's Non-Goals and RFC-0705; [`spec/conformance/v0.2.2.md`](spec/conformance/v0.2.2.md) states the fee in section 3, and the registry accepts `conformance_spec: "0.2.2"`.
- UL 1740 in `examples/rulebooks/industrial-template.yaml`: two rules refuse programs until the operator declares the industrial robot's listing standard (from the list the site accepts, for example UL 1740) and its NRTL listing reference, and two obligations say URML is not part of the listing and changes nothing it covers, and that the robot is used within its listing's conditions. Sites that do not require a listing delete the four. The template notes that UL 1740 edition 4 (2018) follows ISO 10218:2011, not 2025. The standards directory's UL entry now points to a template for each of UL 1740, UL 3100 and UL 3300. Tests cover a missing listing, an unaccepted standard and the warning without a deployment rulebook.
- UL 3100 in `examples/rulebooks/amr-template.yaml`: two rules refuse programs until the operator declares the mobile robot's listing standard (from the list the site accepts, for example UL 3100) and its NRTL listing reference, and two obligations say URML is not part of the listing and changes nothing it covers, and that the robot is used within its listing's conditions. Sites that do not require a listing delete the four. The standards directory's UL entry now points to it for UL 3100 and to the service-robot template for UL 3300. Tests cover a missing listing, an unaccepted standard and the warning without a deployment rulebook.
- `examples/rulebooks/service-robot-template.yaml`: a site's rulebook for service robots in public and commercial spaces, after ANSI/CAN/UL 3300 (service, communication, information, education and entertainment robots). Speed and grip-force caps, hazard zones such as stair landings and escalators, a program allowlist, and programs refused until the operator declares the robot's listing standard (from an accepted list) and its NRTL listing. Obligations: URML is not part of the listing and changes nothing it covers, the robot is used within its listing's conditions, the listing is kept current, and the site's risk assessment covers the public. The standards directory's UL entry now points to it. A test covers each rule.
- `examples/rulebooks/machinery-safety-template.yaml`: a rulebook template after the machinery safety basics, ISO 12100:2010, ISO 13850:2015, ISO 13855:2024, ISO 14119:2024, IEC 60204-1:2016 and IEC 61496-1:2020 / -3:2025. Programs are refused until the operator's deployment rulebook declares the risk assessment, the emergency stop's stop category (`category_0` or `category_1`), the safeguard-distance calculation, the interlocking record, the IEC 61496 type of the protective devices and the electrical verification, and programs never write the outputs wired to safeguards. Its obligations say the emergency stop works whatever URML does and that the URML runtime stops on it and never resumes by itself. A test covers each rule.
- The standards directory is now generated from one file, [`docs/standards/directory.yaml`](docs/standards/directory.yaml), by `tools/scripts/gen_standards_doc.py`, into `README.md` and `directory.json` (which urml.dev/standards renders); a test keeps them in step and checks every link is https. It gains ISO 12100, ISO 13850, ISO 13855, ISO 14119, IEC 60204-1 and IEC 61496, a legend of key terms (risk assessment, type A/B/C standards, PL/SIL/SL, stop categories, safety function, conformity assessment) and links to the publisher's page for every entry. Editions were rechecked: ISO 13855 and ISO 14119 are 2024, IEC 61496-3 is 2025, IEC 62061 has Amendment 2:2026, ISO 21423:2026 is published, VDA 5050 is 3.0.0.
- TLS and broker credentials for `urml-vda5050-runtime` and `urml-iso21423-runtime`. The adapter config takes `broker_tls` (CA file, optional client certificate and key for mutual TLS), `broker_username` and `broker_password_env` (the environment variable holding the password; never the password itself). TLS 1.2 or newer with certificate and host name always verified, no switch to turn either off. `PahoTransport` now returns only once the broker accepts, so a wrong password or a failed TLS check raises `ConnectionError` at connect instead of surfacing as a later timeout, and plain MQTT to a broker on another host warns. Tested against a TLS broker (round trip, wrong password, untrusted CA, wrong host name, mutual TLS) in both runtimes' integration workflows, with throwaway certificates from `tools/scripts/mqtt_tls_fixture.sh`. `docs/security/iec-62443.md` and the cybersecurity template are updated: transport security is now available, and opt-in.
- [`docs/standards/`](docs/standards/README.md): a directory and legend of robot standards, regulations and certifications (ISO 10218, ISO/TS 15066, ISO 3691-4 and R15.08, ISO 13482, ISO 13849, IEC 62061, IEC 61508, IEC 62443, UL 1740/3100/3300, ISO 8373, VDA 5050, ISO 21423, 14 CFR Parts 107 and 89, NDAA 889 and the procurement lists, URML-Certified, evidence reports). Each entry says what it is, why it matters, who needs it, how to meet it, who issues or assesses it, and what URML gives you; the legend explains standards versus regulations versus certifications and who does what.
- `examples/rulebooks/cybersecurity-template.yaml`: a rulebook template after IEC 62443-3-2:2020 and IEC 62443-3-3:2013. Programs are refused until the site operator's deployment rulebook declares the security level (`SL1`..`SL4`) achieved by the zone holding the robot controller and by the zone holding the URML host, at or above their targets, and the references of the zone and conduit model and of the security risk assessment. Its obligations cover what URML does not: authenticated program sources, protected conduits, patching, logging. [`docs/security/iec-62443.md`](docs/security/iec-62443.md) maps URML against the seven foundational requirements and states the gaps, among them that the VDA 5050 and ISO 21423 runtimes use plain MQTT without TLS or broker authentication. URML claims no security level. A test shows declarations accepted, a level below target or a missing record refused, and warnings only without a deployment rulebook.
- `examples/evidence-report/` (RFC-0707, step 5): one warehouse deployment and its evidence report in all four forms (JSON, Markdown, HTML, redacted JSON), with a README written for an auditor who has never used URML: how to read each status, a walk through the example's one gap (a missing speed-monitoring declaration that refuses every program), how to rebuild the report and check its digests, and how to share it. A test fails when a committed report is stale. `docs/safety/safety-model.md` gains an Evidence reports section.
- Redacted and signed evidence reports (RFC-0707, step 4). `urml evidence build --redact` writes a copy fit to share outside the site: geofence and zone geometry and program messages become `[redacted]` (a marker, not a hash, since a hash of a guessable coordinate can be reversed), everything else stays, and the full report's sha256 is recorded. `urml evidence verify` checks an OpenSSH signature (`ssh-keygen -Y sign -n evidence-report@urml.dev`) over a report's exact bytes, offline and in pure Python, against the Licensor keys shipped in the package; plain and FIDO hardware-backed Ed25519 keys, with validity dates judged on the report's `as_of`. No Licensor key is published yet. Procedure in `docs/evidence/signing.md`.
- `urml evidence build --format md|html` (RFC-0707, step 3): the evidence report for people, as Markdown or one static HTML file (inline styles, no scripts, no external requests, readable on a phone). Each opens with the notice, lists the gaps first, and keeps every item, standard and input digest; a test fails if a form drops one. Also fixed: a manifest without provenance no longer lists the policy's provenance rules as passed; `provenance.absent` names them as having nothing to check.

## [0.5.2] - 2026-11-24

`urml-mcp-server` is ready for the official MCP Registry, and `urml evidence build` arrives (RFC-0707, steps 1 and 2). The family is bumped in lockstep to 0.5.2.

### Added

- `urml evidence build` takes programs and conformance evidence (RFC-0707, step 2). `--program` (repeatable) validates each program against the deployment and lists it as passed or refused with every issue; a refused program is a gap. `--conformance-report` and `--registry-entry` add a Conformance section read through `urml-conformance`: the adapter and fixture results, the registry tier, a certification's expiry against `--as-of`, and the report the entry pins. A mock-adapter run, a filtered run, a failed fixture, an uncovered profile, an expired certification, a withdrawn entry or an unpinned report is a gap.
- `urml evidence build` (RFC-0707, Draft, step 1): an evidence report for one robot deployment. It reads the manifest, envelope, policy and rulebooks and marks every item `checked`, `declared`, `runtime`, `missing` or `outside`, in Robot, Provenance, Envelope, Rules and Outside URML sections, regroups rules and obligations by the standard each cites, and counts gaps (missing items plus failed checks). No score, no verdict; the first line says it is not a safety assessment, a certification or a compliance determination. Offline and deterministic: the same files and `--as-of` date give the same bytes. Format in `spec/evidence/`, golden reports for four deployments in the validator tests. Exit 0 without gaps, 1 with gaps, 2 on an unreadable input.
- Rulebook cites take an optional `standard` field (RFC-0707): the standard or regulation a cite draws on, with its edition, as one identifier or a list. It changes no validation result. The bundled 14 CFR Part 107 rulebook and the four safety-standard templates carry it.

### Changed: MCP server

- `urml-mcp-server` is ready for the official MCP Registry. Its README carries the `mcp-name: io.github.urml-dev/urml` line the registry uses to verify PyPI ownership, and `server.json` uses the 2025-12-11 schema and a description within the registry's 100-character limit. `server.json` had stayed at version 0.2.0; `tools/scripts/bump_version.py` now moves it with the family. The family is bumped in lockstep to 0.5.2 so a published version carries the ownership line.

## [0.5.1] - 2026-11-24

`urml-conformance` 0.5.1 records adapter calls in the harness (RFC-0706, conformance spec v0.2.1) and runs from an installed wheel. The rest of the family is rebuilt at 0.5.1 in lockstep.

### Added

- `urml-vda5050-runtime` (`reference/vda5050-runtime`): drives AMRs and AGVs that speak VDA 5050 3.0.0 over MQTT, with no ROS. URML acts as fleet control for each vehicle; every dispatch step becomes one VDA 5050 order, and a step succeeds only when the vehicle's state reports it finished. Implements the mapping proposed in RFC-0297. Tested against a simulated vehicle, with every message validated against the official VDA 5050 schemas, and over a real Mosquitto broker in the gated `vda5050-integration` workflow. Not yet tested on a vendor's vehicle. Known gaps are in `reference/vda5050-runtime/SPEC-GAPS.md`. On PyPI at the family version (0.5.0) since 2026-11-24: `pip install urml-vda5050-runtime`.
- `examples/vda5050/`: the warehouse example run as VDA 5050 orders, with a byte-asserted recorded output.
- [`COMMERCIAL.md`](COMMERCIAL.md#validation-services): paid fleet validation for operators and vehicle validation for AMR and AGV makers.
- `urml-iso21423-runtime` (`reference/iso21423-runtime`): drives mobile robots that speak ISO 21423 (industrial mobile robot interoperability) over MQTT, with no ROS. Each dispatch step becomes one ISO 21423 request to the robot or its fleet manager, and a step succeeds only when the robot's request status reports every action SUCCEEDED. **Validation in progress:** built from public material based on the ISO/FDIS 21423 draft; we are validating it against the published ISO 21423:2026 and make no conformance claim until that is done. Tested against a simulated robot, over a real broker, and cross-checked against OpenRobOps' independently derived schemas. Not on PyPI. `examples/iso21423/` holds a config, a program and a byte-asserted demo.
- `examples/rulebooks/functional-safety-template.yaml`: a rulebook template after ISO 13849-1:2023 / ISO 13849-2, IEC 62061:2021 (with Amendment 1:2024) and IEC 61508:2010 (edition 2.0; edition 3 is forecast for 2027). IEC 61508 levels run `SIL1`..`SIL4`, and an obligation asks the integrator to show URML cannot interfere with safety-related software on shared hardware. [`docs/safety/iec-61508.md`](docs/safety/iec-61508.md) says where URML stands under IEC 61508: outside the safety-related system, with no SIL or systematic capability, and at most a T2 tool if an integrator ever uses the validator in a safety case, without the tool evidence the standard asks for. Programs are refused until the operator's deployment rulebook declares the level reached by the emergency stop, the protective stop and safety-rated speed monitoring, as an ISO 13849 performance level (`PLa`..`PLe`) or an IEC 62061 safety integrity level (`SIL1`..`SIL3`), at or above the level the risk assessment requires, and the reference of the validation record. URML checks the declaration, not the safety function, and counts toward no PL or SIL; the template says so first. It carries no values from either standard and refuses to load until filled in; a test shows sufficient declarations under both standards accepted, a low or missing one refused, and warnings only when no deployment rulebook is loaded.
- `examples/rulebooks/home-template.yaml`: a rulebook template for a personal care robot of the mobile-servant kind, after ISO 13482:2014 (current, and under revision at ISO). Five rules (travel-speed and grip-force caps, hazard zones, no grasping or releasing in excluded zones, a program allowlist) and four obligations URML lists but cannot check. It carries no values from the standard and refuses to load until filled in; a test fills it with sample values and shows each rule refusing what it should against the home example robot.
- `examples/rulebooks/amr-template.yaml`: an integrator's rulebook template for industrial mobile robots, after ISO 3691-4:2023 and ANSI/A3 R15.08-1-2020 (R2026), R15.08-2-2023 and R15.08-3-2026. Five rules (travel-speed cap, forbidden zones, load handling only at stations, a program allowlist, untouched safety outputs) and five obligations URML lists but cannot check. It carries no values from either standard and refuses to load until filled in; a test fills it with sample values and shows each rule refusing what it should.
- **URML-Certified** ([RFC-0705](docs/rfcs/0705-urml-certified.md)): a free conformance certification on public criteria. A third-party runtime version is certified when it passes the full conformance suite for its profiles and the Licensor reproduces that run offline from the public package. The registry gains a `certified` tier, checked by `python -m urml_conformance.registry check` (reproduction report, same fixture set, one exact public version, expiry). Conformance specification `v0.2.0` describes the tier; `TRADEMARK.md` replaces its Phase 4 stub with the policy. Certification covers conformance only, never safety or compliance. Nothing is certified yet.

### Changed: conformance

- The conformance harness records adapter calls ([RFC-0706](docs/rfcs/0706-recorded-adapter-calls.md)). `ConformanceRunner` wraps every adapter, single-robot and each fleet member, in `RecordingAdapter` and checks `audit_methods` and `per_member_audit` against what it recorded. Before this, the runner read a `call_log` only the mock keeps, so a real adapter (`RclpyAdapter`, a vendor SDK) failed 102 of the 103 fixtures that check execution. An adapter no longer keeps or vouches for its own log. `RecordingAdapter` moves to `urml_conformance.recording`; the old import paths still work.
- Conformance specification [v0.2.1](spec/conformance/v0.2.1.md): clause 6 says the suite records the calls. No obligation on a runtime changes. Registry certifications may name `conformance_spec: "0.2.1"`.
- The family is bumped in lockstep to 0.5.1 ([`RELEASING.md`](RELEASING.md#version-coherence)) so `urml-conformance` can ship both changes. Only the conformance package's code changed since 0.5.0; the other packages are rebuilt at the new version unchanged. On PyPI since 2026-11-24, except the isaac, legged, marine, mujoco and opcua runtimes, which waited on PyPI's new-project limit. The isaac, legged, mujoco and opcua runtimes were created at 0.5.2, and the marine runtime at 0.5.3.

### Fixed

- `urml-conformance` installed from a wheel runs outside a repository checkout. The fixtures name manifests, envelopes, policies and rulebooks from `reference/validator/tests/fixtures`, `examples/fleet` and `examples/rulebooks`, which the 0.5.0 wheel did not contain, so `pip install urml-conformance` followed by `python -m urml_conformance` failed with `FileNotFoundError`. A build hook (`conformance/hatch_build.py`) now bundles them, and the `conformance-wheel` workflow runs the suite from built wheels on every change that could break it.
- `gazebo-e2e` in `ros2-integration` now runs its test: it launches the real Jazzy TurtleBot 4 simulation (`turtlebot4_gz_bringup`), keeps pytest's exit code, and pins apt mirrors. It had reported success with no simulator and no test. The nav-patrol fixture passes on the live sim (#17).

## [0.5.0] - 2026-11-22

First release from the new home, [`urml-dev/URML`](https://github.com/urml-dev/URML). All twenty-two packages were built at 0.5.0. PyPI lets a personal account create only about 4 new projects a day, so they reach PyPI in batches: 17 were live by the afternoon of 2026-11-24 (with `urml-vda5050-runtime`, released alongside them). The isaac, legged, mujoco and opcua runtimes followed on 2026-11-25 at 0.5.2, making 21 of 22, and the marine runtime followed on 2026-11-27 at 0.5.3. Until a package is on PyPI it installs from source.

### Changed: license

URML 0.5.0 and later are licensed under the **Business Source License 1.1** ([RFC-0703](docs/rfcs/0703-bsl-relicense.md), [`LICENSING.md`](LICENSING.md)). Research, teaching, evaluation, development, testing, simulation and personal use are free. Production use needs a commercial license: $4 per robot per month, or the Enterprise lifetime package ([`COMMERCIAL.md`](COMMERCIAL.md)). Each release converts to Apache 2.0 two years after it ships. Releases up to and including 0.4.x stay Apache 2.0.

### Changed: project

- The canonical repository moved from `URML-MARS/URML` to `urml-dev/URML`; every link in the repository points at the new location.
- Contributions require the [Contributor License Agreement](CLA.md), checked automatically on pull requests, plus DCO sign-off.
- The MCP server's registry name is now `io.github.urml-dev/urml`.

The entries below were developed on `main` after 0.4.0 and ship in 0.5.0.

### Added: ArduPilot reference runtime

- `urml-ardupilot-runtime` (`ArduCopterAdapter`): ArduCopter over MAVLink through pymavlink, no ROS (#720). On a Pixhawk-class board with ArduCopter 4.6.3, on USB with propellers off (2026-08-29), the bench-battery program ran to success. The bench-hop program passed the validator and the autopilot's own pre-arm checks refused to arm; URML reported the autopilot's reason and stopped. No free flight on hardware is claimed.
- ArduCopter SITL (Copter-4.6.3, run locally): the flight-only conformance fixture, the site-photogrammetry example and the parcel-delivery example passed, 3 of 3 (#721). The run surfaced one defect: ArduCopter 4.6 rejects the MAVLink winch deliver and retract actions, so the adapter uses relative-length control. On 2026-08-30 the programs Gemini 2.5 Pro emitted through the LLM bridge for the two flight-test sentences flew unchanged on the same SITL (#724).
- Payload release through winch and latch (RFC-0684, #771).

### Added: first real adapters for four more kinds of behavior

- Trajectory: `urml-av-runtime` ships `AutowareAdapter`, the first real `plan_path` / `follow_trajectory` adapter (RFC-0020, #774), wired into the MCP server's execute path (#775).
- Expression: `ReachyMiniAdapter` in the edu runtime, the first real expression adapter (RFC-0698, #777). Hermetic tests only; it has not run on a robot yet.
- Relative motion: `GoPiGo3Adapter` in the edu runtime, the first real `drive` / `turn` runtime (RFC-0630, #773).
- Arm: the Spot adapter gains grasp and release behind `arm_attached`, with a Spot-with-Arm manifest (#700). The `capture` primitive gains a camera selector (RFC-0699, #740).
- `MicroduckAdapter` for the Hugging Face duck over its JSON-RPC contract, with the velocity cap held to the policy's training range (#727, #728).

### Added: rulebooks (RFC-0702)

- A rulebook pass for government and company rules (#756, #759). The bundled rulebook, the statically checkable subset of 14 CFR Part 107, applies to drone programs by default. `--no-policy` does not switch it off; `--no-default-rulebooks` does, with a warning. `--rulebook PATH` adds an organization or deployment rulebook. 13 conformance fixtures under `conformance/fixtures/rulebook/`; spec text in `spec/layer-1-hal/rulebook.md`.

### Added: validation records and the registry

- `--evidence-log PATH` appends one validation record per verdict, accepted or refused, with content digests, at every entry point (#762). Opt-in and local.
- `registry/`: a public registry of robots and runtimes validated with URML, submitted by pull request and checked by `python -m urml_conformance.registry check` (#764). Three entries: ArduCopter on a Pixhawk-class board, the GoPiGo3 example adapter, and PX4 in SITL (#766). A compatibility claim covers a whole profile (#767). Rendered at https://urml.dev/registry.

### Added: `urml bench` and clarify mode

- `urml bench` measures how well a model speaks URML, with starter corpora, adversarial corpora, a scripted worst-case striker, and a gate table per row (#743, #751).
- Clarify mode: with `--clarify`, `urml translate` and `urml run` let the model ask one clarifying question instead of guessing. Default off, experimental. Its Spec RFC (RFC-0700) is proposed and not yet merged (#746).

### Added: safety model and the goalkeeper

- `docs/safety/safety-model.md` and `docs/safety/envelope-coverage.md`: what the validator checks for each primitive, and what it cannot see (#752, #758).
- `examples/goalkeeper/`: a scripted compromised model against three robots; every attack refused, no command sent (#754). Worst-case striker rows: 21 of 40 attacks got through before the fixes, 0 of 40 after, with 12 of 12 safe controls still accepted (#755).
- A goal-line conformance lane: every rejected fixture is refused with zero adapter calls (#750).
- The MCP server pins manifest, envelope, profiles and policy per server (#749).
- A STREL compile target for monitorable envelopes; RFC-0667 and RFC-0668 move to Implemented (#760). Dynamic-target grasping (RFC-0671, #753).

### Added: examples

- A learned ExecuTorch policy behind the runtime shield (#688), a Decart Oasis world-model rehearsal (#680), Unitree G1 whole-body (#690), URDF to manifest (#678), MTConnect `MOVE_MATERIAL` lowered to a UR arm (#697), a physical-AI safety-eval harness over Anthropic's Model Hardware Standard (#705), and Times Square geocoding with NYC and FAA rules (#722).

### Fixed: the PX4 adapter flies the program

- The adapter treated every `COMMAND_ACK` as success, so a SITL test could pass while the vehicle stayed on the ground. Each flight primitive is now confirmed from PX4 telemetry (#765). The adapter sends a ground-station heartbeat, and a refused command carries PX4's own reason (#769). Recorded SITL runs, local and not in CI: `reference/px4-runtime/tests/integration/sitl-runs/`.
- `scan` no longer reports success with made-up results, and grasp and capture calls no longer raise TypeErrors, across the reference adapters (#772).

### Added: ROS 2 `scan` through Nav2

- `RclpyAdapter` runs a `scan` step as a real scan plan through Nav2 (#783). Run locally against Nav2's loopback simulator (real planner, controller and behavior tree over a kinematic robot, no physics), not in CI: one validated `scan` step drove Nav2 to all nine waypoints of a serpentine over a 2 m square, a listen-only witness saw the robot within 0.23 m of every waypoint, and a goal off the map came back as `goal_aborted` instead of a success. Record: `reference/ros2-runtime/tests/integration/nav2-runs/2026-09-29-nav2-loopback-scan.md`.

### Removed: the Moltbook agent

- RFC-0640, its ledger, and `tools/moltbook/` are gone (#781). The channel drew no response in seven weeks. The venue-neutral agent guide, `docs/integrations/urml-for-ai-agents.md`, stays. RFC numbering keeps a gap at 0640.

### Changed: `urml translate` and `urml run` carry the request into `description`

- The emitted program's existing optional top-level `description` now holds the sentence (or the spoken transcript) it was translated from, placed right after `profile`. A description the model wrote itself is kept. Runtimes can print it next to the lowered calls; the GoPiGo3 example does, as `prompted by:`. No schema change (Discussion #597).

### Fixed: GoPiGo3 example

- `wait` is honored. The adapter takes a `wait` clock (default `time.sleep`) and the runner gates it exactly like speech: `--execute` holds the robot for the declared duration, a dry run records `time.sleep(N)` in the plan and never blocks. The report line now shows the duration (Discussion #600, Issue #592).
- PR and issue templates link `CONTRIBUTING.md`, `CLAUDE.md`, and `MANIFESTO.md` by absolute URL. Relative links do not resolve from a PR or issue page (Discussion #604).

## [0.4.0] — 2026-08-09

Minor release. Everything is backward-compatible: a v0.3.0 manifest, envelope, and program validate and execute unchanged. All 20 Python packages move to 0.4.0 in lockstep, and 0.4.0 is the first version of the family actually uploaded to PyPI (0.2.0 and 0.3.0 were version alignments on `main`; the index still served 0.1.0).

### Added — Speech front-end (RFC-0670)

- `urml translate --audio request.wav` and `urml run --audio request.wav`: speak the request instead of typing it. A `SpeechProvider` protocol mirrors the LLM provider contract, with adapters for whisper.cpp's `whisper-server` (new `[whisper_cpp]` extra, on-device, the default), OpenAI-compatible transcription endpoints (key not required with a base URL), and a hermetic echo provider. The transcript is echoed to stderr and feeds the unchanged translate path, so the validator boundary is untouched. `--speech-language` hints the language for multilingual requests.

### Added — First-class on-prem LLM providers in the CLI

- `urml translate` and `urml run` gain `--provider ollama` and `--provider llama_cpp`, wiring the RFC-0021 on-device adapters (shipped and tested since v0.2) into the CLI. A new `--base-url` flag overrides the local server endpoint for both, and points `--provider openai` at any OpenAI-compatible server (LM Studio, vLLM).
- `OPENAI_API_KEY` is no longer required when a base URL is set via `--base-url` or `OPENAI_BASE_URL`: local servers ignore the key, so the CLI passes a placeholder. Cloud usage without a base URL is unchanged.
- A dead local server now surfaces as one actionable line naming the endpoint and the fix, instead of a raw httpx traceback.

### Notes

- The PyPI publish (TestPyPI rehearsal, then the real index), the `v0.4.0` git tag, the GitHub release, and the README install-line flip are executed by the maintainer after this lands, per `RELEASING.md`.
- New `tools/scripts/bump_version.py`: the lockstep bump is now scripted and checkable (`--check`), replacing the hand-edited 40-file sweeps of 0.2.0 and 0.3.0.

## [0.3.0] — 2026-07-23

Minor release, and the first to version the full package family in lockstep. Everything is backward-compatible: a v0.2.0 manifest, envelope, and program validate and execute unchanged. All 20 Python packages move to 0.3.0 in lockstep.

### Added — Envelope enforcement (RFC-0667)

- Normative satisfaction semantics for the RFC-0382 temporal-logic core over finite timed traces: completed-trace offline evaluation, three-valued online verdicts (satisfied / violated / pending), strong truncation semantics, and the severity mapping (info records, warning audits, critical vetoes).
- `urml_validator.monitor`: the reference trace evaluator (`evaluate_trace`, `OnlineMonitor`, `compile_envelope_monitors`). Static envelope caps (`max_velocity`, `max_grip_force_n`, altitude) now derive to implicit critical `always` properties, so one evaluator covers declared and derived properties alike.
- `urml_ros2_runtime.shield`: the runtime shield. `Shield` gates each dispatch and observes telemetry; `ShieldedAdapter` wraps any substrate adapter so any driver, a URML runtime or an external policy, passes through envelope checks. New optional `TelemetryAdapter` side-protocol; the frozen RFC-0014 adapter contract is untouched. External runtime-verification backends stay first-class through `compile_to_stl`.

### Added — Rehearsal gate and the `urml run` verb (RFC-0668)

- `urml run "<sentence>"`: translate, validate, optionally rehearse in simulation, then execute, in one verb. `--rehearse` is also available on `urml execute`.
- Rehearsal backends: a hermetic synthetic-kinematics backend (CI floor, honest about being kinematics rather than physics) and a MuJoCo per-tick recording adapter with a declared `SignalMap`. A critical violation in the rehearsed trace blocks execution before any real adapter is constructed.
- The README hero now shows the gate live: the same sentence first blocked (envelope speed cap violated under the default motion assumption), then passing under the deployment's declared profile.

### Added — URML-native model pipeline (RFC-0666)

- New package `urml-model` (`reference/model`): mines conformance gold programs and the curated few-shot library, back-translates programs to utterances (deterministic templates in CI, any `LLMProvider` at scale), filters every record through the validator oracle, and exports SFT/DPO training files. Ships the operator-run LoRA training recipe. No weights, no vendor coupling, nothing leaves the repo checkout.

### Added — Agent surface

- `urml-mcp-server` (`reference/mcp-server`): URML's validate-before-actuate loop as Model Context Protocol tools for any MCP-capable agent. The server never calls an LLM; the calling agent emits URML, the server checks and runs it.
- An Agent Skill (`.github/skills/urml-robot-intent`) with a hermetic no-key, no-robot path.

### Added — Specification and manifests

- Per-capability evidence traceability (RFC-0631): capability claims carry `derived` / `verified` / `declared` / `inferred` evidence strength, with an opt-in policy to require the stronger grades.
- Whole-body kinematic structure and stability limits for legged and humanoid platforms (RFC-0384); whole-body and bimanual manipulation (RFC-0010).
- Realtime cyclic-timing manifest block (RFC-0016) and the zero-copy IPC sub-substrate declaration (RFC-0385).
- `drive` radius parameterization (RFC-0665): a radius plus sweep angle pass through without arc-length arithmetic, closing the small-model orbit-2x failure observed in the field.

### Fixed

- GoPiGo3 example runtime converts URML's FLU (+CCW) frame to the platform's RFD (+CW) frame at the hardware boundary (#591, #598, PR #602). URML's first merged external code contribution, found and fixed on real hardware by @slowrunner.

## [0.2.0] — 2026-06-02

Minor release. The first spec-bumping release since v0.1.0: it transcribes the accepted multi-robot fleet RFCs into the normative layer specs, so the specification stops lagging its own accepted decisions. Layers 1, 3, and 4 advance to v0.2.0; Layer 2 is unchanged (still 20 normative primitives). All additions are backward-compatible — a v0.1.0 manifest and a single-robot program validate unchanged.

### Added — Specification

- **Layer 1 (HAL) → v0.2.0.** Three additive, optional items: a frame `transform` (SE(3) pose in the parent frame), a `mobility.clearance` operational volume (lateral footprint + vertical altitude/depth band), and the new §6 fleet `roster` (binds N per-robot manifests by handle; `world_frame`, `shared_frames`, per-member `anchor`s) plus the `validate_fleet` cross-robot checks. RFCs [0286](docs/rfcs/0286-multi-robot-fleet-addressing.md), [0290](docs/rfcs/0290-frame-transform-graph.md), [0291](docs/rfcs/0291-utm-strategic-deconfliction.md). `manifest_version` stays `"0.1"`.
- **Layer 3 (behavior composition) → v0.2.0.** Two additive composition nodes: `on` (scope a subtree to a fleet member) and `barrier` (synchronize members at a rendezvous). RFC [0286](docs/rfcs/0286-multi-robot-fleet-addressing.md).
- **Layer 4 (NL grammar) → v0.2.0.** Roster-aware fleet (multi-member) prompt assembly and a fleet revision loop (`validate_fleet`), emitting `on`/`barrier` programs. RFC [0286](docs/rfcs/0286-multi-robot-fleet-addressing.md).
- **Sensor schema v0.2 reconciled.** The RFC-0039 sensor capability fields (`beam_count`, `channels`, `time_sync_methods`, `rate_hz_max`, `point_cloud` type), already shipped in the Layer-1 doc since v0.1.1, are now carried normatively at v0.2.0. RFC [0039](docs/rfcs/0039-sensor-schema-v0-2-iteration.md).

### Added — Reference implementation

- **Multi-robot fleet vertical slice.** `validate_fleet` (four cross-robot checks plus shared-frame/anchor validation), a concurrent `FleetRuntime`, the courier-to-arm handoff demo, and a fleet conformance lane (`conformance/fixtures/fleet/`, 14 cases covering ground/air/water separation and the engaged-partners choreography). RFCs [0286](docs/rfcs/0286-multi-robot-fleet-addressing.md), [0290](docs/rfcs/0290-frame-transform-graph.md), [0291](docs/rfcs/0291-utm-strategic-deconfliction.md).
- **`urml-edu-runtime`: fourth platform.** `RoboticalMartyAdapter` graduated to production (real-`martypy` API-surface CI gate), joining VEX V5, LEGO SPIKE, and Thymio.

### Notes

- All 17 in-repo packages (5 published on PyPI + 12 in-repo runtimes) bump 0.1.1 → 0.2.0 in lockstep.
- This is **strategic** cross-robot deconfliction: static rejection of plans that would put two robots in one volume at one time, before execution. It is not a live collision-avoidance loop and not a building-scale traffic manager (that is Open-RMF's domain; URML composes above it).
- The PyPI publish, the `v0.2.0` git tag, and the README/Tutorial-01 install-instruction flip follow [`RELEASING.md`](RELEASING.md) and are gated on the maintainer.

## [0.1.1] — 2026-05-26

Patch release. Phase 1 maintenance since v0.1.0: the first outreach-feedback-driven adapter, two committed homepage diagrams with byte-exact guard tests, and the PyPI packaging fix that should have shipped earlier. No spec change (RFC-0039 sensor schema v0.2 remains in **Draft**); no breaking change.

### Added — Reference implementation

- **`urml-edu-runtime`: `RoboticalMartyAdapter`.** New adapter for the Robotical Marty platform, scaffolded in response to early outreach feedback. Conformance fixtures stay hermetic against `MockROSAdapter`. RFC 0073; commit `d516535`.

### Added — Docs & assets

- **Architecture-stack diagram.** Committed, deterministic SVG of the five-layer URML stack at `docs/assets/architecture-stack.svg`, generated by `tools/scripts/gen_architecture_svg.py` and pinned to `docs/architecture.md` by `reference/validator/tests/test_architecture_svg.py`. Same pure-stdlib, byte-exact, CSS-`@keyframes`-only discipline as the README hero. PR [#129](https://github.com/urml-dev/URML/pull/129).
- **One-intent-many-bodies portability demo.** Committed SVG showing the same URML program executing across multiple substrate adapters, byte-asserted against a live hermetic run. PR [#132](https://github.com/urml-dev/URML/pull/132).

### Added — Outreach (no spec change)

Seven outreach waves since v0.1.0 (Moves #2 through #8, RFCs 0040–0107, 68 RFCs total). Each is a per-target request-for-comment document explicitly framed "No spec change is proposed here." Per-wave ledgers at `examples/lighthouses/outreach-move{2..8}.yaml`. Aggregate response state across all ledgers at release time: 4 engaged · 2 declined · 1 wontfix · 77 none.

### Fixed

- **`urml-validator`: PyPI upload.** Redundant `force-include` in the package build config was breaking PyPI uploads. Removed. Commit [`1d631b4`](https://github.com/urml-dev/URML/commit/1d631b4).

### Notes

- All 17 in-repo packages (5 published on PyPI + 12 in-repo runtimes) bump 0.1.0 → 0.1.1 to preserve the alignment policy from v0.1.0. None of the 12 in-repo runtimes ship to PyPI in v0.1.1 either; that follow-up is per-package and tracked separately.
- Layer-1 sensor schema is normative at v0.1.0 still; the v0.2 iteration ([RFC-0039](docs/rfcs/0039-sensor-schema-v0-2-iteration.md)) lands in a future spec-bumping release once Accepted.
- Phase 1 cosmetics on urml.dev shipped in the website repo (separate from this changelog): why-now hook, architecture SVG, audience-segmented CTAs, Phase 0 → Phase 1 chrome refresh ([urml-website#11](https://github.com/urml-dev/urml-website/pull/11), [#12](https://github.com/urml-dev/urml-website/pull/12)).

## [0.1.0] — 2026-05-22

First public release. URML moves from Phase 0 (solo-author working in public) to **Phase 1**: `pip install urml-validator` (and four sibling packages) ships, external contributions open per [`CONTRIBUTING.md`](CONTRIBUTING.md). The strategic posture, the Core Commitment, and the substrate-neutrality contract are unchanged from the manifesto; what changes is the gate.

### Added — Specification

- **Layer 1 (HAL).** Capability manifest with provenance, safety envelope, and connectivity / link-loss as a validated safety contract. Normative at v0.1.0. RFCs [0001](docs/rfcs/0001-rfc-process.md), [0002](docs/rfcs/0002-initial-primitive-vocabulary.md), [0006](docs/rfcs/0006-connectivity-and-link-loss.md), [0009](docs/rfcs/0009-legged-humanoid-mobility.md), [0014](docs/rfcs/0014-substrate-conformance.md).
- **Layer 2 (intent primitives).** 20 normative primitives: 12 core (`move_to`, `dock`, `hover`, `wait`, `wait_for`, `grasp`, `release`, `detect`, `scan`, `measure`, `capture`, `report`) plus 8 profile-scoped (`speak`/`listen` home; `take_off`/`land`/`return_to_home` drone; `pick_from`/`place_at`/`swap_tool` industrial). RFCs [0002](docs/rfcs/0002-initial-primitive-vocabulary.md), [0013](docs/rfcs/0013-industrial-layer2-primitives.md).
- **Layer 3 (behavior composition).** `sequence` / `branch` / `parallel` / `retry` + `on_error` (`abort_and_report` / `continue` / `retry`). Normative at v0.1.0.
- **Layer 4 (natural-language bridge).** Provider-agnostic prompt contract, validator-feedback revision loop with policy-error short-circuit, schema-derived GBNF + GGUF contract for on-device models. RFC [0021](docs/rfcs/0021-on-device-llm-bridge.md).
- **Profiles.** home, drone, industrial, educational, research, warehouse — each with its own README, default safety envelope, and conformance fixtures. RFCs [0011](docs/rfcs/0011-educational-profile.md), [0012](docs/rfcs/0012-research-profile.md), [0022](docs/rfcs/0022-warehouse-domain-profile.md).
- **Compliance policy enforcement.** Provenance schema on the manifest, pluggable YAML policy DSL, bundled US-federal default policy aligning with NDAA §889 / FY26, FCC Covered List (effective 2025-12-23), Executive Order 14307, and the American Security Robotics Act once enacted. `--no-policy` opt-out. RFCs [0003](docs/rfcs/0003-us-alignment.md), [0004](docs/rfcs/0004-compliance-policy.md), [0005](docs/rfcs/0005-hbom-parsing.md).
- **Substrate-conformance contract.** What it means for a runtime to be URML-compatible, codified normatively. RFC [0014](docs/rfcs/0014-substrate-conformance.md).

### Added — Reference implementation (PyPI)

Five canonical packages ship on PyPI in v0.1.0:

- [`urml-validator`](reference/validator/) — five-pass static validator (argument typing → capability → safety envelope → variable bindings → compliance policy) and the `urml` CLI with seven subcommands: `validate`, `execute`, `schema`, `translate`, `emit-prompt`, `init`, `conformance run`.
- [`urml-ros2-runtime`](reference/ros2-runtime/) — `MockROSAdapter` (hermetic, zero-dep) plus `RclpyAdapter` against the live ROS 2 graph (Nav2, MoveIt 2, vision_msgs). The `home/nav_patrol_positive` conformance fixture is end-to-end verified ×3 on a TurtleBot 4 + Nav2 + Gazebo Ignition simulation via the gated `gazebo-e2e` CI job — green at the job level on three calibration runs; not a hardware-verification claim.
- [`urml-llm-bridge`](reference/llm-bridge/) — provider-agnostic NL → URML bridge with `Anthropic`, `OpenAI`, hermetic `Echo`, plus on-device `llama_cpp` and `ollama` providers (RFC [0021](docs/rfcs/0021-on-device-llm-bridge.md)). Schema-derived GBNF grammar; GGUF model contract; per-model conformance harness.
- [`urml-px4-runtime`](reference/px4-runtime/) — `PX4Adapter` via `pymavlink` (no ROS dependency); `CompositeAdapter` routes a single URML program across a PX4 flight backend and a ROS 2 companion. Hermetic + gated SITL e2e.
- [`urml-conformance`](conformance/) — 101 declarative YAML fixtures (auto-discovered) across 10 profiles, runnable via `urml conformance run`; the bring-your-own-adapter kit for runtime authors.

### Added — Twelve further reference runtimes (in-repo, not on PyPI in v0.1.0)

Hermetic suites green; live e2e is gated CI (calibration-staged, **not** a hardware claim):

- `marine` (BlueROV2 / ArduSub), `industrial-arm` (16 brand adapters: ABB / FANUC / KUKA / YASKAWA / UR / Franka / Kawasaki / Stäubli / Comau / Mitsubishi / Denso / Hyundai / Nachi / Epson / Omron / Hanwha), `legged` (Spot / ANYmal), `humanoid` (Digit), `mobile` (Husky / Jackal); the zero-ROS `opcua` (OPC UA Robotics) and `cobot` (8 native SDKs: UR / Franka / Doosan / Techman / Kinova / Mecademic / Neura / Kassow); `mujoco` and `isaac` (NVIDIA Sim/Lab, local RTX host) sims; `embedded` (micro:bit / Arduino serial); `edu` (VEX / LEGO SPIKE / Thymio); `autosar` (RFC [0019](docs/rfcs/0019-autosar-adaptive-substrate.md) scaffold). Autoware ships manifest + spec only pending RFC [0020](docs/rfcs/0020-autoware-av-substrate.md). Each is one `pip install -e <path>` away from runnable; PyPI follow-up per package.

### Added — Conformance & lighthouses

- **101 conformance fixtures** under `conformance/fixtures/`, hermetic against `MockROSAdapter`: home 18, drone 14, industrial 44, biped 5, quadruped 4, mobile 2, warehouse 8, marine 1, educational 4, research 1. Auto-discovered.
- **Move #1 lighthouse program.** Per-vendor request-for-comment RFCs to 16 Tier-1 vendors (RFCs 0023–0038): Yaskawa, Universal Robots, KUKA, Stäubli, Mitsubishi MELFA, FANUC, Kawasaki, Denso, SCHUNK, Ouster, SICK, Festo, Zivid, Hokuyo, OSRF / Gazebo Sim, ROS-Industrial Consortium. Per-vendor outreach state tracked in `examples/lighthouses/outreach.yaml`; the parameterized demo runner in `examples/lighthouses/demo.py` exercises any single vendor's conformance fixture hermetically.

### Added — Tooling & developer experience

- `make demo` / `make demo-run` / `make demo-record` / `make audit` / `make test`. The flagship `make demo-run` is the universal-language pitch concretised: one English sentence becomes a validated URML program becomes an executed step-by-step trace, hermetic, any-OS, no API key, no robot. The animated SVG hero in the README is exactly what `make demo-run` prints (every line asserted in CI via [`reference/validator/tests/test_demo_svg.py`](reference/validator/tests/test_demo_svg.py)).
- [`tools/scripts/refresh_audit.py`](tools/scripts/refresh_audit.py) — stdlib-only re-measurer for the front-page numbers; honest about rows the host cannot remeasure; does not auto-edit. `make audit`.

### Added — Process & community

- RFC process (RFC [0001](docs/rfcs/0001-rfc-process.md)): Draft → Open → Accepted → Implemented with a 7-day Phase-0 comment window; 22 Spec RFCs and 16 Outreach RFCs filed and indexed (Kind column distinguishes the two; see [`docs/rfcs/README.md`](docs/rfcs/README.md)).
- Public GitHub Discussions open (Q&A, Ideas, Show-and-tell, Builders & Makers, General) per RFC [0008](docs/rfcs/0008-community-discussions.md).
- Manufacturer go-to-market wedge per RFC [0007](docs/rfcs/0007-manufacturer-go-to-market.md); the live manufacturer / federal-validation surface on [urml.dev](https://urml.dev).
- US-federal regulatory alignment per RFC [0003](docs/rfcs/0003-us-alignment.md). Strategic trade-offs accepted in writing.

### Test surface (claims-audit, measured 2026-05-20 with partial 2026-05-22 re-run)

- **765 passed + 28 gated-skipped** across 16 reference packages.
- Live integration is gated CI (`*-integration.yml`, workflow_dispatch + weekly cron). First run of any live e2e is a calibration baseline, not a regression signal. Backing is recorded in [`docs/launch/claims-audit.md`](docs/launch/claims-audit.md).

### Honest scope (no overclaiming)

- **No physical-hardware verification.** Live e2e is simulated (Gazebo / PX4 SITL) or gated CI calibration. Where the README says "verified," it means the gated CI job was green; that is the load-bearing claim, not a hardware-on-a-bench claim.
- **Compliance enforcement is not legal advice.** The bundled default policy mirrors enacted US federal procurement law as of release date; deployers consult counsel. Disclaimers in [`docs/launch/claims-audit.md`](docs/launch/claims-audit.md) and the bundled policy file.
- **Five canonical packages on PyPI in v0.1.0; the twelve further runtimes follow per-package** as each is ready.
- **One maintainer.** Phase 1 opens external contributions; it does not assert contributors have arrived. The `Status: one person` line in [`GOVERNANCE.md`](GOVERNANCE.md) remains true until it isn't.

---

*Released versions are appended above this line as `[X.Y.Z] — YYYY-MM-DD` sections.*
