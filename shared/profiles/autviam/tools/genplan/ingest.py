"""Preserve rough inputs and emit a source manifest + line-indexed body."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .spans import content_sha256, line_index


class IngestMode(str, Enum):
    REQUEST = "request"
    DIGEST = "digest"


@dataclass
class IngestResult:
    mode: IngestMode
    source_id: str
    media_type: str
    text: str
    lines: list[str]
    content_hash: str
    path: str | None = None
    title_hint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def manifest_entry(self) -> dict[str, Any]:
        return {
            "id": self.source_id,
            "media_type": self.media_type,
            "content_hash": self.content_hash,
            "path": self.path,
            "line_count": len(self.lines),
            "byte_length": len(self.text.encode("utf-8")),
            "mode": self.mode.value,
            "title_hint": self.title_hint,
            "authority": "user-asserted",
        }


def _detect_mode(text: str, explicit: IngestMode | None) -> IngestMode:
    if explicit is not None:
        return explicit
    # Heuristic: structured markdown → digest; short plain request → request.
    if re.search(r"(?m)^#{1,6}\s+\S", text) or "```" in text:
        return IngestMode.DIGEST
    if len(text.strip().splitlines()) <= 8 and not re.search(r"(?m)^[-*+]\s+", text):
        return IngestMode.REQUEST
    return IngestMode.DIGEST


def _title_hint(text: str, mode: IngestMode) -> str:
    for line in text.splitlines():
        m = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if m:
            return m.group(1).strip()
    first = text.strip().splitlines()[0].strip() if text.strip() else "untitled"
    if mode is IngestMode.REQUEST:
        return first[:80]
    return first.lstrip("#").strip()[:80] or "untitled"


def ingest_text(
    text: str,
    *,
    source_id: str = "src-input",
    path: str | None = None,
    media_type: str | None = None,
    mode: IngestMode | None = None,
) -> IngestResult:
    # Preserve exact text — do not "fix" newlines or normalize Unicode here.
    resolved_mode = _detect_mode(text, mode)
    if media_type is None:
        if path and path.endswith((".md", ".markdown")):
            media_type = "text/markdown"
        elif resolved_mode is IngestMode.REQUEST:
            media_type = "text/plain"
        else:
            media_type = "text/markdown" if "#" in text or "```" in text else "text/plain"
    return IngestResult(
        mode=resolved_mode,
        source_id=source_id,
        media_type=media_type,
        text=text,
        lines=line_index(text),
        content_hash=content_sha256(text),
        path=path,
        title_hint=_title_hint(text, resolved_mode),
    )


def ingest_path(
    path: Path | str,
    *,
    source_id: str | None = None,
    mode: IngestMode | None = None,
) -> IngestResult:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    sid = source_id or f"src-{p.stem}".replace("_", "-").lower()
    # Ensure src- prefix pattern friendliness
    if not sid.startswith("src-"):
        sid = f"src-{sid}"
    return ingest_text(text, source_id=sid, path=str(p), mode=mode)
