# Explain

Explain **something that exists in this codebase** — a symbol, file, flow, or concept — as a single themed diagram, every node and edge cited to `file:line`. This is AutViam's grounded, fact-checked answer to "diagram X for me": it picks the diagram type that fits the question and renders it in the frozen theme. Uses the frozen report shell (read `references/report_shell.md`) and the Mermaid module (read `references/mermaid_module.md`). No aesthetic choice, no `surf` images.

**Inputs:** `$@` — what to explain. A symbol (`resolveApiBase`), a file (`src/api/client.ts`), a flow ("how the sidecar handshake works"), or a concept ("how AKMS gating degrades gracefully").

**Output is transient** — `~/.agent/diagrams/<slug>.html`, an understanding aid, not a planning asset. (For a durable, reusable module/feature snapshot, use `AutViam_C arch` instead — it writes to `dev/architecture/` with a planning digest.)

---

## Step 0 — Grounding gate (the boundary)

`explain` only does **repo-grounded** topics. Before anything else, confirm the target resolves to real code here: grep/locate the symbol, file, or the functions behind the flow. 

- **Grounded** (symbol/file/flow/concept backed by code in this repo) → continue.
- **Not grounded** (a general concept, an external system, a library you don't vendor, a hypothetical) → **stop and hand off**: tell the user this is open-ended diagramming, which is `visual-explainer`'s job, and suggest `/generate-web-diagram <topic>`. Don't fabricate a repo-grounded diagram for something that isn't in the repo.

If it's partly grounded (a real flow that crosses into an external service), diagram the grounded part and mark the external edges **uncertain**/external — don't invent their internals.

## Step 1 — Data-gather (read-only)

- Resolve the target to its definition(s). For a symbol: read it plus its callers and callees (use the repo's code-intelligence tool (or grep)). For a flow: trace the execution path across files. For a concept: find the code that embodies it (the gate, the handshake, the registry).
- Note the **shape** of the answer: is it a call graph, a step sequence, a state machine, a data path, a layered dependency? That decides the diagram type (Step 2).
- Capture exact `file:line` for every box and arrow you'll draw.

## Step 2 — Pick the diagram type (one diagram, fits the question)

| The question is really… | Diagram | Mermaid |
|---|---|---|
| "what calls / leads to X" · "how does this flow" | call graph / flowchart | `flowchart TD` |
| "what happens, in order, when Y" | sequence | `sequenceDiagram` |
| "what states does Z move through" | state machine | `stateDiagram-v2` (mind the label caveat → `flowchart TD` if labels are rich) |
| "how does data move through W" | data-flow | `flowchart TD` + `\|edge labels\|` |
| "how is this layered / what depends on what" | dependency | `flowchart TD` + `subgraph` |
| "what is the shape of this whole module" | → that's **`AutViam_C arch`**, not explain | — |

One diagram is the target. If the honest answer needs more than ~12 nodes, prefer the hybrid pattern (small Mermaid overview + a couple of `.card`s) per `references/mermaid_module.md` rather than one dense graph.

## Step 3 — Verify (fact-check spine)

Run `commands/FactCheck.md` § inline spine over the diagram you're about to draw: every node is a real symbol/file (cited), every edge is a real call/transition/data path (cited), every label is accurate. Anything you inferred but couldn't ground → mark **uncertain** (dashed edge / `uncertain` badge), never asserted. A diagram that asserts an edge that doesn't exist is worse than no diagram.

## Step 4 — Render (frozen shell, one focused page)

Build one self-contained `.html` per the frozen shell:

1. **Lead `.card`** — the one-paragraph answer in plain words (the intuition), then the citations strip ("traced across `<file>`, `<file>`").
2. **The diagram** — one `.diagram-shell` from the Mermaid module. Color/shape by role using the theme's classes; mark uncertain edges dashed.
3. **Key nodes** — a short list or compact `.tbl-scroll`: each box → `file:line` + one-line what-it-does, so the diagram is traceable back to code.
4. **Gotchas** (only if real) — a `.callout` for non-obvious coupling, ordering dependencies, or the degrade-gracefully branch the diagram implies.

Keep it to what answers the question — `explain` is a focused aid, not a full report. Write to `~/.agent/diagrams/<slug>.html`, open it, tell the user the path.

---

**Slug:** kebab of the target (`sidecar-handshake`, `resolve-api-base`). **vs `arch`:** `explain` answers a *question* about code (transient, one diagram); `arch` *snapshots a module/feature* for reuse in planning (durable HTML + digest). **vs `visual-explainer`:** `explain` is repo-grounded and fact-checked in the frozen theme; anything ungrounded or free-aesthetic stays in `visual-explainer`.
