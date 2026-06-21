# PlanReview

Generate a self-contained HTML review comparing the **current codebase** against a **proposed plan** — risk, blast radius, and a structured critique. Use the frozen report shell (read `references/report_shell.md`). No aesthetic choice, no `surf` images, no Mermaid zoom machinery; diagrams are optional and, when used, kept simple.

**Inputs:** `<plan_file>` (`$1`, path to a markdown plan/spec/RFC). Codebase = `$2` if given, else the working directory.

---

## Data gathering

1. **Read the plan in full.** Extract: problem/motivation · each proposed change (files modified/created/deleted) · rejected alternatives + reasoning · explicit non-goals.
2. **Read every file the plan references** — in full — plus files that import/depend on them (ripple the plan may not mention).
3. **Map the blast radius:** what imports the changed files (grep import paths) · existing tests for them (`.test.*`/`.spec.*` / `tests/`) · configs/types/schemas that may need updates · public API callers depend on.
4. **Cross-reference plan vs code:** does each referenced file/function/type actually exist? Does the plan's description of *current* behavior match the code? Any structural assumptions that don't hold?

## Verification checkpoint (run the fact-check spine)

Before writing HTML, produce the **fact-sheet** per `commands/FactCheck.md` § inline spine: every figure, name, and behavior claim you'll present, each cited to the plan section or `file:line`. Mark anything unverifiable as **uncertain**, not fact. This is your source of truth during generation — do not deviate.

## Report structure (frozen shell — tabs or stacked cards)

1. **Plan summary** — lead with the *intuition*: what problem, what's the core insight; then scope (files touched, scale, new modules/tests). Hero `.card`.
2. **Impact** — files to modify/create/delete, est. lines, new tests, deps affected. Add a **completeness** row: tests covered (green/red), docs (green/yellow/red), migration/rollback (green/grey N/A). A `.tbl-scroll` table or badge row.
3. **Current → planned** — *optional* simple before/after of the touched subsystem as a table or short text (only the parts the plan changes; don't diagram the whole codebase).
4. **Change-by-change** — per change, a card: **current** (what the code does now, signatures/snippets) · **planned** (what the plan proposes) · **rationale** (pull from the plan's reasoning / rejected-alternatives; flag changes that say *what* but not *why* — pre-implementation cognitive debt) · flag any mismatch between the plan's "current behavior" and the actual code.
5. **Dependency & ripple** — callers/importers/downstream the plan may miss. Color-code: covered (green) · likely-affected-but-unmentioned (amber) · definitely-missed (red). Compact (`<details>` if long).
6. **Risk** — cards for edge cases not addressed · assumptions to verify · ordering risks · rollback complexity · **cognitive-complexity** flags (non-obvious coupling, action-at-a-distance, memory-only contracts) each with a one-line mitigation. Severity low/med/high.
7. **Plan review** — the Good/Bad/Ugly/Questions `.gbu` block (see report_shell). Each item cites a plan section + code file. Empty category → "None found".
8. **Understanding gaps** — roll up: count of changes with clear vs missing rationale, the cognitive-complexity flags, and explicit "document X before implementing" recommendations. Makes cognitive debt visible *before* work starts.

Current = neutral/blue, planned additions = green/accent, concern = amber, gap/risk = red. Write to `~/.agent/diagrams/`, open it, tell the user the path.
