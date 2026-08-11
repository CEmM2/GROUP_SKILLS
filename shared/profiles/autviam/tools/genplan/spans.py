"""Source span tracking — line/column ranges into preserved input."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SourceSpan:
    """1-based inclusive line range into a preserved source document."""

    source_id: str
    start_line: int
    end_line: int
    start_col: int = 1
    end_col: int | None = None
    excerpt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "start_col": self.start_col,
            "end_col": self.end_col,
            "excerpt": self.excerpt,
        }


def content_sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def line_index(text: str) -> list[str]:
    """Split preserving exact line content without stripping."""

    if text == "":
        return []
    # Keep line breaks out of content; last empty line after trailing \n is not a line.
    if text.endswith("\n"):
        return text[:-1].split("\n")
    return text.split("\n")


def span_for_lines(
    source_id: str,
    lines: list[str],
    start_line: int,
    end_line: int,
    *,
    max_excerpt: int = 240,
) -> SourceSpan:
    chunk = "\n".join(lines[start_line - 1 : end_line])
    excerpt = chunk if len(chunk) <= max_excerpt else chunk[: max_excerpt - 1] + "…"
    return SourceSpan(
        source_id=source_id,
        start_line=start_line,
        end_line=end_line,
        excerpt=excerpt,
    )


def slugify(text: str, *, max_len: int = 48) -> str:
    raw = "".join(ch.lower() if ch.isalnum() else "-" for ch in text.strip())
    while "--" in raw:
        raw = raw.replace("--", "-")
    raw = raw.strip("-") or "item"
    return raw[:max_len].rstrip("-")
