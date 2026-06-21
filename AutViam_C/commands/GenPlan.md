# GenPlan

The **planning gate** at the front of the AutViam_C pipeline. Turns a feature request into a verified, Plan-2-Tasks-shaped plan markdown (+ a visual companion in the frozen theme) — produced under a **manual read-only discipline** so nothing touches disk until you approve.

`gen-plan` complements the rest of AutViam_C: it produces the `<plan_file>` that `tasks` then decomposes. Pipeline: **`gen-plan` → `tasks` → `phase`×N (or `e2e`) → `diff-review`**.

**Inputs:** `$@` — the feature request / problem statement. Optional codebase path, else the working directory.

> **Codex has no plan mode.** The Claude variant of this command brackets the research phase with `EnterPlanMode`/`ExitPlanMode`, which the harness enforces. Codex has no equivalent, so the read-only gate here is a **discipline you enforce yourself**: Steps 1–5 are research, design, and an explicit approval checkpoint — **no edits, no file writes** until the user approves in Step 5. Treat "no writes before approval" as a hard rule, not a suggestion.

---

## Step 1 — Data-gather (read-only)

- Parse the request: core problem · desired user-facing behavior · constraints · explicit out-of-scope.
- **Architecture digests first (cheap context):** if `dev/architecture/*.md` digests exist for subsystems this feature touches, read those *before* diving into source — they're the token-lean map of modules, edges, and extension points produced by `AutViam_C arch`. Treat them as a starting index, not gospel: spot-verify any digest claim you'll lean on (it may predate recent changes), and prefer reading the actual code for anything the digest marks **uncertain** or doesn't cover.
- Read the relevant codebase: files to modify · existing patterns/conventions to follow · related functionality to integrate with · types/interfaces/APIs to conform to.
- Extension points: hooks/events/plugin seams · config flags · public APIs · test patterns.
- Prior art: similar features, related issues, reusable code.

## Step 2 — Design

State design (new/affected state; draw the state machine if behavior has modes) · API design (commands/functions/endpoints, signatures, error cases) · integration (how it touches existing functionality) · edge cases (concurrency, errors, boundaries, user mistakes).

## Step 3 — Verification fact-sheet (fact-check spine)

Run `commands/FactCheck.md` § inline spine over your own design: every state var, function/signature, file-to-change, edge case, and codebase assumption — each verified against the code, anything unverifiable marked **uncertain**. This fact-sheet is the source of truth for Steps 4 and 6.

## Step 4 — Decompose into AutViam_C shape

Structure the plan as **phases → tasks**, where each task maps to the fields `tasks` (Plan-2-Tasks) owns. Emit per-section line anchors so Scaffold/ExecPhase can honor "context summary first, plan only on `plan_lines` ranges."

| gen-plan section | AutViam_C plan/task field |
|---|---|
| Header + scope | plan title + overview |
| The Problem (before/after) | task `objective` + context |
| State machine / API design | `implementation_steps` |
| Edge cases | `acceptance_criteria` + `risks` |
| Test requirements | `test_plan.tier` + `test_plan.cases` |
| File references | `deliverables` / `scope` |
| Snippets / equations / diagrams / tables / constraints | `plan_assets[asset_type]` — vocab: `code_snippet, equation, diagram, table, constraint` |
| Per-section line anchors | `plan_lines` ranges per task |

## Step 5 — Present for approval → STOP and wait

Summarize the plan (phases, task count, scope, key risks, anything still **uncertain**) and **present it to the user as an explicit go/no-go checkpoint**. This is the gate: **stop here and wait for the user's reply.** Do not write anything yet.

- If the user replies "approved" (or equivalent) → proceed to Step 6.
- If the user asks for revisions → revise the design (loop back through the relevant Steps 1–4, still read-only) and re-present. Stay in the gate until you have an explicit approval.

Because Codex won't block edits for you, the only thing keeping this honest is **not calling any file-writing tool until that approval arrives.**

## Step 6 — Write (post-approval only)

Only after the user has approved:
- Write the plan markdown to `dev/plans/<slug>.md` in the Plan-2-Tasks-shaped structure from Step 4 (this is the canonical input; `tasks` reads it in full once).
- Render the **visual companion** with the frozen shell (read `references/report_shell.md`) to `dev/plans/<slug>-plan.html` — Problem (before/after), state machine, API/commands table, edge-cases table, test requirements, file references, risk callouts. It's a read-aid; the markdown is canonical. Open it.

## Step 7 — Hand off

Print the next command verbatim:

```
AutViam_C tasks dev/plans/<slug>.md
```

---

**Why a manual gate:** it makes `gen-plan` a real gate — read-only analysis + a verification fact-sheet, an explicit approval, and only then a plan on disk. In the Claude variant `EnterPlanMode`/`ExitPlanMode` enforce the read-only window; in Codex there is no such mode, so the write-after-approval ordering is enforced by discipline alone. That makes Step 5 non-negotiable: present, wait for an explicit approval, and write nothing before it.
