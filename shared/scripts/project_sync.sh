#!/usr/bin/env bash
# project_sync.sh — the gated "write to the GitHub Project" wrapper around update_tracker.sh.
#
# update_tracker.sh is the low-level primitive (one `gh project item-edit` per call, IDs cached).
# This script owns the deterministic plumbing AROUND it that was previously LLM prose:
#   - resolve the board from <config> → `project` (4 forms; name → number via `gh project list`)
#   - maintain the `project` block in github_issue_map.json (owner, number, overview_item, phase_items)
#   - idempotency (skip an add already cached in the map) + degrade-gracefully (log + skip, never block)
#
# It bridges the AutViam board config to update_tracker.sh by exporting TRACKER_OWNER/TRACKER_NUMBER.
#
# Usage:
#   project_sync.sh resolve <config_path> [repo_owner]
#       → "OFF" when disabled/absent, else "<owner> <number>". name → number via `gh project list`.
#   project_sync.sh add <map_file> <config_path> <which> <issue_url> [--slug S] [--phase N]
#       which = overview | phase:<N>. Idempotent (skips if already cached). Adds the item, sets
#       Plan/Phase, caches the item id into the map's `project` block.
#   project_sync.sh status <map_file> <which> <status>
#       which = overview | phase:<N>. Sets Status on the cached item (issue URL derived from the map).
#
# Every failure logs to stderr and exits non-zero WITHOUT blocking — the Project is a
# projection-of-a-projection; callers ignore the exit code.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UT="$HERE/update_tracker.sh"
log(){ printf '[project_sync] %s\n' "$*" >&2; }

# resolve_board <config> [repo_owner] → echoes "OFF" or "<owner> <number>"; returns non-zero on unresolvable.
resolve_board(){
  local cfg="$1" fb="${2:-}" spec kind owner val num
  [ -f "$cfg" ] || { echo OFF; return 0; }
  spec="$(CFG="$cfg" FB="$fb" python3 - <<'PY'
import json, os, sys
try:
    cfg = json.load(open(os.environ["CFG"]))
except Exception:
    print("off"); sys.exit(0)
p = cfg.get("project"); fb = os.environ.get("FB", "")
if not p or p == "disable":
    print("off")
elif isinstance(p, str):
    print("name|%s|%s" % (fb, p))
elif isinstance(p, dict):
    owner = p.get("owner") or fb
    if "number" in p: print("direct|%s|%s" % (owner, p["number"]))
    elif "name" in p: print("name|%s|%s" % (owner, p["name"]))
    else: print("off")
else:
    print("off")
PY
)"
  kind="${spec%%|*}"; spec="${spec#*|}"; owner="${spec%%|*}"; val="${spec#*|}"
  [ "$kind" = "off" ] && { echo OFF; return 0; }
  if [ -z "$owner" ]; then
    owner="$(gh repo view --json owner -q .owner.login 2>/dev/null)" || { log "cannot resolve repo owner"; return 1; }
  fi
  if [ "$kind" = "direct" ]; then echo "$owner $val"; return 0; fi
  num="$(gh project list --owner "$owner" --format json 2>/dev/null | NAME="$val" python3 -c '
import json, os, sys
try: d = json.load(sys.stdin)
except Exception: sys.exit(1)
items = d.get("projects", d) if isinstance(d, dict) else d
hits = [p for p in items if p.get("title") == os.environ["NAME"]]
if len(hits) == 1: print(hits[0]["number"])
else: sys.exit(2 if len(hits) > 1 else 3)')" \
    || { log "project name \"$val\" not uniquely resolvable on @$owner — skipping (do not guess)"; return 1; }
  echo "$owner $num"
}

CMD="${1:?usage: project_sync.sh [resolve|add|status] …}"; shift || true
case "$CMD" in
  resolve)
    CFG="${1:?usage: resolve <config_path> [repo_owner]}"; FB="${2:-}"
    resolve_board "$CFG" "$FB" ;;

  add)
    MAP="${1:?usage: add <map_file> <config_path> <which> <issue_url> [--slug S] [--phase N]}"
    CFG="${2:?config_path}"; WHICH="${3:?which}"; URL="${4:?issue_url}"; shift 4
    SLUG=""; PHASE=""
    while [ $# -gt 0 ]; do case "$1" in --slug) SLUG="$2"; shift 2;; --phase) PHASE="$2"; shift 2;; *) shift;; esac; done
    # Idempotency — already cached in the map's project block?
    if [ -f "$MAP" ] && MAP="$MAP" WHICH="$WHICH" python3 - <<'PY'
import json, os, sys
try: m = json.load(open(os.environ["MAP"]))
except Exception: sys.exit(1)
pj = m.get("project", {}); w = os.environ["WHICH"]
ok = bool(pj.get("overview_item")) if w == "overview" else \
     bool(pj.get("phase_items", {}).get(w.split(":", 1)[1])) if w.startswith("phase:") else False
sys.exit(0 if ok else 1)
PY
    then log "$WHICH already on board — skip (idempotent)"; exit 0; fi
    board="$(resolve_board "$CFG")" || exit 1
    [ "$board" = "OFF" ] && { log "project OFF — skip"; exit 0; }
    owner="${board%% *}"; num="${board##* }"
    item="$(TRACKER_OWNER="$owner" TRACKER_NUMBER="$num" "$UT" add "$URL")" || { log "item-add failed for $URL"; exit 1; }
    [ -n "$SLUG" ]  && TRACKER_OWNER="$owner" TRACKER_NUMBER="$num" "$UT" set "$URL" Plan  "$SLUG"  >/dev/null 2>&1 || true
    [ -n "$PHASE" ] && TRACKER_OWNER="$owner" TRACKER_NUMBER="$num" "$UT" set "$URL" Phase "$PHASE" >/dev/null 2>&1 || true
    MAP="$MAP" WHICH="$WHICH" ITEM="$item" OWNER="$owner" NUM="$num" python3 - <<'PY'
import json, os
m = json.load(open(os.environ["MAP"]))
pj = m.setdefault("project", {})
pj.setdefault("owner", os.environ["OWNER"]); pj["number"] = int(os.environ["NUM"])
w = os.environ["WHICH"]; item = os.environ["ITEM"]
if w == "overview": pj["overview_item"] = item
elif w.startswith("phase:"): pj.setdefault("phase_items", {})[w.split(":", 1)[1]] = item
json.dump(m, open(os.environ["MAP"], "w"), indent=2); open(os.environ["MAP"], "a").write("\n")
PY
    log "added $WHICH to board (item $item)" ;;

  status)
    MAP="${1:?usage: status <map_file> <which> <status>}"; WHICH="${2:?which}"; STATUS="${3:?status}"
    info="$(MAP="$MAP" WHICH="$WHICH" python3 - <<'PY'
import json, os, sys
try: m = json.load(open(os.environ["MAP"]))
except Exception: sys.exit(1)
pj = m.get("project", {}); owner = pj.get("owner"); num = pj.get("number"); repo = m.get("repo")
if not (owner and num and repo): sys.exit(1)
w = os.environ["WHICH"]
n = m.get("plan_overview_issue") if w == "overview" else \
    m.get("phases", {}).get(w.split(":", 1)[1], {}).get("issue_number") if w.startswith("phase:") else None
if not n: sys.exit(2)
print("%s\t%s\thttps://github.com/%s/issues/%s" % (owner, num, repo, n))
PY
)" || { log "no board/issue cached for $WHICH — skip"; exit 0; }
    owner="$(printf '%s' "$info" | cut -f1)"; num="$(printf '%s' "$info" | cut -f2)"; url="$(printf '%s' "$info" | cut -f3)"
    TRACKER_OWNER="$owner" TRACKER_NUMBER="$num" "$UT" set "$url" Status "$STATUS" >/dev/null 2>&1 \
      || { log "Status=$STATUS on $WHICH best-effort failed"; exit 1; }
    log "set $WHICH Status=$STATUS" ;;

  *)
    log "usage: project_sync.sh [resolve|add|status] …"; exit 2 ;;
esac
