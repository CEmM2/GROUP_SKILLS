#!/usr/bin/env bash
# update_tracker.sh — set a field on a GitHub Project item, or add an item.
#
# The single executable behind every tracker automation: the pin-bump hook,
# the AutViam project-sync reference, CI status bridges, and manual reconciliation.
# Resolves project/field/option IDs once and caches them so each call is one
# `gh project item-edit`.
#
# Usage:
#   update_tracker.sh add  <issue-or-pr-url>                 # add item, print its item id
#   update_tracker.sh set  <issue-or-pr-url> <field> <value> # set a field (single-select/text/number)
#   update_tracker.sh ids                                    # dump resolved field/option ids
#   update_tracker.sh --refresh ...                          # bust the field-id cache first
#
# Config (env or .codex/scripts/tracker.env):
#   TRACKER_OWNER   (default: SOSOVSKI)
#   TRACKER_NUMBER  (default: 4)
#
# Degrade-gracefully: if gh is unauthenticated or the project/field can't be
# resolved, it logs to stderr and exits non-zero WITHOUT throwing — callers
# (hooks, AutViam) treat the project as a best-effort projection and never block.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "$HERE/tracker.env" ] && . "$HERE/tracker.env"
OWNER="${TRACKER_OWNER:-SOSOVSKI}"
NUMBER="${TRACKER_NUMBER:-4}"
CACHE="${TMPDIR:-/tmp}/ll_tracker_fields_${OWNER}_${NUMBER}.json"

log() { printf '[update_tracker] %s\n' "$*" >&2; }

if [ "${1:-}" = "--refresh" ]; then rm -f "$CACHE"; shift; fi
CMD="${1:-}"; shift || true

gh auth status >/dev/null 2>&1 || { log "gh not authenticated — skipping (project is best-effort)"; exit 3; }

# --- resolve + cache project id, field ids, single-select option ids ----------
ensure_cache() {
  [ -s "$CACHE" ] && return 0
  local proj fields
  proj="$(gh project view "$NUMBER" --owner "$OWNER" --format json 2>/dev/null)" || { log "cannot view project $OWNER/#$NUMBER"; return 1; }
  fields="$(gh project field-list "$NUMBER" --owner "$OWNER" --format json 2>/dev/null)" || { log "cannot list fields"; return 1; }
  PROJ="$proj" FIELDS="$fields" python3 - "$CACHE" <<'PY' || return 1
import json, os, sys
proj = json.loads(os.environ["PROJ"]); fields = json.loads(os.environ["FIELDS"])
out = {"project_id": proj["id"], "fields": {}}
for f in fields["fields"]:
    entry = {"id": f["id"], "type": f["type"]}
    if "options" in f:
        entry["options"] = {o["name"]: o["id"] for o in f["options"]}
    out["fields"][f["name"]] = entry
json.dump(out, open(sys.argv[1], "w"))
PY
}

cache_get() { CACHE="$CACHE" python3 - "$@" <<'PY'
import json, os, sys
c = json.load(open(os.environ["CACHE"]))
what = sys.argv[1]
if what == "project_id": print(c["project_id"]); sys.exit(0)
field = c["fields"].get(sys.argv[2])
if not field: sys.exit(4)
if what == "field_id": print(field["id"]); sys.exit(0)
if what == "field_type": print(field["type"]); sys.exit(0)
if what == "option_id":
    oid = (field.get("options") or {}).get(sys.argv[3]);
    print(oid) if oid else sys.exit(5)
PY
}

item_id_for_url() {  # find an existing project item by its content URL
  gh project item-list "$NUMBER" --owner "$OWNER" --limit 800 --format json 2>/dev/null \
    | URL="$1" python3 -c 'import json,os,sys; [print(i["id"]) or sys.exit(0) for i in json.load(sys.stdin)["items"] if i.get("content",{}).get("url")==os.environ["URL"]]; sys.exit(6)'
}

case "$CMD" in
  add)
    URL="${1:?usage: add <url>}"
    gh project item-add "$NUMBER" --owner "$OWNER" --url "$URL" --format json 2>/dev/null \
      | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' \
      || { log "item-add failed for $URL"; exit 1; }
    ;;
  set)
    URL="${1:?usage: set <url> <field> <value>}"; FIELD="${2:?field}"; VALUE="${3:?value}"
    ensure_cache || exit 1
    PID="$(cache_get project_id)" || exit 1
    FID="$(cache_get field_id "$FIELD")" || { log "no field '$FIELD' on project"; exit 4; }
    FTYPE="$(cache_get field_type "$FIELD")"
    IID="$(item_id_for_url "$URL")" || { log "item not on board (add it first): $URL"; exit 6; }
    case "$FTYPE" in
      *SingleSelect*)
        OID="$(cache_get option_id "$FIELD" "$VALUE")" || { log "no option '$VALUE' on field '$FIELD'"; exit 5; }
        gh project item-edit --id "$IID" --project-id "$PID" --field-id "$FID" --single-select-option-id "$OID" >/dev/null 2>&1 ;;
      *Number*)
        gh project item-edit --id "$IID" --project-id "$PID" --field-id "$FID" --number "$VALUE" >/dev/null 2>&1 ;;
      *)
        gh project item-edit --id "$IID" --project-id "$PID" --field-id "$FID" --text "$VALUE" >/dev/null 2>&1 ;;
    esac || { log "item-edit failed ($FIELD=$VALUE on $URL)"; exit 1; }
    log "set $FIELD=$VALUE on $URL"
    ;;
  ids)
    ensure_cache || exit 1; cat "$CACHE" | python3 -m json.tool ;;
  *)
    log "usage: update_tracker.sh [add|set|ids] ... (see header)"; exit 2 ;;
esac
