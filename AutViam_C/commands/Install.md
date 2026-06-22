# Install

Scans the host repo for Codex prompt profiles and skills that AutViam_C can dispatch during gate reviews or implementation, presents a categorisation plan to the user, and writes `autviam_c_config.json`.

Run once per repo after initial install. Re-run after adding new repo-local prompt profiles or skills, or when you want to change the integration. Idempotent — re-running overwrites only what you confirm.

**Inputs:**
- `[--dry-run]` — show the proposed plan without writing anything

---

## Step 1 — Scan (deterministic)

Look for optional repo-local Codex prompt profiles:

```bash
rg --files .codex/agents .agents/agents agents 2>/dev/null | rg '\.md$'
```

Look for Codex-consumable skills:

```bash
rg --files .codex/skills .agents/skills skills 2>/dev/null | rg '/SKILL\.md$'
```

Exclude:
- AutViam_C's own bundled profiles under `<skill_root>/agents/`
- AutViam_C's own `SKILL.md`
- Claude-only installed agents under `.claude/agents/` unless the user explicitly asks to import them as Codex prompt profiles

Read the YAML frontmatter (`name:`, `description:`, `codex_agent_type:` or `agent_type:`) of each found profile. For skills, read only `name:` and `description:`.

If nothing is found, print "No additional Codex prompt profiles or skills found — nothing to configure." Do not write a config. Exit.

## Step 2 — Check existing config

Read `<skill_root>/autviam_c_config.json` if it exists.

If it exists, show the current integration as a table before proposing changes:

```text
Existing config (installed YYYY-MM-DD):
  domain_reviewer specialists : [profile-a, profile-b]
  spec_reviewer specialists   : []
  implementer skills          : [skill-a]
Proceeding will let you update it.
```

## Step 3 — Categorise and propose trigger patterns

For each found candidate apply these rules in order; first match wins:

| Description keywords | Proposed slot | Codex dispatch | Default trigger type |
|---|---|---|---|
| GPU, kernel, taichi, shader, CUDA, warp, atomic | `domain_reviewer` | `explorer` profile | path: `^(apps|libs|src)/.*\.py$` |
| numerical, physics, FEM, FFT, constitutive, solver, convergence, tolerance, CFL | `domain_reviewer` | `explorer` profile | path: specific source dirs |
| API contract, type check, interface, import, signature | `spec_reviewer` | `explorer` profile | path: relevant module |
| code generation, scaffold, implementation template | `implementer` | skill reference | no agent dispatch |
| unclear | ask the user | — | — |

**Trigger pattern derivation (deterministic):**
Inspect the repo directory structure with:

```bash
ls apps libs src tests 2>/dev/null
```

Then narrow the default path pattern to directories that actually exist and match the candidate's stated scope. Produce concrete `rg`/`grep -E` compatible patterns over `git diff --name-only` output.

Validate proposed patterns when possible:

```bash
git diff --name-only HEAD~1 HEAD | rg '<proposed_pattern>' | head -5
```

If the command returns matches, the pattern is live in this repo — note that in the proposal. If the repo has no prior commit or no matching diff, still propose the pattern but mark it "not observed in current diff".

## Step 4 — Present plan

Show the user a table:

```text
Proposed AutViam_C integration
────────────────────────────────────────────────────────────────────────────
Profile / Skill       Slot               Codex type   Trigger pattern(s)
──────────────────    ───────────────    ─────────    ───────────────────
gpu-kernel-reviewer   domain_reviewer    explorer     ^(apps|libs)/.*\.py$
numerical-verifier    domain_reviewer    explorer     ^apps/tifem/.*\.py$
special-skill         implementer        skill        ^src/special/.*\.py$
docs-sync-checker     (none proposed)    —            description unclear
────────────────────────────────────────────────────────────────────────────

For each entry, options:
  [A]ccept  [M]odify trigger  [S]kip  [R]ename slot
```

Ask the user to confirm, modify, or skip each candidate. Accept free-text overrides for trigger patterns. For `--dry-run`, stop here and print "Dry run — no files written."

Do not proceed past this step until the user responds.

## Step 5 — Write config

Write `<skill_root>/autviam_c_config.json` using the confirmed choices:

```json
{
  "schema_version": "2-codex",
  "installed_at": "<ISO-date>",
  "repo": "<owner/repo or 'local'>",
  "domain_reviewer": {
    "specialists": [
      {
        "name": "<profile-name>",
        "codex_agent_type": "explorer",
        "prompt_file": "<repo-relative path to profile markdown>",
        "description": "<frontmatter description, one line>",
        "trigger_patterns": ["<pattern1>", "<pattern2>"]
      }
    ]
  },
  "spec_reviewer": {
    "specialists": []
  },
  "implementer": {
    "skills": [
      {
        "skill": "<skill-name>",
        "skill_md": "<repo-relative path to SKILL.md>",
        "description": "<frontmatter description, one line>",
        "trigger_patterns": ["<pattern>"]
      }
    ]
  }
}
```

Use Codex file-editing tools to write the config; do not use shell redirection for the JSON. No other files are modified.

Print a confirmation:

```text
autviam_c_config.json written.
  domain_reviewer will dispatch: gpu-kernel-reviewer, numerical-verifier
  spec_reviewer specialists    : (none)
  implementer skills           : special-skill

Re-run 'AutViam_C install' any time to update.
ExecPhase/ExecTask pick up the config automatically — no restart needed.
```

## Step 6 — Install the bundled scripts

Copy the bundled helper scripts into the host repo at a stable repo-local path. The command files already invoke them from `<skill_root>/scripts/` (so they work even without this step); this copy also places them under `.codex/scripts/`, where `references/project_sync.md` expects `update_tracker.sh`. The set: `update_tracker.sh` (Project sync), `init_plan.sh` (slug/dirs/labels/issues/map), `issue_body.sh` (issue-body roundtrip), `gate_state.py` (gate counting + task-JSON writeback), `phase_git.sh` (branch + rollback), `match_specialists.sh` (config-driven specialist matching).

```bash
mkdir -p .codex/scripts
for s in <skill_root>/scripts/*; do
  base="$(basename "$s")"
  if [ -e ".codex/scripts/$base" ]; then
    # Don't clobber a repo-customized copy — drop a .new alongside for the user to diff.
    cp "$s" ".codex/scripts/$base.new"
    echo "$base already present — wrote .codex/scripts/$base.new (diff and merge manually)."
  else
    cp "$s" ".codex/scripts/$base"; chmod +x ".codex/scripts/$base"
    echo "Installed .codex/scripts/$base"
  fi
done
```

The copy itself is plain shell (`cp`/`chmod`); only the `autviam_c_config.json` JSON in Step 5 is written with Codex file-editing tools. All scripts are best-effort / safe: the GitHub & Project scripts no-op unless `gh` is authenticated (and Project sync stays fully off until `autviam_c_config.json` → `project` names a board); the rest only run when a command invokes them, and never block a phase on failure.

## Runtime Notes

- Codex does not install custom named agents globally. Prompt profiles remain markdown files and are loaded into built-in `explorer` or `worker` agents at dispatch time.
- The config is repo-local. It is never pushed upstream to the AutViam_C skill definition.
- Trigger matching at runtime uses `git diff --name-only` plus the configured regex patterns — deterministic shell, not LLM judgment.
- The domain reviewer receives a `specialist_agents` list only when at least one changed file matches a specialist's patterns. Empty list → standard review, no specialist dispatch.
- To reset: delete `autviam_c_config.json` and re-run install, or run with `--dry-run` first.
