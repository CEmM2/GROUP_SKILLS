# Scientific correctness review

Scientific determinism narrows evidence and validates mechanics; it does not replace expert semantic judgment.

## Mandatory routing

Require at least one domain-specialist semantic review when an invalidated claim or changed evidence concerns:

- equations, derivations, constitutive laws, or physical assumptions;
- units, coordinate frames, signs, tensor conventions, or conjugate quantities;
- discretization, integration, stability, convergence, precision, or tolerances;
- estimators, distributions, sampling, uncertainty, significance, or statistical assumptions;
- loss functions, normalization, metrics, training, inference, or reproducibility;
- validation, benchmark, conservation, residual, or error claims.

Require an independent second review for new or changed equations, physical assumptions, safety claims, and security claims. Repositories may extend this list in `.documentron/config.json`.

## Gate sequence

1. **Evidence gate:** deterministically extract the claim, symbols, units, implementation paths, tests, and measured results.
2. **Domain gate:** apply matched specialist lenses to physical, mathematical, numerical, statistical, or ML appropriateness.
3. **Executable gate:** run only configured checks and capture tolerances, norms, residuals, seeds, fixtures, and hardware assumptions.
4. **Independent gate:** when required, use a fresh reviewer that receives the evidence packet and proposed final text, not the author's hidden reasoning.

A passing symbolic identity does not establish model appropriateness. A passing numerical test does not prove the documented assumptions. An LLM verdict without executable evidence does not establish numerical correctness. Report all three separately.

## Required reviewer output

For each finding, provide:

- verdict and severity;
- claim identifier;
- exact evidence paths and symbols;
- assumptions, units, frames, dtype, and tolerances considered;
- uncertainty or missing verification;
- a correction only when supported by evidence.

Do not derive or rewrite an equation merely to make it look conventional. Mark unresolved domain ambiguity for human decision.
