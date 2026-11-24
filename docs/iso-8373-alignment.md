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

# URML terms and ISO 8373:2021

[ISO 8373:2021](https://www.iso.org/standard/75539.html) (Robotics, Vocabulary; third edition, which replaced ISO 8373:2012) is the international vocabulary for robotics. This page lines up the words URML uses with the terms that standard defines, so a reader who knows one can read the other.

The table gives each ISO term's name and clause number and says, in URML's own words, how URML uses the idea. It does not reproduce ISO's definitions: the standard is copyrighted, and its definitions are in the standard. Where a definition matters to you, read clause and definition in a licensed copy.

**Coverage.** This page covers clause 3 (general terms) and clause 4 (mechanical structure), checked on 2026-11-24 against the publicly available preview of the standard. Clauses 5 to 9 (geometry and kinematics, programming and control, performance, sensing and navigation, modularity) are not mapped yet. Terms such as pose, workspace, task program, path and trajectory belong there, and adding them needs a licensed copy. A contribution with clause numbers checked against one is welcome.

## Two differences worth knowing

**URML's "validator" verifies.** In ISO 8373, as in ISO's quality vocabulary, *verification* (3.17) means confirming that specified requirements are met, and *validation* (3.16) means confirming fitness for the intended use. URML's validator checks a program against declared requirements: the robot's manifest, the site's safety envelope, the rulebooks and the compliance policy. In ISO's words that is verification. It does not establish that a robot or an application is fit for its use; a deployment's validation, in ISO's sense, stays with the integrator and the risk assessment. The name `urml validate` is kept because it is the established command; documents that need the ISO sense say "verification".

**"Operator" has two senses.** ISO 8373 uses *operator* (3.11) for the person who starts, monitors and stops a robot. URML documents also use "operator" for the organization that runs a site and owns its safety envelope and deployment rulebooks. When the difference matters, URML writes "site operator" for the organization.

## Clause 3: general terms

| ISO 8373:2021 | Clause | In URML |
|---|---|---|
| robot | 3.1 | Used for any machine a URML runtime drives, including drones, autonomous vehicles and underwater vehicles. Check 3.1 before assuming the two always coincide. |
| autonomy | 3.2 | Not a URML term. URML describes intent; how much the robot decides by itself is the substrate's design. The validator's job is the same at any level of autonomy. |
| control system | 3.4 | Part of what URML calls the **substrate** (ROS 2, PX4, a vendor controller): the software and hardware below URML that actually commands the actuators. |
| robotic device | 3.5 | Not used. A gripper, camera or sensor appears in URML as a block of the capability manifest. |
| industrial robot | 3.6 | The robots the **industrial** profile describes. |
| service robot | 3.7 | The robots the **home** and **social** profiles describe; mobile robots in logistics may be either, depending on the setting. |
| medical robot | 3.8 | Out of URML's scope: there is no medical profile. |
| robotics | 3.10 | Same everyday sense. |
| operator | 3.11 | See *Two differences worth knowing* above. |
| task programmer | 3.12 | Whoever writes a **URML program**: a person, or a language model through the LLM bridge with the validator checking its output. |
| collaboration | 3.13 | No URML term. The industrial profile's force and speed caps, and the home profile's `hand_to_user` release, are where collaborative operation shows up in programs. |
| robot cooperation | 3.14 | URML **fleet programs**: several robots in one program (`on`, `barrier`), checked by `validate_fleet`. |
| human-robot interaction | 3.15 | The home and social profiles' `speak`, `listen`, `look_at` and `gesture`, and the natural-language layer (Layer 4). |
| validation | 3.16 | See *Two differences worth knowing* above. |
| verification | 3.17 | What URML's **validator** does to a program. |

## Clause 4: mechanical structure

| ISO 8373:2021 | Clause | In URML |
|---|---|---|
| actuator | 4.1 | Same sense. URML's guarantee is phrased in it: a program is checked before any actuator moves. |
| robotic arm | 4.2 | An arm in the manifest's `manipulation` block (`arm_count`, `arms`). |
| robotic leg | 4.4 | Legged locomotion: `mobility.drive_type` `quadruped` or `biped` (RFC-0009). |
| link, joint (prismatic, rotary) | 4.7, 4.8 | Not described by URML. Kinematics come from the robot's URDF or the substrate. |
| mechanical interface | 4.11 | Not described by URML. |
| end-effector | 4.12 | A gripper or tool. URML declares grippers in `manipulation.grippers`; a tool change is `swap_tool`; tools driven by a line are `set_output`. |
| gripper | 4.13 | A `manipulation.grippers` entry, with its force range and accepted object classes; used by `grasp`, `release`, `pick_from` and `place_at`. |
| manipulator | 4.14 | The arm and its end-effector together, as the manifest's `manipulation` block declares them. The structural types in 4.14.1 to 4.14.7 (articulated, SCARA, parallel and others) are not distinguished by URML. |
| mobile robot | 4.15 | A robot whose manifest has a `mobility` block; the warehouse profile and the mobile, legged and VDA 5050 runtimes. |

## Keeping this page current

ISO reviews its standards every five years; check the edition before relying on a clause number. When a term here changes meaning in URML, change this page in the same pull request.
