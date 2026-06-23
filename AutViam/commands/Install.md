# Install

Scans the host repo for agents and skills that AutViam can dispatch during gate reviews or
implementation, presents a categorisation plan to the user, and writes `autviam_config.json`.

Run once per repo after initial install. Re-run after adding new agents/skills or when you
want to change the integration. Idempotent — re-running overwrites only what you confirm.

**Inputs:**
- `[--dry-run]` — show the proposed plan without writing anything

---

## Step 1 — Scan (bash, deterministic)

```bash
# Agents present in this repo, excluding AutViam's own
ls .claude/agents/*.md 2>/dev/null \
  | grep -v -E 'autviam-(spec-reviewer|domain-reviewer|phase-orchestrator)\.md$'

# Skills present (top-level SKILL.md per skill directory), excluding AutViam
ls .claude/skills/*/SKILL.md 2>/dev/null \
  | grep -v '/AutViam/'
```

Read the YAML frontmatter (`name:`, `description:`, `tools:`) of each found file.

If nothing is found, print "No additional agents or skills found — nothing to configure."
Do not write a config. Exit.

## Step 2 — Check existing config

```bash
cat <skill_root>/autviam_config.json 2>/dev/null
```

If it exists, show the current integration as a table before proposing changes:

```
Existing config (installed YYYY-MM-DD):
  domain_reviewer specialists : [agent-a, agent-b]
  spec_reviewer specialists   : []
  implementer skills          : []
Proceeding will let you update it.
```

## Step 3 — Categorise and propose trigger patterns

For each found candidate apply these rules **in order**; first match wins:

| Description keywords | Proposed slot | Default trigger type |
|---|---|---|
| GPU, kernel, taichi, shader, CUDA, warp, atomic | `domain_reviewer` | path: `^(apps\|libs)/.*\.py$` |
| numerical, physics, FEM, FFT, constitutive, solver, convergence, tolerance, CFL | `domain_reviewer` | path: specific source dirs |
| API contract, type check, interface, import, signature | `spec_reviewer` | path: relevant module |
| code generation, scaffold, implementation template | `implementer` | — (skill reference) |
| unclear | ask the user | — |

**Trigger pattern derivation (deterministic):**
Inspect the repo directory structure with:
```bash
ls apps/ libs/ src/ 2>/dev/null
```
Then narrow the default path pattern to the directories that actually exist and match the
agent's stated scope. Produce concrete `grep -E` compatible patterns over
`git diff --name-only` output. Validate by running:
```bash
git diff --name-only HEAD~1 HEAD | grep -E '<proposed_pattern>' | head -5
```
If the grep returns matches, the pattern is live in this repo — note that in the proposal.

## Step 4 — Present plan

Show the user a table:

```
Proposed AutViam integration
────────────────────────────────────────────────────────────────────────
Agent / Skill         Slot               Trigger pattern(s)
──────────────────    ───────────────    ──────────────────────────────
gpu-kernel-reviewer   domain_reviewer    ^(apps|libs)/.*\.py$
numerical-verifier    domain_reviewer    ^apps/tife(m|ft)/.*\.py$
                                         ^libs/ticonstit/.*\.py$
docs-sync-checker     (none proposed)    — description unclear; skip?
────────────────────────────────────────────────────────────────────────

For each entry, options:
  [A]ccept  [M]odify trigger  [S]kip  [R]ename slot
```

Ask the user to confirm, modify, or skip each candidate. Accept free-text overrides for
trigger patterns. For `--dry-run`, stop here and print "Dry run — no files written."

Do not proceed past this step until the user responds.

## Step 5 — Write config (deterministic)

Write `<skill_root>/autviam_config.json` using the confirmed choices:

```json
{
  "schema_version": "1",
  "installed_at": "<ISO-date>",
  "repo": "<owner/repo or 'local'>",
  "nested_dispatch": "off",
  "project": "disable",
  "domain_reviewer": {
    "specialists": [
      {
        "agent": "<name>",
        "description": "<frontmatter description, one line>",
        "trigger_patterns": ["<pattern1>", "<pattern2>"]
      }
    ]
  },
  "spec_reviewer": {
    "specialists": []
  },
  "implementer": {
    "skills": []
  }
}
```

Use the `Write` tool — not shell redirection. No other files are modified.

Print a confirmation:

```
autviam_config.json written.
  domain_reviewer will dispatch: gpu-kernel-reviewer, numerical-verifier
  spec_reviewer specialists    : (none)
  implementer skills           : (none)

Re-run '/AutViam install' any time to update.
ExecPhase/ExecTask pick up the config automatically — no restart needed.
```

## Step 6 — Scripts (no copy needed — single location)

The bundled scripts already live at `<skill_root>/scripts/` (`.claude/skills/AutViam/scripts/`) — distribution placed them there, and that is the **single** copy everything uses:
- command files call them as `<skill_root>/scripts/<name>`;
- `project_sync.sh` finds its sibling `update_tracker.sh` in the same dir (`$HERE/update_tracker.sh`);
- the Step 7 hook points at `<skill_root>/scripts/phase-close.sh`, which resolves its siblings (`issue_body.sh`, `project_sync.sh`, `draft_pr.sh`) from that dir too.

There is **no second `.claude/scripts/` copy** — one location, nothing to keep in sync. If you use the GitHub Project board and want fixed defaults, drop an optional `tracker.env` (`TRACKER_OWNER`/`TRACKER_NUMBER`) **beside** `update_tracker.sh` at `<skill_root>/scripts/tracker.env`; otherwise `project_sync.sh` resolves the board from `autviam_config.json` → `project`.

The scripts are best-effort / safe: the GitHub & Project scripts no-op unless `gh` is authenticated (and Project sync stays off until `autviam_config.json` → `project` names a board); the rest only run when a command invokes them, and never block a phase on failure.

## Step 7 — Wire the phase-close backstop hook (optional)

`scripts/phase-close.sh` is a **PostToolUse backstop**: when ExecPhase writes a `Handoff_Phase_<N>.md`, it finalizes the just-completed phase (closes the phase issue, sets its Project item to Done) even if the in-band Step 10b close was interrupted. It is idempotent with the in-band path and a silent no-op for every non-handoff write, so it is safe to leave always-on.

Wire it once per repo as a PostToolUse hook on `Edit|Write` in `.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/skills/AutViam/scripts/phase-close.sh\"", "timeout": 30 }
        ]
      }
    ]
  }
}
```

Using `$CLAUDE_PROJECT_DIR` (not a relative path) keeps the hook resolving correctly from any working directory, including a plan worktree. Skipping this step breaks nothing — ExecPhase Step 10b still closes phases in-band; the hook only adds a backstop for interrupted runs. Verify with `printf '{"tool_input":{"file_path":"/tmp/x.py"}}' | bash .claude/skills/AutViam/scripts/phase-close.sh; echo $?` → prints `0` and nothing else.

**Merge-method labels + repo settings (one-time, best-effort).** The draft PRs `phase-close.sh`/ExecPhase open are labelled `merge:commit` (phase→plan) and `merge:squash` (plan→main) — GitHub can't pin a per-PR merge method, so the label records intent for the eventual `gh pr merge --merge`/`--squash`. Create the labels and allow both methods on the repo:

```bash
gh label create merge:commit --color 1d76db --description "AutViam: merge-commit this PR at merge time" --force
gh label create merge:squash --color 0e8a16 --description "AutViam: squash this PR at merge time" --force
gh api -X PATCH "repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)" -F allow_merge_commit=true -F allow_squash_merge=true >/dev/null 2>&1 || true
```

(The labels also auto-create on first PR; the repo-settings PATCH needs admin and is best-effort.)

## Notes

- **`nested_dispatch`** (default `"off"`) controls E2E execution: `"off"` runs each phase inline in the main thread (correct for Claude Code, which forbids nested subagent dispatch); `"on"` uses the orchestrator subagent; `"auto"` probes once and falls back to `"off"`. Leave it `"off"` unless you've confirmed this environment allows a subagent to spawn subagents. See `commands/E2E.md` § Step 0.
- **`project`** (default `"disable"`) turns on native GitHub Project sync: set it to a board name (or `{owner,name}` / `{owner,number}`) and AutViam adds plan/phase issues to that Project and keeps their Status field in step with the issue lifecycle. `"disable"` (or absent) = no Project calls at all. See `references/project_sync.md`.
- The config is repo-local. It is never pushed upstream to the AutViam skill definition.
- Trigger matching at runtime uses `git diff --name-only | grep -E '<pattern>'` —
  deterministic bash, not LLM judgment.
- The domain reviewer receives a `specialist_agents` list in its prompt only when at least
  one changed file matches a specialist's patterns. Empty list → standard review, no dispatch.
- To reset: delete `autviam_config.json` and re-run install, or run with `--dry-run` first.
