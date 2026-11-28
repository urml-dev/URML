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

# Rulebooks: government and company rules the validator checks

A rulebook states what law or a company allows a robot to do. The validator checks every program against the rulebooks that apply to it, after the safety envelope, and cites the rule when it refuses. The format is in [`spec/layer-1-hal/rulebook.md`](../../spec/layer-1-hal/rulebook.md) and the decision record is [RFC-0702](../../docs/rfcs/0702-rulebooks.md).

These files are a Draft, like RFC-0702. The reference validator reads them: `--rulebook PATH` loads an organization or deployment rulebook, and the bundled FAA rulebook applies by default to aircraft.

## Four files, four owners

| File | Says | Owner |
|---|---|---|
| Manifest | what the robot can do | the robot's maker or integrator |
| Safety envelope | what this site allows physically | the site operator |
| Rulebook | what law and company policy allow | a regulator or an organization; the operator, for declarations and exceptions |
| Compliance policy | what the robot may be made of | procurement |

A rulebook names places and never draws them. A zone name in a rule resolves against the manifest's `declared_areas`, then the envelope's `people_occupancy_zones` and `geofences`.

## The files here

| File | Kind | What it shows |
|---|---|---|
| [`example-warehouse.yaml`](example-warehouse.yaml) | organization | Example Logistics, a fictional company: no photos or video in the restrooms or the HR office, no entry to the server room or the hazmat cage, an allowlist of controller programs, and a 1.5 m/s speed cap |
| [`example-site-standard.yaml`](example-site-standard.yaml) | organization | The same fictional company's site standard: every site declares the area its robots may work in and a speed limit, as two `require_envelope` rules. Until the site's safety envelope sets both, every program is refused with `rule.limit_missing`. Without such a rule, a limit nobody set is not checked, and the program is accepted. |
| [`example-deployment.yaml`](example-deployment.yaml) | deployment | A fictional drone operator: one declaration (a Remote ID broadcast module) and one exception (a fictional certificate of waiver that raises the altitude limit to 500 feet, 152.4 m) |
| [`industrial-template.yaml`](industrial-template.yaml) | organization, template | How an integrator maps ISO 10218-1:2025, ISO 10218-2:2025 (adopted in the US as ANSI/A3 R15.06-2025) and ISO/TS 15066:2016 onto rules and obligations, plus the user obligations of ANSI/A3 R15.06-3-2025, with the robot's UL 1740 listing on record (listing standard and NRTL reference). It carries no values: the ISO text is copyrighted, and every value comes from the integrator's risk assessment and licensed copy. An unfilled template fails to load |
| [`amr-template.yaml`](amr-template.yaml) | organization, template | The same for a site's mobile robots (AMRs and AGVs), after ISO 3691-4:2023 and ANSI/A3 R15.08-1, -2 and -3: a travel-speed cap, zones the robots stay out of, load handling only at stations, a program allowlist, untouched safety outputs, the robot's UL 3100 listing on record (listing standard and NRTL reference), and the obligations URML cannot check. Values from the integrator's licensed copies; an unfilled template fails to load |
| [`functional-safety-template.yaml`](functional-safety-template.yaml) | organization, template | After ISO 13849-1:2023 / ISO 13849-2, IEC 62061:2021 and IEC 61508:2010, with the drives' safety functions after IEC 61800-5-2:2016: programs are refused until the operator's deployment rulebook declares the level each safety function reached (emergency stop, protective stop, speed monitoring), as a performance level (`PLa`..`PLe`) or a safety integrity level (`SIL1`..`SIL3`, and `SIL4` under IEC 61508), and the validation record. URML checks the declaration, not the safety function, and counts toward no PL or SIL. An unfilled template fails to load |
| [`cybersecurity-template.yaml`](cybersecurity-template.yaml) | organization, template | After IEC 62443-3-2:2020 and IEC 62443-3-3:2013: programs are refused until the operator's deployment rulebook declares the security level (`SL1`..`SL4`) the robot's zone and the URML host's zone achieved, and the zone and conduit model and security risk assessment on record. URML is not a security control and counts toward no security level; [`docs/security/iec-62443.md`](../../docs/security/iec-62443.md) says where it stands. An unfilled template fails to load |
| [`machinery-safety-template.yaml`](machinery-safety-template.yaml) | organization, template | After the machinery safety basics: ISO 12100:2010 (risk assessment), ISO 13850:2015 (emergency stop), ISO 13855:2024 (positioning of safeguards), ISO 14119:2024 (interlocking), IEC 60204-1:2016 (electrical equipment), IEC 61496-1:2020 / -3:2025 (light curtains and scanners) and IEC 61800-5-1:2022 (electrical safety of the drives, as an obligation). Programs are refused until the operator declares the risk assessment, the emergency stop's stop category, the safeguard distances, the interlocking, the protective-device type and the electrical verification; programs never write the outputs that drive safeguards. URML never implements or replaces the emergency stop. An unfilled template fails to load |
| [`service-robot-template.yaml`](service-robot-template.yaml) | organization, template | For service robots in public and commercial spaces, after ANSI/CAN/UL 3300 (SCIEE robots): a travel-speed and grip-force cap, hazard zones, a program allowlist, and programs refused until the robot's listing standard and NRTL listing are on record. The listing comes from an NRTL; URML is not part of it and changes nothing it covers. An unfilled template fails to load |
| [`eu-machinery-regulation.yaml`](eu-machinery-regulation.yaml) | government (EU) | Regulation (EU) 2023/1230 on machinery, applying from 20 January 2027, with its own article and annex citations and nothing to fill in. Programs are refused until the operator's deployment rulebook declares the risk assessment, the outcome of the substantial-modification check for integrating URML (Article 3(16), Article 18), the conformity assessment procedure (module A, B+C, H or G, Article 25), the EU declaration of conformity, the technical file and the inventory of safety-relevant software (Annex III, 1.1.9). Its obligations say why URML is not a safety component (Annex II, point 18) and never prevents a stop. Not a default: load it with `--rulebook` |
| [`eu-ai-act.yaml`](eu-ai-act.yaml) | government (EU) | Regulation (EU) 2024/1689 (AI Act) as amended by the Digital Omnibus on AI, Regulation (EU) 2026/1744, for a robot whose programs an AI system proposes through the LLM bridge. Programs are refused until the operator declares whether the AI system is a safety component (Article 6(1a) and (1b)), how people are told they deal with an AI system (Article 50(1)) and the AI literacy measures (Article 4). Obligations: no proposed program skips the validator, a high-risk AI safety component is assessed through the Machinery Regulation (machinery moved to Annex I, Section B; AI requirements by 2 August 2028), no emotion inference at work, and the model provider's own obligations. A robot with no AI system declares `ai_system_in_use: false` and it switches off. Not a default |
| [`eu-cyber-resilience-act.yaml`](eu-cyber-resilience-act.yaml) | government (EU) | Regulation (EU) 2024/2847 (Cyber Resilience Act), applying from 11 December 2027, with its reporting duty (Article 14) in force since 11 September 2026. Programs are refused until the operator declares the product class (Annexes III and IV), the conformity procedure (Article 32), the cybersecurity risk assessment, the software bill of materials, the end of the support period, the vulnerability contact and the EU declaration of conformity. Obligations: 24-hour reporting of exploited vulnerabilities, URML as a third-party component, secure connections by default (TLS and credentials for the MQTT runtimes), security updates, and recording security-relevant activity. Not a default |
| [`home-template.yaml`](home-template.yaml) | organization, template | The same for a personal care robot of the mobile-servant kind, after ISO 13482:2014: travel-speed and grip-force caps, hazard zones, no grasping or releasing in excluded zones, a program allowlist, and the obligations URML cannot check. ISO is revising 13482; check the cites when the new edition is out. An unfilled template fails to load |

The bundled government rulebook lives with the validator: [`us_faa_part107.yaml`](../../reference/validator/src/urml_validator/rulebooks/us_faa_part107.yaml), the statically checkable subset of 14 CFR Part 107 and Part 89. It applies by default to drone programs and to any robot whose manifest declares an aircraft drive type, and `--no-policy` does not switch it off. `--no-default-rulebooks` does, with a warning.

Everything named Example Logistics, Example Aerial Survey or 107W-EXAMPLE-0001 is fictional.

## How the pieces fit

The FAA rulebook caps altitude at 121.92 m (400 feet) above ground level. A program that takes off to 137.16 m (450 feet) is refused, even with `--no-policy` (an excerpt of the output):

```text
  ERROR [rule.cap_exceeded] behavior/steps/0
    field: altitude
    14 CFR 107.51(b): maximum altitude 400 feet (121.92 m) above ground level. take_off.altitude is 137.16 m; the limit is 121.92 m.
    suggestion: Use a value at or below 121.92 m.
    rule: us_faa_part107/altitude_400ft_agl (Federal Aviation Administration, US)
    source: https://www.ecfr.gov/current/title-14/chapter-I/subchapter-F/part-107/subpart-B/section-107.51#p-107.51(b)
```

The operator's deployment rulebook records a waiver as an exception. The exception names its basis and a new limit, and the same program is accepted with a warning that names the waiver. The model cannot write that file: a waiver the user claims in a sentence changes nothing.

The rules a program cannot show, such as visual line of sight, night lighting and weather minimums, appear as obligations in every report. URML lists them and does not check them.

The commands:

```bash
urml validate program.urml.yaml -m manifest.yaml -e envelope.yaml \
  --rulebook examples/rulebooks/example-warehouse.yaml
urml validate flight.urml.yaml -m drone.manifest.yaml \
  --rulebook examples/rulebooks/example-deployment.yaml
```

The conformance fixtures under [`conformance/fixtures/rulebook/`](../../conformance/fixtures/rulebook/) run both files, and each rejected fixture also proves URML sent zero commands.

## Not legal advice

A program passing a rulebook is not a legal compliance determination. A rulebook checks the statically checkable subset of the rules it encodes, and the operator remains responsible for all of them. Verify the bundled rulebook against the current eCFR before relying on it; its `reviewed` date says when it was last checked.
