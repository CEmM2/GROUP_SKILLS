#!/usr/bin/env bash
# match_specialists.sh — deterministic config-driven specialist/skill matcher for AutViam.
#
# SKILL § Post-Install Configuration calls this "deterministic — no LLM at trigger time."
# For the given config section, emits the JSON array of entries whose `trigger_patterns`
# match at least one file in `git diff --name-only <base>..<head>` (OR logic). Absent
# config or empty/missing section → `[]` (backward compatible — reviewer skips specialists).
#
# Variant-agnostic: emits the matched config entries VERBATIM, so it works for the Claude
# schema (`agent`/`trigger_patterns`) and the Codex schema (`name`/`codex_agent_type`/
# `prompt_file`/`trigger_patterns`) alike. The caller passes its own config path.
#
# Usage:
#   match_specialists.sh <config_path> <section> <base_sha> <head_sha>
#     <section>: dot path, e.g. domain_reviewer.specialists | spec_reviewer.specialists | implementer.skills
#   → JSON array of matched entries on stdout.
set -uo pipefail

CONFIG="${1:?usage: match_specialists.sh <config_path> <section> <base_sha> <head_sha>}"
SECTION="${2:?section (e.g. domain_reviewer.specialists)}"
BASE="${3:?base_sha}"
HEAD="${4:?head_sha}"

# No config → empty list. (Repos with no specialist config get standard review.)
[ -f "$CONFIG" ] || { echo "[]"; exit 0; }

CHANGED="$(git diff --name-only "$BASE".."$HEAD" 2>/dev/null)"

CONFIG="$CONFIG" SECTION="$SECTION" CHANGED="$CHANGED" python3 - <<'PY'
import json, os, re, sys
changed = [l for l in os.environ["CHANGED"].splitlines() if l.strip()]
try:
    cfg = json.load(open(os.environ["CONFIG"]))
except Exception:
    print("[]"); sys.exit(0)
node = cfg
for key in os.environ["SECTION"].split("."):
    node = node.get(key) if isinstance(node, dict) else None
    if node is None:
        break
if not isinstance(node, list):
    node = []
matched = []
for entry in node:
    for pat in (entry.get("trigger_patterns") or []):
        try:
            rx = re.compile(pat)
        except re.error:
            continue
        if any(rx.search(f) for f in changed):
            matched.append(entry)
            break
print(json.dumps(matched))
PY
