"""Deterministic semantic classification of preserved source text.

Rules extract structure that is *supported by the source*. Content that cannot
be classified is retained as unclassified spans / open decisions — never
silently dropped or invented.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .ingest import IngestMode, IngestResult
from .spans import SourceSpan, slugify, span_for_lines

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
BULLET_RE = re.compile(r"^(\s*)([-*+]|\d+\.)\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^```([^\n`]*)\s*$")
EQ_BLOCK_RE = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
EQ_INLINE_RE = re.compile(r"(?<!\$)\$(?!\$)([^$\n]+)\$(?!\$)")
LATEX_EQ_RE = re.compile(
    r"\\begin\{equation\*?\}(.+?)\\end\{equation\*?\}", re.DOTALL | re.IGNORECASE
)

SECTION_ALIASES = {
    "requirement": "requirements",
    "requirements": "requirements",
    "req": "requirements",
    "decision": "decisions",
    "decisions": "decisions",
    "design decision": "decisions",
    "open decision": "open_decisions",
    "open decisions": "open_decisions",
    "todo": "open_decisions",
    "gaps": "open_decisions",
    "unknown": "open_decisions",
    "work package": "work_packages",
    "work packages": "work_packages",
    "wp": "work_packages",
    "milestone": "milestones",
    "milestones": "milestones",
    "checkpoint": "semantic_checkpoints",
    "semantic checkpoint": "semantic_checkpoints",
    "scp": "semantic_checkpoints",
    "evidence": "evidence_intents",
    "evidence intent": "evidence_intents",
    "evidence intents": "evidence_intents",
    "asset": "assets",
    "assets": "assets",
    "snippet": "assets",
    "equation": "assets",
    "context": "context_requirements",
    "context requirement": "context_requirements",
    "context requirements": "context_requirements",
}


@dataclass
class ClassificationResult:
    plan: dict[str, Any]
    source_traces: list[dict[str, Any]] = field(default_factory=list)
    unclassified_spans: list[dict[str, Any]] = field(default_factory=list)
    gaps: list[dict[str, Any]] = field(default_factory=list)
    open_decisions: list[dict[str, Any]] = field(default_factory=list)

    def gap_report(self) -> dict[str, Any]:
        return {
            "schema_version": "autviam.genplan.gap-report/v1",
            "gaps": self.gaps,
            "open_decisions": self.open_decisions,
            "unclassified_span_count": len(self.unclassified_spans),
            "unclassified_spans": self.unclassified_spans,
        }


def _trace(obj_id: str, span: SourceSpan, kind: str) -> dict[str, Any]:
    return {
        "object_id": obj_id,
        "object_kind": kind,
        "span": span.to_dict(),
    }


def _stable_id(prefix: str, title: str, used: set[str]) -> str:
    base = f"{prefix}-{slugify(title)}"
    candidate = base
    n = 2
    while candidate in used:
        candidate = f"{base}-{n}"
        n += 1
    used.add(candidate)
    return candidate


def classify(ingest: IngestResult) -> ClassificationResult:
    if ingest.mode is IngestMode.REQUEST:
        return _classify_request(ingest)
    return _classify_digest(ingest)


def _classify_request(ingest: IngestResult) -> ClassificationResult:
    used: set[str] = set()
    title = ingest.title_hint or "request"
    plan_id = _stable_id("plan", title, used)
    prog_id = _stable_id("prog", title, used)
    ms_id = _stable_id("ms", "initial", used)
    wp_id = _stable_id("wp", "scope-request", used)
    scp_id = _stable_id("scp", "clarify-scope", used)
    ei_id = _stable_id("ei", "acceptance-criteria", used)
    od_id = _stable_id("od", "missing-structure", used)

    full_span = span_for_lines(
        ingest.source_id, ingest.lines, 1, max(1, len(ingest.lines))
    )
    request_text = ingest.text.strip()

    plan: dict[str, Any] = {
        "schema_version": "autviam.semantic-plan/v1",
        "plan": {
            "id": plan_id,
            "title": title,
            "program_id": prog_id,
            "authority": "user-asserted",
        },
        "ingestion": {
            "mode": "request",
            "source_id": ingest.source_id,
        },
        "sources": {
            "manifest": [ingest.manifest_entry()],
        },
        "problem": {
            "statement": request_text,
            "authority": "user-asserted",
            "source_span": full_span.to_dict(),
        },
        "milestones": [
            {
                "id": ms_id,
                "title": "Initial delivery",
                "authority": "inferred",
                "program_id": prog_id,
                "note": "Inferred skeleton for request mode; not source-structured.",
            }
        ],
        "work_packages": [
            {
                "id": wp_id,
                "title": "Scope the request into verifiable work",
                "authority": "inferred",
                "milestone_id": ms_id,
            }
        ],
        "semantic_checkpoints": [
            {
                "id": scp_id,
                "title": "Clarify scope and success criteria",
                "authority": "inferred",
                "work_package_id": wp_id,
            }
        ],
        "evidence_intents": [
            {
                "id": ei_id,
                "title": "Record explicit acceptance criteria",
                "authority": "inferred",
                "semantic_checkpoint_id": scp_id,
            }
        ],
        "requirements": [
            {
                "id": _stable_id("req", "request-body", used),
                "statement": request_text,
                "authority": "user-asserted",
                "kind": "functional",
                "source_span": full_span.to_dict(),
            }
        ],
        "decisions": [],
        "assets": [],
        "context_requirements": [],
        "open_decisions": [
            {
                "id": od_id,
                "statement": (
                    "Request mode produced a skeleton only; milestones, work packages, "
                    "and evidence intent beyond the request body remain open."
                ),
                "authority": "inferred",
                "status": "open",
                "source_span": full_span.to_dict(),
            }
        ],
        "extensions": {
            "autviam.genplan": {
                "mode": "request",
                "invented_structure": True,
                "note": "Structural skeleton is explicit inferred, not silent invention.",
            }
        },
    }

    traces = [
        _trace(plan_id, full_span, "plan"),
        _trace(plan["requirements"][0]["id"], full_span, "requirement"),
        _trace(od_id, full_span, "open_decision"),
    ]
    gaps = [
        {
            "id": "gap-request-structure",
            "kind": "missing-structure",
            "message": "No markdown structure; hierarchy is inferred skeleton.",
            "object_ids": [ms_id, wp_id, scp_id, ei_id],
        }
    ]
    return ClassificationResult(
        plan=plan,
        source_traces=traces,
        gaps=gaps,
        open_decisions=list(plan["open_decisions"]),
    )


def _classify_digest(ingest: IngestResult) -> ClassificationResult:
    lines = ingest.lines
    used: set[str] = set()
    traces: list[dict[str, Any]] = []
    unclassified: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    open_decisions: list[dict[str, Any]] = []

    title = ingest.title_hint or "digested-plan"
    plan_id = _stable_id("plan", title, used)
    prog_id = _stable_id("prog", title, used)

    milestones: list[dict[str, Any]] = []
    work_packages: list[dict[str, Any]] = []
    scps: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    requirements: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    assets: list[dict[str, Any]] = []
    context_reqs: list[dict[str, Any]] = []

    current_section: str | None = None
    current_ms: str | None = None
    current_wp: str | None = None
    current_scp: str | None = None
    covered_lines: set[int] = set()

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        line_no = i + 1

        # Fenced code → snippet asset
        fm = FENCE_RE.match(line)
        if fm:
            lang = (fm.group(1) or "").strip() or "text"
            start = line_no
            i += 1
            body: list[str] = []
            while i < n and not FENCE_RE.match(lines[i]):
                body.append(lines[i])
                i += 1
            end = i + 1 if i < n else i
            if i < n:
                i += 1  # closing fence
            for ln in range(start, end + 1):
                covered_lines.add(ln)
            span = span_for_lines(ingest.source_id, lines, start, min(end, n))
            aid = _stable_id("asset", f"snippet-{lang}-{start}", used)
            assets.append(
                {
                    "id": aid,
                    "title": f"Snippet ({lang}) at L{start}",
                    "authority": "user-asserted",
                    "asset_authority": "illustrative",
                    "kind": "snippet",
                    "language": lang,
                    "content": "\n".join(body),
                    "source_span": span.to_dict(),
                }
            )
            traces.append(_trace(aid, span, "asset"))
            continue

        hm = HEADING_RE.match(line)
        if hm:
            level = len(hm.group(1))
            text = hm.group(2).strip()
            covered_lines.add(line_no)
            span = span_for_lines(ingest.source_id, lines, line_no, line_no)
            key = SECTION_ALIASES.get(text.lower())
            if key:
                current_section = key
                # Section headers themselves are classification anchors, not objects.
                traces.append(
                    {
                        "object_id": f"section-{slugify(text)}",
                        "object_kind": "section_marker",
                        "span": span.to_dict(),
                        "section": key,
                    }
                )
                i += 1
                continue

            # Hierarchy by heading depth (A-002: no Phase)
            if level <= 1:
                # H1 already used as title; treat additional H1 as milestone
                mid = _stable_id("ms", text, used)
                milestones.append(
                    {
                        "id": mid,
                        "title": text,
                        "authority": "user-asserted",
                        "program_id": prog_id,
                        "source_span": span.to_dict(),
                    }
                )
                current_ms = mid
                current_wp = None
                current_scp = None
                current_section = None
                traces.append(_trace(mid, span, "milestone"))
            elif level == 2:
                mid = _stable_id("ms", text, used)
                milestones.append(
                    {
                        "id": mid,
                        "title": text,
                        "authority": "user-asserted",
                        "program_id": prog_id,
                        "source_span": span.to_dict(),
                    }
                )
                current_ms = mid
                current_wp = None
                current_scp = None
                current_section = None
                traces.append(_trace(mid, span, "milestone"))
            elif level == 3:
                if current_ms is None:
                    current_ms = _stable_id("ms", "default", used)
                    milestones.append(
                        {
                            "id": current_ms,
                            "title": "Default milestone",
                            "authority": "inferred",
                            "program_id": prog_id,
                            "note": "Inferred because a work package heading appeared first.",
                        }
                    )
                    gaps.append(
                        {
                            "id": f"gap-missing-milestone-before-{slugify(text)}",
                            "kind": "inferred-parent",
                            "message": "Work package heading before any milestone; default milestone inferred.",
                        }
                    )
                wpid = _stable_id("wp", text, used)
                work_packages.append(
                    {
                        "id": wpid,
                        "title": text,
                        "authority": "user-asserted",
                        "milestone_id": current_ms,
                        "source_span": span.to_dict(),
                    }
                )
                current_wp = wpid
                current_scp = None
                current_section = "work_packages"
                traces.append(_trace(wpid, span, "work_package"))
            elif level == 4:
                if current_wp is None:
                    if current_ms is None:
                        current_ms = _stable_id("ms", "default", used)
                        milestones.append(
                            {
                                "id": current_ms,
                                "title": "Default milestone",
                                "authority": "inferred",
                                "program_id": prog_id,
                            }
                        )
                    current_wp = _stable_id("wp", "default", used)
                    work_packages.append(
                        {
                            "id": current_wp,
                            "title": "Default work package",
                            "authority": "inferred",
                            "milestone_id": current_ms,
                        }
                    )
                    gaps.append(
                        {
                            "id": f"gap-missing-wp-before-{slugify(text)}",
                            "kind": "inferred-parent",
                            "message": "Semantic checkpoint heading before work package; default WP inferred.",
                        }
                    )
                scpid = _stable_id("scp", text, used)
                scps.append(
                    {
                        "id": scpid,
                        "title": text,
                        "authority": "user-asserted",
                        "work_package_id": current_wp,
                        "source_span": span.to_dict(),
                    }
                )
                current_scp = scpid
                current_section = "semantic_checkpoints"
                traces.append(_trace(scpid, span, "semantic_checkpoint"))
            else:
                # Deeper headings → evidence intent if under scp, else open decision
                if current_scp is not None:
                    eiid = _stable_id("ei", text, used)
                    evidence.append(
                        {
                            "id": eiid,
                            "title": text,
                            "authority": "user-asserted",
                            "semantic_checkpoint_id": current_scp,
                            "source_span": span.to_dict(),
                        }
                    )
                    traces.append(_trace(eiid, span, "evidence_intent"))
                else:
                    odid = _stable_id("od", text, used)
                    od = {
                        "id": odid,
                        "statement": text,
                        "authority": "user-asserted",
                        "status": "open",
                        "source_span": span.to_dict(),
                        "note": "Deep heading without scp parent.",
                    }
                    open_decisions.append(od)
                    traces.append(_trace(odid, span, "open_decision"))
            i += 1
            continue

        bm = BULLET_RE.match(line)
        if bm:
            body = bm.group(3).strip()
            covered_lines.add(line_no)
            span = span_for_lines(ingest.source_id, lines, line_no, line_no)
            section = current_section or "requirements"
            if section == "requirements":
                rid = _stable_id("req", body[:40], used)
                requirements.append(
                    {
                        "id": rid,
                        "statement": body,
                        "authority": "user-asserted",
                        "kind": "functional",
                        "source_span": span.to_dict(),
                    }
                )
                traces.append(_trace(rid, span, "requirement"))
            elif section == "decisions":
                did = _stable_id("dec", body[:40], used)
                decisions.append(
                    {
                        "id": did,
                        "statement": body,
                        "authority": "user-asserted",
                        "status": "proposed",
                        "source_span": span.to_dict(),
                    }
                )
                traces.append(_trace(did, span, "decision"))
            elif section == "open_decisions":
                odid = _stable_id("od", body[:40], used)
                od = {
                    "id": odid,
                    "statement": body,
                    "authority": "user-asserted",
                    "status": "open",
                    "source_span": span.to_dict(),
                }
                open_decisions.append(od)
                traces.append(_trace(odid, span, "open_decision"))
            elif section == "evidence_intents":
                if current_scp is None:
                    # attach later via gap if no scp
                    odid = _stable_id("od", f"ei-{body[:30]}", used)
                    open_decisions.append(
                        {
                            "id": odid,
                            "statement": f"Evidence intent without scp parent: {body}",
                            "authority": "user-asserted",
                            "status": "open",
                            "source_span": span.to_dict(),
                        }
                    )
                else:
                    eiid = _stable_id("ei", body[:40], used)
                    evidence.append(
                        {
                            "id": eiid,
                            "title": body,
                            "authority": "user-asserted",
                            "semantic_checkpoint_id": current_scp,
                            "source_span": span.to_dict(),
                        }
                    )
                    traces.append(_trace(eiid, span, "evidence_intent"))
            elif section == "context_requirements":
                cid = _stable_id("ctx", body[:40], used)
                context_reqs.append(
                    {
                        "id": cid,
                        "concept": body,
                        "authority": "user-asserted",
                        "necessity": "required",
                        "inference": "forbidden",
                        "source_span": span.to_dict(),
                    }
                )
                traces.append(_trace(cid, span, "context_requirement"))
            elif section == "assets":
                aid = _stable_id("asset", body[:40], used)
                assets.append(
                    {
                        "id": aid,
                        "title": body,
                        "authority": "user-asserted",
                        "asset_authority": "reference",
                        "kind": "note",
                        "source_span": span.to_dict(),
                    }
                )
                traces.append(_trace(aid, span, "asset"))
            elif section == "work_packages":
                if current_ms is None:
                    current_ms = _stable_id("ms", "default", used)
                    milestones.append(
                        {
                            "id": current_ms,
                            "title": "Default milestone",
                            "authority": "inferred",
                            "program_id": prog_id,
                        }
                    )
                wpid = _stable_id("wp", body[:40], used)
                work_packages.append(
                    {
                        "id": wpid,
                        "title": body,
                        "authority": "user-asserted",
                        "milestone_id": current_ms,
                        "source_span": span.to_dict(),
                    }
                )
                current_wp = wpid
                traces.append(_trace(wpid, span, "work_package"))
            elif section == "milestones":
                mid = _stable_id("ms", body[:40], used)
                milestones.append(
                    {
                        "id": mid,
                        "title": body,
                        "authority": "user-asserted",
                        "program_id": prog_id,
                        "source_span": span.to_dict(),
                    }
                )
                current_ms = mid
                traces.append(_trace(mid, span, "milestone"))
            elif section == "semantic_checkpoints":
                if current_wp is None:
                    gaps.append(
                        {
                            "id": f"gap-scp-orphan-{line_no}",
                            "kind": "missing-parent",
                            "message": f"Checkpoint bullet without work package at L{line_no}",
                        }
                    )
                    odid = _stable_id("od", body[:40], used)
                    open_decisions.append(
                        {
                            "id": odid,
                            "statement": body,
                            "authority": "user-asserted",
                            "status": "open",
                            "source_span": span.to_dict(),
                        }
                    )
                else:
                    scpid = _stable_id("scp", body[:40], used)
                    scps.append(
                        {
                            "id": scpid,
                            "title": body,
                            "authority": "user-asserted",
                            "work_package_id": current_wp,
                            "source_span": span.to_dict(),
                        }
                    )
                    current_scp = scpid
                    traces.append(_trace(scpid, span, "semantic_checkpoint"))
            else:
                unclassified.append(span.to_dict())
            i += 1
            continue

        # Equation blocks on this line / multi-line handled via full-text pass later
        if line.strip() == "" or line.strip() == "---":
            covered_lines.add(line_no)
            i += 1
            continue

        # Non-empty prose: mark covered only if we attach it; else unclassified later
        i += 1

    # Full-text equation extraction (content still in source; mark line coverage)
    full = ingest.text
    for match in LATEX_EQ_RE.finditer(full):
        start_line = full[: match.start()].count("\n") + 1
        end_line = full[: match.end()].count("\n") + 1
        for ln in range(start_line, end_line + 1):
            covered_lines.add(ln)
        span = span_for_lines(ingest.source_id, lines, start_line, end_line)
        aid = _stable_id("asset", f"equation-latex-{start_line}", used)
        assets.append(
            {
                "id": aid,
                "title": f"LaTeX equation at L{start_line}",
                "authority": "user-asserted",
                "asset_authority": "normative",
                "kind": "equation",
                "notation": "latex",
                "content": match.group(1).strip(),
                "source_span": span.to_dict(),
            }
        )
        traces.append(_trace(aid, span, "asset"))

    for match in EQ_BLOCK_RE.finditer(full):
        start_line = full[: match.start()].count("\n") + 1
        end_line = full[: match.end()].count("\n") + 1
        for ln in range(start_line, end_line + 1):
            covered_lines.add(ln)
        span = span_for_lines(ingest.source_id, lines, start_line, end_line)
        aid = _stable_id("asset", f"equation-block-{start_line}", used)
        assets.append(
            {
                "id": aid,
                "title": f"Display equation at L{start_line}",
                "authority": "user-asserted",
                "asset_authority": "normative",
                "kind": "equation",
                "notation": "tex-display",
                "content": match.group(1).strip(),
                "source_span": span.to_dict(),
            }
        )
        traces.append(_trace(aid, span, "asset"))

    for match in EQ_INLINE_RE.finditer(full):
        start_line = full[: match.start()].count("\n") + 1
        covered_lines.add(start_line)
        span = span_for_lines(ingest.source_id, lines, start_line, start_line)
        aid = _stable_id("asset", f"equation-inline-{start_line}-{match.start()}", used)
        assets.append(
            {
                "id": aid,
                "title": f"Inline equation at L{start_line}",
                "authority": "user-asserted",
                "asset_authority": "normative",
                "kind": "equation",
                "notation": "tex-inline",
                "content": match.group(1).strip(),
                "source_span": span.to_dict(),
            }
        )
        traces.append(_trace(aid, span, "asset"))

    # Unclassified non-empty lines are NOT dropped — recorded explicitly.
    for idx, line in enumerate(lines, start=1):
        if idx in covered_lines:
            continue
        if not line.strip():
            continue
        # Skip pure equation remnants already extracted
        if line.strip().startswith("$$") or "\\begin{equation" in line:
            continue
        span = span_for_lines(ingest.source_id, lines, idx, idx)
        unclassified.append(span.to_dict())
        # Also promote to open decision so they remain in semantic plan
        odid = _stable_id("od", f"unclassified-L{idx}", used)
        open_decisions.append(
            {
                "id": odid,
                "statement": line.strip(),
                "authority": "user-asserted",
                "status": "open",
                "source_span": span.to_dict(),
                "note": "Unclassified source line retained as open decision (not dropped).",
            }
        )
        traces.append(_trace(odid, span, "open_decision"))
        covered_lines.add(idx)

    if not milestones:
        mid = _stable_id("ms", "default", used)
        milestones.append(
            {
                "id": mid,
                "title": "Default milestone",
                "authority": "inferred",
                "program_id": prog_id,
            }
        )
        gaps.append(
            {
                "id": "gap-no-milestone",
                "kind": "missing-structure",
                "message": "No milestone heading found; default inferred.",
            }
        )
        current_ms = mid

    if not work_packages:
        gaps.append(
            {
                "id": "gap-no-work-package",
                "kind": "missing-structure",
                "message": "No work package extracted from source headings/lists.",
            }
        )

    full_span = span_for_lines(ingest.source_id, lines, 1, max(1, len(lines)))
    plan: dict[str, Any] = {
        "schema_version": "autviam.semantic-plan/v1",
        "plan": {
            "id": plan_id,
            "title": title,
            "program_id": prog_id,
            "authority": "user-asserted",
            "source_span": span_for_lines(
                ingest.source_id, lines, 1, 1 if lines else 1
            ).to_dict(),
        },
        "ingestion": {
            "mode": "digest",
            "source_id": ingest.source_id,
        },
        "sources": {
            "manifest": [ingest.manifest_entry()],
        },
        "problem": {
            "statement": title,
            "authority": "user-asserted",
            "source_span": full_span.to_dict(),
        },
        "milestones": milestones,
        "work_packages": work_packages,
        "semantic_checkpoints": scps,
        "evidence_intents": evidence,
        "requirements": requirements,
        "decisions": decisions,
        "assets": assets,
        "context_requirements": context_reqs,
        "open_decisions": open_decisions,
        "extensions": {
            "autviam.genplan": {
                "mode": "digest",
                "invented_structure": False,
                "unclassified_count": len(unclassified),
            }
        },
    }
    traces.insert(0, _trace(plan_id, full_span, "plan"))

    return ClassificationResult(
        plan=plan,
        source_traces=traces,
        unclassified_spans=unclassified,
        gaps=gaps,
        open_decisions=open_decisions,
    )
