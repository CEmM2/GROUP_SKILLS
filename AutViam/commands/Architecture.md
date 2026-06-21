# Architecture

Snapshot a module's (or a just-implemented feature's) architecture as a **durable** themed page plus a **token-lean markdown digest** that planning (yours or `gen-plan`'s) can cheaply re-read. Uses the frozen report shell (read `references/report_shell.md`) and the opt-in Mermaid module (read `references/mermaid_module.md`) for the topology overview. No aesthetic choice, no `surf` images.

Unlike the transient reports (`diff-review`, `plan-review`, `fact-check` → `~/.agent/diagrams/`), architecture output is a **planning asset**: it persists in-repo under `dev/architecture/` so it can aid the next plan.

**Two modes**, detected from `$@`:

| Invocation | Mode | Scope |
|---|---|---|
| `arch <path> [path...]` | **snapshot** | current structure of the given modules/dirs/files |
| `arch --feature <plan_file>` | **end-of-implementation** | the architecture of the feature the plan just implemented |
| `arch` (no arg) | ask | prompt for module paths or a `--feature` plan |

`--name <slug>` overrides the derived output slug. `--feature` mode is what `e2e` hands off at the end of a run (see `commands/E2E.md` § Step 4).

---

## Step 1 — Scope (read-only)

**Snapshot mode:** the targets are the paths in `$@`. List them (`git ls-files <path>`), then read each module's entry points, public surface (exported/`def`/`class`/`pub` symbols — adapt to the language), and its imports of *other in-scope* modules. Don't read vendored/third-party trees unless explicitly targeted.

**End-of-implementation mode:** read the plan's context summaries and `github_issue_map.json` for the slug. The feature surface = files touched by the plan's implementation branches: `git diff --name-only <plan_base>..HEAD` (or the merge commit). Group touched files into modules; read each in full plus the immediate code it calls/returns to, enough to state responsibilities and edges. Mark new vs. modified per `git diff --name-status`.

In both modes, build a **module list**: for each module — its responsibility (one line), public surface (key symbols + one-line each), and its dependency edges to other in-scope modules (`A → B: what flows`).

## Step 2 — Verification (fact-check spine)

Run `commands/FactCheck.md` § inline spine over the module list: every module path, every symbol name, every edge, every responsibility claim is cited to `file:line` (or the `git` command that produced it). Anything you can't ground — an inferred edge, an assumed responsibility — is marked **uncertain** and rendered with the `uncertain` treatment, never stated as fact. This fact-sheet is the source of truth for Steps 3–4.

## Step 3 — Render the page (frozen shell + hybrid pattern)

Build one self-contained `.html` per the frozen shell. Use the **hybrid pattern** — topology up top, detail below — so it stays readable regardless of module count:

1. **Overview** — lead `.card`: what this subsystem/feature *is* in two sentences, then a compact metrics strip (modules, public symbols, external deps; in feature mode also files new/modified, lines ±).
2. **Topology** — one Mermaid `flowchart TD` overview from the Mermaid module (≤8 nodes; one node per module, edges = dependencies, edge labels = what flows). If there are >8 modules, group into subsystems for the overview and keep the per-module detail in the grid below. In feature mode, tag new modules (e.g. `:::isnew`) so the diagram shows what the feature added.
3. **Modules** — a `.cards` grid: one `.card` per module with its responsibility, public surface (symbols as a tight list, each with a one-line role; `code.inline` for names), and its in/out edges. Feature mode adds a green `new` / amber `modified` `.badge` per module. Snippets only — never paste whole files.
4. **Edges & contracts** — a `.tbl-scroll` table of the dependency edges: `from → to · what flows · contract/invariant`. This is the part planning reuses most.
5. **Extension points & risks** — `.callout`s: seams a future change would hook (hooks/events/config/public APIs), plus coupling or invariants not enforced by types/tests. In feature mode, end with "what a follow-up should not break."

Uncertain items keep the `uncertain` badge throughout. Write the HTML to `dev/architecture/<slug>.html`.

## Step 4 — Write the planning digest (token-lean)

Write a compact companion `dev/architecture/<slug>.md` — the machine-readable half, sized so `gen-plan`/the planner can read it in full cheaply (target ≤ ~150 lines). Structure:

```markdown
# Architecture digest — <subsystem or feature>
_Source: <snapshot of paths… | feature <plan_file> @ <short-sha>> · generated <date>_

## Modules
- **<module>** (`path/`) — <one-line responsibility>. Public: `sym()`, `Class`. [new|modified|stable]

## Edges
- `<from>` → `<to>` — <what flows> · <contract/invariant>

## Entry points
- `<entrypoint>` (`file:line`) — <when it runs>

## Extension points
- <seam> (`file:line`) — <what hooks here>

## Uncertain / unverified
- <claim> — <why it couldn't be grounded>
```

Keep prose out; it's a structured index, not a narrative. The HTML is for humans, the digest is for planning. Stamp the date from the environment context (do not invent one).

## Step 5 — Deliver

Open the HTML (`open dev/architecture/<slug>.html` on macOS). Tell the user both paths. Print the planning tie-in verbatim:

```
Planning reuse: gen-plan reads dev/architecture/<slug>.md during data-gather when it exists.
Refresh after structural change: /AutViam arch <paths>   (or  arch --feature <plan_file>)
```

---

**Slug derivation:** `--name` if given; else feature-mode → the plan stem; else snapshot-mode → a kebab slug of the common path (e.g. `services/logic_loom_api/assistant` → `assistant`), de-collided with a short suffix if `dev/architecture/<slug>.*` already exists for a *different* scope. Re-running the same scope **overwrites** in place — the digest is meant to be refreshed, not accumulated.

**Why durable + digest:** the snapshot's job is to feed the *next* plan. A transient HTML in `~/.agent/diagrams/` can't be re-read by `gen-plan`; an in-repo digest can, at a fraction of the tokens of re-deriving the architecture from source every plan. The HTML keeps the same facts human-legible and shareable.
