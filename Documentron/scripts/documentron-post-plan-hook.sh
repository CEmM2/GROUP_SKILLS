#!/usr/bin/env bash
set -euo pipefail

# Documentron optional AutViam close-plan hook.
# Usage: documentron-post-plan-hook.sh <plan_file> [repo_root]
# It prepares a deterministic post-plan packet. The host runtime may then perform
# only the semantic reviews required by that packet.

PLAN_FILE="${1:-}"
REPO_ROOT="${2:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
if [ -z "$PLAN_FILE" ]; then
  echo "documentron-post-plan-hook: missing plan_file" >&2
  exit 2
fi
mkdir -p "$REPO_ROOT/.documentron/hooks"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULT="$(python3 "$HERE/documentron.py" --repo "$REPO_ROOT" prepare --command post-plan --plan "$PLAN_FILE")"
PACKET="$(printf '%s' "$RESULT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["packet"])')"
printf '%s\n' "$RESULT" > "$REPO_ROOT/.documentron/hooks/pending-post-plan.json"
printf 'Documentron packet prepared: %s\n' "$PACKET"
