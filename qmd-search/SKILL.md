---
name: qmd-search
description: Search AKMS knowledge nodes and code mirrors using QMD (BM25 keyword and semantic vector search). Replaces grep for knowledge retrieval.
---

# QMD Search for AKMS

Search the AKMS knowledge graph sources — global vault nodes, local nodes, code
mirrors, and session history — using QMD's BM25 keyword search and semantic vector
search. This skill replaces `grep` with structured, index-backed retrieval.

## When to Use This Skill

**Activate when the agent needs to:**

- Find knowledge nodes relevant to a task before generating a loadout
- Search code mirrors for implementation patterns
- Look up session history for past pitfalls or lessons
- Find nodes by concept (semantic) when exact keywords are unknown
- Verify whether a node already exists before creating a new one (dedup)

**Do NOT use when:**

- You already have a loadout — read it instead of searching
- You need the compiled graph structure — use `graph.json` directly
- You need to modify nodes — qmd is read-only search

---

## Prerequisites

### Installing QMD CLI

QMD must be installed on the host machine. It is **not** bundled with AKMS.

```bash
# Install qmd-cli (check https://github.com/AgenticQMD/qmd for latest)
pip install qmd-cli
# or
brew install qmd
```

Verify installation:

```bash
qmd --version
qmd status
```

### Setting Up AKMS Collections

QMD indexes directories as *collections*. AKMS requires four collections, mapped
to the directories that hold knowledge content:

```bash
# 1. Global vault — shared domain knowledge across all repos
qmd collection create akms-global-nodes --path "${AKMS_GLOBAL_VAULT:-$HOME/.claude/akms/nodes}"

# 2. Local nodes — repo-specific agent-written knowledge
qmd collection create akms-local-nodes --path "<repo>/knowledge/local-nodes"

# 3. Code mirror — indexed source code for code-level search
qmd collection create akms-code-mirror --path "<repo>/knowledge/code-mirror"

# 4. Sessions — AgentMemory and PCD files from past phases
qmd collection create akms-sessions --path "<repo>/knowledge/sessions"
```

Replace `<repo>` with your actual repository root. For per-repo collections, use
a naming convention that includes the repo name:

```bash
# Example for a repo called "tifem"
qmd collection create akms-tifem-local-nodes --path ~/git/tifem/knowledge/local-nodes
qmd collection create akms-tifem-code-mirror --path ~/git/tifem/knowledge/code-mirror
qmd collection create akms-tifem-sessions    --path ~/git/tifem/knowledge/sessions
```

### Indexing and Updating

After creating collections, build the initial index:

```bash
# Index all collections (BM25)
qmd update

# Generate embeddings for semantic search
qmd embed
```

**Keeping indexes current:** Run after any AKMS operation that creates or modifies
`.md` files (build_graph, update_graph, generate_mirror):

```bash
qmd update && qmd embed
```

Both commands are incremental — only new or changed files are processed.

---

## Search Commands

AKMS currently supports two search modes. **`query` (hybrid + LLM reranking) is
not supported** — it requires an LLM call and breaks determinism (NFR-D01).

### 1. BM25 Keyword Search (Default)

```bash
qmd search "<query>" --collection <collection-name>
```

- Fast, exact keyword matching against the BM25 index
- Best for: specific terms, node ids, tag names, file paths, function names
- Deterministic — same query always returns same results

**Examples:**

```bash
# Find nodes about return mapping algorithms
qmd search "return mapping" --collection akms-global-nodes

# Find local nodes tagged with plasticity
qmd search "plasticity" --collection akms-tifem-local-nodes

# Search code mirror for a specific function
qmd search "get_DefGrad" --collection akms-tifem-code-mirror

# Find past sessions about a task
qmd search "TCR-101" --collection akms-tifem-sessions
```

### 2. Semantic Vector Search

```bash
qmd search "<query>" --semantic --collection <collection-name>
```

- Similarity matching against pre-computed embeddings (no LLM call)
- Best for: conceptual queries where exact wording may vary
- Use when BM25 returns too few results or the concept has many synonyms

**Examples:**

```bash
# Conceptual: "how deformation works" → finds kinematics nodes
qmd search "deformation gradient computation" --semantic --collection akms-global-nodes

# Find code that does something similar to what you need
qmd search "stress tensor assembly for hexahedral elements" --semantic --collection akms-tifem-code-mirror
```

### 3. Retrieving Full Documents

Search results return snippets with document IDs. To get the full content:

```bash
qmd get "#<docid>"
```

**Always quote the docid** (the `#` prefix is part of the identifier).

---

## Search Strategy for AKMS Agents

### Node Lookup (Before Loadout Generation)

When `query_subgraph.py` needs to find nodes matching task tags:

```bash
# Step 1: BM25 search global nodes by each tag
qmd search "taichi gpu kernel" --collection akms-global-nodes

# Step 2: BM25 search local nodes (repo-specific knowledge)
qmd search "taichi gpu kernel" --collection akms-tifem-local-nodes

# Step 3: If results are sparse, try semantic on global
qmd search "GPU computation patterns for finite elements" --semantic --collection akms-global-nodes
```

### Dedup Check (Before Creating New Nodes)

Before `update_graph.py` creates a tentative node from `new_knowledge`:

```bash
# Check if a similar node already exists
qmd search "<suggested_id> <title keywords>" --collection akms-global-nodes
qmd search "<suggested_id> <title keywords>" --collection akms-tifem-local-nodes

# If BM25 misses, try semantic for conceptual overlap
qmd search "<content_draft first sentence>" --semantic --collection akms-global-nodes
```

### Code Search (Replacing grep)

For agents that need to find implementation patterns:

```bash
# Find where a function is mirrored
qmd search "get_Edot" --collection akms-tifem-code-mirror

# Find code related to a concept
qmd search "phase field damage evolution" --semantic --collection akms-tifem-code-mirror
```

### Session History

For finding past pitfalls, lessons, or approaches:

```bash
# What happened in phase 2?
qmd search "phase 2" --collection akms-tifem-sessions

# Find pitfalls about Taichi session conflicts
qmd search "taichi session conflict" --collection akms-tifem-sessions
```

---

## Integration with AKMS Pipeline

### Where QMD is Called

| Pipeline stage | QMD usage | Fallback if unavailable |
|---|---|---|
| `query_subgraph.py` | Content summaries for loadout | Loadout in routing mode only (paths, no summaries) |
| `generate_loadout.py` | Inline content retrieval | `qmd_available: false` in loadout header |
| `update_graph.py` | Dedup check for new_knowledge | Skip dedup, create tentative node |
| `generate_mirror.py` | None (writes, doesn't read) | N/A |
| `graph_status.py` | None (reads graph.json) | N/A |

### Degraded Mode

If `qmd` is not installed or collections are not set up, AKMS operates in
**degraded mode**:

- `generate_loadout.py` sets `qmd_available: false` in the loadout header
- Loadouts contain node table with file paths only (routing mode)
- No inline content or summaries in loadouts
- Agents must read node files directly via their `content_ref` paths
- Dedup checks are skipped — may create duplicate tentative nodes

To detect degraded mode programmatically:

```python
import shutil

def is_qmd_available() -> bool:
    """Check if qmd CLI is installed and accessible."""
    return shutil.which("qmd") is not None
```

---

## QMD Command Reference

| Command | Description | AKMS usage |
|---|---|---|
| `qmd search "<query>" --collection <name>` | BM25 keyword search | Primary search mode |
| `qmd search "<query>" --semantic --collection <name>` | Vector semantic search | Conceptual queries |
| `qmd get "#<docid>"` | Retrieve full document by id | Get node content after search |
| `qmd update` | Index new/changed files (incremental) | After build_graph, update_graph |
| `qmd embed` | Generate embeddings (incremental) | After qmd update |
| `qmd status` | Show collections and index stats | Diagnostics |
| `qmd collection list` | List all collections | Verify setup |
| `qmd collection create <name> --path <dir>` | Create a new collection | Initial setup |

### Not Supported

| Command | Why |
|---|---|
| `qmd query "<query>"` | Uses LLM reranking — breaks determinism (NFR-D01), adds latency and cost |

---

## Troubleshooting

### "Collection not found"

```bash
qmd collection list
# If missing, recreate:
qmd collection create akms-global-nodes --path "${AKMS_GLOBAL_VAULT:-$HOME/.claude/akms/nodes}"
```

### Search returns no results

1. Check the collection has been indexed: `qmd status`
2. Run `qmd update` to index new files
3. For semantic search, ensure embeddings exist: `qmd embed`
4. Try BM25 first — if that finds nothing, the content isn't indexed

### Stale results after node changes

```bash
# Re-index after any AKMS mutation
qmd update && qmd embed
```

### QMD not installed

AKMS works without QMD in degraded mode. Install when ready:

```bash
pip install qmd-cli
```

---

## Notes

- QMD indexes `.md` files only — binary files, JSON, and YAML are not searchable
- BM25 and semantic search are both local and private — no data leaves the machine
- Embeddings are computed once per file and cached; `qmd embed` is incremental
- Collection paths can use `~` and environment variables
- The global vault collection (`akms-global-nodes`) is shared across all repos;
  per-repo collections (`akms-<repo>-*`) are repo-specific
