#!/usr/bin/env python3
"""Deterministic plumbing for Documentron.

The script deliberately owns repository discovery, scope resolution, claim extraction,
cache invalidation, specialist matching, patch application, validation, and report
rendering.  It never calls an LLM.  Its JSON packets are the bounded hand-off to the
semantic reviewer described by the skill.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import html
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "1"
TEXT_SUFFIXES = {
    ".c", ".cc", ".cpp", ".cu", ".cuh", ".f", ".f90", ".go", ".h", ".hpp",
    ".java", ".jl", ".json", ".md", ".m", ".py", ".rst", ".rs", ".sh",
    ".tex", ".toml", ".ts", ".tsx", ".yaml", ".yml",
}
DOC_SUFFIXES = {".md", ".rst", ".tex"}
EXCLUDED_PARTS = {".git", ".venv", "node_modules", "site", "__pycache__"}
VERDICTS = {"confirmed", "corrected", "contradicted", "uncertain", "unsupported"}
SCIENTIFIC_CLAIM_TYPES = {
    "algorithmic", "equation", "ml", "numerical", "physical-assumption",
    "scientific", "statistical", "validation",
}
INDEPENDENT_REVIEW_TYPES = {"equation", "physical-assumption", "safety", "security"}


CONFIG_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "documentron-config.json"
DEFAULT_CONFIG: dict[str, Any] = json.loads(CONFIG_TEMPLATE.read_text(encoding="utf-8"))


def canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def find_repo_root(start: Path) -> Path:
    start = start.resolve()
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return start


def relpath(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def safe_repo_path(root: Path, raw: str) -> Path:
    candidate = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes repository: {raw}") from exc
    return candidate


def git(root: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def tracked_files(root: Path) -> list[str]:
    result = git(root, ["ls-files", "-z"], check=False)
    if result.returncode == 0:
        return sorted(item for item in result.stdout.split("\0") if item)
    files: list[str] = []
    for path in root.rglob("*"):
        if path.is_file() and not EXCLUDED_PARTS.intersection(path.relative_to(root).parts):
            files.append(relpath(path, root))
    return sorted(files)


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = json.loads(json.dumps(base))
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(root: Path) -> dict[str, Any]:
    config_path = root / ".documentron" / "config.json"
    configured = read_json(config_path, {})
    if not isinstance(configured, dict):
        raise ValueError(f"{config_path} must contain a JSON object")
    config = deep_merge(DEFAULT_CONFIG, configured)
    if str(config.get("schema_version")) != SCHEMA_VERSION:
        raise ValueError(f"unsupported Documentron schema_version: {config.get('schema_version')!r}")
    return config


def matches_any(path: str, patterns: Iterable[str]) -> bool:
    normalized = path.replace(os.sep, "/")
    return any(fnmatch.fnmatchcase(normalized, pattern) for pattern in patterns)


def is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES


def resolve_scope(root: Path, args: argparse.Namespace) -> list[str]:
    scope: set[str] = set()
    if getattr(args, "base", None) and getattr(args, "head", None):
        result = git(root, ["diff", "--name-only", "-z", args.base, args.head])
        scope.update(item for item in result.stdout.split("\0") if item)
    for raw in getattr(args, "paths", None) or []:
        path = safe_repo_path(root, raw)
        if path.is_dir():
            scope.update(relpath(p, root) for p in path.rglob("*") if p.is_file())
        elif path.exists():
            scope.add(relpath(path, root))
        else:
            # Deleted paths remain meaningful when supplied by git or the caller.
            scope.add(Path(raw).as_posix())
    paths_file = getattr(args, "paths_file", None)
    if paths_file:
        for raw in Path(paths_file).read_text(encoding="utf-8").splitlines():
            if raw.strip():
                scope.add(Path(raw.strip()).as_posix())
    plan = getattr(args, "plan", None)
    if plan:
        plan_path = safe_repo_path(root, plan)
        text = plan_path.read_text(encoding="utf-8")
        scope.add(relpath(plan_path, root))
        candidates = re.findall(r"`([^`\n]+)`", text)
        for candidate in candidates:
            candidate = candidate.split(":", 1)[0].strip()
            if candidate and (root / candidate).exists():
                path = safe_repo_path(root, candidate)
                if path.is_file():
                    scope.add(relpath(path, root))
    return sorted(scope)


def configured_doc_paths(root: Path, config: dict[str, Any]) -> list[str]:
    docs: set[str] = set()
    for raw in config["documentation"]["roots"]:
        path = safe_repo_path(root, raw)
        if path.is_file() and path.suffix.lower() in DOC_SUFFIXES:
            docs.add(relpath(path, root))
        elif path.is_dir():
            docs.update(relpath(p, root) for p in path.rglob("*") if p.suffix.lower() in DOC_SUFFIXES)
    return sorted(docs)


def affected_docs(root: Path, config: dict[str, Any], scope: list[str]) -> list[str]:
    direct = {path for path in scope if Path(path).suffix.lower() in DOC_SUFFIXES and (root / path).exists()}
    for mapping in config.get("mappings", []):
        if any(matches_any(path, mapping.get("source_globs", [])) for path in scope):
            for doc in configured_doc_paths(root, config):
                if matches_any(doc, mapping.get("documentation_globs", [])):
                    direct.add(doc)
    scientific = config["scientific_review"]
    if any(matches_any(path, scientific.get("source_globs", [])) for path in scope):
        for doc in configured_doc_paths(root, config):
            if matches_any(doc, scientific.get("documentation_globs", [])):
                direct.add(doc)
    return sorted(direct)


def paragraph_blocks(text: str) -> Iterable[tuple[int, int, str]]:
    lines = text.splitlines()
    start: int | None = None
    buf: list[str] = []
    in_fence = False
    for index, line in enumerate(lines, 1):
        if line.lstrip().startswith("```"):
            if start is not None:
                yield start, index - 1, "\n".join(buf).strip()
                start, buf = None, []
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not line.strip():
            if start is not None:
                yield start, index - 1, "\n".join(buf).strip()
                start, buf = None, []
            continue
        if start is None:
            start = index
        buf.append(line)
    if start is not None:
        yield start, len(lines), "\n".join(buf).strip()


CLAIM_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("equation", re.compile(r"\$\$|\\\[|\\begin\{(?:equation|align)|\\frac|\\nabla|\\sigma|\\epsilon")),
    ("physical-assumption", re.compile(r"\b(?:assum(?:e|ption)|boundary condition|initial condition|constitutive|isotropic|anisotropic|objective|frame|units?)\b", re.I)),
    ("numerical", re.compile(r"\b(?:convergen|stabil|discret|tolerance|residual|time[- ]step|CFL|finite element|finite difference|spectral|quadrature|solver)\w*\b", re.I)),
    ("statistical", re.compile(r"\b(?:p[- ]?value|confidence interval|estimator|variance|bias|distribution|hypothesis|regression|likelihood|posterior|sample size)\b", re.I)),
    ("ml", re.compile(r"\b(?:loss function|gradient|training|inference|normalization|metric|checkpoint|seed|determin|neural network|model)\b", re.I)),
    ("validation", re.compile(r"\b(?:benchmark|validation|verified|accuracy|error norm|relative error|absolute error|rtol|atol)\b", re.I)),
    ("security", re.compile(r"\b(?:security|authentication|authorization|secret|credential|encryption|permission)\b", re.I)),
    ("safety", re.compile(r"\b(?:safety|interlock|watchdog|emergency stop|hazard|safe shutdown)\b", re.I)),
    ("algorithmic", re.compile(r"\b(?:algorithm|complexity|iteration|update rule|objective function|optimizer|integration scheme)\b", re.I)),
    ("quantitative", re.compile(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?%?", re.I)),
    ("naming", re.compile(r"`[A-Za-z_][A-Za-z0-9_./:-]*`")),
    ("behavioral", re.compile(r"\b(?:returns?|produces?|writes?|reads?|loads?|saves?|supports?|requires?|computes?|updates?|converts?)\b", re.I)),
]


def extract_claims(root: Path, docs: list[str], evidence_hash: str) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for doc in docs:
        path = root / doc
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        normalized_occurrences: dict[str, int] = {}
        for start, end, block in paragraph_blocks(text):
            types = sorted({kind for kind, pattern in CLAIM_PATTERNS if pattern.search(block)})
            if not types:
                continue
            normalized = " ".join(block.split())
            occurrence = normalized_occurrences.get(normalized, 0)
            normalized_occurrences[normalized] = occurrence + 1
            claim_key = f"{doc}\0{normalized}"
            if occurrence:
                claim_key = f"{claim_key}\0{occurrence}"
            claim_id = sha256_text(claim_key)
            claims.append({
                "claim_id": claim_id,
                "document": doc,
                "start_line": start,
                "end_line": end,
                "paragraph_hash": sha256_text(block),
                "evidence_hash": evidence_hash,
                "claim_types": types,
                "semantic_required": bool(set(types) - {"naming", "quantitative"}),
                "scientific_review_required": bool(set(types) & SCIENTIFIC_CLAIM_TYPES),
                "text": block,
            })
    return claims


def scope_hash(root: Path, scope: list[str]) -> str:
    digest = hashlib.sha256()
    for raw in scope:
        digest.update(raw.encode("utf-8") + b"\0")
        path = root / raw
        if path.is_file():
            digest.update(path.read_bytes())
        else:
            digest.update(b"<missing>")
        digest.update(b"\0")
    return digest.hexdigest()


def load_ledger(root: Path) -> dict[str, dict[str, Any]]:
    ledger_path = root / ".documentron" / "claims.jsonl"
    result: dict[str, dict[str, Any]] = {}
    if not ledger_path.exists():
        return result
    for line_number, line in enumerate(ledger_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        item = json.loads(line)
        if not isinstance(item, dict) or "claim_id" not in item:
            raise ValueError(f"invalid claim ledger row {line_number}")
        result[item["claim_id"]] = item
    return result


def invalidated_claims(claims: list[dict[str, Any]], ledger: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    invalidated = []
    for claim in claims:
        prior = ledger.get(claim["claim_id"])
        if not prior or prior.get("paragraph_hash") != claim["paragraph_hash"] or prior.get("evidence_hash") != claim["evidence_hash"]:
            invalidated.append(claim)
    return invalidated


def specialist_matches(
    specialist: dict[str, Any], command: str, scope: list[str], claims: list[dict[str, Any]]
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    commands = specialist.get("commands", [])
    if commands and command not in commands and "*" not in commands:
        return False, []
    source_globs = specialist.get("source_globs", [])
    doc_globs = specialist.get("documentation_globs", [])
    claim_types = set(specialist.get("claim_types", []))
    if source_globs and any(matches_any(path, source_globs) for path in scope):
        reasons.append("source_glob")
    if doc_globs and any(matches_any(path, doc_globs) for path in scope):
        reasons.append("documentation_glob")
    present_types = {kind for claim in claims for kind in claim.get("claim_types", [])}
    if claim_types and claim_types & present_types:
        reasons.append("claim_type")
    has_triggers = bool(source_globs or doc_globs or claim_types)
    return (bool(reasons) if has_triggers else True), reasons or (["command"] if not has_triggers else [])


def matched_specialists(
    config: dict[str, Any], command: str, scope: list[str], claims: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    matched = []
    for specialist in config.get("specialists", []):
        ok, reasons = specialist_matches(specialist, command, scope, claims)
        if ok:
            item = dict(specialist)
            item["match_reasons"] = reasons
            matched.append(item)
    return sorted(matched, key=lambda item: item.get("name", ""))


def llm_policy(
    config: dict[str, Any], scope: list[str], claims: list[dict[str, Any]], affected: list[str],
    *, all_claims_present: bool,
) -> dict[str, Any]:
    policy = config["llm_policy"]
    scientific = config["scientific_review"]
    claim_types = {kind for claim in claims for kind in claim["claim_types"]}
    scientific_source_in_scope = any(matches_any(path, scientific.get("source_globs", [])) for path in scope)
    scientific_source_changed = scientific_source_in_scope and (bool(claims) or not all_claims_present)
    scientific_claim = bool(claim_types & set(scientific.get("claim_types", [])))
    semantic_claim = any(claim["semantic_required"] for claim in claims)
    documentation_gap = scientific_source_changed and not affected
    reviews = 0
    reasons: list[str] = []
    if semantic_claim:
        reviews = max(reviews, int(policy.get("ordinary_semantic_reviews", 1)))
        reasons.append("invalidated_semantic_claim")
    if scientific.get("required", True) and (scientific_claim or scientific_source_changed):
        reviews = max(reviews, int(policy.get("scientific_minimum_reviews", 1)))
        reasons.append("scientific_semantics")
    independent = set(policy.get("independent_review_for", [])) & claim_types
    if independent:
        reviews = max(reviews, 2)
        reasons.append("independent_review:" + ",".join(sorted(independent)))
    reviews = min(reviews, int(policy.get("maximum_reviews", 2)))
    return {
        "required_reviews": reviews,
        "reasons": reasons,
        "documentation_gap_review": documentation_gap,
        "deterministic_only": reviews == 0,
    }


def evidence_excerpt(root: Path, raw: str, limit: int) -> dict[str, Any]:
    path = root / raw
    item: dict[str, Any] = {"path": raw, "exists": path.exists()}
    if not path.is_file():
        return item
    data = path.read_bytes()
    item["sha256"] = sha256_bytes(data)
    item["size"] = len(data)
    if is_text_file(path):
        decoded = data.decode("utf-8", errors="replace")
        item["excerpt"] = decoded[:limit]
        item["excerpt_truncated"] = len(decoded) > limit
    return item


def build_packet(root: Path, args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    config = load_config(root)
    scope = resolve_scope(root, args)
    affected = affected_docs(root, config, scope)
    evidence_fingerprint = scope_hash(root, scope)
    claims = extract_claims(root, affected, evidence_fingerprint)
    ledger = load_ledger(root)
    invalidated = invalidated_claims(claims, ledger)
    specialists = matched_specialists(config, args.command, scope, invalidated)
    policy = llm_policy(config, scope, invalidated, affected, all_claims_present=bool(claims))
    max_bytes = int(config["llm_policy"].get("packet_max_bytes", 120000))
    per_file = max(1000, min(12000, max_bytes // max(1, len(scope))))
    evidence = [evidence_excerpt(root, path, per_file) for path in scope]
    packet: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "command": args.command,
        "scope": scope,
        "scope_hash": evidence_fingerprint,
        "affected_documents": affected,
        "invalidated_claims": invalidated,
        "reused_claim_count": len(claims) - len(invalidated),
        "specialists": specialists,
        "llm_policy": policy,
        "evidence": evidence,
    }
    encoded = canonical_json(packet).encode("utf-8")
    if len(encoded) > max_bytes:
        for item in packet["evidence"]:
            item.pop("excerpt", None)
            item["excerpt_omitted_for_packet_limit"] = True
        packet["packet_limit_warning"] = {
            "limit_bytes": max_bytes,
            "action": "Read only the cited paths needed for invalidated claims.",
        }
        encoded = canonical_json(packet).encode("utf-8")
    packet["packet_bytes"] = len(encoded)
    run_seed = canonical_json({
        "command": args.command,
        "scope_hash": evidence_fingerprint,
        "claims": [claim["claim_id"] for claim in invalidated],
        "specialists": [item.get("name") for item in specialists],
    })
    run_id = sha256_text(run_seed)[:16]
    output = safe_repo_path(root, args.output) if getattr(args, "output", None) else root / ".documentron" / "runs" / run_id / "packet.json"
    atomic_write(output, canonical_json(packet))
    return output, packet


def validate_semantic_result(packet: dict[str, Any], result: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(result, dict):
        return ["result must be a JSON object"]
    reviews = result.get("reviews")
    if not isinstance(reviews, list):
        errors.append("reviews must be an array")
        reviews = []
    required = int(packet.get("llm_policy", {}).get("required_reviews", 0))
    if len(reviews) < required:
        errors.append(f"requires at least {required} review(s), received {len(reviews)}")
    reviewer_names: list[str] = []
    covered_by_review: list[set[str]] = []
    applied_lenses: set[str] = set()
    for index, review in enumerate(reviews):
        if not isinstance(review, dict):
            errors.append(f"reviews[{index}] must be an object")
            continue
        reviewer = review.get("reviewer")
        if not isinstance(reviewer, str) or not reviewer.strip():
            errors.append(f"reviews[{index}].reviewer must be a non-empty string")
        else:
            reviewer_names.append(reviewer)
        if review.get("verdict") not in VERDICTS:
            errors.append(f"reviews[{index}].verdict must be one of {sorted(VERDICTS)}")
        evidence_used = review.get("evidence_used", [])
        if not isinstance(evidence_used, list):
            errors.append(f"reviews[{index}].evidence_used must be an array")
        elif required and not evidence_used:
            errors.append(f"reviews[{index}].evidence_used must not be empty")
        lenses = review.get("lenses_applied", [])
        if not isinstance(lenses, list) or not all(isinstance(item, str) for item in lenses):
            errors.append(f"reviews[{index}].lenses_applied must be an array of strings")
        else:
            applied_lenses.update(lenses)
        claim_results = review.get("claim_results", [])
        covered: set[str] = set()
        if not isinstance(claim_results, list):
            errors.append(f"reviews[{index}].claim_results must be an array")
        else:
            for result_index, claim_result in enumerate(claim_results):
                if not isinstance(claim_result, dict):
                    errors.append(f"reviews[{index}].claim_results[{result_index}] must be an object")
                    continue
                claim_id = claim_result.get("claim_id")
                if not isinstance(claim_id, str) or not claim_id:
                    errors.append(f"reviews[{index}].claim_results[{result_index}] missing claim_id")
                else:
                    covered.add(claim_id)
                if claim_result.get("verdict") not in VERDICTS:
                    errors.append(
                        f"reviews[{index}].claim_results[{result_index}].verdict must be one of {sorted(VERDICTS)}"
                    )
        covered_by_review.append(covered)
    if required > 1 and len(set(reviewer_names)) < required:
        errors.append("independent reviews require distinct reviewer names")
    expected_claims = {claim["claim_id"] for claim in packet.get("invalidated_claims", [])}
    for index, covered in enumerate(covered_by_review[:required]):
        missing = expected_claims - covered
        if missing:
            errors.append(f"reviews[{index}] does not cover {len(missing)} invalidated claim(s)")
    required_lenses = {item.get("name") for item in packet.get("specialists", []) if item.get("name")}
    missing_lenses = required_lenses - applied_lenses
    if missing_lenses:
        errors.append("matched specialist lenses not applied: " + ", ".join(sorted(missing_lenses)))
    patches = result.get("patches", [])
    if not isinstance(patches, list):
        errors.append("patches must be an array")
    else:
        for index, patch in enumerate(patches):
            if not isinstance(patch, dict):
                errors.append(f"patches[{index}] must be an object")
                continue
            for field in ("path", "old_text", "old_text_sha256", "new_text"):
                if field not in patch:
                    errors.append(f"patches[{index}] missing {field}")
        if patches and not reviews:
            errors.append("semantic patches require at least one review")
    return errors


def apply_patches(root: Path, patches: list[dict[str, Any]], *, dry_run: bool) -> list[str]:
    updated: dict[Path, str] = {}
    changed: list[str] = []
    for index, patch in enumerate(patches):
        path = safe_repo_path(root, str(patch["path"]))
        if path.suffix.lower() not in DOC_SUFFIXES and path.name != "README.md":
            raise ValueError(f"patch {index} targets non-documentation file: {patch['path']}")
        content = updated.get(path, path.read_text(encoding="utf-8"))
        old_text = str(patch["old_text"])
        if sha256_text(old_text) != patch["old_text_sha256"]:
            raise ValueError(f"patch {index} old_text hash mismatch")
        occurrences = content.count(old_text)
        if occurrences != 1:
            raise ValueError(f"patch {index} precondition expected one match, found {occurrences}")
        updated[path] = content.replace(old_text, str(patch["new_text"]), 1)
    for path, content in updated.items():
        changed.append(relpath(path, root))
        if not dry_run:
            atomic_write(path, content)
    return sorted(changed)


def record_result(root: Path, packet: dict[str, Any], result: dict[str, Any]) -> None:
    ledger = load_ledger(root)
    per_claim: dict[str, list[str]] = {}
    for review in result.get("reviews", []):
        for claim_result in review.get("claim_results", []):
            per_claim.setdefault(claim_result["claim_id"], []).append(claim_result["verdict"])
    for claim in packet.get("invalidated_claims", []):
        verdicts = per_claim.get(claim["claim_id"], [])
        verdict = "confirmed" if verdicts and all(item == "confirmed" for item in verdicts) else (verdicts[-1] if verdicts else "uncertain")
        ledger[claim["claim_id"]] = {
            "claim_id": claim["claim_id"],
            "document": claim["document"],
            "start_line": claim["start_line"],
            "end_line": claim["end_line"],
            "paragraph_hash": claim["paragraph_hash"],
            "evidence_hash": claim["evidence_hash"],
            "claim_types": claim["claim_types"],
            "verdict": verdict,
            "scope_hash": packet.get("scope_hash"),
        }
    rows = "".join(canonical_json(ledger[key]).replace("\n", "") + "\n" for key in sorted(ledger))
    atomic_write(root / ".documentron" / "claims.jsonl", rows)


def markdown_links(root: Path, docs: list[str]) -> list[dict[str, Any]]:
    broken: list[dict[str, Any]] = []
    pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for raw in docs:
        path = root / raw
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), 1):
            for match in pattern.finditer(line):
                target = match.group(1).split("#", 1)[0].strip()
                if not target or target.startswith(("http://", "https://", "mailto:")):
                    continue
                if target.startswith("/"):
                    resolved = (root / target.lstrip("/")).resolve()
                else:
                    resolved = (path.parent / target).resolve()
                try:
                    resolved.relative_to(root)
                except ValueError:
                    broken.append({"path": raw, "line": line_number, "target": target, "reason": "outside_repo"})
                    continue
                if not resolved.exists():
                    broken.append({"path": raw, "line": line_number, "target": target, "reason": "missing"})
    return broken


def doctor(root: Path, *, run_commands: bool) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    try:
        config = load_config(root)
    except (ValueError, json.JSONDecodeError) as exc:
        return {"status": "failed", "errors": [{"check": "config", "message": str(exc)}], "warnings": []}
    names: set[str] = set()
    for specialist in config.get("specialists", []):
        name = specialist.get("name")
        if not name:
            errors.append({"check": "specialist", "message": "specialist missing name"})
        elif name in names:
            errors.append({"check": "specialist", "message": f"duplicate specialist: {name}"})
        names.add(name)
        prompt_file = specialist.get("prompt_file")
        if prompt_file and not safe_repo_path(root, prompt_file).exists():
            errors.append({"check": "specialist", "message": f"missing prompt_file: {prompt_file}"})
    docs = configured_doc_paths(root, config)
    errors.extend({"check": "link", **item} for item in markdown_links(root, docs))
    command_results = []
    for command in config.get("validation", {}).get("allowlisted_commands", []):
        argv = shlex.split(command)
        available = bool(argv and shutil.which(argv[0]))
        item: dict[str, Any] = {"command": command, "available": available, "ran": False}
        if not available:
            warnings.append({"check": "validation_command", "message": f"unavailable: {command}"})
        elif run_commands:
            completed = subprocess.run(argv, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            item.update({"ran": True, "returncode": completed.returncode, "output": completed.stdout[-8000:]})
            if completed.returncode:
                errors.append({"check": "validation_command", "message": f"failed: {command}"})
        command_results.append(item)
    return {
        "status": "failed" if errors else "passed",
        "errors": errors,
        "warnings": warnings,
        "documents_checked": len(docs),
        "validation_commands": command_results,
    }


def render_report(data: dict[str, Any], title: str) -> tuple[str, str]:
    status = str(data.get("status", data.get("outcome", "unknown")))
    markdown = [f"# {title}", "", f"Status: `{status}`", ""]
    for key in sorted(data):
        if key in {"status", "outcome"}:
            continue
        markdown.extend([f"## {key.replace('_', ' ').title()}", "", "```json", json.dumps(data[key], indent=2, sort_keys=True, ensure_ascii=False), "```", ""])
    md = "\n".join(markdown).rstrip() + "\n"
    body = html.escape(md)
    page = (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<title>{html.escape(title)}</title><style>"
        "body{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;"
        "color:#18202a;background:#f7f8fa}pre{white-space:pre-wrap;background:white;border:1px solid #d8dee8;"
        "border-radius:8px;padding:1.25rem;line-height:1.45}</style></head>"
        f"<body><h1>{html.escape(title)}</h1><pre>{body}</pre></body></html>\n"
    )
    return md, page


def discover_specialists(root: Path) -> list[dict[str, Any]]:
    manifests = []
    for path in root.rglob("documentron-specialist.json"):
        if EXCLUDED_PARTS.intersection(path.relative_to(root).parts):
            continue
        item = read_json(path)
        if not isinstance(item, dict) or not item.get("name"):
            raise ValueError(f"invalid specialist manifest: {path}")
        item = dict(item)
        item["manifest_file"] = relpath(path, root)
        manifests.append(item)
    return sorted(manifests, key=lambda item: item["name"])


def cmd_init(root: Path, args: argparse.Namespace) -> int:
    state = root / ".documentron"
    for child in ("runs", "reports", "architecture"):
        (state / child).mkdir(parents=True, exist_ok=True)
    config_path = state / "config.json"
    if not config_path.exists():
        atomic_write(config_path, canonical_json(DEFAULT_CONFIG))
    print(canonical_json({"status": "initialized", "config": relpath(config_path, root)}), end="")
    return 0


def cmd_inventory(root: Path, args: argparse.Namespace) -> int:
    config = load_config(root)
    files = tracked_files(root)
    result = {
        "files": files,
        "documents": configured_doc_paths(root, config),
        "design_documents": sorted(
            raw for raw in files if any(raw == base or raw.startswith(base.rstrip("/") + "/") for base in config["documentation"]["design_doc_roots"])
        ),
        "manifests": sorted(raw for raw in files if Path(raw).name in {"pyproject.toml", "package.json", "Cargo.toml", "Project.toml", "mkdocs.yml", "mkdocs.yaml"}),
    }
    print(canonical_json(result), end="")
    return 0


def cmd_scope(root: Path, args: argparse.Namespace) -> int:
    print(canonical_json({"scope": resolve_scope(root, args)}), end="")
    return 0


def cmd_prepare(root: Path, args: argparse.Namespace) -> int:
    output, packet = build_packet(root, args)
    print(canonical_json({
        "packet": relpath(output, root),
        "llm_policy": packet["llm_policy"],
        "invalidated_claims": len(packet["invalidated_claims"]),
        "specialists": [item.get("name") for item in packet["specialists"]],
    }), end="")
    return 0


def cmd_match(root: Path, args: argparse.Namespace) -> int:
    config = load_config(root)
    scope = resolve_scope(root, args)
    docs = affected_docs(root, config, scope)
    claims = extract_claims(root, docs, scope_hash(root, scope))
    print(canonical_json(matched_specialists(config, args.command, scope, claims)), end="")
    return 0


def cmd_validate_result(root: Path, args: argparse.Namespace) -> int:
    packet = read_json(safe_repo_path(root, args.packet))
    result = read_json(safe_repo_path(root, args.result))
    errors = validate_semantic_result(packet, result)
    print(canonical_json({"valid": not errors, "errors": errors}), end="")
    return 1 if errors else 0


def cmd_apply_result(root: Path, args: argparse.Namespace) -> int:
    packet_path = safe_repo_path(root, args.packet)
    result_path = safe_repo_path(root, args.result)
    packet = read_json(packet_path)
    result = read_json(result_path)
    errors = validate_semantic_result(packet, result)
    if errors:
        print(canonical_json({"status": "rejected", "errors": errors}), end="")
        return 1
    changed = apply_patches(root, result.get("patches", []), dry_run=args.dry_run)
    if not args.dry_run:
        record_result(root, packet, result)
    print(canonical_json({"status": "dry-run" if args.dry_run else "applied", "changed": changed}), end="")
    return 0


def cmd_doctor(root: Path, args: argparse.Namespace) -> int:
    result = doctor(root, run_commands=args.run_commands)
    if args.output:
        output = safe_repo_path(root, args.output)
        atomic_write(output, canonical_json(result))
    print(canonical_json(result), end="")
    return 1 if result["status"] == "failed" else 0


def cmd_render(root: Path, args: argparse.Namespace) -> int:
    data = read_json(safe_repo_path(root, args.input))
    md, page = render_report(data, args.title)
    md_path = safe_repo_path(root, args.markdown)
    html_path = safe_repo_path(root, args.html)
    atomic_write(md_path, md)
    atomic_write(html_path, page)
    print(canonical_json({"markdown": relpath(md_path, root), "html": relpath(html_path, root)}), end="")
    return 0


def cmd_discover(root: Path, args: argparse.Namespace) -> int:
    manifests = discover_specialists(root)
    if args.write:
        config_path = root / ".documentron" / "config.json"
        config = load_config(root)
        config["specialists"] = manifests
        atomic_write(config_path, canonical_json(config))
    print(canonical_json({"specialists": manifests, "written": bool(args.write)}), end="")
    return 0


def add_scope_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--paths", nargs="*")
    parser.add_argument("--paths-file")
    parser.add_argument("--plan")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    sub.add_parser("init")
    sub.add_parser("inventory")
    scope = sub.add_parser("scope")
    add_scope_arguments(scope)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--command", required=True, choices=["check", "factcheck", "update", "refresh", "architecture", "theory", "post-plan"])
    prepare.add_argument("--output")
    add_scope_arguments(prepare)
    match = sub.add_parser("match-specialists")
    match.add_argument("--command", required=True)
    add_scope_arguments(match)
    validate_result = sub.add_parser("validate-result")
    validate_result.add_argument("--packet", required=True)
    validate_result.add_argument("--result", required=True)
    apply_result = sub.add_parser("apply-result")
    apply_result.add_argument("--packet", required=True)
    apply_result.add_argument("--result", required=True)
    apply_result.add_argument("--dry-run", action="store_true")
    doctor_parser = sub.add_parser("doctor")
    doctor_parser.add_argument("--run-commands", action="store_true")
    doctor_parser.add_argument("--output")
    render = sub.add_parser("render-report")
    render.add_argument("--input", required=True)
    render.add_argument("--title", required=True)
    render.add_argument("--markdown", required=True)
    render.add_argument("--html", required=True)
    discover = sub.add_parser("discover-specialists")
    discover.add_argument("--write", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = find_repo_root(Path(args.repo))
    commands = {
        "init": cmd_init,
        "inventory": cmd_inventory,
        "scope": cmd_scope,
        "prepare": cmd_prepare,
        "match-specialists": cmd_match,
        "validate-result": cmd_validate_result,
        "apply-result": cmd_apply_result,
        "doctor": cmd_doctor,
        "render-report": cmd_render,
        "discover-specialists": cmd_discover,
    }
    try:
        return commands[args.subcommand](root, args)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(canonical_json({"status": "error", "error": str(exc)}), end="", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
