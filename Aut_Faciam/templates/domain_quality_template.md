Task tool (general-purpose):
  model: [same model tier as implementer for this task]
  description: "Domain quality review for Task <task_id>"
  prompt: |
    You are reviewing an implementation for domain correctness and code quality.

    ## Task Specification

    <PASTE FULL TASK JSON CONTENT HERE>

    ## Implementer's Report

    <paste implementer's report here>

    ## Diff to Review

    Base: <BASE_SHA>
    Head: <HEAD_SHA>

    Run `git diff <BASE_SHA>..<HEAD_SHA>` to see the changes.

    ## Design Documents

    Review against: `dev/design_docs/`
    Read any design docs referenced by the task's plan_file or plan_assets.

    ## CRITICAL: Verify by Reading Code

    Do not trust the implementer's report. Read the actual diff.

    ## Your Job

    **Physics and numerics:**
    - Is the implementation consistent with the variational/balance-law foundation?
    - Are tensor operations, stress-strain conjugacy, and objectivity requirements correct?
    - Are numerical tolerances appropriate for the dtype in use?
    - Do boundary conditions and loading match the spec?

    **Code quality:**
    - Does the code follow existing patterns and conventions in the codebase?
    - Are names clear, accurate, and consistent with the domain?
    - Is there unnecessary complexity or over-engineering?

    **Integration safety:**
    - Does the change break any existing interfaces or assumptions?
    - Are imports, function signatures, and data flows consistent with callers?

    **Design doc adherence:**
    - Does the implementation match the design documents?
    - Are there deviations? If so, are they justified?

    Report:
    - Score (0-10): start from 10; deduct 1 point per minor issue and 2 points per medium issue; report the breakdown: minor / medium / high / critical issue counts
    - Approved — only if score ≥ 8 and there are no high or critical issues
    - If score < 8, do not approve; the implementer must fix the issues and re-run the Gate.
    - Issues: [list each with severity, file:line, and explanation]
