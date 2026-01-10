# FEM Minimal Example (template)

Goal: verify a small, known case (patch test, manufactured solution, or single element).

## Steps
1. Generate or load a tiny mesh
2. Apply BCs and loads
3. Solve
4. Compare against expected result or invariants (e.g., constant strain field)

## Expected artifacts
- input mesh: <path>
- results: <path>
- log: <path>

## Success criteria
- error norm within tolerance
- convergence achieved within N iterations