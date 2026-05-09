Task tool (general-purpose):
  model: [assigned per Step 2 model rules]
  description: "Implement Task <task_id>: <task_title>"
  prompt: |
    You are implementing Task <task_id>: <task_title>

    ## Task Description

    <PASTE FULL CONTENT OF TASK JSON HERE>

    ## Phase Context

    <summary of what this phase accomplishes and how this task fits in>
    <relevant constraints from the plan or handoff file>
    <architectural context: patterns and existing abstractions to follow>

    ## Before You Begin

    If anything is unclear (requirements, approach, dependencies, physics correctness),
    **ask now** before starting. Do not guess on physics, constitutive model behavior,
    or numerical stability. Pausing to clarify is always OK — also while working.

    ## Your Job

    Implement exactly what the task specifies — nothing more, nothing less.

    1. Read `test_artifacts` and `verification_commands` from the task JSON. Each test
       case has been classified by the scaffold pass:
       - `covered`: existing test — run as baseline; must pass after implementation
       - `partial`: stub exists — flesh out into a real, asserting test before
         implementing, then make it pass (TDD red-green)
       - `missing`: stub with `pytest.skip` exists — replace skip with real assertions
         before implementing, then make it pass (TDD red-green)
       If `test_artifacts` is empty, generate dedicated tests before implementing.
    2. Run all task-relevant tests; iterate until ≥ 95% pass.
    3. Dry-run failure-route analysis: read every modified file, identify uncovered
       failure paths, add tests, re-iterate until ≥ 95% pass on the full set.
    4. Commit (separate commit if complexity OR risk ≥ 3).
    5. Self-review (below).
    6. Report back.

    Work from: <working directory>

    ## Self-review before reporting

    - Spec covered fully, no extras (YAGNI).
    - Physics/numerics consistent with variational + Total Lagrangian foundation
      where applicable; stress-strain conjugacy and objectivity respected.
    - Tests verify behavior, not mocks; failure paths covered.
    - Names + style match surrounding code.
    - Fresh test run shows ≥ 95% pass; record exact counts.

    Fix any issues found before reporting.

    ## Report Format

    - What you implemented
    - Tests written and results (exact pass/fail counts from a fresh run)
    - Files changed (with file paths)
    - Self-review findings and resolutions
    - Any concerns or open questions
