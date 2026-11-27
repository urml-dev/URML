"""Guards for the Claude Code plugin bundle (plugins/urml/).

Two invariants:

1. The skill bundled in the plugin is byte-identical to the canonical
   Agent Skill under .github/skills/. One source of truth; the plugin
   copy exists only because plugins must be self-contained.
2. The plugin's version sites stay in lockstep with the MCP server's
   release version (reference/mcp-server/server.json): plugin.json
   "version" and the exact ==pin in .mcp.json. The Claude directory
   requires an exact pin, and a stale pin would ship users an old
   server.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "urml"
CANON_SKILL = REPO / ".github" / "skills" / "urml-robot-intent"
PLUGIN_SKILL = PLUGIN / "skills" / "urml-robot-intent"


def _skill_files(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_plugin_skill_matches_canonical() -> None:
    assert _skill_files(PLUGIN_SKILL) == _skill_files(CANON_SKILL)


def test_plugin_versions_in_lockstep() -> None:
    server = json.loads((REPO / "reference" / "mcp-server" / "server.json").read_text())
    release = server["version"]

    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["version"] == release

    mcp = json.loads((PLUGIN / ".mcp.json").read_text())
    args = mcp["mcpServers"]["urml"]["args"]
    assert f"urml-mcp-server=={release}" in args


def test_marketplace_entry_matches_manifest() -> None:
    marketplace = json.loads(
        (REPO / ".claude-plugin" / "marketplace.json").read_text()
    )
    entries = {p["name"]: p for p in marketplace["plugins"]}
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["name"] in entries
    assert entries[manifest["name"]]["source"] == "./plugins/urml"
