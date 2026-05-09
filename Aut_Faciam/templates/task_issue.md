## <task_id>: <task_title>

**Phase:** #<phase_issue_number> · **Tier:** <test_plan.tier> · **Plan:** `<plan_file>:<plan_lines>`
**Spec:** `<tasks_folder>/json/<task_id>.json` (authoritative — read this first)

### Objective
<1–2 sentence objective from task.objective>

### Test Checklist
<!-- One line per existing test_artifact (covered) and per generated stub. Test files alone are linked here; the spec JSON carries the rest. -->
- [ ] `<test_file_path>::<test_function>` — <one line>
- [ ] `<stub_file_path>::<test_function>` — <one line>

### Blocked By
<!-- If task.blocked_by non-empty: -->
- #<blocker_issue_number> (<blocker_task_id>)
<!-- Else: -->
None

### Dispatch
```
Read #<this_issue_number> and implement per the spec JSON.
```
