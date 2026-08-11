#!/usr/bin/env bash
# phase-close.sh — PostToolUse backstop that finalizes a phase when its handoff is written.
#
# Wire it as a PostToolUse hook on Edit|Write (Claude Code settings.json, or Codex .codex/hooks.json).
# It fires on every file write but does nothing unless the written file is a `Handoff_Phase_<K>.md`
# (ExecPhase Step 10a writes this at the end of phase K-1). When it sees one, it idempotently
# finalizes the *completed* phase K-1: closes that phase's issue (label swap in-progress→done) and
# sets the GitHub Project item Status to Done. This is the backstop for when ExecPhase Step 10b's
# in-band close is skipped/interrupted; both paths are idempotent, so running both is safe. It never
# rewrites the issue body (it does not tick task checkboxes — that stays with the in-band Step 10b).
#
# Input (PostToolUse convention, shared by Claude Code and Codex hooks):
#   JSON on stdin with `.tool_input.file_path`. For manual use, pass the handoff path as $1.
#
# Always exits 0 — a hook must never block the tool that triggered it. All GitHub/Project work is
# best-effort: it self-skips when gh is unauthenticated, no issue map exists, or project sync is off.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- resolve the written file path: stdin JSON (.tool_input.file_path) or $1 -------------------
RAW=""; [ -t 0 ] || RAW="$(cat 2>/dev/null || true)"
FILE="$(RAW="$RAW" ARG="${1:-}" python3 - <<'PY' 2>/dev/null || true
import json, os
raw = os.environ.get("RAW", "")
fp = ""
if raw.strip():
    try:
        fp = (json.loads(raw).get("tool_input") or {}).get("file_path") or ""
    except Exception:
        fp = ""
print(fp or os.environ.get("ARG", ""))
PY
)"

[ -n "$FILE" ] || exit 0

# --- only act on a phase handoff file ----------------------------------------------------------
base="$(basename "$FILE")"
case "$base" in
  Handoff_Phase_*.md) ;;
  *) exit 0 ;;
esac
K="${base#Handoff_Phase_}"; K="${K%.md}"
case "$K" in *[!0-9]*|"") exit 0 ;; esac      # not an integer → ignore
COMPLETED=$(( K - 1 ))
[ "$COMPLETED" -ge 1 ] || exit 0              # Handoff_Phase_1 → no prior phase to close

TASKS_DIR="$(cd "$(dirname "$FILE")" && pwd 2>/dev/null)" || exit 0
MAP="$TASKS_DIR/github_issue_map.json"
[ -f "$MAP" ] || exit 0                        # local-only run — nothing to project/close

# --- phase issue number from the map -----------------------------------------------------------
ISSUE="$(MAP="$MAP" P="$COMPLETED" python3 - <<'PY' 2>/dev/null || true
import json, os
try:
    m = json.load(open(os.environ["MAP"]))
    print((m.get("phases", {}).get(os.environ["P"], {}) or {}).get("issue_number") or "")
except Exception:
    print("")
PY
)"

# --- best-effort: close the phase issue (idempotent — skip if already closed) -------------------
if [ -n "$ISSUE" ] && gh auth status >/dev/null 2>&1; then
  state="$(gh issue view "$ISSUE" --json state -q .state 2>/dev/null || echo "")"
  if [ "$state" = "OPEN" ]; then
    if [ -x "$HERE/issue_body.sh" ]; then
      "$HERE/issue_body.sh" close "$ISSUE" --remove in-progress --add done \
        --comment "Phase $COMPLETED finalized by phase-close.sh backstop (handoff written)." >/dev/null 2>&1 || true
    else
      gh issue edit "$ISSUE" --remove-label in-progress --add-label done >/dev/null 2>&1 || true
      gh issue close "$ISSUE" --comment "Phase $COMPLETED finalized by phase-close.sh backstop (handoff written)." >/dev/null 2>&1 || true
    fi
  fi
fi

# --- best-effort: set Project Status=Done (self-gated; no-op when project sync is off) ----------
if [ -x "$HERE/project_sync.sh" ]; then
  "$HERE/project_sync.sh" status "$MAP" "phase:$COMPLETED" Done >/dev/null 2>&1 || true
fi

# --- best-effort: open the draft PR for this phase (phase branch → plan branch), idempotent -----
if [ -x "$HERE/draft_pr.sh" ]; then
  "$HERE/draft_pr.sh" phase "$MAP" "$COMPLETED" "$FILE" >/dev/null 2>&1 || true
  # If this was the LAST phase, also open the plan → main draft PR (plan complete).
  LAST="$(MAP="$MAP" python3 - <<'PY' 2>/dev/null || true
import json, os
try: print(max((int(k) for k in json.load(open(os.environ["MAP"])).get("phases", {})), default=0))
except Exception: print(0)
PY
)"
  if [ -n "$LAST" ] && [ "$COMPLETED" = "$LAST" ]; then
    "$HERE/draft_pr.sh" plan "$MAP" "$FILE" >/dev/null 2>&1 || true
  fi
fi

exit 0
