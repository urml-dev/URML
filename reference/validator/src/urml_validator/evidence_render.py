"""Human forms of an evidence report: Markdown and one static HTML file (RFC-0707, step 3).

Both render the JSON report and add nothing it lacks: every item, with its
status and text, appears in every form, and the notice opens every form. The
HTML is a single file with inline styles, no scripts and no external requests,
so it opens offline and can be attached to an audit file. Both are
deterministic: the same report gives the same text.
"""

from __future__ import annotations

import html
from collections.abc import Iterator

from urml_validator.evidence_report import STATUSES, EvidenceReport, Item, Section

#: What each status means, as a reader-facing legend.
STATUS_MEANING = {
    "checked": "The validator checks this before a program runs.",
    "declared": "Someone states this; URML records who and does not verify it.",
    "runtime": "The runtime must enforce this while a program runs.",
    "missing": "Something a rule, the policy or the envelope needs is absent.",
    "outside": "URML cannot see this; someone else must cover it.",
}


def _gaps(report: EvidenceReport) -> Iterator[tuple[Section, Item]]:
    for section in report.sections:
        for item in section.items:
            if item.status == "missing" or item.result == "fail":
                yield section, item


def _status_label(item: Item) -> str:
    return f"{item.status}, {item.result}" if item.result is not None else item.status


def _subtitle(report: EvidenceReport) -> str:
    parts = [f"As of {report.as_of}", f"urml-validator {report.inputs.validator['version']}"]
    if report.inputs.profiles:
        parts.append("profiles: " + ", ".join(report.inputs.profiles))
    parts.append(f"policy: {report.inputs.policy}")
    return " · ".join(parts)


def _redaction_line(report: EvidenceReport) -> str:
    assert report.redaction is not None
    n = len(report.redaction.removed)
    return (
        f"Redacted copy: {n} value{'s' if n != 1 else ''} removed (site geometry and program messages). "
        f"The full report's sha256 is {report.redaction.full_report_sha256}."
    )


def _gap_line(report: EvidenceReport) -> str:
    c = report.counts
    if c.gaps == 0:
        return "Gaps: none. Nothing is missing and no check failed."
    failed = f"{c.failed_checks} failed check" + ("" if c.failed_checks == 1 else "s")
    return f"Gaps: {c.gaps} ({c.by_status['missing']} missing, {failed})."


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def _cell(text: str) -> str:
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def render_markdown(report: EvidenceReport) -> str:
    """The report as Markdown: summary, gaps, every section, by standard, inputs."""
    robot = report.subject.get("robot_id") or "robot"
    out: list[str] = [f"# Evidence report: {robot}", "", f"> {report.notice}", "", _subtitle(report), ""]
    if report.redaction is not None:
        out += [_redaction_line(report), ""]

    out += ["## Summary", "", "| Status | Items | Meaning |", "|---|---|---|"]
    for status in STATUSES:
        out.append(f"| `{status}` | {report.counts.by_status[status]} | {STATUS_MEANING[status]} |")
    out += ["", _gap_line(report), ""]

    gaps = list(_gaps(report))
    if gaps:
        out += ["## Gaps", ""]
        for section, item in gaps:
            out.append(f"- **{section.title}** `{item.id}` ({_status_label(item)}): {_cell(item.text)}")
        out.append("")

    for section in report.sections:
        out += [f"## {section.title}", ""]
        if not section.items:
            out += [section.note or "No items.", ""]
            continue
        out += ["| Status | Item | What the report knows |", "|---|---|---|"]
        for item in section.items:
            out.append(f"| `{_status_label(item)}` | `{item.id}` | {_cell(item.text)} |")
        out.append("")

    out += ["## By standard", ""]
    if not report.by_standard:
        out += ["No rule or obligation cites a standard.", ""]
    else:
        out += ["| Standard | " + " | ".join(STATUSES) + " |", "|---|" + "---|" * len(STATUSES)]
        for group in report.by_standard:
            counts = " | ".join(str(len(group.items.get(s, []))) for s in STATUSES)
            out.append(f"| {_cell(group.standard)} | {counts} |")
        out.append("")

    out += ["## Inputs", "", "| Role | Id | File | Digest |", "|---|---|---|---|"]
    for ref in report.inputs.files:
        name = "bundled" if ref.bundled else (ref.name or "")
        out.append(f"| {ref.role} | {_cell(ref.id or '')} | {_cell(name)} | `{ref.digest}` |")
    out += [
        "",
        "Rebuild this report from the same files with `urml evidence build` and the same `--as-of` "
        "date, and compare digests.",
        "",
    ]
    return "\n".join(out)


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

_STYLE = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#5d5d57;--rule:#dcd9d0;--card:#ffffff;
--checked:#1f6f43;--declared:#7a5a00;--runtime:#2a5a9e;--missing:#b3261e;--outside:#5d5d57}
@media (prefers-color-scheme:dark){:root{--bg:#161614;--fg:#ecebe6;--muted:#a3a29b;--rule:#3a3934;
--card:#1f1f1c;--checked:#6fcf97;--declared:#e2b93b;--runtime:#7fb0f0;--missing:#ff8a80;--outside:#a3a29b}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1040px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:26px;margin:0 0 12px}h2{font-size:19px;margin:36px 0 10px;border-bottom:1px solid var(--rule);
padding-bottom:6px}
.notice{border-left:4px solid var(--missing);background:var(--card);padding:10px 14px;margin:0 0 12px;font-weight:600}
.sub,.note{color:var(--muted)}
table{width:100%;border-collapse:collapse;background:var(--card)}
th,td{text-align:left;vertical-align:top;padding:7px 10px;border-bottom:1px solid var(--rule)}
th{font-size:13px;color:var(--muted);font-weight:600}
td.id,code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;overflow-wrap:break-word}
a{color:var(--runtime)}
.s{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;font-weight:600;border:1px solid;
white-space:nowrap}
.s-checked{color:var(--checked)}.s-declared{color:var(--declared)}.s-runtime{color:var(--runtime)}
.s-missing{color:var(--missing)}.s-outside{color:var(--outside)}.s-fail{color:var(--missing)}
.wrap{overflow-x:auto}
@media (max-width:640px){td.id{max-width:140px}}
""".strip()


def _e(text: str) -> str:
    return html.escape(text, quote=True)


def _id(item_id: str) -> str:
    """An item id, escaped, with break opportunities after its dots."""
    return _e(item_id).replace(".", ".<wbr>")


def _badge(item: Item) -> str:
    cls = "s-fail" if item.result == "fail" else f"s-{item.status}"
    return f'<span class="s {cls}">{_e(_status_label(item))}</span>'


def render_html(report: EvidenceReport) -> str:
    """The report as one static HTML page: inline styles, no scripts, no external requests."""
    robot = report.subject.get("robot_id") or "robot"
    out: list[str] = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>Evidence report: {_e(robot)}</title>",
        f"<style>{_STYLE}</style>",
        "</head>",
        "<body>",
        "<main>",
        f"<h1>Evidence report: {_e(robot)}</h1>",
        f'<p class="notice">{_e(report.notice)}</p>',
        f'<p class="sub">{_e(_subtitle(report))}</p>',
        *([f'<p class="note"><strong>{_e(_redaction_line(report))}</strong></p>'] if report.redaction else []),
        "<h2>Summary</h2>",
        '<div class="wrap"><table><thead><tr><th>Status</th><th>Items</th><th>Meaning</th></tr></thead><tbody>',
    ]
    for status in STATUSES:
        out.append(
            f'<tr><td><span class="s s-{status}">{status}</span></td>'
            f"<td>{report.counts.by_status[status]}</td><td>{_e(STATUS_MEANING[status])}</td></tr>"
        )
    out += ["</tbody></table></div>", f"<p><strong>{_e(_gap_line(report))}</strong></p>"]

    gaps = list(_gaps(report))
    if gaps:
        out += ["<h2>Gaps</h2>", "<ul>"]
        for section, item in gaps:
            out.append(
                f'<li><a href="#{_e(item.id)}"><code>{_id(item.id)}</code></a> '
                f"({_e(section.title)}, {_badge(item)}): {_e(item.text)}</li>"
            )
        out.append("</ul>")

    for section in report.sections:
        out.append(f'<h2 id="section-{_e(section.id)}">{_e(section.title)}</h2>')
        if not section.items:
            out.append(f'<p class="note">{_e(section.note or "No items.")}</p>')
            continue
        out.append(
            '<div class="wrap"><table><thead><tr><th>Status</th><th>Item</th>'
            "<th>What the report knows</th></tr></thead><tbody>"
        )
        for item in section.items:
            out.append(
                f'<tr id="{_e(item.id)}"><td>{_badge(item)}</td><td class="id">{_id(item.id)}</td>'
                f"<td>{_e(item.text)}</td></tr>"
            )
        out.append("</tbody></table></div>")

    out.append("<h2>By standard</h2>")
    if not report.by_standard:
        out.append('<p class="note">No rule or obligation cites a standard.</p>')
    else:
        head = "".join(f"<th>{s}</th>" for s in STATUSES)
        out.append(f'<div class="wrap"><table><thead><tr><th>Standard</th>{head}</tr></thead><tbody>')
        for group in report.by_standard:
            cells = "".join(f"<td>{len(group.items.get(s, []))}</td>" for s in STATUSES)
            out.append(f"<tr><td>{_e(group.standard)}</td>{cells}</tr>")
        out.append("</tbody></table></div>")

    out += [
        "<h2>Inputs</h2>",
        '<div class="wrap"><table><thead><tr><th>Role</th><th>Id</th><th>File</th><th>Digest</th></tr></thead><tbody>',
    ]
    for ref in report.inputs.files:
        name = "bundled" if ref.bundled else (ref.name or "")
        out.append(
            f"<tr><td>{_e(ref.role)}</td><td>{_e(ref.id or '')}</td><td>{_e(name)}</td>"
            f'<td class="id">{_e(ref.digest)}</td></tr>'
        )
    out += [
        "</tbody></table></div>",
        '<p class="note">Rebuild this report from the same files with <code>urml evidence build</code> and the '
        "same <code>--as-of</code> date, and compare digests.</p>",
        "</main>",
        "</body>",
        "</html>",
        "",
    ]
    return "\n".join(out)


__all__ = ["STATUS_MEANING", "render_html", "render_markdown"]
