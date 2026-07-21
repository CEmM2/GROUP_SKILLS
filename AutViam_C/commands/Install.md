# Install

Installs and validates AutViam_C's explicit Path-2 runtime profiles, then scans the host repo for optional prompt lenses and skills, presents a categorisation plan, and writes `autviam_c_config.json`.

Run once per repo after initial install. Re-run after adding new repo-local prompt profiles or skills, or when you want to change the integration. Idempotent — re-running overwrites only what you confirm.

**Inputs:**
- `[--dry-run]` — show the proposed plan without writing anything

---

## Step 0 — Install and validate required runtime profiles

Generate the nineteen managed custom profiles under the consumer repository's `.codex/agents/`:

```bash
python <skill_root>/scripts/install_agent_profiles.py \
  --skill-root <skill_root> \
  --repo-root <repo_root> \
  --output-dir <repo_root>/.codex/agents
```

For `--dry-run`, pass `--dry-run` to the installer. It validates generated TOML in memory and reports intended writes without changing the repo. Do not run the installed-profile validator in dry-run mode unless all nineteen managed profiles already exist.

The installer updates only files bearing its managed marker. On an unmanaged filename collision it writes `<name>.toml.new`, reports an incomplete installation, and exits nonzero; stop and ask the user to reconcile the collision. Never overwrite an unmanaged profile automatically.

When upgrading from the 16-profile layout, the installer retires only its three managed generic `reviewer-*.toml` files after replacing them with separate Gate A and Gate B families. Same-named unmanaged files are preserved.

After a real install, validate the complete policy and all profiles:

```bash
python <skill_root>/scripts/validate_codex_agent_routing.py \
  --policy <skill_root>/references/codex-agent-routing.json \
  --agents-dir <repo_root>/.codex/agents
```

Any nonzero result is fatal. Do not continue to configuration or dispatch. This validator proves policy, source rendering, and installed TOML consistency; it cannot prove that the active Codex account/runtime can dispatch every pinned model.

When installation succeeds, tell the user to start a new Codex session so the custom profiles are discoverable. In that new session, perform a bounded live smoke check before the first real AutViam_C run:

1. Resolve and dispatch one `mechanical_read_only` task scored 1/1 through `search_luna_medium`; require the returned subagent to answer only `PASS`.
2. Resolve and dispatch representative Terra and Sol read-only routes the same way.
3. Confirm each live subagent reports the exact profile/model selected by the resolver.

If any custom profile or pinned model (especially Luna) is unavailable, Path 2 is blocked in that runtime. Do not substitute a built-in profile or a different model, and do not claim runtime verification from the static validator alone.

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
  "nested_dispatch": "off",
  "project": "disable",
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

The bundled scripts already live at `<skill_root>/scripts/` (`.codex/skills/AutViam_C/scripts/`) — distribution placed them there, and that is the **single** copy everything uses:
- command files call them as `<skill_root>/scripts/<name>`;
- `install_agent_profiles.py`, `resolve_codex_agent.py`, and `validate_codex_agent_routing.py` own Path-2 profile installation, resolution, evidence, and exhaustive validation;
- `expand_codex_agents.py` is a deprecated compatibility entry point that exits nonzero and directs callers to `install_agent_profiles.py`; template-derived profiles cannot satisfy Path 2's exact managed-source validation;
- `project_sync.sh` finds its sibling `update_tracker.sh` in the same dir (`$HERE/update_tracker.sh`);
- the Step 7 hook points at `<skill_root>/scripts/phase-close.sh`, which resolves its siblings (`issue_body.sh`, `project_sync.sh`, `draft_pr.sh`) from that dir too.

There is **no second `.codex/scripts/` copy** — one location, nothing to keep in sync. If you use the GitHub Project board and want fixed defaults, drop an optional `tracker.env` (`TRACKER_OWNER`/`TRACKER_NUMBER`) **beside** `update_tracker.sh` at `<skill_root>/scripts/tracker.env`; otherwise `project_sync.sh` resolves the board from `autviam_c_config.json` → `project`.

The scripts are best-effort / safe: the GitHub & Project scripts no-op unless `gh` is authenticated (and Project sync stays off until `autviam_c_config.json` → `project` names a board); the rest only run when a command invokes them, and never block a phase on failure.

## Step 7 — Wire the phase-close backstop hook (optional)

`scripts/phase-close.sh` is a **PostToolUse backstop**: when ExecPhase writes a `Handoff_Phase_<N>.md`, it finalizes the just-completed phase (closes the phase issue, sets its Project item to Done) even if the in-band Step 10b close was interrupted. It is idempotent with the in-band path and a silent no-op for every non-handoff write, so it is safe to leave always-on. The script reads the same PostToolUse stdin JSON (`.tool_input.file_path`) that Codex hooks already use, so no Codex-specific adaptation is needed.

Wire it once per repo as a PostToolUse hook on `Edit|Write` in `.codex/hooks.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "command": "bash \"$CLAUDE_PROJECT_DIR/.codex/skills/AutViam_C/scripts/phase-close.sh\"", "timeout": 30 }
        ]
      }
    ]
  }
}
```

Using `$CLAUDE_PROJECT_DIR` (not a relative path) keeps the hook resolving correctly from any working directory, including a plan worktree. Skipping this step breaks nothing — ExecPhase Step 10b still closes phases in-band; the hook only adds a backstop for interrupted runs. Verify with `printf '{"tool_input":{"file_path":"/tmp/x.py"}}' | bash .codex/skills/AutViam_C/scripts/phase-close.sh; echo $?` → prints `0` and nothing else.

**Merge-method labels + repo settings (one-time, best-effort).** The draft PRs `phase-close.sh`/ExecPhase open are labelled `merge:commit` (phase→plan) and `merge:squash` (plan→main) — GitHub can't pin a per-PR merge method, so the label records intent for the eventual `gh pr merge --merge`/`--squash`. Create the labels and allow both methods on the repo:

```bash
gh label create merge:commit --color 1d76db --description "AutViam_C: merge-commit this PR at merge time" --force
gh label create merge:squash --color 0e8a16 --description "AutViam_C: squash this PR at merge time" --force
gh api -X PATCH "repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)" -F allow_merge_commit=true -F allow_squash_merge=true >/dev/null 2>&1 || true
```

(The labels also auto-create on first PR; the repo-settings PATCH needs admin and is best-effort.)

## Runtime Notes

- **`nested_dispatch`** (default `"off"`) controls E2E execution: `"off"` runs each phase inline in the main thread; `"on"` uses the routed custom orchestrator profile; `"auto"` performs one routed nesting probe and falls back to `"off"`. Leave it `"off"` unless this Codex runtime lets the custom orchestrator spawn routed subagents. See `commands/E2E.md` § Nested-Dispatch capability.
- Nested orchestrator mode normally requires `[agents] max_depth = 2` in the active Codex `config.toml`; Codex defaults to depth 1. Do not change this automatically—tell the user when `nested_dispatch` is `on` or `auto` and let the capability probe verify it.
- **`project`** (default `"disable"`) turns on native GitHub Project sync: set it to a board name (or `{owner,name}` / `{owner,number}`) and AutViam_C adds plan/phase issues to that Project and keeps their Status field in step with the issue lifecycle. `"disable"` (or absent) = no Project calls at all. See `references/project_sync.md`.
- The six bundled Markdown files are the canonical role-behavior sources. The generated `.codex/agents/*.toml` files embed one source body each and add Codex model, effort, sandbox, and serialization metadata; dispatches use the TOML profile directly and do not reload the Markdown.
- Every dispatch must run `resolve_codex_agent.py` and use exactly its `agent` result. Built-in `worker`, `explorer`, and `default` profiles and parent model/effort inheritance are prohibited.
- The config is repo-local. It is never pushed upstream to the AutViam_C skill definition.
- Trigger matching at runtime uses `git diff --name-only` plus the configured regex patterns — deterministic shell, not LLM judgment.
- The domain reviewer receives a `specialist_agents` list only when at least one changed file matches a specialist's patterns. Empty list → standard review, no specialist dispatch.
- To reset: delete `autviam_c_config.json` and re-run install, or run with `--dry-run` first.
