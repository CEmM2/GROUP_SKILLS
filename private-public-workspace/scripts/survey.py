"""Compare a private repository with its public counterpart, read-only.

Every file on the private branch is sorted into one of these groups:

- private by rule: matched by the publishing kit's excludes (``--kit``), or,
  without a kit, absent from the public side;
- identical: the public side has the same content at the same path;
- rewritten on publish: the kit replaces text in it, so it always differs;
- private ahead: the public content is an older version from the private
  branch's own history;
- public version on another private branch: the public content exists in the
  private repository, but not on this branch;
- public ahead: the private content is an older version from the public history;
- diverged: neither side contains the other's version.

It also names the public commit whose tree is closest to the private branch,
which tells whether the private branch is the last publication with nothing
newer, and lists private files under the top-level names the public side owns
(those have to move).

Usage:
    survey.py --private PATH --private-ref REF --public PATH --public-ref REF
              [--name NAME --kit repos.toml] [--history N]

``--public`` may be a normal or bare clone; a ``--filter=blob:none`` clone is
enough, because only object IDs are compared. Prints JSON.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tomllib
from collections import Counter
from pathlib import Path


def git(repo: str, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", repo, *args], check=True, capture_output=True, text=True
    ).stdout


def tree(repo: str, ref: str) -> dict[str, str]:
    """Path -> blob ID for every file at a ref."""
    files = {}
    for entry in git(repo, "ls-tree", "-r", "-z", ref).split("\0"):
        if entry:
            meta, path = entry.split("\t", 1)
            files[path] = meta.split()[2]
    return files


def objects(repo: str, ref: str) -> set[str]:
    """Every object ID reachable from ``ref`` (``--all`` for every ref).

    Blob IDs come from the trees, so no file contents are downloaded.
    """
    out = git(repo, "rev-list", "--objects", ref, "--missing=allow-any")
    return {line.split(" ", 1)[0] for line in out.splitlines()}


def under(path: str, prefixes: list[str]) -> bool:
    return any(path == p or path.startswith(p.rstrip("/") + "/") for p in prefixes)


def by_folder(paths: list[str], depth: int = 2) -> dict[str, int]:
    def top(p: str) -> str:
        parts = p.split("/")
        return "/".join(parts[:depth]) + ("/" if len(parts) > depth else "")

    return dict(Counter(top(p) for p in paths).most_common(15))


def closest_public_commit(
    public: str, public_ref: str, priv: dict[str, str], ignore: set[str], limit: int
) -> dict[str, object]:
    """The public commit whose files differ least from the private copies."""
    best: dict[str, object] = {}
    for line in git(
        public, "rev-list", f"--max-count={limit}", public_ref
    ).splitlines():
        pub = tree(public, line)
        shared = [p for p in pub if p in priv and p not in ignore]
        differing = sum(1 for p in shared if pub[p] != priv[p])
        missing = sum(1 for p in pub if p not in priv)
        score = differing + missing
        if not best or score < best["score"]:  # type: ignore[operator]
            subject = git(
                public, "log", "-1", "--format=%h %ad %s", "--date=short", line
            )
            best = {
                "commit": subject.strip(),
                "score": score,
                "differing": differing,
                "public_files_missing_in_private": missing,
            }
        if score == 0:
            break
    return best


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--private", required=True)
    ap.add_argument("--private-ref", required=True)
    ap.add_argument("--public", required=True)
    ap.add_argument("--public-ref", required=True)
    ap.add_argument("--kit", help="publishing kit repos.toml (optional)")
    ap.add_argument("--name", help="the repository's entry name in the kit")
    ap.add_argument("--history", type=int, default=300, help="public commits to search")
    args = ap.parse_args()

    excludes: list[str] = []
    exceptions: list[str] = []
    rewritten: set[str] = set()
    if args.kit:
        config = tomllib.loads(Path(args.kit).read_text())
        entry = next(r for r in config["repo"] if r["source"] == (args.name or ""))
        excludes = list(
            dict.fromkeys(
                config["defaults"].get("exclude", []) + entry.get("exclude_extra", [])
            )
        )
        exceptions = entry.get("exceptions", [])
        rewritten = {r["file"] for r in entry.get("replacements", [])}

    priv = tree(args.private, args.private_ref)
    pub = tree(args.public, args.public_ref)
    priv_branch = objects(args.private, args.private_ref)
    priv_any = objects(args.private, "--all")
    pub_history = objects(args.public, "--all")

    groups: dict[str, list[str]] = {
        "rewritten_on_publish": [],
        "private_ahead": [],
        "public_version_on_another_private_branch": [],
        "public_ahead": [],
        "diverged": [],
    }
    private_by_rule: list[str] = []
    private_rule_but_public: list[str] = []
    not_published: list[str] = []
    identical = 0
    for path, blob in priv.items():
        if excludes and under(path, excludes) and not under(path, exceptions):
            private_by_rule.append(path)
            if path in pub:
                private_rule_but_public.append(path)
            continue
        if path not in pub:
            (not_published if excludes else private_by_rule).append(path)
        elif pub[path] == blob:
            identical += 1
        elif path in rewritten:
            groups["rewritten_on_publish"].append(path)
        elif pub[path] in priv_branch:
            groups["private_ahead"].append(path)
        elif pub[path] in priv_any:
            groups["public_version_on_another_private_branch"].append(path)
        elif blob in pub_history:
            groups["public_ahead"].append(path)
        else:
            groups["diverged"].append(path)

    public_only = sorted(p for p in pub if p not in priv)
    public_top = {p.split("/", 1)[0] for p in pub}
    to_move = sorted(
        p for p in priv if p not in pub and p.split("/", 1)[0] in public_top
    )

    report = {
        "private": f"{args.private_ref} {git(args.private, 'rev-parse', '--short', args.private_ref).strip()}",
        "public": f"{args.public_ref} {git(args.public, 'rev-parse', '--short', args.public_ref).strip()}",
        "private_tracked": len(priv),
        "public_tracked": len(pub),
        "private_by_rule": len(private_by_rule),
        "private_by_rule_by_folder": by_folder(private_by_rule, 1),
        "private_by_rule_yet_on_public": private_rule_but_public[:20],
        "identical": identical,
        "differing": {k: len(v) for k, v in groups.items()},
        "differing_samples": {k: v[:12] for k, v in groups.items() if v},
        "not_excluded_but_missing_from_public": len(not_published),
        "not_excluded_but_missing_from_public_by_folder": by_folder(not_published),
        "public_only": len(public_only),
        "public_only_content_found_in_private_history": sum(
            1 for p in public_only if pub[p] in priv_any
        ),
        "public_only_by_folder": by_folder(public_only),
        "private_files_under_public_top_level_names": len(to_move),
        "private_files_under_public_top_level_names_by_folder": by_folder(to_move, 4),
        "closest_public_commit": closest_public_commit(
            args.public, args.public_ref, priv, rewritten, args.history
        ),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
