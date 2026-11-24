"""Render the standards directory from docs/standards/directory.yaml.

    python tools/scripts/gen_standards_doc.py          # write README.md and directory.json
    python tools/scripts/gen_standards_doc.py --check  # exit 1 if either is stale

directory.yaml is the single source. README.md is what GitHub shows;
directory.json is what urml.dev/standards renders (the website copies it at
build). Both are generated, deterministic and committed.
reference/validator/tests/test_standards_directory.py runs --check.

Standard library and PyYAML only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "docs" / "standards"
SOURCE = DIR / "directory.yaml"
README = DIR / "README.md"
JSON_OUT = DIR / "directory.json"

ENTRY_FIELDS = (
    "id",
    "name",
    "title",
    "kind",
    "area",
    "who_short",
    "what",
    "why",
    "who",
    "how",
    "text",
    "assess",
    "urml",
)
HEADER = """<p align="center">
  <a href="https://urml.dev"><img src="https://urml.dev/favicon.svg" alt="URML" width="72" height="72"></a>
</p>

<p align="center">
  A small, opinionated, human-readable language for describing robot intent.
</p>

<p align="center">
  <a href="https://urml.dev"><b>urml.dev</b></a>
</p>

---

"""


class DirectoryError(ValueError):
    """directory.yaml breaks the shape the generator expects."""


def _links(value: Any, where: str) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise DirectoryError(f"{where}: links must be a list")
    for link in value:
        if not isinstance(link, dict) or set(link) != {"label", "url"}:
            raise DirectoryError(f"{where}: each link is {{label, url}}")
        if not str(link["url"]).startswith("https://"):
            raise DirectoryError(f"{where}: {link['url']} is not an https URL")
    return value


def load(path: Path = SOURCE) -> dict[str, Any]:
    """Read and check directory.yaml."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    kinds = {k["id"] for k in data["legend"]["kinds"]}
    support = {s["id"] for s in data["legend"]["support"]}
    for role in data["legend"]["roles"]:
        _links(role.get("links"), f"role {role['id']}")
    ids: set[str] = set()
    for group in data["groups"]:
        for entry in group["entries"]:
            missing = [f for f in ENTRY_FIELDS if f not in entry]
            if missing:
                raise DirectoryError(f"entry {entry.get('id')}: missing {missing}")
            if entry["id"] in ids:
                raise DirectoryError(f"entry {entry['id']} appears twice")
            ids.add(entry["id"])
            if entry["kind"] not in kinds:
                raise DirectoryError(
                    f"entry {entry['id']}: kind {entry['kind']} is not in the legend"
                )
            for s in entry["urml"].get("support", []):
                if s not in support:
                    raise DirectoryError(
                        f"entry {entry['id']}: support {s} is not in the legend"
                    )
            _links(entry["text"], f"entry {entry['id']} text")
            _links(entry["assess"].get("links"), f"entry {entry['id']} assess")
            _links(entry["urml"].get("links"), f"entry {entry['id']} urml")
    for term in data["legend"]["terms"]:
        if term.get("see") is not None and term["see"] not in ids:
            raise DirectoryError(
                f"term {term['term']}: see {term['see']} is not an entry"
            )
    if not isinstance(data, dict):
        raise DirectoryError(f"{path} is not a mapping")
    return data


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def _md_links(links: list[dict[str, str]]) -> str:
    return ", ".join(f"[{link['label']}]({link['url']})" for link in links)


def _cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def render_markdown(data: dict[str, Any]) -> str:
    kinds = {k["id"]: k for k in data["legend"]["kinds"]}
    support = {s["id"]: s for s in data["legend"]["support"]}
    entries = [e for g in data["groups"] for e in g["entries"]]
    out = [
        HEADER + f"# {data['title']}",
        "",
        _cell(data["lead"]),
        "",
        _cell(data["caveat"]) + f" Checked on {data['checked']}.",
        "",
    ]
    out += [
        (
            "> This file is generated from [`directory.yaml`](directory.yaml) by "
            "[`tools/scripts/gen_standards_doc.py`](../../tools/scripts/gen_standards_doc.py). "
            "Edit the YAML, then run the script. "
            "The same content is at [urml.dev/standards](https://urml.dev/standards)."
        ),
        "",
    ]
    out += [
        "## Legend",
        "",
        "### Kinds of document",
        "",
        "| Kind | What it is | Binding? | Example |",
        "|---|---|---|---|",
    ]
    for k in data["legend"]["kinds"]:
        out.append(
            f"| **{k['name']}** | {_cell(k['what'])} | {_cell(k['binding'])} | {_cell(k['example'])} |"
        )
    out += [
        "",
        "### Who does what",
        "",
        "| Role | What it does | Where to find them |",
        "|---|---|---|",
    ]
    for r in data["legend"]["roles"]:
        out.append(
            f"| **{r['name']}** | {_cell(r['what'])} | {_md_links(r.get('links', []))} |"
        )
    out += ["", "### Key terms", ""]
    for t in data["legend"]["terms"]:
        see = f" See [{t['see']}](#{t['see']})." if t.get("see") else ""
        out.append(f"- **{t['term']}.** {_cell(t['what'])}{see}")
    out += ["", "### What URML gives you", "", "| Support | Meaning |", "|---|---|"]
    for s in data["legend"]["support"]:
        out.append(f"| **{s['name']}** | {_cell(s['what'])} |")
    out += ["", _cell(data["legend"]["not_a_certifier"]), ""]

    out += [
        "## Index",
        "",
        "| Entry | Kind | Area | Who needs it | URML support |",
        "|---|---|---|---|---|",
    ]
    for e in entries:
        sup = (
            ", ".join(support[s]["name"] for s in e["urml"].get("support", []))
            or "None yet"
        )
        out.append(
            f"| [{e['name']}](#{e['id']}) | {kinds[e['kind']]['name']} | {_cell(e['area'])} | "
            f"{_cell(e['who_short'])} | {sup} |"
        )
    out.append("")

    for group in data["groups"]:
        if not group["entries"]:
            continue
        out += [f"## {group['title']}", "", _cell(group["intro"]), ""]
        for e in group["entries"]:
            out += [f'<a id="{e["id"]}"></a>', "", f"### {e['name']}: {e['title']}", ""]
            status = f" **{e['status']}**" if e.get("status") else ""
            out.append(f"*{kinds[e['kind']]['name']} · {e['area']}*{status}")
            out.append("")
            out.append(f"- **What it is.** {_cell(e['what'])}")
            out.append(f"- **Why it matters.** {_cell(e['why'])}")
            out.append(f"- **Who needs it.** {_cell(e['who'])}")
            out.append(f"- **How to meet it.** {_cell(e['how'])}")
            out.append(f"- **Where to get the text.** {_md_links(e['text'])}")
            assess_links = _md_links(e["assess"].get("links", []))
            out.append(
                f"- **Who assesses it.** {_cell(e['assess']['text'])}"
                + (f" {assess_links}" if assess_links else "")
            )
            urml_links = _md_links(e["urml"].get("links", []))
            out.append(
                f"- **What URML gives you.** {_cell(e['urml']['text'])}"
                + (f" {urml_links}" if urml_links else "")
            )
            out.append("")
    out += [
        "## Missing something?",
        "",
        (
            "To add or correct an entry, edit [`directory.yaml`](directory.yaml), run "
            "`python tools/scripts/gen_standards_doc.py`, and open a pull request with the publisher's catalogue link "
            "for the edition."
        ),
        "",
    ]
    return "\n".join(out)


def render_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=False, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 when README.md or directory.json is stale",
    )
    args = parser.parse_args(argv)
    data = load()
    outputs = {README: render_markdown(data), JSON_OUT: render_json(data)}
    stale = [
        p
        for p, text in outputs.items()
        if not p.exists() or p.read_text(encoding="utf-8") != text
    ]
    if args.check:
        for path in stale:
            print(
                f"{path.relative_to(ROOT)} is stale; run python tools/scripts/gen_standards_doc.py",
                file=sys.stderr,
            )
        return 1 if stale else 0
    for path, text in outputs.items():
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
