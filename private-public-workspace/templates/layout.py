"""Where the files of the former single repository live now.

Copy to ``private_tests/_layout.py`` and fill in ``MOVED``. Private tests
written when public and private files shared one checkout name files by their
path in it; ``repo_path`` maps such a path to its present home: the public
repository under ``public/``, moved private files to their new place,
everything else at the workspace root.
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_ROOT = WORKSPACE_ROOT / "public"

# Old path -> new path, both relative to the root of the old single checkout.
# One entry per row of the move table; longer prefixes first.
MOVED: tuple[tuple[str, str], ...] = (
    # ("packages/core/tests/plan_tests", "private_tests/core/plan_tests"),
)


def _public_top() -> frozenset[str]:
    """Top-level names the public repository owns, read from the checkout."""
    if not PUBLIC_ROOT.is_dir():
        return frozenset()
    return frozenset(p.name for p in PUBLIC_ROOT.iterdir() if p.name != ".git")


_PUBLIC_TOP = _public_top()


def repo_path(relative: str | os.PathLike[str]) -> Path:
    """Return the present location of a path given relative to the old repository root."""
    rel = PurePosixPath(Path(relative).as_posix()).as_posix()
    for old, new in MOVED:
        if rel == old or rel.startswith(old + "/"):
            return WORKSPACE_ROOT / (new + rel[len(old) :])
    if rel.split("/", 1)[0] in _PUBLIC_TOP:
        return PUBLIC_ROOT / rel
    return WORKSPACE_ROOT / rel
