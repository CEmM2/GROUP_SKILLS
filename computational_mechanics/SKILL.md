---
name: computational_mechanics
description: Expert guidance for computational mechanics algorithms focusing on large-deformation finite elements, rate-dependent plasticity (Perzyna, Barlat 2004-18p), phase-field fracture, and FFT-Galerkin spectral methods. Use when deriving mathematical formulations, implementing constitutive models, translating tensor algebra to code, validating FEM/FFT solvers, or debugging numerical issues in solid mechanics. Complements taichi-gpu-sim for Taichi implementation details.
---

# Computational Mechanics Skill

Provides expert-level guidance on **large deformation kinematics**, **rate-dependent plasticity**, **phase-field fracture**, and **FFT-Galerkin spectral methods** for heterogeneous materials.

## Prime Directive
Derive first, code second. Every algorithm must be traceable to a variational principle or balance law.

## Default Assumptions
Unless the user specifies otherwise:
- **Formulation**: Total Lagrangian (TL) for large deformation
- **Decomposition**: Multiplicative $\mathbf{F} = \mathbf{F}^e \mathbf{F}^p$ for finite plasticity
- **Integration**: Implicit backward Euler for rate-dependent problems
- **Stress/Strain pairing**: Second Piola-Kirchhoff $\mathbf{S}$ with Green-Lagrange $\mathbf{E}$

## Workflow
1. **Clarify the physics**: Formulation (TL/UL), constitutive model, loading conditions
2. **Establish kinematics**: Define strain measure, ensure conjugate stress pairing
3. **Derive weak form/residual**: From virtual work or energy functional
4. **Discretize**: Finite elements or FFT-Galerkin
5. **Linearize**: Consistent tangent for Newton-Raphson
6. **Validate**: Patch tests, benchmark problems, energy conservation

## Meta-Rules for Implementation

### Kinematics & Coordinates
- Use **convected coordinates** for automatic objectivity: covariant basis $\mathbf{g}_i$, contravariant $\mathbf{g}^i$, metric $g_{ij} = \mathbf{g}_i \cdot \mathbf{g}_j$
- Green-Lagrange strain: $E_{ij} = \frac{1}{2}(g_{ij} - G_{ij})$ where $G_{ij}$ is reference metric
- For spatial formulations, use **Lie derivatives** for objective rates

### Numerical Implementation
- **Matrix-free** for GPU: compute $\mathbf{f}_{int}$ and $D\mathbf{R}[\mathbf{u}]\cdot\Delta\mathbf{u}$ directly, avoid global $\mathbf{K}$ assembly
- **Return mapping**: Always use radial return with consistent tangent
- **Time stepping**: Check CFL stability for explicit; check $J = \det(\mathbf{F}) > 0$ for element inversion

### Verification Checklist
Before code review, verify:
- [ ] Stress-strain conjugacy: $\mathbf{S}$ with $\mathbf{E}$, or $\boldsymbol{\sigma}$ with $\mathbf{d}$
- [ ] Gradient convention: $\nabla_X$ (material) vs $\nabla_x$ (spatial)
- [ ] Objectivity: Lie derivative or convected formulation for spatial tensors
- [ ] Material symmetries: $\mathbb{C}_{ijkl} = \mathbb{C}_{klij}$ (major), $\mathbb{C}_{ijkl} = \mathbb{C}_{jikl}$ (minor)
- [ ] Phase-field: Degradation $g(\phi)$ applied only to tensile energy $\psi^+$

## Table of Contents

### Reference Documents
| Topic | File | Key Content |
|-------|------|-------------|
| Math & Kinematics | `reference/01_math_kinematics.md` | Tensor algebra, convected coordinates, Lie derivatives, deformation measures |
| Constitutive Models | `reference/02_constitutive.md` | Perzyna viscoplasticity, Barlat 2004-18p, temperature coupling, phase-field fracture |
| FEM & Solvers | `reference/03_fem_solvers.md` | TL weak form, matrix-free operators, staggered phase-field solver |
| FFT-Galerkin | `reference/04_fft_spectral.md` | Lippmann-Schwinger, Green's operator, polarization schemes |

### Templates
| Template | File | Purpose |
|----------|------|---------|
| Barlat 2004-18p | `templates/barlat_plasticity.py` | Anisotropic yield with analytical eigenvalue solver |
| Validation Suite | `templates/validation_benchmarks.py` | Taylor anvil, Sneddon crack, biaxial tests |

## Quick Reference

### Stress Measures
| Name | Symbol | Configuration | Conjugate Strain |
|------|--------|---------------|------------------|
| Cauchy | $\boldsymbol{\sigma}$ | Spatial | Rate of deformation $\mathbf{d}$ |
| 1st Piola-Kirchhoff | $\mathbf{P}$ | Two-point | $\dot{\mathbf{F}}$ |
| 2nd Piola-Kirchhoff | $\mathbf{S}$ | Reference | Green-Lagrange $\mathbf{E}$ |
| Kirchhoff | $\boldsymbol{\tau} = J\boldsymbol{\sigma}$ | Spatial | $\mathbf{d}$ |
| Mandel | $\mathbf{M} = \mathbf{C}^e\mathbf{S}$ | Intermediate | $\mathbf{L}^p$ |

### Key Transformations
```
Push-forward:   τ = F S F^T        (S → τ)
Pull-back:      S = F^{-1} τ F^{-T} (τ → S)
Lie derivative: L_v(τ) = F · (d/dt)(F^{-1} τ F^{-T}) · F^T
```

### Phase-Field Energy Split (Miehe)
```
ψ⁺ = λ/2 ⟨tr(ε)⟩₊² + μ tr(ε₊²)    (tension, degraded)
ψ⁻ = λ/2 ⟨tr(ε)⟩₋² + μ tr(ε₋²)    (compression, intact)
g(φ) = (1-φ)² + k                   (k ≈ 1e-6 for stability)
```

### FFT-Galerkin Essentials
```
Lippmann-Schwinger: ε̃(x) = -Γ⁰ * τ(ε̃)
Fourier space:      ε̂(ξ) = ε̄ - Γ̂⁰(ξ) : τ̂(ξ)
Green's operator:   Γ̂⁰ᵢⱼₖₗ(ξ) = (ξⱼξₗ/|ξ|²) [C⁰ᵢⱼₖₗ ξⱼξₗ]⁻¹
```

## When to Use This Skill
- Deriving weak forms or residual equations for nonlinear solids
- Implementing constitutive models (plasticity, damage, fracture)
- Converting tensor equations to matrix/Voigt notation
- Debugging stress/strain inconsistencies
- Setting up FFT-based micromechanics simulations
- Validating against analytical solutions or benchmarks

## Complementary Skill
Use **taichi-gpu-sim** for:
- Taichi kernel optimization and data layout
- GPU performance tuning and atomic reduction strategies
- SNode design and memory access patterns
