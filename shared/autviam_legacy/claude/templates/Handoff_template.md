# Phase <phase_id> Handoff

> **Authoring rule:** skip any section, table row, or header below that has no
> content for this phase. Do not carry empty placeholders forward — drop them.

> **From**: Phase <phase_id> agent  
> **To**: Phase <phase_id+1> agent  
> **Date**: YYYY-MM-DD  
> **Branch**: <branch_name>  
> **Plan**: <plan_file_path>  

---

## Skills to Load Before Starting

<!-- List skills relevant to Phase <phase_id+1> based on the task types involved.
     Check the project's CLAUDE.md for available domain skills. -->
- <skill relevant to next phase's tasks>

---

## Phase <phase_id> Completion Summary

| Task ID | Title | Commit | Tests (pass/total) | Failing Tests |
|---------|-------|--------|--------------------|---------------|
|         |       |        |                    |               |

**Overall test status**: X/Y task-dedicated tests passing across the phase.

---

## Routing Summary

| Task ID | Purpose | Agent | Model | Effort | Capability | Parent | Depth | Policy | Enforcement |
|---------|---------|-------|-------|--------|------------|--------|-------|--------|-------------|
|         |         |       |       |        |            |        |       |        | hook / procedural / externally-overridden |

**Routing evidence:** `<tasks_folder>/json/<task_id>.json#routing_evidence` and `<routing_ticket_path>`

---

## Session Reset Packet

> Use this after clearing the Codex/Claude session. It should be short enough to read first,
> but specific enough to decide whether a task should be fixed now, deferred, or retried
> by an agent with extra instructions.

**Next command:** `/AutViam scaffold <phase_id+1> <plan_file>` or `/AutViam exec <phase_id+1> <plan_file>`

| Task ID | Title | Status | Gate A Score | Gate B Score | Gate C | Decision |
|---------|-------|--------|--------------|--------------|--------|----------|
|         |       | done / skipped / gate-cap-hit | 10/10 | 9/10 | pass/total | fix now / defer / retry / accept |

### Gate Findings

- **<task_id> — <title>**
  - **Gate A:** <score>/10. <1 sentence: spec compliance finding, or "clean pass; no actionable findings.">
  - **Gate B:** <score>/10. <1 sentence: domain/code-quality finding, or "clean pass; no actionable findings.">
  - **Recommended action:** <fix now | defer | retry with instructions | accept>. <short reason.>

---

## Architecture and State After Phase <phase_id>

> What the codebase looks like NOW. The next agent must understand this before touching anything.

- **New files created**: (paths + one-line purpose each)
- **Modified files**: (paths + what changed)
- **New Taichi fields/kernels**: (names, shapes, dtypes, what they represent)
- **Data layout changes**: (anything that affects how other modules read/write state)
- **Interfaces added or changed**: (function signatures, class APIs, config keys)

---

## Assumptions Made During Phase <phase_id>

> Decisions taken that were not explicit in the spec. These may need revisiting.

| Assumption | Where it applies | Rationale | Risk if wrong |
|------------|-----------------|-----------|---------------|
|            |                 |           |               |

---

## Known Issues and Deferred Concerns

### Failing tests (quantified)
| Test name/file | Failure reason | Impact on Phase <phase_id+1> |
|----------------|---------------|------------------------------|
|                |               |                              |

### Known bugs or behavioral limitations
> Issues observed but intentionally out of scope for this phase.

### Test coverage gaps
> Behaviors that are untested or only partially tested. Flag anything where a gap could affect Phase <phase_id+1> correctness.

---

## Lessons Learned

### Process
> Parallelism conflicts, subagent coordination issues, review loop patterns, etc.

### Physics and numerics
> Constitutive model behavior, solver tolerance surprises, stability issues, convergence patterns, etc.

---

## What Phase <phase_id+1> Must Know Before Starting

> High-signal context that is NOT obvious from reading the plan or the task files.

- **Critical dependencies**: which Phase <phase_id> outputs Phase <phase_id+1> tasks directly consume
- **High-risk tasks in Phase <phase_id+1>**: flag the 1-2 tasks most likely to cause problems and why
- **Recommended starting point**: which task to tackle first and why
- **Anything that would have saved Phase <phase_id> significant time if known at the start**
