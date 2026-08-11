# Failure Mode Taxonomy

Use these categories consistently in every gate-failure entry. The `failure_mode` field in the JSON block of `gate_entry.md` must be one of these strings — they are the search index keys for finding prior similar failures.

| Category | Meaning | Search hints |
|---|---|---|
| `missing_impl` | Required feature not implemented | missing, not implemented, skipped, AC unaddressed |
| `extra_work` | Unrequested features added | extra, over-engineered, YAGNI, scope creep |
| `misunderstanding` | Requirement interpreted incorrectly | misread, wrong interpretation, off-spec |
| `physics_error` | Constitutive/numerical correctness issue | physics, numerics, convergence, tensor, conjugacy |
| `test_gap` | Insufficient test coverage | coverage, untested, edge case, no assertion |
| `style_violation` | Code quality or convention issue | style, naming, convention, lint |
| `integration_break` | Broke something outside the task's scope | regression, broke, side effect, downstream |

## Why these matter

Before dispatching an implementer for any task, scan `gates/phase_*_gates.md` for prior failures matching the task's risk profile (physics-heavy task → search `physics_error`; integration-heavy task → search `integration_break`). The resolution recorded against the passing follow-up attempt is usually directly applicable.

The cap at 3 failures per gate (see SKILL.md § Gate Failure Cap) means each failure entry needs a real `resolution` field — not just a category. Empty resolutions are signal that the loop is thrashing.
