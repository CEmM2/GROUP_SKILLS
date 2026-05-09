Task tool (general-purpose):
  model: [same model tier as implementer for this task]
  description: "Spec compliance review for Task <task_id>"
  prompt: |
    You are reviewing whether an implementation matches its specification.

    ## Spec

    <PASTE FULL TASK JSON CONTENT HERE>

    ## Implementer's report

    <paste implementer's report here>

    ## Job

    Verify by reading the actual code (do not trust the report).
    Check for: missing requirements, extra/unrequested work, misinterpretation.

    Report:
    - ✅ Compliant, or
    - ❌ Issues: <list with file:line>
