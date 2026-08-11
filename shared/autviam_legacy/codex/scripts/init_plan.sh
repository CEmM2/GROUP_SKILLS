#!/usr/bin/env bash
# init_plan.sh — deterministic per-plan plumbing for AutViam Plan-2-Tasks (Step 7).
#
# Owns the mechanical halves: slug derivation, folder scaffolding, label diff/create,
# issue creation (the `gh issue create` call), issue-map write, and task-JSON issue
# annotation. Issue BODIES stay LLM-rendered — pass them as --body-file.
# All GitHub steps degrade gracefully (skip on `gh` unauthenticated; exit 3).
#
# Usage:
#   init_plan.sh slug <plan_file>
#       → prints plan_slug: lowercase, `_` and spaces → `-`, drop extension, collapse `-`.
#   init_plan.sh dirs <tasks_folder>
#       → mkdir -p <tasks_folder>/{json,gates,reviews,scratch}  (scratch = gitignored transient bodies)
#   init_plan.sh labels <slug> <plan_name> <phase_count>
#       → create only the MISSING labels (diff vs `gh label list`), incl phase-1..phase-<phase_count>.
#   init_plan.sh create-issue --title T --labels "a,b" --body-file F
#       → gh issue create … ; prints the new issue NUMBER.
#   init_plan.sh map <tasks_folder> <plan_file> <slug> <overview_issue> <repo> <N:issue> [<N:issue>…]
#       → write <tasks_folder>/github_issue_map.json
#   init_plan.sh annotate <json_dir> <map_file>
#       → add "github_issue":{phase_issue,repo} to each task JSON keyed by its "phase".
set -uo pipefail
log(){ printf '[init_plan] %s\n' "$*" >&2; }

CMD="${1:?usage: init_plan.sh [slug|dirs|labels|create-issue|map|annotate] …}"; shift || true
case "$CMD" in
  slug)
    PF="${1:?usage: slug <plan_file>}"
    base="$(basename "$PF")"; base="${base%.*}"
    printf '%s' "$base" | tr 'A-Z' 'a-z' | tr ' _' '--' | tr -s '-'; echo ;;

  dirs)
    TF="${1:?usage: dirs <tasks_folder>}"
    mkdir -p "$TF/json" "$TF/gates" "$TF/reviews" "$TF/scratch"
    log "scaffolded $TF/{json,gates,reviews,scratch}" ;;

  labels)
    SLUG="${1:?usage: labels <slug> <plan_name> <phase_count>}"; NAME="${2:?plan_name}"; PHASES="${3:?phase_count}"
    gh auth status >/dev/null 2>&1 || { log "gh not authenticated — skipping labels"; exit 3; }
    existing="$(gh label list --json name -q '.[].name' 2>/dev/null)"
    ensure(){
      printf '%s\n' "$existing" | grep -qxF "$1" && return 0
      gh label create "$1" --color "$2" --description "$3" >/dev/null 2>&1 && log "created label $1" || true
    }
    ensure "plan:$SLUG"      1d76db "Plan: $NAME"
    ensure "plan-issue"      0075ca "Plan overview issue"
    ensure "phase-issue"     7057ff "Phase parent issue"
    ensure "not-scaffolded"  e4e669 "Phase not yet scaffolded"
    ensure "scaffolded"      0e8a16 "Phase scaffolded"
    ensure "in-progress"     fbca04 "Phase actively executing"
    ensure "done"            0e8a16 "Phase complete"
    ensure "gate-cap-hit"    b60205 "Task hit 4th gate failure — manual intervention required"
    ensure "tier:unit"        f9d0c4 "Unit test tier"
    ensure "tier:integration" f9d0c4 "Integration test tier"
    ensure "tier:regression"  f9d0c4 "Regression test tier"
    i=1; while [ "$i" -le "$PHASES" ]; do ensure "phase-$i" d4c5f9 "Phase $i"; i=$((i+1)); done
    log "labels ensured (missing-only)" ;;

  create-issue)
    TITLE=""; LABELS=""; BODY=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --title)     TITLE="$2"; shift 2 ;;
        --labels)    LABELS="$2"; shift 2 ;;
        --body-file) BODY="$2";  shift 2 ;;
        *)           shift ;;
      esac
    done
    [ -n "$TITLE" ] && [ -n "$BODY" ] || { log "create-issue needs --title and --body-file"; exit 2; }
    [ -f "$BODY" ] || { log "body file not found: $BODY"; exit 1; }
    gh auth status >/dev/null 2>&1 || { log "gh not authenticated — skipping issue create"; exit 3; }
    url="$(gh issue create --title "$TITLE" ${LABELS:+--label "$LABELS"} --body-file "$BODY" 2>/dev/null)" \
      || { log "gh issue create failed"; exit 1; }
    printf '%s\n' "$url" | grep -oE '[0-9]+$' ;;

  map)
    TF="${1:?usage: map <tasks_folder> <plan_file> <slug> <overview_issue> <repo> <N:issue>…}"
    PF="${2:?plan_file}"; SLUG="${3:?slug}"; OV="${4:?overview_issue}"; REPO="${5:?repo}"; shift 5
    TF="$TF" PF="$PF" SLUG="$SLUG" OV="$OV" REPO="$REPO" PHASES="$*" python3 - <<'PY'
import json, os
phases = {}
for tok in os.environ["PHASES"].split():
    if ":" in tok:
        n, iss = tok.split(":", 1)
        phases[str(n)] = {"issue_number": int(iss)}
m = {
    "plan_file": os.environ["PF"],
    "plan_slug": os.environ["SLUG"],
    "plan_overview_issue": int(os.environ["OV"]),
    "phases": phases,
    "repo": os.environ["REPO"],
}
path = os.path.join(os.environ["TF"], "github_issue_map.json")
open(path, "w").write(json.dumps(m, indent=2) + "\n")
print("wrote " + path)
PY
    ;;

  annotate)
    JD="${1:?usage: annotate <json_dir> <map_file>}"; MAP="${2:?map_file}"
    JD="$JD" MAP="$MAP" python3 - <<'PY'
import json, os, glob
m = json.load(open(os.environ["MAP"]))
repo = m.get("repo", ""); phases = m.get("phases", {})
n = 0
for fp in glob.glob(os.path.join(os.environ["JD"], "*.json")):
    t = json.load(open(fp))
    pi = phases.get(str(t.get("phase", "")), {}).get("issue_number")
    if pi is None:
        continue
    t["github_issue"] = {"phase_issue": pi, "repo": repo}
    json.dump(t, open(fp, "w"), indent=4); open(fp, "a").write("\n")
    n += 1
print(f"annotated {n} task JSON(s)")
PY
    ;;

  *)
    log "usage: init_plan.sh [slug|dirs|labels|create-issue|map|annotate] …"; exit 2 ;;
esac
