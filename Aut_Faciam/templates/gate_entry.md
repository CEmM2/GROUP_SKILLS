# Gate History Format

Each phase gets a file: `<tasks_folder>/gates/phase_<N>_gates.md`

Hybrid format: prose for BM25/semantic search across past failures, JSON blocks for programmatic parsing. Prose should use domain language so future searches match on concepts, not task IDs.

## Per-attempt format

````markdown
#### Attempt <n> — <PASS|FAIL>
<1–2 sentences in domain language: what happened, what fixed it (on PASS), or what failed and why (on FAIL).>

```json
{"gate":"A","attempt":1,"result":"fail","failure_mode":"missing_impl",
 "what_failed":"…","why":"…","resolution":"…","timestamp":"<ISO>"}
```
````

The JSON carries `failure_mode`, `what_failed`, `why`, `resolution` — keep prose short and domain-rich rather than restating those fields.

## File Structure

```markdown
# Phase <N> Gate History

Plan: `<plan_file>` · Branch: `<branch_name>`

---

## <task_id>: <task_title>

**Issue:** #<task_issue_number>
**Started:** <ISO> · **Completed:** <ISO or "in progress">

### Gate A — Spec Compliance
<one or more attempt blocks>

### Gate B — Domain Quality
<one or more attempt blocks>

### Gate C — Verification
<one attempt block; on PASS include test_results + commit in the JSON>
```

## Canonical example (one per file is enough)

````markdown
#### Attempt 1 — FAIL
Boundary condition handler missing: task required Dirichlet BC enforcement on the displacement field but only the interior solver loop was implemented; acceptance criterion #3 had no corresponding code.

```json
{"gate":"A","attempt":1,"result":"fail","failure_mode":"missing_impl",
 "what_failed":"AC#3 displacement BCs at constrained nodes",
 "why":"implementer missed the BC scope in spec","timestamp":"<ISO>"}
```

#### Attempt 2 — PASS
Added `BoundaryConditionHandler.apply_dirichlet()` in `boundary.py`; reads constrained DOFs from mesh config and enforces via penalty method. Satisfies AC#3.

```json
{"gate":"A","attempt":2,"result":"pass",
 "resolution":"BoundaryConditionHandler.apply_dirichlet via penalty","timestamp":"<ISO>"}
```
````

## Key Principles

1. **Prose first, JSON second.** Prose is what searches match on — write in domain terms.
2. **Self-contained failures.** A reader should grasp what went wrong without opening the task JSON or plan.
3. **Resolution closes the loop.** Every failure is followed by a passing attempt that names what fixed it — the most valuable part for future reference.
4. **Use the failure-mode taxonomy below** so entries are programmatically aggregable.

## Failure Mode Taxonomy

| Category | Meaning | Search terms |
|----------|---------|--------------|
| `missing_impl` | Required feature not implemented | missing, not implemented, skipped |
| `extra_work` | Unrequested features added | extra, over-engineered, YAGNI |
| `misunderstanding` | Requirement interpreted incorrectly | misread, wrong interpretation |
| `physics_error` | Constitutive/numerical correctness issue | physics, numerical, convergence, tensor |
| `test_gap` | Insufficient test coverage | coverage, untested, edge case |
| `style_violation` | Code quality or convention issue | style, naming, convention |
| `integration_break` | Broke something outside task scope | regression, broke, side effect |
