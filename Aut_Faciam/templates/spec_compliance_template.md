Task tool (general-purpose):
  model: [same model tier as implementer for this task]
  description: "Spec compliance review for Task <task_id>"
  prompt: |
    You are reviewing whether an implementation matches its specification.

    ## What Was Requested

    <PASTE FULL TASK JSON CONTENT HERE>

    ## What the Implementer Claims They Built

    <paste implementer's report here>

    ## CRITICAL: Do Not Trust the Report

    Verify everything independently by reading the actual code.

    **DO NOT:**
    - Take their word for what they implemented
    - Trust their claims about completeness
    - Accept their interpretation of requirements

    **DO:**
    - Read the actual code they wrote
    - Compare implementation to requirements line by line
    - Check for missing pieces they claimed to implement
    - Look for extra features they did not mention

    ## Your Job

    Verify by reading code (not by trusting the report):

    **Missing requirements:** Did they implement everything requested? Did they skip or
    claim something works without actually implementing it?

    **Extra/unneeded work:** Did they build things not requested? Did they over-engineer
    or add unrequested features?

    **Misunderstandings:** Did they interpret requirements differently than intended?
    Did they solve the wrong problem?

    Report:
    - ✅ Spec compliant (after code inspection confirms everything matches)
    - ❌ Issues: [list specifically what is missing or extra, with file:line references]

