---
name: computational-mechanics
description: Derives and implements nonlinear solid mechanics algorithms: tensor calculus, finite-strain kinematics (Total Lagrangian, convected coordinates), rate- and temperature-dependent plasticity, brittle/ductile fracture (phase-field, GTN), and FFT-Galerkin micromechanics. Use for FEM/FFT constitutive updates, objective stress integration, solver architecture, and verification.
---

# Computational Mechanics

Entry-point Skill for computational mechanics implementation work.

## Scope

Use this Skill when the task involves **math-to-code translation** for:

- Tensor algebra/calculus (push-forward/pull-back, curvilinear/convected bases)
- Large deformation kinematics (Total Lagrangian, large rotations, large strains)
- Rate- and temperature-dependent plasticity (Perzyna, Duvaut-Lions, implicit BE)
- Brittle/ductile fracture (phase-field, Gurson/GTN family, coupling strategies)
- FFT-Galerkin micromechanics (Lippmann-Schwinger, Newton-Krylov, high contrast)

**Taichi note:** if Taichi code is requested, consult the `taichi-gpu-sim` Skill for Taichi-specific best practices and performance rules. This Skill focuses on the *mechanics*.

## Default standards

1. **State the configuration and stress measure** (e.g., TL with $S$ and $E$, or spatial with Cauchy $\sigma$ and $D$).
2. **Objectivity is non-negotiable**: use a corotational/objective update if integrating rates in the spatial frame.
3. **Finite strain plasticity** defaults to multiplicative split $F = F^e F^p$ unless small-strain is explicitly requested.
4. **Rate dependence** defaults to implicit backward Euler for stability.
5. **Phase-field fracture** defaults to staggered alternate minimization (u/phi) with a tension/compression energy split.
6. Prefer **matrix-free operators** (directional derivatives / JVPs) over assembled global tangents when scale/performance matters.

## Progressive disclosure map

### Tensor calculus and notation
- `reference/notation-cheatsheet.md`
- `reference/tensor-calculus.md`

### Kinematics: TL convected coordinates, large rotations/strains
- `reference/kinematics-tl-convected.md`
- `reference/objective-rates-integration.md`

### Plasticity: rate + temperature coupling
- `reference/constitutive-viscoplastic-thermo.md`

### Fracture: phase-field, brittle/ductile, GTN
- `reference/phase-field-fracture.md`
- `reference/ductile-fracture-gtn-phasefield.md`

### FFT-Galerkin micromechanics
- `reference/fft-galerkin-micromechanics.md`

### Solver architecture and validation
- `reference/solver-architecture-matrixfree.md`
- `reference/verification-benchmarks.md`

## Templates

Python skeletons (NumPy-first, easy to port to Taichi/JAX/PyTorch):

- `templates/tensor_ops.py`
- `templates/tl_convected_element.py`
- `templates/newton_krylov_matrixfree.py`
- `templates/j2_perzyna_return_mapping.py`
- `templates/miehe_spectral_split.py`
- `templates/phasefield_staggered_solver.py`
- `templates/fft_lippmann_schwinger.py`
- `templates/pytest_benchmarks_template.py`

## Verification checklist (quick)

- Kinematics: correct $\nabla_X$ vs $\nabla_x$ usage, $J=\det F>0$.
- Stress pairing: TL uses $(S,E)$; spatial uses $(\sigma,D)$.
- Objectivity: rotating body does not create spurious stress.
- Plasticity: yield/flow/consistency are satisfied (or viscoplastic overstress is correct).
- Thermo: plastic dissipation produces $\Delta T$ with correct units/sign.
- Phase-field: irreversibility ($\dot\phi\ge 0$), no cracking in compression (energy split).
- FFT: zero-frequency handling, equilibrium residual in Fourier space decreases.
