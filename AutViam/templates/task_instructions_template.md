autviam_routing_ticket: <absolute routing ticket path>
agent_profile: <exact agent returned by resolve_claude_agent.py>
current_depth: <resolver depth>
maximum_depth: <resolver max_depth>
task_json_path: <absolute task JSON path>
phase_context_path: <absolute Phase context path>
handoff_path: <absolute handoff path, or omitted>
working_directory: <plan worktree root>

## Plan excerpts

<Only the task's referenced plan-line excerpts; empty when none.>

## Cross-phase warnings

<Relevant prior failure patterns; omit when empty.>

## Repo-configured skills

<Matched skill names and SKILL.md paths; omit when empty.>

Read the task JSON and the other paths yourself. Implement exactly the assigned scope, preserve routing state, use the scaffolded tests, and report exact verification counts and changed files. Do not perform Gate A or Gate B review. Do not pass a model override to any Agent call.

For a retry, the caller prepends only the prior gate Issues list. Re-read the same task JSON, fix those issues, rerun task tests, and map each issue to its resolution.
