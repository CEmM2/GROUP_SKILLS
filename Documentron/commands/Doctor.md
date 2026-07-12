# Doctor

Validate documentation infrastructure without an LLM.

Run:

```bash
python3 <skill_root>/scripts/documentron.py --repo . doctor --output .documentron/reports/doctor.json
```

Add `--run-commands` only when explicitly asked to execute allowlisted documentation builds. Render the JSON report with `render-report`. Do not invoke an agent to reinterpret deterministic failures.
