## Phase <N>: <phase_name>

**Status:** ✅ Scaffolded
**Plan overview:** #<plan_overview_issue_number>
**Context:** `Phase_<N>_context_summary.md` (`<rel_path>`)
<!-- Phase 2+: filled by ExecPhase Step 10 once the previous phase completes -->
**Handoff in:** `Handoff_Phase_<N>.md` (`<rel_path>`)

### Scaffold Summary
| Metric | Value |
|---|---|
| Tasks scaffolded | <N> |
| Cases covered | <N> |
| Cases stubbed | <N> |
| Tasks needing review | <N> |
| Files created | <N> |

### Tasks
<!-- Phase-issues-only: tasks are checkboxes here, not separate issues. -->
<!-- ExecPhase/ExecTask flip these to [x] when a task completes Gate C. -->
- [ ] P<N>-1 — <task_title_1>
- [ ] P<N>-2 — <task_title_2>

### Local artifacts
- Specs: `<tasks_folder>/json/P<N>-*.json` (authoritative — agents read these directly)
- Gate history: `<tasks_folder>/gates/phase_<N>_gates.md`
- Tracker: `<tracking_file>`
