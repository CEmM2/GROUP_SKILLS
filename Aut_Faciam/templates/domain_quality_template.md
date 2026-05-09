Task tool (general-purpose):
  model: [same model tier as implementer for this task]
  description: "Domain quality review for Task <task_id>"
  prompt: |
    You are reviewing an implementation for domain correctness and code quality.

    ## Spec

    <PASTE FULL TASK JSON CONTENT HERE>

    ## Implementer's report

    <paste implementer's report here>

    ## Diff

    Base: <BASE_SHA> · Head: <HEAD_SHA>
    Run `git diff <BASE_SHA>..<HEAD_SHA>` to see the changes.
    Design docs: review against `dev/design_docs/` and any docs referenced from the
    task's `plan_file` or `plan_assets`.

    ## Job

    Verify by reading the diff (do not trust the report). Check:

    - **Physics/numerics**: variational/balance-law consistency; tensor ops, stress-strain
      conjugacy, objectivity; tolerances appropriate for dtype; BCs and loading match spec.
    - **Code quality**: follows existing patterns and conventions; names clear and accurate;
      no unnecessary complexity.
    - **Integration safety**: no broken interfaces or assumptions; imports, signatures, data
      flows consistent with callers.
    - **Design doc adherence**: matches design docs; deviations justified.

    Report:
    - Score (0–10): start from 10; deduct 1 per minor issue, 2 per medium issue. Report
      breakdown: minor / medium / high / critical counts.
    - Approved only if score ≥ 8 and zero high/critical issues. Otherwise the implementer
      must fix and re-run the gate.
    - Issues: each with severity, file:line, explanation.
