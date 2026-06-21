# DiffReview

Generate a self-contained HTML review of a code diff — before/after, structured code review, decision log, and re-entry context. Use the frozen report shell (read `references/report_shell.md`). No aesthetic choice, no `surf` images, no Mermaid zoom machinery.

**Scope detection** from `$1`:
- branch name → working tree vs that branch · commit hash → `git show <hash>` · `HEAD` → uncommitted (`git diff` + `--staged`) · PR number `#42` → `gh pr diff 42` · range `a..b` → that range · no arg → default `main`.

---

## Data gathering

- `git diff --stat <ref>` and `git diff --name-status <ref> --` (separate src from tests).
- Line counts on key files (`git show <ref>:file | wc -l` vs `wc -l`).
- New public API surface: grep added lines for exported symbols (adapt to the language — `def`/`class` for Python, `export`/`function`/`class`/`interface` for TS, etc.).
- Read all changed files in full, including surrounding code needed to judge behavior.
- Housekeeping: is `CHANGELOG.md` updated? Do `README.md`/`docs/*.md` need updates for new/changed features?
- Reconstruct decision rationale: mine this session's conversation for approaches discussed and alternatives rejected; read commit messages / PR descriptions for committed work.

## Verification checkpoint (run the fact-check spine)

Produce the **fact-sheet** per `commands/FactCheck.md` § inline spine: every line/file/function count and every name/behavior claim, cited to the git command or `file:line`. Mark unverifiable items **uncertain**. Source of truth during generation.

## Report structure (frozen shell — tabs or stacked cards)

1. **Executive summary** — lead with *intuition* (why these changes exist, the core insight), then factual scope (X files, Y lines, Z modules). Hero `.card`.
2. **Metrics** — lines +/−, files changed, new modules, test counts, as a compact card/table. **Housekeeping** badges: CHANGELOG updated (green/red), docs needed (green/yellow/red).
3. **Major changes** — before/after panels per significant area (data flow, API, config, UI). Snippets only; `overflow-wrap:break-word`.
4. **File map** — changed-file tree with new/modified/deleted indicators. Compact (`<details>` if long).
5. **Test coverage** — before/after test counts and what's covered.
6. **Code review** — Good/Bad/Ugly/Questions `.gbu` block. **Bad** = concrete bugs/regressions/missing error handling; **Ugly** = tech debt / maintainability / works-now-bites-later. Each cites file + line range. Empty → "None found".
7. **Decision log** — per significant design choice: **Decision** (one line) · **Rationale** (constraints/trade-offs; from conversation if available, inferred from code if not) · **Alternatives** rejected · **Confidence**: High (sourced — green) / Medium (inferred — blue, label "inferred") / Low (not recoverable — amber, "document before committing"). Low-confidence cards are cognitive-debt hotspots.
8. **Re-entry context** — note from present-you to future-you: **key invariants** not enforced by types/tests · **non-obvious coupling** · **gotchas** (ordering deps, implicit contracts) · **don't forget** (follow-up migrations/config/docs). Compact.

Red = removed/before, green = added/after, amber = modified, blue = neutral context. Write to `~/.agent/diagrams/`, open it, tell the user the path.

> `gen-plan`/AutViam tie-in: run `diff-review` after a phase or a full run to review what was implemented against the plan. Its sibling `arch --feature <plan_file>` answers the other half — not "is this diff good?" but "what is the feature's architecture now?" — and persists a planning digest under `dev/architecture/`. `diff-review` is the transient verdict; `arch` is the durable map.
