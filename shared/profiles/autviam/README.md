# AutViam profile skeleton (Planning Alpha / A2-3)

Canonical independently versioned AutViam profile source for the Whatter profile kernel.

## Layout

```text
profiles/autviam/
├── profile.yaml                 # Whatter-compilable profile source
├── schemas/semantic-plan/       # Semantic-plan schema (package files)
├── ontology/                    # Hierarchy + scp/ecp vocabulary
├── roles/                       # Planning role descriptions
├── policies/                    # Subscription/local capability requirements
├── pipelines/                   # Human-readable pipeline docs
├── fixtures/{valid,invalid}/    # Semantic plan fixtures
└── tools/validate_semantic_plan.py
```

## Semantic hierarchy (A-002)

```text
Program → Milestone → Work Package → Semantic Checkpoint (scp-*) → Evidence Intent
```

**Phase is not a semantic object.** PlanCompile may introduce execution phases and `ecp-*` checkpoints without semantic amendment.

## Compile

From a Whatter checkout (no kernel changes required):

```bash
whatter profile compile /path/to/Skills_repo/profiles/autviam \
  -o /tmp/autviam.compiled.json
```

## Validate fixtures

```bash
python profiles/autviam/tools/validate_semantic_plan.py --suite
```
