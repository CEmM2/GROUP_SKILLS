# Install

Install and configure Documentron without LLM inference.

## Workflow

1. Copy or symlink the skill into the platform's skill directory. Claude may additionally install named agent definitions; Codex keeps prompt profiles bundled.
2. Run `scripts/documentron.py --repo . init`.
3. Run `discover-specialists` and present manifests exactly as declared. Do not infer roles or trigger patterns from prose descriptions.
4. On approval, run `discover-specialists --write` or update `.documentron/config.json` through a structured edit.
5. Run `doctor` without executing validation commands.

Specialists publish `documentron-specialist.json` conforming to `templates/documentron-specialist.schema.json`.

## AutViam integration

With `--with-autviam-hook`, wire `scripts/documentron-post-plan-hook.sh` after successful plan closure. The hook runs deterministic `prepare --command post-plan --plan <path>` and records the packet path. It does not claim to execute an assistant runtime. Read `references/autviam_post_plan_hook.md`.
