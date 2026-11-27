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

# An evidence report, read by an auditor

This folder holds one robot deployment and the evidence report built from it ([RFC-0707](../../docs/rfcs/0707-evidence-report.md)). It is written for someone who audits, certifies, buys or insures robots and has never used URML.

**Open [`report.html`](report.html) in a browser, or read [`report.md`](report.md).** The JSON ([`report.json`](report.json)) is the canonical form; the other two render it.

An evidence report is not a safety assessment, a certification or a compliance determination, and its first line says so. It tells you what URML checks for this robot at this site before any program runs, what people have only declared, what is left to the robot's software while it runs, what is missing, and what URML cannot see at all.

## The deployment

A mobile robot with an arm (`warehouse_amr_1`) in Hall 2 of a fictional warehouse. Every value here is an example.

| File | What it says | Who owns it |
|---|---|---|
| [`manifest.yaml`](manifest.yaml) | What the robot can do: speed, gripper, sensors, component origins | The robot maker or integrator |
| [`envelope.yaml`](envelope.yaml) | What this site allows: a 1 m/s limit, the hall's boundary, a break area robots must not enter | The site operator |
| [`amr-rules.yaml`](amr-rules.yaml) | The site's rules for mobile robots, after ISO 3691-4 and ANSI/A3 R15.08 | The integrator |
| [`functional-safety.yaml`](functional-safety.yaml) | Programs wait until each safety function's level is on record, after ISO 13849, IEC 62061 and IEC 61508 | The integrator |
| [`declarations.yaml`](declarations.yaml) | The levels the safety functions reached, from the validation records | The site operator |
| [`../warehouse/pick-to-conveyor.urml.yaml`](../warehouse/pick-to-conveyor.urml.yaml) | One task program to check against all of the above | Whoever writes the robot's tasks |

The two rulebooks are filled-in copies of URML's [templates](../rulebooks/). They carry no text or values from the standards, which are copyrighted: the clause numbers read "n.n (from a licensed copy)" on purpose.

## How to read it

Every line of the report has one of five statuses.

| Status | What it means for you |
|---|---|
| `checked` | URML refuses any program that breaks this, before the robot moves. You can rely on the check; you still need to judge whether the limit itself is right. |
| `declared` | Someone states this and the report names who. URML does not verify it. Ask for the record behind it. |
| `runtime` | The robot's software must enforce this while it runs. No check before the run covers it. Ask how the runtime does it. |
| `missing` | Something a rule, the policy or the envelope needs is absent. This is a gap. |
| `outside` | URML cannot see this. Someone else must cover it, and the report lists what. |

The report starts with a count per status and a list of **gaps**: missing items plus checks that failed. There is no score and no pass mark. A report with no gaps is not a safe robot; it is a deployment whose paperwork is complete as far as URML can see.

**By standard** regroups the rules and obligations under the standard each one cites, so you can start from ISO 3691-4 or IEC 61508 and see what URML checks for it and what it leaves to others.

**Outside URML** always lists the same five things: the robot's safety-related control, everything below the software URML talks to, the physical site, whether any declaration is true, and anything that does not pass through URML. The obligations the rulebooks place on people (a current risk assessment, trained staff, validated safety functions) appear under Rules, also as `outside`.

## Reading a gap

This report has two gaps, and they are one problem.

1. `rule.hall_2_safety.speed_monitoring_declared` is **missing**. The site's functional-safety rulebook asks the operator to declare the level the robot's safety-rated speed monitoring reached. [`declarations.yaml`](declarations.yaml) declares the emergency stop and the protective stop but not speed monitoring.
2. `validated.pick-to-conveyor` is **checked, fail**. Because of the missing declaration, URML refuses every program at this site, including the warehouse task.

The fix is not in URML: the operator finds the speed-monitoring level in the integrator's validation records and declares it. URML then checks that the declared level meets the requirement. It never checks that the speed monitoring works; that is the work of the integrator and, if you are certifying, of you.

## Checking the report yourself

Do not trust this report because it is here. Rebuild it. `urml evidence build` ships in urml-validator on PyPI (`pip install urml-validator==0.5.3`); run it from a checkout of this repository at the `v0.5.3` tag so the example files are there:

```bash
cd examples/evidence-report
urml evidence build --manifest manifest.yaml --envelope envelope.yaml \
  --profile warehouse \
  --rulebook amr-rules.yaml --rulebook functional-safety.yaml --rulebook declarations.yaml \
  --program ../warehouse/pick-to-conveyor.urml.yaml \
  --as-of 2026-11-24 --out rebuilt.json
```

The command runs offline. With 0.5.3 from PyPI and the files of the `v0.5.3` tag, `rebuilt.json` is byte for byte `report.json` (21 checked, 9 declared, 4 runtime, 1 missing, 15 outside). On `main` between releases the committed report is built by the validator on `main`, which can be ahead of the release on PyPI; build from a checkout after `python bootstrap.py` to match that one byte for byte. The report's Inputs section lists a digest for every file, so you can also confirm you were given the files it describes. Exit code 1 means the report has gaps; 2 means a file could not be read.

`--format md` and `--format html` write the human forms, and `python build.py` rebuilds all four committed files at once. Both work with 0.5.3 from PyPI; 0.5.2 wrote JSON only.

## Sharing it outside the site

[`report.redacted.json`](report.redacted.json) is the copy to send to someone outside the site: `--redact` removes the hall's boundary, the break area's shape and the validator's messages on programs, which can quote coordinates. Every status, rule and count stays. (`--redact` and `urml evidence verify` below ship from 0.5.3.) Its `redaction` block records the sha256 of the full report, so if you are later shown the full report you can check it is the same one.

A report reviewed by the Licensor also comes with a signature file. `urml evidence verify report.json` checks it offline; see [`docs/evidence/signing.md`](../../docs/evidence/signing.md). A signature says the Licensor rebuilt and reviewed the report. It is not a certification.

## Not to be confused with

[`../evidence/`](../evidence/) is a different example: the per-capability evidence tags of RFC-0631 (how one capability claim was established). This report prints those tags, for example "No evidence tag: the claim's source is not recorded" next to each capability.
