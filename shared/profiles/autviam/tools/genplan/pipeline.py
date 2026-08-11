"""End-to-end GenPlan alpha pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .approve import approve_plan
from .classify import ClassificationResult, classify
from .ingest import IngestMode, IngestResult, ingest_path, ingest_text
from .normalize import NormalizedPlan, dumps_canonical, normalize_semantic_plan
from .views import render_html_view, render_markdown_view

# Reuse A2-3 validator when available (same package tools/).
import sys

_TOOLS = Path(__file__).resolve().parents[1]
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))
try:
    from validate_semantic_plan import validate_semantic_plan
except ImportError:  # pragma: no cover
    validate_semantic_plan = None  # type: ignore[assignment]


@dataclass
class GenPlanResult:
    ingest: IngestResult
    classification: ClassificationResult
    normalized: NormalizedPlan
    validation: dict[str, Any] | None
    approval: dict[str, Any] | None
    markdown_view: str
    html_view: str
    source_trace_report: dict[str, Any]
    gap_report: dict[str, Any]

    def plan_yaml(self) -> str:
        # YAML dump of normalized plan (block style, stable key order via json roundtrip)
        return yaml.safe_dump(
            self.normalized.plan,
            sort_keys=True,
            allow_unicode=True,
            default_flow_style=False,
        )

    def write_package(self, out_dir: Path | str) -> dict[str, Path]:
        root = Path(out_dir)
        root.mkdir(parents=True, exist_ok=True)
        sources = root / "sources"
        sources.mkdir(exist_ok=True)
        paths: dict[str, Path] = {}

        src_path = sources / f"{self.ingest.source_id}.txt"
        src_path.write_text(self.ingest.text, encoding="utf-8")
        paths["source"] = src_path

        manifest_path = sources / "manifest.json"
        manifest_path.write_text(
            dumps_canonical(self.normalized.plan.get("sources", {}).get("manifest", [])),
            encoding="utf-8",
        )
        paths["manifest"] = manifest_path

        plan_yaml = root / "plan.yaml"
        plan_yaml.write_text(self.plan_yaml(), encoding="utf-8")
        paths["plan_yaml"] = plan_yaml

        plan_norm = root / "plan.normalized.json"
        plan_norm.write_text(self.normalized.normalized_json, encoding="utf-8")
        paths["plan_normalized"] = plan_norm

        plan_md = root / "plan.md"
        plan_md.write_text(self.markdown_view, encoding="utf-8")
        paths["plan_md"] = plan_md

        plan_html = root / "plan.html"
        plan_html.write_text(self.html_view, encoding="utf-8")
        paths["plan_html"] = plan_html

        trace_path = root / "source-trace-report.json"
        trace_path.write_text(
            dumps_canonical(self.source_trace_report), encoding="utf-8"
        )
        paths["source_trace"] = trace_path

        gap_path = root / "gap-report.json"
        gap_path.write_text(dumps_canonical(self.gap_report), encoding="utf-8")
        paths["gap_report"] = gap_path

        if self.approval is not None:
            ap = root / "approval.json"
            ap.write_text(dumps_canonical(self.approval), encoding="utf-8")
            paths["approval"] = ap

        if self.validation is not None:
            vp = root / "validation.json"
            vp.write_text(dumps_canonical(self.validation), encoding="utf-8")
            paths["validation"] = vp

        return paths


def run_genplan(
    text: str | None = None,
    *,
    path: Path | str | None = None,
    mode: IngestMode | None = None,
    source_id: str = "src-input",
    approve: bool = False,
    approver_id: str = "operator",
    out_dir: Path | str | None = None,
) -> GenPlanResult:
    if path is not None:
        ingest = ingest_path(path, source_id=source_id, mode=mode)
    elif text is not None:
        ingest = ingest_text(text, source_id=source_id, mode=mode)
    else:
        raise ValueError("text or path required")

    classification = classify(ingest)
    normalized = normalize_semantic_plan(classification.plan)

    validation = None
    if validate_semantic_plan is not None:
        validation = validate_semantic_plan(normalized.plan)

    approval = None
    if approve:
        approval = approve_plan(normalized, approver_id=approver_id)

    md = render_markdown_view(normalized.plan)
    html = render_html_view(normalized.plan)

    source_trace_report = {
        "schema_version": "autviam.genplan.source-trace/v1",
        "source": ingest.manifest_entry(),
        "traces": classification.source_traces,
        "unclassified_spans": classification.unclassified_spans,
        "coverage": {
            "line_count": len(ingest.lines),
            "traced_object_count": len(
                {t.get("object_id") for t in classification.source_traces}
            ),
            "unclassified_count": len(classification.unclassified_spans),
        },
    }
    gap_report = classification.gap_report()

    result = GenPlanResult(
        ingest=ingest,
        classification=classification,
        normalized=normalized,
        validation=validation,
        approval=approval,
        markdown_view=md,
        html_view=html,
        source_trace_report=source_trace_report,
        gap_report=gap_report,
    )
    if out_dir is not None:
        result.write_package(out_dir)
    return result
