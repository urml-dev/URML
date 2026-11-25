"""The Licensor's reproduction run (``urml_conformance.reproduce``, RFC-0705, RFC-0708).

What it refuses before installing anything, the offline guard, the check of a
finished reproduction, and how it fills the entry. The whole run, from a
submitted entry to an entry the registry check accepts, is in
``test_registry.py``.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from urml_conformance import __version__ as conformance_version
from urml_conformance.report import ConformanceReport, StepTime
from urml_conformance.reproduce import (
    LICENSOR,
    OFFLINE_GUARD,
    Plan,
    ReproductionError,
    certification_fields,
    check_reproduction,
    insert_certification,
    plan_reproduction,
    record_timing,
)

REPORT_REL = "registry/evidence/bot/conformance-report.json"


def _report(**overrides: Any) -> dict[str, Any]:
    report: dict[str, Any] = {
        "format": "urml.conformance-report/1",
        "adapter": "bot_runtime:BotAdapter",
        "urml_conformance_version": conformance_version,
        "fixture_count": 1,
        "fixtures_sha256": "a" * 64,
        "profiles": ["educational"],
        "results": [{"name": "educational/one", "passed": True, "diagnostics": []}],
    }
    report.update(overrides)
    return report


def _submitted(root: Path, **runtime: Any) -> Path:
    """A submitted entry applying for URML-Certified: no Licensor fields yet."""
    report = root / REPORT_REL
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(_report()) + "\n", encoding="utf-8")
    entry = {
        "id": "bot",
        "runtime": {"package": "bot-runtime", "version": "1.0.0", "adapter": "bot_runtime:BotAdapter", **runtime},
        "compatibility": {
            "tier": "certified",
            "profiles": ["educational"],
            "report": {"path": REPORT_REL, "sha256": hashlib.sha256(report.read_bytes()).hexdigest()},
            "certification": {
                "conformance_spec": "0.2.2",
                "attestation": "The runtime meets the six clauses of the conformance contract.",
            },
        },
    }
    path = root / "registry" / "entries" / "bot.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(entry, sort_keys=False), encoding="utf-8")
    return path


def test_a_submitted_entry_gives_a_plan(tmp_path: Path) -> None:
    plan = plan_reproduction(_submitted(tmp_path), tmp_path)
    assert (plan.package, plan.version, plan.adapter, plan.profiles) == (
        "bot-runtime",
        "1.0.0",
        "bot_runtime:BotAdapter",
        ("educational",),
    )


@pytest.mark.parametrize(
    ("runtime", "reason"),
    [
        ({"package": "urml-px4-runtime"}, "does not certify its own runtimes"),
        ({"package": "examples/bot"}, "not a distribution name"),
        ({"version": ">=1.0"}, "not one exact release"),
        ({"adapter": "urml_ros2_runtime:MockROSAdapter"}, "hermetic mock"),
        ({"adapter": "no-colon"}, "module:attribute"),
    ],
    ids=["first-party", "repository-path", "version-range", "mock-adapter", "bad-adapter"],
)
def test_an_entry_that_cannot_be_certified_is_refused_before_install(
    tmp_path: Path, runtime: dict[str, Any], reason: str
) -> None:
    with pytest.raises(ReproductionError) as exc:
        plan_reproduction(_submitted(tmp_path, **runtime), tmp_path)
    assert any(reason in problem for problem in exc.value.problems), exc.value.problems


def test_no_attestation_and_a_self_reported_tier_are_refused(tmp_path: Path) -> None:
    path = _submitted(tmp_path)
    entry = yaml.safe_load(path.read_text(encoding="utf-8"))
    entry["compatibility"]["tier"] = "self_reported"
    del entry["compatibility"]["certification"]["attestation"]
    path.write_text(yaml.safe_dump(entry), encoding="utf-8")
    with pytest.raises(ReproductionError) as exc:
        plan_reproduction(path, tmp_path)
    assert any("tier is not certified" in p for p in exc.value.problems)
    assert any("attestation is missing" in p for p in exc.value.problems)


def test_a_self_report_that_does_not_match_its_pin_is_refused(tmp_path: Path) -> None:
    path = _submitted(tmp_path)
    (tmp_path / REPORT_REL).write_text(json.dumps(_report(fixture_count=2)) + "\n", encoding="utf-8")
    with pytest.raises(ReproductionError, match="sha256 does not match"):
        plan_reproduction(path, tmp_path)


def _plan(tmp_path: Path) -> Plan:
    return plan_reproduction(_submitted(tmp_path), tmp_path)


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"results": [{"name": "educational/one", "passed": False, "diagnostics": ["x"]}]}, "1 of 1 fixtures failed"),
        ({"adapter": "other:Adapter"}, "not the entry's adapter"),
        ({"fixtures_sha256": "b" * 64}, "different fixture set"),
        ({"profiles": ["educational", "home"]}, "exactly the claimed profiles"),
        ({"results": [], "fixture_count": 0}, "ran no fixtures"),
    ],
    ids=["failed", "other-adapter", "other-fixtures", "other-profiles", "empty"],
)
def test_a_reproduction_that_does_not_match_is_not_granted(
    tmp_path: Path, overrides: dict[str, Any], reason: str
) -> None:
    reproduction = ConformanceReport.model_validate(_report(**overrides))
    problems = check_reproduction(_plan(tmp_path), reproduction)
    assert any(reason in problem for problem in problems), problems


def test_a_matching_reproduction_passes(tmp_path: Path) -> None:
    assert check_reproduction(_plan(tmp_path), ConformanceReport.model_validate(_report())) == []


def _guard_probe(snippet: str) -> subprocess.CompletedProcess[str]:
    guard = OFFLINE_GUARD.split("sys.argv = [", 1)[0]
    return subprocess.run([sys.executable, "-c", guard + snippet], capture_output=True, text=True, check=False)


def test_the_guard_refuses_the_network_and_allows_loopback() -> None:
    probe = _guard_probe(
        """
server = socket.socket()
server.bind(("127.0.0.1", 0))
server.listen(1)
client = socket.create_connection(server.getsockname(), timeout=5)
client.close()
socket.getaddrinfo("localhost", 80)
for attempt in (
    lambda: socket.socket().connect(("203.0.113.7", 80)),
    lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b"x", ("203.0.113.7", 53)),
    lambda: socket.getaddrinfo("example.org", 443),
):
    try:
        attempt()
    except OSError as exc:
        assert "network is off" in str(exc), exc
    else:
        raise SystemExit("reached the network")
print("guarded")
"""
    )
    assert probe.returncode == 0, probe.stderr
    assert probe.stdout.strip() == "guarded"


def test_certification_fields_stay_inside_the_rules() -> None:
    fields = certification_fields(
        report_path="registry/evidence/bot/reproduction-report.json",
        report_sha256="c" * 64,
        reproduced_on=dt.date(2026, 12, 1),
        environment="bot-runtime 1.0.0 from PyPI, network off after install except loopback.",
    )
    assert fields["certified_on"] == fields["reproduction"]["date"] == "2026-12-01"
    assert fields["expires"] == "2027-12-01"
    assert fields["reproduction"]["by"] == LICENSOR
    with pytest.raises(ValueError, match="1 to 366"):
        certification_fields(
            report_path="r.json",
            report_sha256="c" * 64,
            reproduced_on=dt.date(2026, 12, 1),
            environment="x",
            validity_days=400,
        )
    with pytest.raises(ValueError, match="bans"):
        certification_fields(
            report_path="r.json",
            report_sha256="c" * 64,
            reproduced_on=dt.date(2026, 12, 1),
            environment="a certified environment",
        )


ENTRY_TEXT = """\
# A comment the submitter wrote.
id: bot
compatibility:
  tier: certified
  certification:
    conformance_spec: "0.2.2"
    attestation: >-
      The runtime meets the six clauses
      of the conformance contract.
    certified_on: "2025-12-01"
    expires: "2026-12-01"
    reproduction:
      by: old

notes: kept
"""


def test_filling_the_entry_replaces_old_fields_and_keeps_the_rest() -> None:
    fields = certification_fields(
        report_path="registry/evidence/bot/reproduction-report.json",
        report_sha256="c" * 64,
        reproduced_on=dt.date(2026, 12, 1),
        environment="bot-runtime 1.0.0 from PyPI, network off after install except loopback.",
    )
    text = insert_certification(ENTRY_TEXT, fields)
    assert text.startswith("# A comment the submitter wrote.\n")
    assert "      of the conformance contract.\n" in text
    assert "2025-12-01" not in text and "by: old" not in text
    assert text.endswith("\n\nnotes: kept\n")
    data = yaml.safe_load(text)
    cert = data["compatibility"]["certification"]
    assert cert["certified_on"] == "2026-12-01" and cert["expires"] == "2027-12-01"
    assert cert["reproduction"]["report"]["sha256"] == "c" * 64
    assert data["notes"] == "kept"


def test_an_entry_without_a_certification_block_cannot_be_filled() -> None:
    with pytest.raises(ReproductionError, match="no certification"):
        insert_certification("id: bot\n", {"certified_on": "2026-12-01"})


def test_the_step_times_go_into_the_reproduction_report(tmp_path: Path) -> None:
    """RFC-0708: the cost of a run is measured, so each step's time is in the report it pins."""
    path = tmp_path / "reproduction-report.json"
    path.write_text(json.dumps(_report()) + "\n", encoding="utf-8")
    steps = [
        StepTime(step="plan", seconds=0.01),
        StepTime(step="install", seconds=9.5),
        StepTime(step="run", seconds=0.6),
    ]
    record_timing(path, steps)
    again = record_timing(path, steps[:1])  # a second write replaces the first, it does not append
    assert [step.step for step in again.timing or []] == ["plan"]
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["timing"] == [{"step": "plan", "seconds": 0.01}]
    assert stored["results"] == _report()["results"]
    assert check_reproduction(_plan(tmp_path), ConformanceReport.model_validate(stored)) == []


@pytest.mark.parametrize(
    "timing",
    [[{"step": "review", "seconds": 1.0}], [{"step": "run", "seconds": -1.0}], [{"step": "run"}]],
    ids=["unknown-step", "negative", "no-seconds"],
)
def test_a_report_refuses_timing_it_cannot_mean(timing: list[dict[str, Any]]) -> None:
    with pytest.raises(ValueError):
        ConformanceReport.model_validate(_report(timing=timing))


def test_a_report_without_timing_still_parses() -> None:
    """A self-report, or a reproduction written before timing existed, carries none."""
    assert ConformanceReport.model_validate(_report()).timing is None
