"""AutViam GenPlan alpha — Markdown/plain-text → canonical semantic plan.

Deterministic extraction preserves source spans. Unsupported or ambiguous
content becomes open decisions / gaps; nothing source-supported is silently
dropped. Approval binds the normalized semantic hash and source manifest hash.
"""

from __future__ import annotations

from .approve import approve_plan, verify_approval
from .ingest import IngestMode, IngestResult, ingest_path, ingest_text
from .normalize import NormalizedPlan, normalize_semantic_plan
from .pipeline import GenPlanResult, run_genplan
from .views import render_html_view, render_markdown_view

__all__ = [
    "GenPlanResult",
    "IngestMode",
    "IngestResult",
    "NormalizedPlan",
    "approve_plan",
    "ingest_path",
    "ingest_text",
    "normalize_semantic_plan",
    "render_html_view",
    "render_markdown_view",
    "run_genplan",
    "verify_approval",
]
