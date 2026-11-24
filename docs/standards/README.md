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

# Robot standards, regulations and certifications: a directory

Robots are covered by standards, laws and certification schemes from many bodies, and the names alone rarely say which one applies to you, whether it is binding, or who can attest to it. This page is a map. For each entry it says what it is, why it matters, who needs it, how you meet it, who issues or assesses it, and what URML gives you for it.

It is a starting point, not advice. Which documents apply to a machine depends on what it is, where it works and who buys it; decide that with your risk assessment, a licensed copy of each standard, and, for anything binding, counsel. URML quotes no copyrighted standard text. Editions were checked on 2026-11-24; check the publisher's catalogue before relying on a year.

## Legend

**Kinds of document**

| Kind | What it is | Binding? |
|---|---|---|
| Standard | A consensus document from a standards body (ISO, IEC, ANSI-accredited bodies such as A3 and UL, industry associations such as VDA). It says how to do something well. | Not by itself. It becomes binding when a law, a contract or a buyer requires it. |
| Regulation | Law or a rule made under law (14 CFR Part 107, NDAA Section 889). | Yes, for whoever it covers. |
| Certification | A third party's statement, after an assessment, that a product, process or person meets a document. | Only as far as a law or a buyer requires it. |
| Listing or mark | A certification you can see on the product, issued by an accredited lab, such as an NRTL listing to a UL standard. | Often required by employers, insurers and local inspectors. |
| Self-declaration | The maker states conformance and keeps the evidence. | Carries the maker's liability. |
| Procurement list | A list a buyer uses to admit or exclude vendors, such as the FCC Covered List or the DCMA Blue List. | Binding on that buyer's purchases. |

**Who does what**

| Term | Meaning |
|---|---|
| Standards body | Writes and sells the document: ISO, IEC, ANSI (the US member of ISO and IEC, and its webstore), A3, UL Standards & Engagement, ISA, VDA. |
| Certification body | Assesses and issues certificates: for example TÜV SÜD, TÜV Rheinland, UL Solutions, SGS, Intertek, DEKRA, exida. The standards body usually does not certify. |
| NRTL | Nationally Recognized Testing Laboratory: a lab OSHA recognizes to certify products to listed US safety standards. |
| Risk assessment | The analysis of a specific machine at a specific site that decides which requirements and which levels apply. Nearly every safety and security standard starts from it. |
| PL, SIL, SL | Performance level (ISO 13849), safety integrity level (IEC 62061, IEC 61508), security level (IEC 62443): how much a safety function or a security zone must withstand. |

**What URML gives you**

| URML support | Meaning |
|---|---|
| Rulebook template | A file that turns the standard's checkable limits into rules the validator enforces before a program runs, and lists the rest as obligations. It carries no values from the standard. |
| Runtime | A URML runtime that speaks the protocol. |
| Position page | A page that says where URML stands under the standard and what it does not claim. |
| Bundled rules | Checks that ship in the validator and are on by default. |
| Evidence report | `urml evidence build` lists, per deployment, what URML checks for each cited standard and what it leaves to others. |

URML is never a safety function, a security control or a certifier for any document below. It refuses programs that break declared limits, and it records what was declared. The certificates themselves come from the bodies named in each entry.

## Index

| Entry | Kind | Area | Who needs it | URML support |
|---|---|---|---|---|
| [ISO 10218-1 and -2:2025, ANSI/A3 R15.06-2025](#iso-10218-industrial-robots) | Standard | Industrial robot safety | Robot makers, integrators, users of industrial robots | Rulebook template |
| [ISO/TS 15066:2016](#isots-15066-collaborative-operation) | Technical specification | Collaborative robots | Anyone running robots alongside people | Rulebook template (force and speed caps) |
| [ISO 3691-4:2023, ANSI/A3 R15.08](#iso-3691-4-and-ansia3-r1508-mobile-robots) | Standard | Mobile robots, AGVs | Makers and sites running AMRs and AGVs | Rulebook template |
| [ISO 13482:2014](#iso-13482-personal-care-robots) | Standard | Personal care robots | Makers of service robots that work near people | Rulebook template |
| [ISO 13849-1:2023, -2](#iso-13849-safety-related-control) | Standard | Functional safety of machinery | Anyone designing safety functions | Rulebook template |
| [IEC 62061:2021](#iec-62061-functional-safety-of-machinery) | Standard | Functional safety of machinery | Designers of electrical safety control | Rulebook template |
| [IEC 61508:2010](#iec-61508-basic-functional-safety) | Standard | Functional safety, all sectors | Makers of safety components; robots outside machinery standards | Rulebook template, position page |
| [IEC 62443](#iec-62443-industrial-cybersecurity) | Standard series | Industrial cybersecurity | Asset owners, integrators, makers of control products | Rulebook template, position page |
| [UL 1740, UL 3100, UL 3300](#ul-1740-ul-3100-ul-3300-us-product-listings) | Standard, listing | US product safety | Makers selling robots into US workplaces and public spaces | None yet |
| [ISO 8373:2021](#iso-8373-vocabulary) | Standard | Vocabulary | Anyone writing about robots precisely | Alignment page |
| [VDA 5050](#vda-5050-fleet-interface) | Industry standard | AGV and AMR fleet interface | Fleet operators, vehicle makers | Runtime |
| [ISO 21423](#iso-21423-mobile-robot-interoperability) | Standard | Mobile robot interoperability | Fleet operators, robot makers | Runtime (validation in progress) |
| [14 CFR Part 107 and Part 89](#14-cfr-part-107-and-part-89-small-drones) | Regulation | Small drones in the US | Anyone flying a drone commercially in the US | Bundled rules |
| [NDAA Section 889, FCC Covered List, DCMA Blue List](#ndaa-section-889-fcc-covered-list-dcma-blue-list) | Regulation, procurement lists | Supply chain | Vendors to the US government and its contractors | Bundled policy |
| [URML-Certified](#urml-certified) | Certification | URML conformance | Makers of third-party URML runtimes | The program itself |
| [Evidence report](#evidence-reports) | Not a certification | Evidence for all of the above | Integrators, auditors, buyers | `urml evidence` |

## Machine safety

### ISO 10218, industrial robots

- **What it is.** ISO 10218-1:2025 (the robot) and ISO 10218-2:2025 (robot applications and cells): the international safety requirements for industrial robots. In the US they are adopted as ANSI/A3 R15.06-2025, which replaces R15.06-2012 and adds a US-only Part 3 for users.
- **Why it matters.** It is the reference a buyer, an insurer, an inspector or a court uses to ask whether an industrial robot cell was made safely. OSHA has no robot-specific standard and looks to consensus standards such as R15.06.
- **Who needs it.** Robot makers (part 1), integrators who build cells (part 2), and companies that run them (R15.06-3).
- **How to achieve it.** Do a risk assessment of the cell; design the safeguards and safety functions it calls for; validate them; keep the technical file. Makers usually declare conformance, often backed by a third-party assessment.
- **From whom.** Text: ISO, or the ANSI webstore for R15.06. Assessment: certification bodies such as TÜV SÜD, TÜV Rheinland, UL Solutions or SGS.
- **What URML gives you.** [`industrial-template.yaml`](https://github.com/urml-dev/URML/blob/main/examples/rulebooks/industrial-template.yaml): speed and force caps, a program allowlist, untouched safety outputs, and the obligations URML cannot check.

### ISO/TS 15066, collaborative operation

- **What it is.** ISO/TS 15066:2016, the technical specification for robots that share space with people: power and force limiting, speed and separation monitoring. ISO 10218-2:2025 now incorporates its content.
- **Why it matters.** It is where the limits for contact between a robot and a person come from.
- **Who needs it.** Anyone running a collaborative application.
- **How to achieve it.** As for ISO 10218: risk assessment, limits set per body region and task, measurement and validation of the application.
- **From whom.** Text: ISO or ANSI. Assessment: the same certification bodies.
- **What URML gives you.** The force and speed caps in the industrial template; values come from your licensed copy.

### ISO 3691-4 and ANSI/A3 R15.08, mobile robots

- **What it is.** ISO 3691-4:2023, safety requirements for driverless industrial trucks and their systems. ANSI/A3 R15.08-1-2020 (reaffirmed 2026), R15.08-2-2023 and R15.08-3-2026, the US standard for industrial mobile robots: the robot, the system and site, and the user.
- **Why it matters.** Warehouses and factories now run fleets among people; these documents set how the vehicles detect people, slow, stop and stay in their zones.
- **Who needs it.** Makers of AMRs and AGVs, integrators, and sites that run them.
- **How to achieve it.** Risk assessment of the site and routes; safety-rated personnel detection and speed control; marked zones; validation; training.
- **From whom.** Text: ISO; A3 or the ANSI webstore for R15.08. Assessment: certification bodies.
- **What URML gives you.** [`amr-template.yaml`](https://github.com/urml-dev/URML/blob/main/examples/rulebooks/amr-template.yaml): a travel-speed cap, forbidden zones, load handling only at stations, a program allowlist.

### ISO 13482, personal care robots

- **What it is.** ISO 13482:2014, safety requirements for robots that work close to people outside industry: mobile servants, physical assistants, person carriers. ISO is revising it.
- **Why it matters.** It is the main international reference for service robots in homes, care and public spaces.
- **Who needs it.** Makers of personal care and service robots.
- **How to achieve it.** Hazard identification and risk assessment of the robot in its intended use, then the protective measures and validation the standard calls for.
- **From whom.** Text: ISO. Assessment: certification bodies.
- **What URML gives you.** [`home-template.yaml`](https://github.com/urml-dev/URML/blob/main/examples/rulebooks/home-template.yaml): speed and grip-force caps, hazard zones, no handling in excluded zones.

### ISO 13849, safety-related control

- **What it is.** ISO 13849-1:2023 (design) and ISO 13849-2 (validation): how to design the parts of a machine's control system that perform safety functions, rated by performance level, PLa to PLe.
- **Why it matters.** An emergency stop, a protective stop or speed monitoring is only as good as its design; the required PL says how good it must be.
- **Who needs it.** Machine and robot makers, integrators who add safety functions.
- **How to achieve it.** Set the required level (PLr) from the risk assessment; design the architecture; calculate and validate the achieved PL; document it.
- **From whom.** Text: ISO. Product and component certification: bodies such as TÜV SÜD, TÜV Rheinland, exida, UL Solutions. Personnel certification in functional safety exists too.
- **What URML gives you.** [`functional-safety-template.yaml`](https://github.com/urml-dev/URML/blob/main/examples/rulebooks/functional-safety-template.yaml): programs wait until each safety function's achieved level is declared and meets the requirement. URML counts toward no PL.

### IEC 62061, functional safety of machinery

- **What it is.** IEC 62061:2021 with Amendment 1:2024: the machinery standard for safety-related control, rated by SIL 1 to 3. A machine is designed to it or to ISO 13849.
- **Why it matters, who needs it, how, from whom.** As for ISO 13849, in the SIL vocabulary.
- **What URML gives you.** The same functional-safety template, which takes SILs.

### IEC 61508, basic functional safety

- **What it is.** IEC 61508:2010, parts 1 to 7, edition 2.0: the basic functional-safety standard for electrical, electronic and programmable systems, SIL 1 to 4. IEC 62061 applies it to machinery. Edition 3 is forecast for 2027.
- **Why it matters.** Safety controllers, drives with safe torque off and safety-rated sensors are designed and certified to it, and robots outside the machinery standards use it directly.
- **Who needs it.** Makers of safety components and of safety-related software.
- **How to achieve it.** The full safety lifecycle: hazard analysis, safety requirements, design and verification to the target SIL, and, for software, development to IEC 61508-3.
- **From whom.** Text: IEC. Certification: bodies such as TÜV SÜD, TÜV Rheinland, exida, UL Solutions.
- **What URML gives you.** The functional-safety template (SIL 1 to 4) and [a position page](https://github.com/urml-dev/URML/blob/main/docs/safety/iec-61508.md): URML is outside the safety-related system and has no SIL.

## Security

### IEC 62443, industrial cybersecurity

- **What it is.** ISA/IEC 62443, the series for the security of industrial automation and control systems. Parts used most: 2-1 (the asset owner's security program), 3-2 (risk assessment, zones and conduits), 3-3 (system requirements and security levels SL 1 to 4), 4-1 (secure development lifecycle) and 4-2 (component requirements).
- **Why it matters.** Robots are networked control systems. Buyers in manufacturing, energy and logistics increasingly ask suppliers for IEC 62443 evidence.
- **Who needs it.** Asset owners (2-1, 3-2), integrators (3-3), and makers of control products (4-1, 4-2).
- **How to achieve it.** Model the site as zones and conduits; set target levels from a security risk assessment; meet the system and component requirements; for products, develop under a 4-1 lifecycle.
- **From whom.** Text: IEC or ISA (identical ANSI/ISA editions). Certification: the ISASecure schemes of the ISA Security Compliance Institute (SDLA for the 4-1 development process, SSA for systems against 3-3, CSA for components against 4-2), the IECEE scheme, and certification bodies.
- **What URML gives you.** [`cybersecurity-template.yaml`](https://github.com/urml-dev/URML/blob/main/examples/rulebooks/cybersecurity-template.yaml) and [a position page](https://github.com/urml-dev/URML/blob/main/docs/security/iec-62443.md) that maps URML against the foundational requirements and states its gaps. URML is not a security control and claims no SL.

## US product listings

### UL 1740, UL 3100, UL 3300, US product listings

- **What it is.** US product safety standards published by UL: UL 1740 for industrial robots and robotic equipment, UL 3100 for automated mobile platforms, and ANSI/CAN/UL 3300 for service, communication, information, education and entertainment robots. A robot is tested and listed to one of them by an NRTL.
- **Why it matters.** Employers, insurers and local electrical inspectors in the US often expect equipment to carry an NRTL listing.
- **Who needs it.** Makers selling robots into US workplaces and public spaces. Pick the standard by robot type and check its scope.
- **How to achieve it.** Design to the standard, submit the product to an NRTL for testing, then keep the listing through the lab's follow-up inspections.
- **From whom.** Text: UL Standards & Engagement. Testing and listing: NRTLs such as UL Solutions, Intertek, TÜV Rheinland or CSA Group; OSHA publishes which lab is recognized for which standard.
- **What URML gives you.** Nothing specific yet. A listing concerns the robot's hardware and electrical safety, below anything URML touches.

## Vocabulary and interoperability

### ISO 8373, vocabulary

- **What it is.** ISO 8373:2021, the international robotics vocabulary.
- **Why it matters.** Specifications, contracts and safety files read the same way when they use the same words.
- **Who needs it.** Anyone writing requirements or documentation about robots.
- **How to achieve it, from whom.** Nothing to certify; buy the text from ISO.
- **What URML gives you.** [An alignment page](https://github.com/urml-dev/URML/blob/main/docs/iso-8373-alignment.md) that lines up URML's terms with the standard's.

### VDA 5050, fleet interface

- **What it is.** VDA 5050 3.0.0, the interface between a fleet controller and AGVs or AMRs over MQTT, published by the German automotive and machinery associations VDA and VDMA.
- **Why it matters.** One controller can drive vehicles from different makers.
- **Who needs it.** Fleet operators and vehicle makers.
- **How to achieve it.** Implement the messages and state machine; test against the official schemas and the other side's implementation. The specification is free; we know of no formal certification scheme for it.
- **From whom.** The VDA 5050 repository on GitHub.
- **What URML gives you.** [`urml-vda5050-runtime`](https://github.com/urml-dev/URML/tree/main/reference/vda5050-runtime), on PyPI, and paid fleet and vehicle validation ([pricing](https://urml.dev/pricing)).

### ISO 21423, mobile robot interoperability

- **What it is.** ISO 21423:2026, interoperability between industrial mobile robots, their fleet managers and site systems over MQTT.
- **Why it matters, who needs it.** As for VDA 5050, as an ISO standard.
- **How to achieve it, from whom.** Implement it from a licensed copy bought from ISO; we know of no certification scheme yet.
- **What URML gives you.** [`urml-iso21423-runtime`](https://github.com/urml-dev/URML/tree/main/reference/iso21423-runtime), built from public material based on the draft. Validation against the published standard is in progress, and URML makes no conformance claim until it is done.

## Regulation and procurement

### 14 CFR Part 107 and Part 89, small drones

- **What it is.** The FAA's rules for small unmanned aircraft in the US: operating rules (Part 107) and Remote ID (Part 89).
- **Why it matters.** It is federal law for commercial drone flights.
- **Who needs it.** Anyone flying a small drone for work in the US, and drone makers (Remote ID).
- **How to achieve it.** The remote pilot passes the FAA's aeronautical knowledge test and gets a remote pilot certificate; the aircraft is registered; it broadcasts Remote ID from a standard Remote ID drone or a broadcast module covered by an FAA-accepted declaration of compliance; operations outside the rules need a waiver or authorization through the FAA's DroneZone.
- **From whom.** The FAA.
- **What URML gives you.** The [bundled Part 107 rulebook](https://github.com/urml-dev/URML/blob/main/reference/validator/src/urml_validator/rulebooks/us_faa_part107.yaml), on by default for aircraft: altitude, speed and over-people limits, one aircraft per pilot, Remote ID declared, and the rules no static check can see as obligations. A refusal is not a legal determination.

### NDAA Section 889, FCC Covered List, DCMA Blue List

- **What it is.** US supply-chain rules. NDAA Section 889 bars federal agencies and their contractors from certain telecommunications and video-surveillance equipment; later NDAAs extend similar limits to drones and their parts. The FCC Covered List names equipment the FCC no longer authorizes. The Blue List of drones cleared for Department of Defense use, formerly DIU's Blue UAS list, is now managed by DCMA.
- **Why it matters.** It decides who can sell robots and drones to the US government and its contractors.
- **Who needs it.** Vendors to federal agencies and contractors, and anyone whose customers are.
- **How to achieve it.** Know and document where every critical component comes from; make the contract representations; for the Blue List, go through DCMA's review.
- **From whom.** The statutes and FAR clauses; the FCC; DCMA.
- **What URML gives you.** The [bundled compliance policy](https://github.com/urml-dev/URML/blob/main/reference/validator/src/urml_validator/policies/us_federal_default.yaml), on by default for `urml validate`, which checks the component origins a manifest declares. It is not legal advice and not a procurement determination.

## URML's own

### URML-Certified

- **What it is.** A free certification that a third-party runtime conforms to the URML specification for its profiles ([RFC-0705](https://github.com/urml-dev/URML/blob/main/docs/rfcs/0705-urml-certified.md)).
- **Why it matters.** A buyer can tell that a runtime's conformance claim was reproduced by someone other than its authors.
- **Who needs it.** Makers of URML runtimes for their robots or substrates.
- **How to achieve it.** Pass the full conformance suite with your own adapter, publish the package, and the Licensor reproduces the run offline from the public package. It lasts at most 366 days.
- **From whom.** The Licensor, Yahalomik Ltd., through the [registry](https://urml.dev/registry). Free.
- **What it is not.** It certifies conformance to URML only: not safety, not security, not regulatory compliance.

### Evidence reports

- **What it is.** Not a certification. `urml evidence build` writes one report per robot deployment that marks every item checked, declared, runtime, missing or outside, and regroups the rules by the standard each one cites ([RFC-0707](https://github.com/urml-dev/URML/blob/main/docs/rfcs/0707-evidence-report.md)).
- **Why it matters.** It gives integrators, auditors and buyers one page that shows, for every entry above that a deployment cites, what URML checks and what someone else must cover.
- **How to get one.** Run it yourself and rebuild it to check it ([worked example](https://github.com/urml-dev/URML/tree/main/examples/evidence-report)), or ask the Licensor for a reviewed report through the [validation services](https://urml.dev/pricing).

## Missing something?

This directory lists what URML supports or what its users ask about most. To add an entry, open a pull request against `docs/standards/README.md` with the publisher's catalogue link for the edition.
