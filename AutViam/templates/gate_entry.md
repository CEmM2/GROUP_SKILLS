# Gate History Format

Each phase gets a file: `<tasks_folder>/gates/phase_<N>_gates.md`.

Hybrid format: prose for BM25/semantic search across past failures, JSON blocks for programmatic parsing. Prose uses domain language so future searches match on concepts, not task IDs.

Failure-mode taxonomy lives in `references/failure_modes.md` — refer to it when classifying a failure.

## Per-attempt format

````markdown
#### Attempt <n> — <PASS|FAIL>
<1–2 sentences in domain language: what happened; what fixed it (PASS) or what failed and why (FAIL).>

```json
{"gate":"A","attempt":1,"result":"fail","failure_mode":"missing_impl",
 "what_failed":"…","why":"…","timestamp":"<ISO>"}
```

(`resolution` belongs to the PASS attempt that follows a FAIL — see the canonical example below.)
````

JSON fields:
- `gate`: `"A"`, `"B"`, or `"C"`
- `attempt`: int (1-indexed)
- `result`: `"pass"` or `"fail"`
- `failure_mode`: one of the values in `references/failure_modes.md` (FAIL only)
- `what_failed`, `why`: short strings (FAIL only)
- `resolution`: short string naming the fix (PASS attempt that follows a FAIL)
- `test_results`: object `{"passed":N,"total":N}` (Gate C PASS only)
- `commit`: SHA (Gate C PASS only)
- `timestamp`: ISO 8601

## File structure

```markdown
# Phase <N> Gate History

Plan: `<plan_file>` · Branch: `<branch_name>`

---

## <task_id>: <task_title>

**Started:** <ISO> · **Completed:** <ISO or "in progress">
**Failure counters:** A=<n> B=<n> C=<n>

### Gate A — Spec Compliance
<one or more attempt blocks>

### Gate B — Domain Quality
<one or more attempt blocks>

### Gate C — Verification
<one attempt block; on PASS include test_results + commit in the JSON>
```

## Gate-cap-hit status block (4th failure on same gate)

When a task hits the cap, append this block to its task section:

````markdown
## STATUS: gate-cap-hit on Gate <X>

Failures (all on Gate <X>):
1. <one-line summary from Attempt 1's prose>
2. <one-line summary from Attempt 2's prose>
3. <one-line summary from Attempt 3's prose>
4. <one-line summary from Attempt 4's prose>

User decision: <pending | take-over | retry-with-instructions | skip | rollback | stop>
````

Once the user's decision is recorded, append a brief note describing what was done.

## Canonical example

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

## Key principles

1. **Prose first, JSON second.** Prose is what searches match on — write in domain terms.
2. **Self-contained failures.** A reader should grasp what went wrong without opening the task JSON or plan.
3. **Resolution closes the loop.** Every failure is followed by a passing attempt that names what fixed it.
4. **3-failure cap is real.** If the 4th attempt fails, stop. Don't keep retrying past the cap.
