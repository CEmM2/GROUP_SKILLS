"""Generated Markdown/HTML views that mirror canonical semantic YAML content."""

from __future__ import annotations

import html
from typing import Any


def _list_section(title: str, items: list[dict[str, Any]], fields: list[str]) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        lines.append("_None._")
        lines.append("")
        return lines
    for item in items:
        iid = item.get("id", "?")
        label = item.get("title") or item.get("statement") or item.get("concept") or ""
        lines.append(f"- `{iid}`: {label}")
        for field in fields:
            if field in item and field not in {"id", "title", "statement", "concept"}:
                lines.append(f"  - {field}: {item[field]}")
    lines.append("")
    return lines


def render_markdown_view(plan: dict[str, Any]) -> str:
    p = plan.get("plan") or {}
    lines = [
        f"# {p.get('title', 'Semantic plan')}",
        "",
        f"- plan id: `{p.get('id')}`",
        f"- program id: `{p.get('program_id')}`",
        f"- authority: `{p.get('authority')}`",
        f"- schema: `{plan.get('schema_version')}`",
        "",
    ]
    if isinstance(plan.get("problem"), dict) and plan["problem"].get("statement"):
        lines += ["## Problem", "", plan["problem"]["statement"], ""]
    lines += _list_section("Milestones", plan.get("milestones") or [], ["authority", "program_id"])
    lines += _list_section(
        "Work packages", plan.get("work_packages") or [], ["authority", "milestone_id"]
    )
    lines += _list_section(
        "Semantic checkpoints",
        plan.get("semantic_checkpoints") or [],
        ["authority", "work_package_id"],
    )
    lines += _list_section(
        "Evidence intents",
        plan.get("evidence_intents") or [],
        ["authority", "semantic_checkpoint_id"],
    )
    lines += _list_section(
        "Requirements", plan.get("requirements") or [], ["authority", "kind"]
    )
    lines += _list_section("Decisions", plan.get("decisions") or [], ["authority", "status"])
    lines += _list_section(
        "Assets", plan.get("assets") or [], ["authority", "asset_authority", "kind"]
    )
    lines += _list_section(
        "Open decisions", plan.get("open_decisions") or [], ["authority", "status", "note"]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_html_view(plan: dict[str, Any]) -> str:
    md_like = render_markdown_view(plan)
    # Deterministic minimal HTML — content is the escaped markdown view body
    # structured into preformatted sections for exact comparison in tests.
    p = plan.get("plan") or {}
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8"/>',
        f"<title>{html.escape(str(p.get('title', 'Semantic plan')))}</title>",
        "</head>",
        "<body>",
        f"<h1>{html.escape(str(p.get('title', 'Semantic plan')))}</h1>",
        "<ul>",
        f"<li>plan id: <code>{html.escape(str(p.get('id')))}</code></li>",
        f"<li>program id: <code>{html.escape(str(p.get('program_id')))}</code></li>",
        f"<li>authority: <code>{html.escape(str(p.get('authority')))}</code></li>",
        f"<li>schema: <code>{html.escape(str(plan.get('schema_version')))}</code></li>",
        "</ul>",
    ]

    def section(title: str, items: list[dict[str, Any]], primary: str) -> None:
        parts.append(f"<h2>{html.escape(title)}</h2>")
        if not items:
            parts.append("<p><em>None.</em></p>")
            return
        parts.append("<ul>")
        for item in items:
            label = item.get(primary) or item.get("title") or item.get("statement") or ""
            parts.append(
                f"<li><code>{html.escape(str(item.get('id')))}</code>: "
                f"{html.escape(str(label))}</li>"
            )
        parts.append("</ul>")

    section("Milestones", plan.get("milestones") or [], "title")
    section("Work packages", plan.get("work_packages") or [], "title")
    section("Semantic checkpoints", plan.get("semantic_checkpoints") or [], "title")
    section("Evidence intents", plan.get("evidence_intents") or [], "title")
    section("Requirements", plan.get("requirements") or [], "statement")
    section("Decisions", plan.get("decisions") or [], "statement")
    section("Assets", plan.get("assets") or [], "title")
    section("Open decisions", plan.get("open_decisions") or [], "statement")
    parts += ["</body>", "</html>", ""]
    # Embed a content fingerprint comment for view↔yaml matching tests
    ids = []
    for key in (
        "milestones",
        "work_packages",
        "semantic_checkpoints",
        "evidence_intents",
        "requirements",
        "decisions",
        "assets",
        "open_decisions",
    ):
        for item in plan.get(key) or []:
            if isinstance(item, dict) and item.get("id"):
                ids.append(str(item["id"]))
    parts.insert(-1, f"<!-- object-ids: {' '.join(sorted(ids))} -->")
    _ = md_like  # available for dual-format callers
    return "\n".join(parts)
