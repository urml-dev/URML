"""The bundled default policy cites only sources that were checked.

Until 2026-11-27 the file cited a bill that was never enacted (the American
Security Robotics Act), the wrong act for the LiDAR restriction ("FY26 NDAA
section 164", which is a KC-46 provision), section 889 of the FY2019 NDAA for
rules it does not support, and two NIST publications that say nothing about
hardware bills of materials.

These tests read the file as text, comments included, because the comments
are where the sources live. Every legal citation in it must be on a list
that was checked against the primary text, written in one fixed form so the
test can find it. Adding a citation means reading the source first and then
adding it to the list here.
"""

from __future__ import annotations

import re
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
WALKTHROUGH = REPO_ROOT / "docs" / "demos" / "compliance-walkthrough.md"

# Bills that are not law. A bill leaves this list on the day it is enacted,
# and only then may the policy cite it.
PENDING_BILLS = (
    "American Security Robotics Act",
    "H.R. 8189",
    "S. 4235",
)

# Checked on 2026-11-27 against govinfo.gov, docs.fcc.gov, acquisition.gov
# and federalregister.gov. (section, fiscal year of the NDAA) pairs, so a
# right section number under the wrong act does not pass.
CHECKED_NDAA_SECTIONS = {
    ("889", "2019"),  # Pub. L. 115-232: telecommunications and video surveillance equipment
    ("848", "2020"),  # Pub. L. 116-92: foreign-made unmanned aircraft systems (DoD)
    ("1260H", "2021"),  # Pub. L. 116-283: list of Chinese military companies
    ("817", "2023"),  # Pub. L. 117-263: amends section 848, four covered countries
    ("805", "2024"),  # Pub. L. 118-31: DoD procurement from listed companies
    ("1821", "2024"),  # Pub. L. 118-31: American Security Drone Act of 2023 (1821 to 1833)
    ("164", "2025"),  # Pub. L. 118-159: foreign-made LiDAR (DoD), names Hesai Technology
    ("1709", "2025"),  # Pub. L. 118-159: DJI and Autel Robotics equipment, FCC Covered List
    ("162", "2026"),  # Pub. L. 119-60: amends section 164 of the FY2025 NDAA
    ("845", "2026"),  # Pub. L. 119-60: amends section 805 of the FY2024 NDAA
}
CHECKED_PUBLIC_LAWS = {"115-232", "116-92", "116-283", "117-263", "118-31", "118-159", "119-60"}
CHECKED_FEDERAL_REGISTER = {("91", "35189"), ("90", "24727")}
CHECKED_FCC_NOTICES = {"25-1086", "26-786"}
CHECKED_US_CODE = {("10", "4872")}
CHECKED_FAR = {"4.21", "40.202"}
CHECKED_EXECUTIVE_ORDERS = {"14307"}


def _policy_text() -> str:
    return resources.files("urml_validator.policies").joinpath("us_federal_default.yaml").read_text(encoding="utf-8")


def _flat(text: str) -> str:
    """The file as one line: comment markers and line breaks removed, so a wrapped citation still matches."""
    return re.sub(r"\s+", " ", re.sub(r"(?m)^\s*#", " ", text))


def _policy() -> dict[str, Any]:
    loaded = yaml.safe_load(_policy_text())
    assert isinstance(loaded, dict)
    return loaded


def test_the_default_policy_cites_no_pending_bill() -> None:
    flat = _flat(_policy_text()).lower()
    cited = [bill for bill in PENDING_BILLS if bill.lower() in flat]
    assert cited == [], f"the default policy cites bills that are not law: {cited}"


def test_every_ndaa_citation_names_a_checked_section_of_the_right_act() -> None:
    flat = _flat(_policy_text())
    found = set(re.findall(r"[Ss]ections? (\d+[A-Z]?)(?: to \d+)? of the FY(\d{4}) NDAA", flat))
    assert found, "the default policy cites no NDAA section in the checked form"
    assert found <= CHECKED_NDAA_SECTIONS, f"unchecked NDAA citations: {sorted(found - CHECKED_NDAA_SECTIONS)}"


def test_ndaa_citations_use_the_form_this_test_can_read() -> None:
    """`section N of the FYXXXX NDAA`. A section sign or a two-digit year would slip past the check above."""
    flat = _flat(_policy_text())
    assert "§" not in flat
    assert re.findall(r"\bFY ?\d{2}\b(?!\d)", flat) == []
    loose = re.findall(r"NDAA (?:section|sec\.) ?\d+", flat, flags=re.IGNORECASE)
    assert loose == [], f"write these as 'section N of the FYXXXX NDAA': {loose}"


def test_every_other_legal_citation_is_on_the_checked_list() -> None:
    flat = _flat(_policy_text())
    checks: list[tuple[str, set[Any], set[Any]]] = [
        ("public laws", set(re.findall(r"Pub\. L\. (\d+-\d+)", flat)), CHECKED_PUBLIC_LAWS),
        ("Federal Register", set(re.findall(r"\b(\d+) FR (\d+)\b", flat)), CHECKED_FEDERAL_REGISTER),
        ("FCC notices", set(re.findall(r"\bDA (\d+-\d+)\b", flat)), CHECKED_FCC_NOTICES),
        ("US Code", set(re.findall(r"\b(\d+) U\.S\.C\. (\d+)\b", flat)), CHECKED_US_CODE),
        ("FAR", set(re.findall(r"\bFAR (?:subpart )?(\d+\.\d+)\b", flat)), CHECKED_FAR),
        ("executive orders", set(re.findall(r"\bExecutive Order (\d+)\b", flat)), CHECKED_EXECUTIVE_ORDERS),
    ]
    for label, found, checked in checks:
        assert found <= checked, f"unchecked {label} citations: {sorted(found - checked)}"
    assert set(re.findall(r"Pub\. L\. (\d+-\d+)", flat)), "the default policy names no public law"


def test_every_rule_has_a_source_note_and_every_note_has_a_rule() -> None:
    text = _policy_text()
    header = text.split("policy_version:", 1)[0]
    noted: set[str] = set()
    for line in re.findall(r"(?m)^# - (.+)$", header):
        noted.update(part.strip() for part in line.split(","))
    rule_ids = {rule["id"] for rule in _policy()["rules"]}
    assert rule_ids - noted == set(), f"rules without a source note: {sorted(rule_ids - noted)}"
    assert noted - rule_ids == set(), f"source notes for rules that do not exist: {sorted(noted - rule_ids)}"


def test_no_message_says_the_law_prohibits_the_robot() -> None:
    """Every rule in the file reaches further than the statute it draws on, so none may claim a prohibition."""
    for rule in _policy()["rules"]:
        message = rule["on_violation"].get("message", "")
        assert "prohibited" not in message.lower(), rule["id"]


def test_the_compliance_walkthrough_quotes_the_messages_the_policy_emits() -> None:
    walkthrough = re.sub(r"\s+", " ", WALKTHROUGH.read_text(encoding="utf-8"))
    messages = {rule["id"]: re.sub(r"\s+", " ", rule["on_violation"]["message"]).strip() for rule in _policy()["rules"]}
    for rule_id in ("critical_country_denylist", "covered_vendor_denylist"):
        assert messages[rule_id] in walkthrough, f"docs/demos/compliance-walkthrough.md misquotes {rule_id}"
