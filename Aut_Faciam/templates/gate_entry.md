# Gate History Format

Each phase gets a file: `<tasks_folder>/gates/phase_<N>_gates.md`

This hybrid format combines searchable prose (for BM25/semantic search across past failures) with embedded JSON blocks (for programmatic parsing). The prose should be written in natural language that captures the *why* — future searches will match on domain concepts, not just task IDs.

## File Structure

```markdown
# Phase <N> Gate History

Generated during ExecPhase/ExecTask execution.
Plan: `<plan_file>`
Branch: `<branch_name>`

---

## <task_id>: <task_title>

**Issue:** #<task_issue_number>
**Started:** <ISO timestamp>
**Completed:** <ISO timestamp or "in progress">

### Gate A — Spec Compliance

#### Attempt 1 — FAIL

The spec compliance reviewer found that <describe what was missing or wrong in plain
language, including domain-specific terms that would make this discoverable by search>.

For example: "The boundary condition handler was not implemented. The task required
Dirichlet BC enforcement on the displacement field, but the implementer only handled
the interior solver loop. The reviewer flagged that acceptance criterion #3
(displacement BCs at constrained nodes) had no corresponding code."

**Failure mode:** `missing_impl`
**What failed:** <specific description — which acceptance criteria, which deliverable>
**Why:** <root cause — why did the implementer get this wrong?>

```json
{"gate": "A", "attempt": 1, "result": "fail", "timestamp": "<ISO>", "failure_mode": "missing_impl", "what_failed": "<brief>", "why": "<brief>"}
```

#### Attempt 2 — PASS

<Describe what was changed to resolve the previous failure. Again, use domain language.>

For example: "Added BoundaryConditionHandler class in boundary.py with apply_dirichlet()
method. The handler reads constrained DOFs from the mesh config and enforces them via
penalty method. This satisfies acceptance criterion #3."

**Resolution:** <what the implementer changed to fix attempt 1's failure>

```json
{"gate": "A", "attempt": 2, "result": "pass", "timestamp": "<ISO>", "resolution": "<brief>"}
```

### Gate B — Domain Quality

#### Attempt 1 — PASS

<Brief note on what the reviewer confirmed.>

```json
{"gate": "B", "attempt": 1, "result": "pass", "timestamp": "<ISO>"}
```

### Gate C — Verification

#### Attempt 1 — PASS

All task-relevant tests pass. Evidence: 12/12 tests passed (100%).
Commit: `<sha>`

```json
{"gate": "C", "attempt": 1, "result": "pass", "timestamp": "<ISO>", "test_results": {"passed": 12, "total": 12, "percentage": 100}, "commit": "<sha>"}
```

---

## <next_task_id>: <next_task_title>

...
```

## Key Principles

1. **Prose first, JSON second.** The prose sections are what future searches will match on. Write them in domain language — "constitutive model", "stress tensor symmetry", "solver convergence" — not just "the test failed." The JSON embeds are for tooling.

2. **Failure descriptions should be self-contained.** Someone reading a failure entry should understand what went wrong without needing to open the task JSON or plan. Include which acceptance criteria, which deliverables, and which files were involved.

3. **Resolution descriptions close the loop.** Every failure must eventually have a corresponding resolution (on the passing attempt that follows). This is the most valuable part for future reference — "we hit X, and Y fixed it."

4. **Failure mode categories must be from the taxonomy** defined in SKILL.md. This enables programmatic aggregation across phases.

## Failure Mode Taxonomy

| Category | Meaning | Search terms (for discovery) |
|----------|---------|------------------------------|
| `missing_impl` | Required feature not implemented | missing, not implemented, skipped, omitted |
| `extra_work` | Unrequested features added | extra, unnecessary, over-engineered, YAGNI |
| `misunderstanding` | Requirement interpreted incorrectly | misread, wrong interpretation, confused |
| `physics_error` | Constitutive/numerical correctness issue | physics, numerical, convergence, stability, tensor, constitutive |
| `test_gap` | Insufficient test coverage | coverage, untested, missing test, edge case |
| `style_violation` | Code quality or convention issue | style, naming, convention, pattern |
| `integration_break` | Broke something outside task scope | regression, broke, side effect, downstream |
