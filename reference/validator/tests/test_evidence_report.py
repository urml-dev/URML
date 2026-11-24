"""The evidence report (RFC-0707, Draft), step 1.

Golden reports for four deployments, built from the fixture inputs under
`tests/fixtures/evidence/<scenario>/`. Each scenario's `scenario.yaml` names
its inputs, so `urml evidence build` rebuilds the same report from the same
files. Regenerate the golden files with `URML_REGEN_EVIDENCE=1 pytest
tests/test_evidence_report.py`, then read the diff before committing it.
"""

from __future__ import annotations

import copy
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError as PydanticValidationError

from urml_validator import validate
from urml_validator._version import __version__
from urml_validator.cli import main
from urml_validator.evidence_report import (
    NOTICE,
    STATUSES,
    EvidenceInputError,
    EvidenceReport,
    build_evidence_report,
    render_json,
    report_schema,
)
from urml_validator.rulebook_engine import bundled_rulebooks
from urml_validator.schemas.rulebook import Cite, Rulebook

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
FIXTURES = HERE / "fixtures" / "evidence"
SCENARIOS = sorted(p.name for p in FIXTURES.iterdir() if (p / "scenario.yaml").is_file())
SCHEMA = REPO_ROOT / "spec" / "evidence" / "v0.1.0" / "report.schema.json"
TEMPLATES = [
    REPO_ROOT / "examples" / "rulebooks" / f"{name}-template.yaml"
    for name in ("industrial", "amr", "home", "functional-safety")
]
FIXED_OUTSIDE = [
    "outside.safety_control",
    "outside.below_substrate",
    "outside.site",
    "outside.declarations",
    "outside.unmediated",
]


def _yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _scenario(name: str) -> tuple[Path, dict[str, Any]]:
    folder = FIXTURES / name
    data = _yaml(folder / "scenario.yaml")
    assert isinstance(data, dict)
    return folder, data


def _build(name: str) -> EvidenceReport:
    folder, sc = _scenario(name)
    manifest_path = (folder / sc["manifest"]).resolve()
    envelope_path = (folder / sc["envelope"]).resolve() if sc["envelope"] else None
    return build_evidence_report(
        _yaml(manifest_path),
        _yaml(envelope_path) if envelope_path is not None else None,
        as_of=date.fromisoformat(sc["as_of"]),
        profiles=sc["profiles"],
        rulebooks=[_yaml(folder / rb) for rb in sc["rulebooks"]],
        manifest_base_dir=manifest_path.parent,
        manifest_name=manifest_path.name,
        envelope_name=envelope_path.name if envelope_path is not None else None,
        rulebook_names=[Path(rb).name for rb in sc["rulebooks"]],
    )


def _cli_args(name: str) -> list[str]:
    folder, sc = _scenario(name)
    args = ["evidence", "build", "--manifest", str(folder / sc["manifest"]), "--as-of", sc["as_of"]]
    if sc["envelope"]:
        args += ["--envelope", str(folder / sc["envelope"])]
    for profile in sc["profiles"]:
        args += ["--profile", profile]
    for rb in sc["rulebooks"]:
        args += ["--rulebook", str(folder / rb)]
    return args


def _golden_form(text: str) -> str:
    """The report with the validator version masked, so a version bump does not stale the golden files."""
    return text.replace(f'"version": "{__version__}"', '"version": "VERSION"')


def _items(report: EvidenceReport) -> dict[str, Any]:
    return {item.id: item for section in report.sections for item in section.items}


# ----- golden reports -----


@pytest.mark.parametrize("name", SCENARIOS)
def test_the_report_matches_its_golden_file(name: str) -> None:
    golden = FIXTURES / name / "expected.json"
    text = _golden_form(render_json(_build(name)))
    if os.environ.get("URML_REGEN_EVIDENCE") == "1":
        golden.write_text(text, encoding="utf-8")
    assert golden.read_text(encoding="utf-8") == text


@pytest.mark.parametrize("name", SCENARIOS)
def test_the_same_inputs_give_the_same_bytes(name: str) -> None:
    assert render_json(_build(name)) == render_json(_build(name))


@pytest.mark.parametrize("name", SCENARIOS)
def test_every_golden_report_follows_the_schema(name: str) -> None:
    text = (FIXTURES / name / "expected.json").read_text(encoding="utf-8")
    report = EvidenceReport.model_validate_json(text)
    assert render_json(report) == text


def test_the_committed_schema_is_the_model_schema() -> None:
    committed = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert committed == report_schema()


@pytest.mark.parametrize("name", SCENARIOS)
def test_the_report_carries_no_local_path(name: str) -> None:
    text = render_json(_build(name))
    assert str(REPO_ROOT) not in text
    assert str(Path.home()) not in text


# ----- what every report says -----


@pytest.mark.parametrize("name", SCENARIOS)
def test_every_report_has_the_notice_the_sections_and_the_fixed_blind_spots(name: str) -> None:
    report = _build(name)
    assert report.notice == NOTICE
    assert [s.id for s in report.sections] == ["robot", "provenance", "envelope", "rules", "outside"]
    outside = report.sections[-1]
    assert [i.id for i in outside.items] == FIXED_OUTSIDE
    assert all(i.status == "outside" for i in outside.items)


@pytest.mark.parametrize("name", SCENARIOS)
def test_counts_add_up(name: str) -> None:
    report = _build(name)
    items = list(_items(report).values())
    assert set(report.counts.by_status) == set(STATUSES)
    assert sum(report.counts.by_status.values()) == len(items)
    for status in STATUSES:
        assert report.counts.by_status[status] == sum(1 for i in items if i.status == status)
    failed = sum(1 for i in items if i.result == "fail")
    assert report.counts.gaps == report.counts.by_status["missing"] + failed


def test_a_report_never_claims_safety_or_compliance() -> None:
    for name in SCENARIOS:
        text = render_json(_build(name)).lower()
        for word in ("is safe", "is compliant", "certified safe", "score"):
            assert word not in text, (name, word)


# ----- the scenarios say what they should -----


def test_the_warehouse_with_every_declaration_has_no_gaps() -> None:
    report = _build("amr-warehouse")
    items = _items(report)
    assert report.counts.gaps == 0
    assert items["limit.max_velocity"].detail["effective"] == 1.0
    assert items["rule.cell_7_safety.protective_stop_declared"].status == "declared"
    assert items["rule.cell_7_safety.protective_stop_declared"].detail["declared_by"] == "cell_7_safety_declarations"
    assert items["obligation.cell_7_safety.urml_cannot_interfere"].status == "outside"


def test_the_industrial_cell_shows_its_gaps() -> None:
    report = _build("industrial-cell")
    items = _items(report)
    missing = sorted(i for i, item in items.items() if item.status == "missing")
    assert missing == [
        "envelope.absent",
        "rule.cell_7_safety.emergency_stop_declared",
        "rule.cell_7_safety.protective_stop_declared",
        "rule.cell_7_safety.safety_validation_on_record",
        "rule.cell_7_safety.speed_monitoring_declared",
    ]
    assert report.counts.gaps == 5


def test_the_drone_groups_its_rules_under_part_107_and_part_89() -> None:
    report = _build("drone-parcel")
    groups = {g.standard: g for g in report.by_standard}
    assert set(groups) == {"14 CFR Part 107", "14 CFR Part 89"}
    assert all(g.keyed_by == "standard" for g in groups.values())
    assert "rule.us_faa_part107.remote_identification" in groups["14 CFR Part 89"].items["missing"]


def test_one_standard_written_two_ways_lands_in_one_group() -> None:
    _, sc = _scenario("industrial-cell")
    folder = FIXTURES / "industrial-cell"
    books = [_yaml(folder / rb) for rb in sc["rulebooks"]]
    for book in books:
        for rule in [*book.get("rules", []), *book.get("obligations", [])]:
            if "ISO 10218-2:2025" in rule["cite"]["text"]:
                rule["cite"]["text"] = rule["cite"]["text"].replace("ISO 10218-2:2025", "ISO 10218-2 (2025)")
    report = build_evidence_report(
        _yaml(folder / sc["manifest"]), None, as_of=date(2026, 11, 24), profiles=["industrial"], rulebooks=books
    )
    assert "ISO 10218-2 (2025)" not in {g.standard for g in report.by_standard}


def test_without_the_standard_field_rules_group_on_the_cite_text() -> None:
    book = {
        "rulebook_version": "0.1",
        "rulebook_id": "site_rules",
        "title": "Site rules",
        "issuer": {"kind": "organization", "name": "Example Site"},
        "source_status": "organization_policy",
        "rules": [
            {
                "id": "slow",
                "title": "Slow travel",
                "cite": {"text": "ISO 3691-4:2023, clause 4.2"},
                "cap": {"quantity": "speed_m_per_s", "max": 0.5},
            }
        ],
    }
    folder, sc = _scenario("amr-warehouse")
    report = build_evidence_report(
        _yaml(folder / sc["manifest"]), None, as_of=date(2026, 11, 24), profiles=["warehouse"], rulebooks=[book]
    )
    groups = {g.standard: g for g in report.by_standard}
    assert groups["ISO 3691-4:2023"].keyed_by == "text"
    assert groups["ISO 3691-4:2023"].items == {"checked": ["rule.site_rules.slow"]}


def test_policy_off_is_on_the_record() -> None:
    folder, sc = _scenario("amr-warehouse")
    report = build_evidence_report(_yaml(folder / sc["manifest"]), None, as_of=date(2026, 11, 24), policy=None)
    items = _items(report)
    assert items["policy.off"].status == "outside"
    assert not any(i.startswith("policy_rule.") for i in items)
    assert report.inputs.policy == "off"


def test_a_failing_policy_rule_is_a_gap() -> None:
    folder, sc = _scenario("amr-warehouse")
    manifest = copy.deepcopy(_yaml(folder / sc["manifest"]))
    manifest["provenance"]["components"][0]["vendor"] = "dji"
    report = build_evidence_report(manifest, None, as_of=date(2026, 11, 24))
    failing = [i for i in _items(report).values() if i.result == "fail"]
    assert [i.id for i in failing] == ["policy_rule.covered_vendor_denylist"]
    assert report.counts.failed_checks == 1


def test_a_broken_manifest_is_an_input_error() -> None:
    with pytest.raises(EvidenceInputError):
        build_evidence_report({"robot_id": "x", "mobility": {"drive_type": "nope"}}, None, as_of=date(2026, 11, 24))


def test_digests_ignore_file_format() -> None:
    folder, sc = _scenario("home-helper")
    manifest = _yaml(folder / sc["manifest"])
    as_json = json.loads(json.dumps(manifest))
    a = build_evidence_report(manifest, None, as_of=date(2026, 11, 24))
    b = build_evidence_report(as_json, None, as_of=date(2026, 11, 24))
    assert a.inputs.files[0].digest == b.inputs.files[0].digest


# ----- the CLI -----


def test_cli_writes_the_golden_report_and_exits_0_without_gaps(tmp_path: Path) -> None:
    out = tmp_path / "report.json"
    assert main([*_cli_args("amr-warehouse"), "--out", str(out)]) == 0
    golden = (FIXTURES / "amr-warehouse" / "expected.json").read_text(encoding="utf-8")
    assert _golden_form(out.read_text(encoding="utf-8")) == golden


def test_cli_exits_1_when_something_is_missing(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(_cli_args("industrial-cell")) == 1
    out = capsys.readouterr().out
    assert _golden_form(out) == (FIXTURES / "industrial-cell" / "expected.json").read_text(encoding="utf-8")


def test_cli_exits_2_on_a_bad_date_or_a_missing_file(tmp_path: Path) -> None:
    args = _cli_args("home-helper")
    bad_date = list(args)
    bad_date[bad_date.index("--as-of") + 1] = "24/11/2026"
    assert main(bad_date) == 2
    assert main(["evidence", "build", "--manifest", str(tmp_path / "none.yaml"), "--as-of", "2026-11-24"]) == 2


def test_cli_requires_as_of() -> None:
    folder, sc = _scenario("home-helper")
    with pytest.raises(SystemExit):
        main(["evidence", "build", "--manifest", str(folder / sc["manifest"])])


# ----- the `standard` field on cites -----


def test_standard_takes_one_identifier_or_a_list() -> None:
    assert Cite(text="x", standard="ISO 3691-4:2023").standards() == ["ISO 3691-4:2023"]
    assert Cite(text="x", standard=["ISO 13849-1:2023", "IEC 62061:2021"]).standards() == [
        "ISO 13849-1:2023",
        "IEC 62061:2021",
    ]
    assert Cite(text="x").standards() == []


@pytest.mark.parametrize("bad", [[], ["ISO 3691-4:2023", "ISO 3691-4:2023"], "", " ISO 3691-4:2023", 7])
def test_standard_refuses_empty_repeated_padded_or_non_string_values(bad: Any) -> None:
    with pytest.raises(PydanticValidationError):
        Cite(text="x", standard=bad)


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: p.stem)
def test_every_template_cite_names_its_standard(path: Path) -> None:
    data = _yaml(path)
    for entry in [*data.get("rules", []), *data.get("obligations", [])]:
        cite = entry["cite"]
        assert cite.get("standard"), (path.name, entry["id"])
        for standard in [cite["standard"]] if isinstance(cite["standard"], str) else cite["standard"]:
            assert standard.split(":")[0].split(" ")[-1] in cite["text"], (entry["id"], standard)


def test_every_bundled_rule_cite_names_its_standard() -> None:
    for book in bundled_rulebooks():
        cites = [(r.id, r.cite) for r in book.rules] + [(o.id, o.cite) for o in book.obligations]
        for entry_id, cite in cites:
            assert cite is not None and cite.standards(), (book.rulebook_id, entry_id)


def test_the_standard_field_changes_no_validation_output() -> None:
    folder = REPO_ROOT / "examples" / "drone"
    program = _yaml(folder / "parcel-delivery.urml.yaml")
    manifest = _yaml(folder / "parcel-delivery.manifest.yaml")
    envelope = _yaml(folder / "parcel-delivery.envelope.yaml")
    result = validate(program, manifest, envelope, profiles=("drone",))
    for issue in result.all_issues:
        cite = (issue.detail or {}).get("cite")
        if isinstance(cite, dict):
            assert set(cite) == {"text", "url"}
    for report in result.rulebooks:
        for obligation in report.obligations:
            if obligation["cite"] is not None:
                assert set(obligation["cite"]) == {"text", "url"}


def test_a_rulebook_without_the_field_still_loads() -> None:
    book = _yaml(FIXTURES / "amr-warehouse" / "amr-rules.yaml")
    for entry in [*book["rules"], *book["obligations"]]:
        entry["cite"].pop("standard", None)
    Rulebook.model_validate(book)
