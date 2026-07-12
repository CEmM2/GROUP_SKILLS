# Design docs handling

Always search for design docs when running `get_familiar`, `check`, `update`, `refresh`, `architecture`, and `theory` commands.

## Default roots

- `design_docs/`
- `dev/design_docs/`
- `docs/design/`
- `architecture/`
- `dev/architecture/`

## Frontmatter

Prefer design docs with YAML frontmatter:

```yaml
---
title: Backend Architecture
status: accepted
owner: Shmuel
created: 2026-06-10
updated: 2026-07-12
applies_to:
  - src/solvers/
  - docs/dev/architecture.md
  - docs/theory/numerical-method.md
export_policy: adapt
theory_relevant: true
---
```

Status values: `draft`, `proposed`, `accepted`, `active`, `implemented`, `superseded`, `deprecated`, `rejected`, `archived`, `unknown`.

## Export policy

- `ignore`: do not use in docs, but may cite in reports.
- `link`: link only.
- `summarize`: summarize into docs.
- `adapt`: rewrite into docs with structure and cleanup.
- `include`: include almost directly; use rarely.

## Extraction rules

Extract:

- architecture rules
- implementation invariants
- terminology
- repo conventions
- theory rationale
- design constraints
- planned vs implemented mismatches

Every extracted rule must cite the source as `file:line` or `file:line-line` when possible. If line numbers are unavailable, cite the file and mark confidence lower.

## Warning

Design docs are authoritative for intent and rationale. They are not implementation proof.
