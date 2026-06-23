# Credits & third-party attribution

AutViam_C's report layer borrows from the **visual-explainer** skill by **Nico Bailon**
(GitHub: [`nicobailon`](https://github.com/nicobailon)), used under the MIT License.

## What was borrowed

- **`references/mermaid_module.md`** — the zoom / pan / fit / expand Mermaid diagram
  engine (the `.diagram-shell` HTML structure, the CSS chrome, and the interaction
  module) is adapted from visual-explainer's `templates/mermaid-flowchart.html`.
  AutViam_C's changes: the Mermaid `themeVariables` are read from the frozen
  `templates/report_theme.css` palette via `getComputedStyle` instead of being
  hard-coded, and a `data-theme` `MutationObserver` re-renders every diagram when the
  ◐ theme toggle flips.
- **Diagram-type guidance** in `mermaid_module.md`, `commands/Architecture.md`, and
  `commands/Explain.md` (when to use flowchart vs. sequence vs. state vs. data-flow,
  the `<br/>`-not-`\n` and `stateDiagram-v2` label caveats, the hybrid-pattern rule
  for 15+ nodes) distills visual-explainer's `SKILL.md` and CSS-patterns guidance.

AutViam_C's own work — not borrowed: the frozen report theme (`report_theme.css`, pinned
from the AKMS "Seuss" theme) and shell (`report_shell.md`), and the `arch` / `explain`
commands (repo-grounded, fact-checked, durable planning digests).

## License (visual-explainer)

```
MIT License

Copyright (c) 2025 Nico Bailon

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
