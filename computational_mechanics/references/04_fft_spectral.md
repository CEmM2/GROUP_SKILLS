# Spectral Methods (FFT-Galerkin)

## 1. Overview

FFT-based solvers for periodic heterogeneous materials (RVEs). Faster than FEM for regular grids due to FFT efficiency ($O(N\log N)$).

**Key applications**:
- Computational homogenization of composites
- Polycrystal plasticity
- Microstructure-sensitive fracture

## 2. Problem Statement

Find strain field $\boldsymbol{\varepsilon}(\mathbf{x})$ in periodic RVE $\Omega$ satisfying:

$$\nabla \cdot \boldsymbol{\sigma} = 0 \quad \text{in } \Omega$$
$$\boldsymbol{\sigma}(\mathbf{x}) = \mathbb{C}(\mathbf{x}) : \boldsymbol{\varepsilon}(\mathbf{x})$$
$$\langle\boldsymbol{\varepsilon}\rangle = \bar{\boldsymbol{\varepsilon}} \quad \text{(prescribed macroscopic strain)}$$

with periodic boundary conditions on $\partial\Omega$.

## 3. Lippmann-Schwinger Equation

### Derivation
Introduce reference medium $\mathbb{C}^0$ and polarization stress:
$$\boldsymbol{\tau}(\mathbf{x}) = (\mathbb{C}(\mathbf{x}) - \mathbb{C}^0) : \boldsymbol{\varepsilon}(\mathbf{x})$$

The equilibrium becomes:
$$\nabla \cdot (\mathbb{C}^0 : \boldsymbol{\varepsilon} + \boldsymbol{\tau}) = 0$$

Using Green's function of reference medium:
$$\boldsymbol{\varepsilon}(\mathbf{x}) = \bar{\boldsymbol{\varepsilon}} - (\boldsymbol{\Gamma}^0 * \boldsymbol{\tau})(\mathbf{x})$$

This is the **Lippmann-Schwinger equation**—implicit because $\boldsymbol{\tau}$ depends on $\boldsymbol{\varepsilon}$.

### Fourier Space Form
Convolution becomes product:
$$\hat{\boldsymbol{\varepsilon}}(\boldsymbol{\xi}) = \bar{\boldsymbol{\varepsilon}}\delta(\boldsymbol{\xi}) - \hat{\boldsymbol{\Gamma}}^0(\boldsymbol{\xi}) : \hat{\boldsymbol{\tau}}(\boldsymbol{\xi})$$

For $\boldsymbol{\xi} \neq 0$:
$$\hat{\boldsymbol{\varepsilon}}(\boldsymbol{\xi}) = -\hat{\boldsymbol{\Gamma}}^0(\boldsymbol{\xi}) : \hat{\boldsymbol{\tau}}(\boldsymbol{\xi})$$

For $\boldsymbol{\xi} = 0$:
$$\hat{\boldsymbol{\varepsilon}}(0) = \bar{\boldsymbol{\varepsilon}} \quad \text{(macroscopic average)}$$

## 4. Green's Operator

### Definition
Fourth-order tensor $\boldsymbol{\Gamma}^0$ derived from Green's function:
$$\Gamma^0_{ijkl}(\mathbf{x}) = -G^0_{ki,jl}(\mathbf{x})$$

### Fourier Space (Isotropic Reference)
$$\hat{\Gamma}^0_{ijkl}(\boldsymbol{\xi}) = \frac{1}{4\mu^0|\boldsymbol{\xi}|^2}\left(\delta_{ki}\xi_l\xi_j + \delta_{li}\xi_k\xi_j + \delta_{kj}\xi_l\xi_i + \delta_{lj}\xi_k\xi_i\right) - \frac{\lambda^0+\mu^0}{\mu^0(\lambda^0+2\mu^0)}\frac{\xi_i\xi_j\xi_k\xi_l}{|\boldsymbol{\xi}|^4}$$

where $\lambda^0$, $\mu^0$ are Lamé constants of reference medium.

### Acoustic Tensor Form
$$\hat{G}^0_{km}(\boldsymbol{\xi}) = \left[C^0_{ijkl}\xi_j\xi_l\right]^{-1}_{im}$$

Then:
$$\hat{\Gamma}^0_{ijkl}(\boldsymbol{\xi}) = \xi_j\xi_l\hat{G}^0_{ik}(\boldsymbol{\xi})$$

with symmetrization over $ij$ and $kl$.

## 5. Solver Algorithms

### Basic Scheme (Moulinec-Suquet)
Fixed-point iteration:

```
Initialize: ε⁰(x) = ε̄
For k = 0, 1, 2, ... until convergence:
    
    1. Constitutive (real space):
       σᵏ(x) = C(x) : εᵏ(x)
       τᵏ(x) = σᵏ(x) - C⁰ : εᵏ(x)
    
    2. FFT:
       τ̂ᵏ(ξ) = FFT(τᵏ(x))
    
    3. Update (Fourier space):
       ε̂ᵏ⁺¹(ξ) = -Γ̂⁰(ξ) : τ̂ᵏ(ξ)  for ξ ≠ 0
       ε̂ᵏ⁺¹(0) = ε̄
    
    4. IFFT:
       εᵏ⁺¹(x) = IFFT(ε̂ᵏ⁺¹(ξ))
    
    5. Check convergence:
       |∇·σᵏ| / |⟨σᵏ⟩| < tol
```

**Convergence criterion** (equilibrium in Fourier):
$$\frac{\sqrt{\sum_{\boldsymbol{\xi}\neq 0}|\boldsymbol{\xi}\cdot\hat{\boldsymbol{\sigma}}|^2}}{|\hat{\boldsymbol{\sigma}}(0)|} < tol$$

### Reference Medium Selection
Critical for convergence. Common choices:

**Arithmetic mean** (good for moderate contrast):
$$\lambda^0 = \frac{1}{2}(\lambda_{min} + \lambda_{max}), \quad \mu^0 = \frac{1}{2}(\mu_{min} + \mu_{max})$$

**Geometric mean** (better for high contrast):
$$\mu^0 = \sqrt{\mu_{min}\mu_{max}}$$

### Polarization Schemes (Accelerated)

**Augmented Lagrangian** (Michel et al.):
```
εᵏ⁺¹ = ε̄ - Γ̂⁰ : λᵏ
eᵏ⁺¹ = (C + C⁰)⁻¹ : (C⁰ : εᵏ⁺¹ + λᵏ)
λᵏ⁺¹ = λᵏ + C⁰ : (εᵏ⁺¹ - eᵏ⁺¹)
```

Converges for infinite contrast (voids, rigid inclusions).

### Krylov-Based Schemes (CG/GMRES)

Treat Lippmann-Schwinger as linear system:
$$\mathcal{A}(\boldsymbol{\varepsilon}) = \bar{\boldsymbol{\varepsilon}}$$

where:
$$\mathcal{A}(\boldsymbol{\varepsilon}) = \boldsymbol{\varepsilon} + \mathcal{F}^{-1}\left[\hat{\boldsymbol{\Gamma}}^0 : \mathcal{F}[(\mathbb{C}-\mathbb{C}^0):\boldsymbol{\varepsilon}]\right]$$

Solve with conjugate gradient. Faster convergence than basic scheme.

## 6. Nonlinear Extension

### (Pseudo-)Time Discretization
For plasticity, march through load history:

```
For load step n → n+1:
    ε̄ₙ₊₁ = prescribed macroscopic strain
    
    Solve: ε(x) such that ⟨σ(ε, history)⟩ satisfies equilibrium
    
    Update internal variables (plastic strain, hardening, etc.)
```

### Newton-Raphson in FFT
Linearize residual:
$$\mathbf{R}(\boldsymbol{\varepsilon}) = \boldsymbol{\varepsilon} + \mathcal{F}^{-1}[\hat{\boldsymbol{\Gamma}}^0 : \hat{\boldsymbol{\tau}}] - \bar{\boldsymbol{\varepsilon}} = 0$$

Tangent operator:
$$\frac{\partial\mathbf{R}}{\partial\boldsymbol{\varepsilon}} = \mathbf{I} + \mathcal{F}^{-1}[\hat{\boldsymbol{\Gamma}}^0 : \mathcal{F}[(\mathbb{C}^{tan} - \mathbb{C}^0):\cdot]]$$

where $\mathbb{C}^{tan} = \partial\boldsymbol{\sigma}/\partial\boldsymbol{\varepsilon}$ is the algorithmic tangent.

## 7. FFT-Based Phase-Field Fracture

### Staggered Approach
Alternate between:
1. **Mechanical**: FFT solve for $\boldsymbol{\varepsilon}$ with degraded stiffness
2. **Phase-field**: FFT solve for $\phi$

### Phase-Field in Fourier Space
Helmholtz-type equation:
$$\phi + \ell^2\nabla^2\phi = \ell\frac{g'(\phi)\mathcal{H}}{G_c}$$

In Fourier:
$$\hat{\phi}(\boldsymbol{\xi}) = \frac{\hat{h}(\boldsymbol{\xi})}{1 + \ell^2|\boldsymbol{\xi}|^2}$$

where $h = \ell g'(\phi)\mathcal{H}/G_c$.

### Gibbs Phenomena
Sharp interfaces (crack, void) cause oscillations. Mitigation:
- Discrete derivatives (finite difference in physical space)
- Spectral filtering
- Rotated schemes

## 8. Homogenization

### Effective Properties
**Macroscopic stress**:
$$\bar{\boldsymbol{\sigma}} = \langle\boldsymbol{\sigma}\rangle = \frac{1}{|\Omega|}\int_\Omega\boldsymbol{\sigma}(\mathbf{x})\,dV$$

**Effective stiffness**:
$$\bar{\mathbb{C}} = \frac{\partial\bar{\boldsymbol{\sigma}}}{\partial\bar{\boldsymbol{\varepsilon}}}$$

Compute by perturbing macroscopic strain in 6 directions.

### Hill-Mandel Condition
Energy consistency:
$$\bar{\boldsymbol{\sigma}} : \bar{\boldsymbol{\varepsilon}} = \langle\boldsymbol{\sigma}:\boldsymbol{\varepsilon}\rangle$$

Automatically satisfied with periodic BCs.

## 9. Implementation Notes

### DFT Conventions
Be consistent with normalization:
- numpy: $\hat{f}(k) = \sum_{n=0}^{N-1} f(n) e^{-2\pi i kn/N}$
- Factor of $1/N$ on inverse

### Frequency Grid
For $N$ grid points with spacing $h$:
$$\xi_k = \begin{cases} k/(Nh) & k < N/2 \\ (k-N)/(Nh) & k \geq N/2 \end{cases}$$

### Zero Frequency
$\boldsymbol{\xi} = 0$ requires special handling:
- $\hat{\boldsymbol{\Gamma}}^0(0)$ undefined → set to zero
- $\hat{\boldsymbol{\varepsilon}}(0) = \bar{\boldsymbol{\varepsilon}}$ enforces macroscopic strain

### Symmetry
For real-valued fields, exploit conjugate symmetry:
$$\hat{f}(-\boldsymbol{\xi}) = \hat{f}^*(\boldsymbol{\xi})$$

Use `rfft` for efficiency.

### Typical Grid Sizes
- 2D: $256^2$ to $1024^2$
- 3D: $64^3$ to $256^3$ (memory limited)

## 10. Performance Comparison

| Method | Contrast | Iterations | Memory |
|--------|----------|------------|--------|
| Basic | Low (<10) | ~50-100 | Low |
| Basic | High (>100) | >1000 | Low |
| Augmented Lagrangian | Any | ~100 | Medium |
| Newton-CG | Any | ~10-20 | Medium |

Choose based on material contrast and problem size.
