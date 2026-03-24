Task tool (general-purpose):
  model: [assigned per Step 2 model rules]
  description: "Implement Task <task_id>: <task_title>"
  prompt: |
    You are implementing Task <task_id>: <task_title>

    ## Task Description

    <PASTE FULL CONTENT OF TASK JSON HERE>

    ## Phase Context

    <summary of what this phase accomplishes and how this task fits in>
    <any relevant constraints from the plan or handoff file>
    <architectural context: patterns in use, existing abstractions to follow>

    ## Before You Begin

    If you have questions about:
    - The requirements or acceptance criteria
    - The approach or implementation strategy
    - Dependencies, assumptions, or physics correctness
    - Anything unclear in the task description

    **Ask them now.** Raise any concerns before starting work.

    ## Your Job

    Once you are clear on requirements:
    1. Implement exactly what the task specifies — nothing more, nothing less
    2. Before writing any code, read `test_artifacts` and `verification_commands` from the task JSON.
       The scaffold pass has already classified each test case — act accordingly:
       - `covered`: run the existing test immediately as a baseline; it must pass after implementation
       - `partial`: a stub exists — flesh it out into a real, asserting test before implementing,
         then make it pass (TDD red-green)
       - `missing`: a stub exists with `pytest.skip` — replace the skip with real assertions before
         implementing, then make it pass (TDD red-green)
       If `test_artifacts` is empty or missing, generate dedicated tests before implementing.
    3. Run all task-relevant tests (existing + fleshed-out stubs); iterate until ≥ 95% pass
    4. Dry-run failure-route analysis: read every file you modified and identify failure paths
       not covered by any test. For each uncovered path, write an additional test and
       re-iterate until ≥ 95% of ALL task-relevant tests pass (including newly added ones)
    5. Commit your work (separate commit if complexity OR risk ≥ 3)
    6. Self-review (see below)
    7. Report back

    Work from: <working directory>

    **While you work:** If you encounter something unexpected or unclear, ask questions.
    It is always OK to pause and clarify. Do not guess or make assumptions — especially
    on physics, constitutive model behavior, or numerical stability.

    ## Before Reporting Back: Self-Review

    Review your work with fresh eyes. Ask yourself:

    **Completeness:**
    - Did I implement everything in the spec?
    - Are there requirements I skipped or misread?
    - Are there edge cases I did not handle?

    **Physics and numerics:**
    - Is the implementation consistent with the variational/balance-law foundation?
    - Are stress-strain conjugacy and objectivity requirements respected?
    - Have I verified consistency with the Total Lagrangian formulation where applicable?

    **Quality:**
    - Is this my best work?
    - Are names clear and accurate?
    - Is the code clean, idiomatic, and consistent with existing patterns?

    **Discipline:**
    - Did I avoid overbuilding (YAGNI)?
    - Did I only build what was requested?

    **Testing:**
    - Do tests verify behavior, not just mock behavior?
    - Did I follow TDD?
    - Is coverage comprehensive including failure paths?

    If you find issues during self-review, fix them now before reporting.

    ## Report Format

    When done, report:
    - What you implemented
    - Tests written and results (exact pass/fail counts from a fresh run)
    - Files changed (with file paths)
    - Self-review findings (if any) and how you resolved them
    - Any concerns or open questions