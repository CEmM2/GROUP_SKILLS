"""CLI: python -m genplan (from tools/ with PYTHONPATH)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .ingest import IngestMode
from .pipeline import run_genplan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AutViam GenPlan alpha")
    parser.add_argument("input", type=Path, help="Markdown or plain-text plan path")
    parser.add_argument(
        "--mode",
        choices=("auto", "request", "digest"),
        default="auto",
        help="Ingestion mode (default: auto-detect)",
    )
    parser.add_argument("--out", type=Path, required=True, help="Output plan package directory")
    parser.add_argument("--approve", action="store_true", help="Write approval.json")
    parser.add_argument("--approver", default="operator", help="Approver identity")
    parser.add_argument("--source-id", default="src-input", help="Source id")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)

    mode = None if args.mode == "auto" else IngestMode(args.mode)
    result = run_genplan(
        path=args.input,
        mode=mode,
        source_id=args.source_id,
        approve=args.approve,
        approver_id=args.approver,
        out_dir=args.out,
    )
    summary = {
        "mode": result.ingest.mode.value,
        "normalized_hash": result.normalized.normalized_hash,
        "source_manifest_hash": result.normalized.source_manifest_hash,
        "validation_valid": (result.validation or {}).get("valid"),
        "open_decisions": len(result.normalized.plan.get("open_decisions") or []),
        "approval_binding_hash": (result.approval or {}).get("binding_hash"),
        "out": str(args.out),
    }
    if args.json_summary:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(
            f"genplan mode={summary['mode']} normalized_hash={summary['normalized_hash']} "
            f"valid={summary['validation_valid']} out={args.out}"
        )
    if result.validation is not None and not result.validation.get("valid"):
        for err in result.validation.get("errors") or []:
            print(f"  validation: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
