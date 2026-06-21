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

## Step 6 — Install the project-tracker helper (deterministic)

Copy the bundled `update_tracker.sh` helper into the host repo so the GitHub Project
sync path has an executable to call. This is the single script that
`references/project_sync.md`, Plan-2-Tasks §7h, ScaffoldPhase, and ExecPhase invoke
when Project sync is armed.

```bash
mkdir -p .claude/scripts
if [ -e .claude/scripts/update_tracker.sh ]; then
  # Don't clobber a repo-customized helper — drop a .new alongside for the user to diff.
  cp <skill_root>/scripts/update_tracker.sh .claude/scripts/update_tracker.sh.new
  echo "update_tracker.sh already present — wrote .claude/scripts/update_tracker.sh.new instead (diff and merge manually)."
else
  cp <skill_root>/scripts/update_tracker.sh .claude/scripts/update_tracker.sh
  chmod +x .claude/scripts/update_tracker.sh
  echo "Installed .claude/scripts/update_tracker.sh"
fi
```

The helper is **best-effort / no-op unless armed**: it only does anything when this repo's
`autviam_config.json` → `project` names a board (and `gh` is authenticated). With
`project: "disable"` (the default) nothing calls it, and even when armed it degrades
gracefully — an unauthenticated `gh` or an unresolvable field logs to stderr and exits
non-zero without ever blocking a phase. Installing it now just means the executable is in
place for the day you flip `project` on.

## Notes

- **`nested_dispatch`** (default `"off"`) controls E2E execution: `"off"` runs each phase inline in the main thread (correct for Claude Code, which forbids nested subagent dispatch); `"on"` uses the orchestrator subagent; `"auto"` probes once and falls back to `"off"`. Leave it `"off"` unless you've confirmed this environment allows a subagent to spawn subagents. See `commands/E2E.md` § Step 0.
- **`project`** (default `"disable"`) turns on native GitHub Project sync: set it to a board name (or `{owner,name}` / `{owner,number}`) and AutViam adds plan/phase issues to that Project and keeps their Status field in step with the issue lifecycle. `"disable"` (or absent) = no Project calls at all. See `references/project_sync.md`.
- The config is repo-local. It is never pushed upstream to the AutViam skill definition.
- Trigger matching at runtime uses `git diff --name-only | grep -E '<pattern>'` —
  deterministic bash, not LLM judgment.
- The domain reviewer receives a `specialist_agents` list in its prompt only when at least
  one changed file matches a specialist's patterns. Empty list → standard review, no dispatch.
- To reset: delete `autviam_config.json` and re-run install, or run with `--dry-run` first.
