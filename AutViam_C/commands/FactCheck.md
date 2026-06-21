# FactCheck

Verify the factual accuracy of a document against the actual codebase and git history, correct inaccuracies **in place**, and append a verification summary. This is a fact-checker — it does **not** second-guess analysis, opinions, or design judgments, and it does not restructure the document.

It is also the shared **verification spine** that `plan-review`, `diff-review`, and `gen-plan` run inline as their "verification fact-sheet" step.

**Inputs:** `<target>` — a file path (`.md`, `.html`, or any text doc). If omitted, verify the most recently modified `.html` in `~/.agent/diagrams/` (`ls -t ~/.agent/diagrams/*.html | head -1`).

---

## Phase 1 — Extract claims

Read the file. Extract every **verifiable** claim:
- **Quantitative** — line/file/function/test counts, any numeric metric
- **Naming** — function, type, module, file-path references
- **Behavioral** — what code does, how it works, before/after comparisons
- **Structural** — architecture, dependency/import relationships, module boundaries
- **Temporal** — git history, commit attributions, timeline entries

Skip subjective content (opinions, design judgments, readability) — not verifiable.

## Phase 2 — Verify against source

For each claim, go to the source:
- Re-read every referenced file; check signatures, types, behavior against the actual code.
- Git claims → re-run `git diff --stat`, `git log`, `git diff --name-status` and compare numbers.
- Before/after claims → read both sides (`git show <ref>:file` vs working tree) so they aren't swapped or fabricated.

Classify each: **Confirmed** (matches) · **Corrected** (was wrong — note old → new) · **Unverifiable** (can't be checked / references something absent).

## Phase 3 — Correct in place

Surgical text replacements only:
- Fix wrong numbers, names, paths, behavior descriptions; fix before/after swaps.
- If a section is fundamentally wrong (not a detail), rewrite its content while preserving surrounding structure.
- HTML: preserve layout, the frozen theme, animations, and any diagrams (unless a label is factually wrong). Markdown: preserve heading structure and organization.

## Phase 4 — Verification summary

- **HTML**: insert a verification `.card` (a subtle, muted one) as the final section, using the frozen theme — read `references/report_shell.md` for the shell classes. Do not restyle the page.
- **Markdown**: append a `## Verification Summary` section.

Include: total claims checked · confirmed (count) · corrections (brief list, e.g. "`processCleanup` → `runCleanup` per `worker.ts:45`") · unverifiable claims flagged.

## Phase 5 — Report

Tell the user what was checked, what was corrected, and open the file (HTML in browser; markdown path in chat). If nothing needed correcting, say so — the confirmation still has value.

Write corrections to the original file.

---

**As an inline spine** (called from plan-review / diff-review / gen-plan): run Phases 1–2 only and emit the structured fact-sheet — every claim with its source `file:line` or git command, classified, with anything unverifiable marked **uncertain rather than stated as fact**. That fact-sheet is the caller's source of truth during HTML generation; the caller does not deviate from it.
