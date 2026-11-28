---
rfc: 0714
title: A rulebook can require a site limit
author: Ido Yahalomi (greenvh@gmail.com)
state: Draft
created: 2026-11-28
updated: 2026-11-28
amends: RFC-0702 (a seventh rule kind, `require_envelope`)
supersedes: none
superseded-by: none
---

<p align="center">
  <a href="https://urml.dev"><img src="https://urml.dev/favicon.svg" alt="URML" width="72" height="72"></a>
</p>

<p align="center">
  The standard language for robot intent.
</p>

<p align="center">
  <a href="https://urml.dev"><b>urml.dev</b></a>
</p>

---

# RFC-0714: A rulebook can require a site limit

Kind: Spec. This RFC adds one rule kind to rulebooks ([RFC-0702](0702-rulebooks.md)) and one error code. It changes no envelope field, no manifest field and no primitive, and it adds a rule to no government rulebook.

## Summary

The validator checks a program against the limits a site's safety envelope sets. A limit nobody set is not checked, and the program is accepted all the same. An envelope with no geofence passes every place a program names.

This RFC adds a rule kind, `require_envelope`, with which a rulebook requires the envelope to set the limits it lists. A deployment that loads such a rulebook and leaves a listed limit unset has every program refused with a new code, `rule.limit_missing`, until the envelope sets it. The evidence report shows the rule as `checked` when the envelope sets the limit and as `missing` when it does not, under the standard the rule cites.

## Motivation

The geofence check does nothing when the envelope declares no geofence. The comment on `_check_envelope_geofence` calls that "the common case for home / industrial deployments", and the fixtures agree: of the 254 single-robot conformance fixtures on main, 157 give no envelope and 80 give an envelope without a geofence. The same holds for every other limit. With no `max_velocity` in the envelope, only the manifest's own maximum bounds a speed.

That default is right. Most deployments are a robot on a bench, and a validator that refused them for want of a fence would be switched off. It is wrong for one kind of deployment: a site whose owner, insurer or regulator says a robot works only inside a defined area. That site has no way to make the validator insist on the area being defined. If the operator forgets the geofence, or passes the wrong envelope file, the validator accepts every program and says nothing.

The rulebook is where such a requirement belongs. A rulebook states what law or a company demands, the operator loads it on purpose, and each rule carries its citation. The six rule kinds of RFC-0702 cannot say it:

- `cap`, `forbid_primitive`, `forbid_zone_entry`, `forbid_over_people` and `max_concurrent_aircraft` judge the steps of a program.
- `require_declared` judges a declaration, which is a statement the operator makes and URML does not verify.

Whether an envelope sets a limit is neither. It is a fact about the deployment's own files that the validator can check for itself.

The evidence report ([RFC-0707](0707-evidence-report.md)) has the same blind spot from the other side. It marks an unset limit as `missing` in some cases and lists each geofence as `checked`, but no rule ties either to a requirement. A reader who groups the report by standard sees declarations and obligations, and no checked item, for any rulebook whose one checkable demand is that a limit exists.

## Detailed design

### The rule kind

```yaml
require_envelope:
  fields: [<envelope field>, ...]   # required, at least one, each once
```

`fields` names safety-envelope fields from a closed list:

| Field | Set when |
|---|---|
| `geofences` | the list has at least one entry |
| `people_occupancy_zones` | the list has at least one entry |
| `max_velocity`, `max_altitude`, `max_payload`, `max_grip_force_n`, `max_drop_height` | a number is given; `0` counts |

These are the limits the validator checks before a program runs. Fields the validator does not check statically, such as `weather` and `link_loss_policy`, are not on the list. A name outside the list makes the rulebook invalid.

### Judging

The rule is judged once per robot that executes steps: once for a single-robot program, and once per member that has a step in a fleet program. When the robot has no envelope, or its envelope leaves a listed field unset, the rule is violated with `rule.limit_missing`. The message names the missing fields, and `detail.missing_fields` lists them.

Three points of semantics:

- **It is an error with or without a deployment rulebook.** `require_declared` is a warning when no deployment rulebook is loaded, because nobody has been asked to file the declaration. The envelope is an input of its own. The operator either passed one that sets the limit or did not.
- **It does not judge the value.** A geofence that covers the whole building satisfies the rule. What a limit should be comes from the risk assessment, or from a `cap` rule. The rule only stops "nobody set this limit, so nothing was checked" from being an accepted state.
- **A manifest limit does not satisfy it.** The manifest says what the robot can do. The envelope says what this site allows. A rule about the site is satisfied by the site's file.

An exception in a deployment rulebook covers the rule when the rule is `exceptable`, as for every other kind. The violation then keeps its code and becomes a warning that names the basis.

The violation carries `remediation_hint: fix_deployment`. No edit to the program can set a limit in the envelope, so the LLM bridge stops at once and does not send the refusal back to the model.

### With no program

`rulebook_inventory`, which the evidence report uses, judges `require_envelope` rules as it judges `require_declared` rules: neither depends on a program's steps.

The report gives the rule's item one of two statuses:

- `checked` when the envelope sets every listed field. The item says the rule is checked at every validation.
- `missing` when it does not. The item names the unset fields and says every program is refused until they are set. `missing` already means "something a loaded rule, policy or the envelope requires is absent".

The item carries the rule's `cite`, so the "By standard" section counts it under the standard the rule names. When an exception covers the rule, the item is `checked` and names the exception, as for other kinds.

### Spec changes

[`spec/layer-1-hal/rulebook.md`](../../spec/layer-1-hal/rulebook.md): the list of kind keys, a section for `require_envelope` after `require_declared`, the row for `rule.limit_missing` in the table of error codes, and its place beside `rule.declaration_missing` among the codes whose fix is in the deployment. The sentence that says a rule is one of six fixed kinds says seven.

### Validator changes

- `schemas/rulebook.py`: `RequireEnvelopeBody`, the `EnvelopeField` list, and `require_envelope` in `RULE_KINDS` and on `Rule`.
- `errors.py`: `RULE_LIMIT_MISSING = "rule.limit_missing"`. Error codes are public API; this one is added and none is renamed.
- `rulebook_engine.py`: `_judge_require_envelope`, called from the rule loop and from `inventory`.
- `evidence_report.py`: the two statuses above.

### Reference runtime changes

None. `URMLRuntime.execute` validates again with the caller's rulebooks and envelope before its first adapter call, so it refuses the same programs. The goal-line lane confirms it for the new rejected fixture.

### Conformance suite changes

| Fixture | Expects |
|---|---|
| `rulebook/14_site_without_geofence_rejected` | `rule.limit_missing`: the envelope sets a speed limit and no geofence |
| `rulebook/15_site_with_geofence_accepted` | accepted and executed: the envelope sets both |

Both load a new example, [`examples/rulebooks/example-site-standard.yaml`](../../examples/rulebooks/example-site-standard.yaml), the site standard of the fictional company that `example-warehouse.yaml` already uses. It has two rules: every site declares the area its robots may work in, and every site sets a speed limit.

### Measurement

Measured on 26d40f0 with the change applied, Python 3.11.

| What was run | Result |
|---|---|
| The 269 conformance fixtures on main | No fixture changes outcome |
| All 271 fixtures, with the two new ones | 271 of 271 pass |
| Goal-line lane (`python -m urml_conformance --goal-line`) | 129 of 129 rejected fixtures refused by the runtime with zero adapter calls (128 before, plus the new one) |
| Every package suite | All pass. The validator suite gains 33 tests: 30 for the rule kind, and three that run for each listed example file. The LLM bridge suite gains one |
| Every shipped rulebook | Unchanged. No shipped rulebook uses the new kind except the new example |

## Backward compatibility

The change adds. No rulebook that loads today changes meaning, and no program changes outcome unless its operator loads a rulebook that uses the new kind.

A rulebook file that uses `require_envelope` does not load in a validator released before this change. That validator reports `rule.rulebook_invalid` and refuses the program, which is the safe direction. `rulebook_version` stays `"0.1"`, as the maintainer decided on 2026-11-28.

`export_schema("rulebook")` gains the kind. Three tests that enumerate things by name were extended: the set of kind keys and the list of example files in `test_rulebook_files.py`, and the list of fixtures that rest on a caller's rulebook in `test_goal_line.py`.

## Drawbacks

- **Presence is not adequacy.** An operator can satisfy the rule with a geofence around the whole county. The rule moves a deployment from "no limit, no check" to "some limit, checked", and a reader of an evidence report must not take `checked` here for more than that. The spec section and the report text say so.
- **The verdict now depends on which envelope was passed.** Under such a rulebook, `urml validate` with no `--envelope` refuses a program that is otherwise fine. That is the point for a deployment, and friction for a developer trying a program on a laptop.
- **A seventh kind.** RFC-0702 kept the vocabulary small on purpose. Each kind is one more thing every implementation of rulebooks has to carry.
- **The field list follows the envelope schema.** A new envelope limit needs a decision on whether a rule may require it, and a spec edit when the answer is yes.

## Alternatives considered

**Make the envelope pass refuse when no geofence is declared.** One global rule and no new kind. On main, 237 of the 254 single-robot fixtures declare no geofence, as do most of the examples. A robot arm on a bench has no use for a fence, and a validator that refused it by default would be switched off. What a site must declare is a policy choice, and policy lives in rulebooks. Rejected.

**Use `require_declared` with a declaration such as `work_area_declared: true`.** It needs no new kind. A declaration is a statement the operator makes, and the evidence report marks it `declared`, with the sentence "URML checks the declaration is there and allowed, not that it is true". Here the validator can check the fact itself, and asking the operator to assert it adds a second place for the two to disagree. Rejected.

**A flag in the envelope, such as `require_geofence: true`.** The envelope would require itself. The operator who forgets the fence forgets the flag, and an envelope that was never passed cannot require anything. Rejected.

**Tie the built-in checks to clauses inside the validator.** The geofence check could carry a citation, so a report would count it under a standard. That puts one jurisdiction's clause numbers into the core, where nothing records who reviewed them or when. Rulebooks exist to hold citations, each with an issuer and a review date. Rejected.

**Free-form field paths.** `fields` could take any dotted path into the envelope. The first design rule of the rulebook format is "No expression language", and a closed list keeps a rulebook readable by someone who does not know the schema. Rejected.

## Prior art

- `require_declared` in RFC-0702 is the same shape for a different fact: a rule judged once per validation, about the deployment, with its fix in the deployment and not in the program.
- The evidence report's `missing` status (RFC-0707) already names the state this rule refuses: "something a loaded rule, policy or the envelope requires is absent".
- Container platforms separate the same two things. The platform enforces the resource limits a workload declares, and a separate admission policy refuses a workload that declares none. The policy says nothing about what the limit should be.
- [RFC-0713](https://github.com/urml-dev/URML/pull/118) closes the neighboring gap: a target the envelope cannot place is refused. That one is about a fence that exists and cannot judge. This one is about a fence that does not exist.

## Unresolved questions

1. **Which shipped rulebooks should use it.** This RFC adds the kind and a fictional company example. Adding a `require_envelope` rule to a government rulebook or a standards template changes what that file refuses and what it claims about a clause, so each one is a separate change with its own citation review.
2. **`rulebook_version`.** *Resolved 2026-11-28: it stays `"0.1"`.* A file that uses the new kind fails closed on an older validator, which is the safe direction, and a 0.x format may gain additions. Moving to `"0.2"` would give the older validator a clearer error and would mean supporting two format versions from now on.
3. **Zones with an override.** A people-occupancy zone marked `allow_override: true` counts as declared. Should a rule be able to ask for a zone that is enforced?
4. **Other deployment facts.** A rulebook might want to require things outside the envelope, such as the validation record being on. That is a different input and is not proposed here.

## Implementation note

One pull request carries this RFC, the spec section, the validator change, the tests, the example rulebook and the two fixtures. It stays a draft for the seven-day comment window of [RFC-0001](0001-rfc-process.md). If the RFC is accepted, the state line and the index row change in that pull request before it merges.

The fixture count on the README badge and in `docs/launch/claims-audit.md` moves by two. Those numbers are transcribed by the maintainer from `make audit`, so the pull request reports the drift and does not edit them.

## Self-review (Phase 0)

- [x] The Summary alone tells a reader what is being proposed.
- [x] The Motivation is grounded in a concrete use case, not hypothetical needs.
- [x] The Detailed design names every affected spec document and reference component.
- [x] At least one alternative is genuinely considered (not a strawman).
- [x] Drawbacks are listed; at least one of them is a real downside, not a humblebrag.
- [x] Backward compatibility is honest about what breaks.
- [x] If this RFC adds a Layer-2 primitive, both ROS-2 and non-ROS implementation sketches are present (substrate-neutrality acid test). Not applicable: no primitive is added. The rule reads the envelope only and names no substrate.
- [x] The implementation note explains how this lands, not just what.
- [x] The author has re-read [`CLAUDE.md`](../../CLAUDE.md) §What Claude Should Never Do and confirmed this proposal does not violate it.
