# GenPlan

The **planning gate** at the front of the AutViam pipeline. Turns a feature request into a verified, Plan-2-Tasks-shaped plan markdown (+ a visual companion in the frozen theme) — produced inside **plan mode** so nothing touches disk until you approve.

`gen-plan` complements the rest of AutViam: it produces the `<plan_file>` that `tasks` then decomposes. Pipeline: **`gen-plan` → `tasks` → `phase`×N (or `e2e`) → `diff-review`**.

**Inputs:** `$@` — the feature request / problem statement. Optional codebase path, else the working directory. Optional `branch=this` → fork the plan branch from the current branch instead of `main` (see Step 6).

---

## Step 0 — Enter plan mode

Call **`EnterPlanMode`**. Everything in Steps 1–4 is read-only research and design — **no edits, no file writes** until after approval. (Plan mode forbids edits; respect it.)

## Step 1 — Data-gather (read-only)

- Parse the request: core problem · desired user-facing behavior · constraints · explicit out-of-scope.
- **Architecture digests first (cheap context):** if `dev/architecture/*.md` digests exist for subsystems this feature touches, read those *before* diving into source — they're the token-lean map of modules, edges, and extension points produced by `/AutViam arch`. Treat them as a starting index, not gospel: spot-verify any digest claim you'll lean on (it may predate recent changes), and prefer reading the actual code for anything the digest marks **uncertain** or doesn't cover.
- Read the relevant codebase: files to modify · existing patterns/conventions to follow · related functionality to integrate with · types/interfaces/APIs to conform to.
- Extension points: hooks/events/plugin seams · config flags · public APIs · test patterns.
- Prior art: similar features, related issues, reusable code.

## Step 2 — Design

State design (new/affected state; draw the state machine if behavior has modes) · API design (commands/functions/endpoints, signatures, error cases) · integration (how it touches existing functionality) · edge cases (concurrency, errors, boundaries, user mistakes).

## Step 3 — Verification fact-sheet (fact-check spine)

Run `commands/FactCheck.md` § inline spine over your own design: every state var, function/signature, file-to-change, edge case, and codebase assumption — each verified against the code, anything unverifiable marked **uncertain**. This fact-sheet is the source of truth for Steps 4 and 6.

## Step 4 — Decompose into AutViam shape

Structure the plan as **phases → tasks**, where each task maps to the fields `tasks` (Plan-2-Tasks) owns. Emit per-section line anchors so Scaffold/ExecPhase can honor "context summary first, plan only on `plan_lines` ranges."

| gen-plan section | AutViam plan/task field |
|---|---|
| Header + scope | plan title + overview |
| The Problem (before/after) | task `objective` + context |
| State machine / API design | `implementation_steps` |
| Edge cases | `acceptance_criteria` + `risks` |
| Test requirements | `test_plan.tier` + `test_plan.cases` |
| File references | `deliverables` / `scope` |
| Snippets / equations / diagrams / tables / constraints | `plan_assets[asset_type]` — vocab: `code_snippet, equation, diagram, table, constraint` |
| Per-section line anchors | `plan_lines` ranges per task |

## Step 5 — Present for approval → ExitPlanMode

Summarize the plan (phases, task count, scope, key risks, anything still **uncertain**) and call **`ExitPlanMode`** for the user's go/no-go. Do not write anything yet.

## Step 6 — Write (post-approval; edits re-enabled)

Only after approval:
- Write the plan markdown to `dev/plans/<slug>.md` in the Plan-2-Tasks-shaped structure from Step 4 (this is the canonical input; `tasks` reads it in full once).
- Render the **visual companion** with the frozen shell (read `references/report_shell.md`) to `dev/plans/<slug>-plan.html` — Problem (before/after), state machine, API/commands table, edge-cases table, test requirements, file references, risk callouts. It's a read-aid; the markdown is canonical. Open it.
- **Create the plan branch** (SKILL.md § Branch & Worktree Model): → `<skill_root>/scripts/phase_git.sh plan-branch <slug>` forks `<slug>` from `main` **without checkout**, so `Plan-2-Tasks` can claim it for the plan worktree. If `branch=this` was passed, fork from the current branch instead: `<skill_root>/scripts/phase_git.sh plan-branch <slug> --from "$(git branch --show-current)"`. (Idempotent — `Plan-2-Tasks` re-runs it for hand-written plans that skipped `gen-plan`.)

## Step 7 — Hand off

Print the next command verbatim:

```
/AutViam tasks dev/plans/<slug>.md
```

---

**Why plan mode:** it makes `gen-plan` a real gate — read-only analysis + a verification fact-sheet, an explicit approval, and only then a plan on disk. The write-after-approval ordering is non-negotiable: plan mode forbids edits, so Steps 6–7 must follow `ExitPlanMode`.
