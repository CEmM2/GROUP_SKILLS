"""Rewrite how moved private tests find "the repository root".

Tests written for the single checkout locate the root in two ways:

1. a helper such as ``_repo_root()`` that walks up until a folder holds both
   ``pyproject.toml`` and ``dev/`` (or ``packages/``);
2. ``Path(__file__).resolve().parents[N]``, counted from the test's old place.

Neither folder exists after the split. This script makes the helper return the
workspace root and sends every path built on either form through
``repo_path`` from ``private_tests/_layout.py`` (see ``templates/layout.py``).

Usage:
    rewrite_root_lookups.py PRIVATE_TESTS_DIR --old-home GROUP=OLD_DIR [...]

``--old-home core=packages/core/tests`` says that files now under
``private_tests/core/`` used to live under ``packages/core/tests/``; it is
needed to work out what ``parents[N]`` meant.

This is a starting point, not a proof: it edits only the patterns above, and a
path assembled some other way stays as it was. Afterwards check every file
still parses, read the diff, and run the tests. Expect a few files to need a
hand edit (a test that asserts its own location, lists files by path, or runs
pytest in a subprocess).
"""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path, PurePosixPath

FINDER = re.compile(
    r"^def (_repo_root|_find_repo_root|_root|repo_root)\(\) -> Path:\n(?:(?:[ \t]+.*)?\n)+?(?=\S)",
    re.M,
)
HERE = r"(?:pathlib\.)?Path\(__file__\)(?:\.resolve\(\))?\.parents\[(\d+)\]"
CHAIN = r'((?:\s*/\s*"[^"\n]+")+)'
SEG = re.compile(r'"([^"\n]+)"')
IMPORT = re.compile(r"^(?:import|from) [^\n(]*(?:\([^)]*\))?[^\n]*$", re.M)


def joined(base: str, chain: str) -> str:
    return "/".join(([base] if base else []) + SEG.findall(chain))


def call(rel: str) -> str:
    return f'repo_path("{rel}")' if rel else "WORKSPACE_ROOT"


def rewrite_finder(text: str) -> str:
    match = FINDER.search(text)
    if match is None:
        return text
    name = match[1]
    body = (
        f"def {name}() -> Path:\n"
        '    """The workspace root. Public files are under ``public/``; see ``repo_path``."""\n'
        "    return WORKSPACE_ROOT\n\n\n"
    )
    new = text[: match.start()] + body + text[match.end() :]
    new = re.sub(rf"{name}\(\){CHAIN}", lambda m: call(joined("", m[1])), new)
    new = re.sub(rf"{name}\(\)\s*/\s*([A-Za-z_]\w*)", r"repo_path(\1)", new)
    if re.search(rf"^\s+root = {name}\(\)$", new, re.M):
        new = re.sub(rf"\broot{CHAIN}", lambda m: call(joined("", m[1])), new)
        new = re.sub(r"\broot\s*/\s*([A-Za-z_]\w*)", r"repo_path(\1)", new)
        new = re.sub(
            r"\broot\.joinpath\(\*([A-Za-z_]\w*)\)", r"repo_path(Path(*\1))", new
        )
    return new


def rewrite_parents(text: str, old_file: PurePosixPath) -> str:
    def old_dir(n: int) -> str:
        folder = old_file.parents[n].as_posix()
        return "" if folder == "." else folder

    variables = {
        m[2]: old_dir(int(m[3]))
        for m in re.finditer(
            rf"^(\s*)([A-Za-z_]\w*) = {HERE}[ \t]*(?:#.*)?$", text, re.M
        )
    }
    new = re.sub(
        rf"{HERE}{CHAIN}", lambda m: call(joined(old_dir(int(m[1])), m[2])), text
    )
    new = re.sub(HERE, lambda m: call(old_dir(int(m[1]))), new)
    for name, base in variables.items():
        guard = rf"(?<![\w.]){re.escape(name)}"
        prefix = f"{base}/" if base else ""
        new = re.sub(rf"{guard}{CHAIN}", lambda m, b=base: call(joined(b, m[1])), new)
        new = re.sub(
            rf'{guard}\s*/\s*f"([^"\n]+)"',
            lambda m, p=prefix: f'repo_path(f"{p}{m[1]}")',
            new,
        )
        if base:
            new = re.sub(
                rf"{guard}\s*/\s*([A-Za-z_]\w*)",
                lambda m, b=base: f'repo_path(Path("{b}") / {m[1]})',
                new,
            )
        else:
            new = re.sub(rf"{guard}\s*/\s*([A-Za-z_]\w*)", r"repo_path(\1)", new)
    return new


def add_import(text: str) -> str:
    # Count uses, not mentions: the rewritten helper's docstring names repo_path.
    needs = [
        name
        for name, use in (
            ("WORKSPACE_ROOT", r"\bWORKSPACE_ROOT\b"),
            ("repo_path", r"\brepo_path\("),
        )
        if re.search(use, text)
    ]
    if not needs or "from _layout import" in text:
        return text
    imports = list(IMPORT.finditer(text))
    at = imports[-1].end() if imports else 0
    return text[:at] + f"\nfrom _layout import {', '.join(needs)}" + text[at:]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("tests_dir", type=Path)
    ap.add_argument("--old-home", action="append", default=[], metavar="GROUP=OLD_DIR")
    args = ap.parse_args()
    homes = dict(item.split("=", 1) for item in args.old_home)

    changed, broken = [], []
    for path in sorted(args.tests_dir.rglob("*.py")):
        rel = path.relative_to(args.tests_dir)
        if rel.parts[0] not in homes:
            continue  # helpers at the top level are not moved tests
        text = path.read_text(encoding="utf-8")
        new = rewrite_finder(text)
        if re.search(HERE, new):
            new = rewrite_parents(
                new, PurePosixPath(homes[rel.parts[0]], *rel.parts[1:])
            )
        new = add_import(new)
        if new == text:
            continue
        path.write_text(new, encoding="utf-8")
        changed.append(str(rel))
        try:
            ast.parse(new)
        except SyntaxError as exc:
            broken.append(f"{rel}: {exc}")

    print(f"{len(changed)} files rewritten")
    for item in broken:
        print("DOES NOT PARSE:", item)


if __name__ == "__main__":
    main()
