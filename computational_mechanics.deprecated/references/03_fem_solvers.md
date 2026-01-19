# Finite Element Architecture

## 1. Total Lagrangian (TL) Formulation

All quantities referred to the initial (reference) configuration $\Omega_0$.

### Weak Form (Virtual Work)
$$\delta W = \int_{\Omega_0} \mathbf{S} : \delta\mathbf{E}\,dV_0 - \delta W_{ext} = 0$$

- $\mathbf{S}$: 2nd Piola-Kirchhoff stress
- $\mathbf{E}$: Green-Lagrange strain
- $dV_0$: reference volume element

### Residual Vector
$$\mathbf{R}(\mathbf{u}) = \mathbf{f}_{int}(\mathbf{u}) - \mathbf{f}_{ext}$$

**Internal force**:
$$\mathbf{f}_{int} = \mathop{\mathbf{A}}_{e=1}^{n_{el}} \int_{\Omega_e} \mathbf{B}^T_L \mathbf{S}\,dV_0$$

where $\mathbf{B}_L$ is the nonlinear strain-displacement matrix.

### Strain-Displacement Relation
Green-Lagrange in terms of displacement gradient:
$$\mathbf{E} = \frac{1}{2}\left(\mathbf{H} + \mathbf{H}^T + \mathbf{H}^T\mathbf{H}\right)$$

where $\mathbf{H} = \nabla_X \mathbf{u}$.

**Variation**:
$$\delta\mathbf{E} = \frac{1}{2}\left(\delta\mathbf{H} + \delta\mathbf{H}^T + \mathbf{H}^T\delta\mathbf{H} + \delta\mathbf{H}^T\mathbf{H}\right)$$

### B-Matrix Construction
For TL formulation, split into linear and nonlinear parts:
$$\mathbf{B}_L = \mathbf{B}_0 + \mathbf{B}_{NL}(\mathbf{u})$$

**Linear part** (standard small-strain B):
$$B_{0,IJ}^{aK} = \frac{1}{2}\left(\delta_{IK}\frac{\partial N_a}{\partial X_J} + \delta_{JK}\frac{\partial N_a}{\partial X_I}\right)$$

**Nonlinear part** (displacement-dependent):
$$B_{NL,IJ}^{aK} = \frac{1}{2}\left(\frac{\partial u_L}{\partial X_I}\frac{\partial N_a}{\partial X_J}\delta_{LK} + \frac{\partial u_L}{\partial X_J}\frac{\partial N_a}{\partial X_I}\delta_{LK}\right)$$

## 2. Convected Coordinates Implementation

Simplifies objectivity—strain is simply metric difference.

### Algorithm
1. **Compute metrics**:
   - Reference: $G_{IJ}$ from initial nodal positions
   - Current: $g_{ij}$ from deformed nodal positions
   
2. **Strain**:
   $$E_{ij} = \frac{1}{2}(g_{ij} - G_{ij})$$

3. **Constitutive update** (in convected frame):
   - Evaluate stress $S^{ij}$ from strain $E_{ij}$
   
4. **Transform to Cartesian** (if needed for output):
   $$S_{cart} = J_G \mathbf{G}^I \otimes \mathbf{G}^J S_{IJ}$$

### Advantage
No need for objective rate corrections—convected components are automatically frame-invariant.

## 3. Matrix-Free Solvers

Avoid assembling global stiffness matrix $\mathbf{K}$ for GPU efficiency.

### Internal Force Computation
Element-wise quadrature, atomic scatter to global nodes:

```python
@ti.kernel
def compute_internal_force(u: ti.template(), f_int: ti.template()):
    for e in range(n_elements):
        f_e = ti.Matrix.zero(dt, n_nodes_per_elem * ndim)
        for g in range(n_gauss):
            # Get deformation gradient at Gauss point
            F = compute_F(e, g, u)
            # Constitutive: F → S
            S = constitutive(F, ...)
            # First Piola: P = F·S
            P = F @ S
            # Integrate: ∫ P : ∇N dV₀
            for a in range(n_nodes_per_elem):
                for i in range(ndim):
                    for J in range(ndim):
                        f_e[a*ndim + i] += P[i,J] * dN_dX[e,g,a,J] * w[g] * det_J0[e,g]
        # Scatter to global (with atomics)
        for a in range(n_nodes_per_elem):
            node = connectivity[e, a]
            for i in range(ndim):
                ti.atomic_add(f_int[node, i], f_e[a*ndim + i])
```

### Jacobian-Vector Product (for CG/GMRES)
Matrix-free directional derivative:

**Finite difference approximation**:
$$\mathbf{J}\mathbf{v} \approx \frac{\mathbf{R}(\mathbf{u} + \epsilon\mathbf{v}) - \mathbf{R}(\mathbf{u})}{\epsilon}$$

Choose $\epsilon \sim 10^{-8} \|\mathbf{u}\| / \|\mathbf{v}\|$.

**Analytical tangent** (preferred):
$$D\mathbf{R}[\mathbf{u}]\cdot\Delta\mathbf{u} = \int_{\Omega_0} (\delta\mathbf{E} : \mathbb{C}^{ep} : \Delta\mathbf{E} + \mathbf{S} : \delta\Delta\mathbf{E})\,dV_0$$

### Preconditioner Strategies
1. **Diagonal (Jacobi)**: Cheap, often sufficient
2. **Block diagonal**: Element-level 
3. **Algebraic multigrid**: For large problems
4. **Incomplete Cholesky**: Requires sparse assembly (defeats matrix-free)

## 4. Newton-Raphson with Line Search

```python
def newton_solve(u, tol=1e-6, max_iter=20):
    for it in range(max_iter):
        R = compute_residual(u)
        norm_R = norm(R)
        if norm_R < tol:
            return u, True
        
        # Solve: K·Δu = -R (matrix-free CG)
        delta_u = cg_solve(lambda v: Kv_product(u, v), -R)
        
        # Line search (backtracking)
        alpha = 1.0
        for _ in range(10):
            u_trial = u + alpha * delta_u
            R_trial = compute_residual(u_trial)
            if norm(R_trial) < norm_R:
                break
            alpha *= 0.5
        
        u = u_trial
    return u, False
```

## 5. Staggered Phase-Field Solver

Alternate between mechanical and phase-field subproblems.

### Algorithm
```
For each load step:
    Initialize: φ⁰ = φₙ, u⁰ = uₙ
    For k = 0, 1, 2, ... until convergence:
        
        # Mechanical step (fix φ)
        Solve: R_u(uᵏ⁺¹, φᵏ) = 0  [Newton-Raphson]
        
        # Phase-field step (fix u)
        Solve: R_φ(uᵏ⁺¹, φᵏ⁺¹) = 0  [Often linear, direct solve]
        
        # Apply irreversibility
        φᵏ⁺¹ = max(φᵏ⁺¹, φₙ)
        
        # Check stagger convergence
        if |φᵏ⁺¹ - φᵏ| < tol_stagger:
            break
    
    Update: uₙ₊₁ = uᵏ⁺¹, φₙ₊₁ = φᵏ⁺¹
```

### Phase-Field Residual
$$R_\phi = \int_\Omega \left[g'(\phi)\mathcal{H}\,\delta\phi + G_c\left(\frac{\phi}{\ell}\delta\phi + \ell\nabla\phi\cdot\nabla\delta\phi\right)\right]dV = 0$$

For AT-2 with Miehe split, this is **linear in φ** → direct solve possible.

### Mechanical Residual with Degradation
$$R_u = \int_\Omega g(\phi)\frac{\partial\psi^+}{\partial\boldsymbol{\varepsilon}}:\nabla^s\delta\mathbf{u}\,dV + \int_\Omega\frac{\partial\psi^-}{\partial\boldsymbol{\varepsilon}}:\nabla^s\delta\mathbf{u}\,dV - f_{ext} = 0$$

## 6. Time Integration

### Explicit (Central Difference)
$$\mathbf{u}_{n+1} = 2\mathbf{u}_n - \mathbf{u}_{n-1} + \Delta t^2 \mathbf{M}^{-1}(\mathbf{f}_{ext} - \mathbf{f}_{int})$$

**Stability**: $\Delta t \leq \Delta t_{crit} = h_{min}/c$ where $c = \sqrt{E/\rho}$

### Implicit (Newmark-β)
$$\mathbf{u}_{n+1} = \mathbf{u}_n + \Delta t\,\dot{\mathbf{u}}_n + \Delta t^2\left[(1/2-\beta)\ddot{\mathbf{u}}_n + \beta\ddot{\mathbf{u}}_{n+1}\right]$$

**Common choices**:
- Average acceleration: $\beta=1/4$, $\gamma=1/2$ (unconditionally stable)
- Linear acceleration: $\beta=1/6$, $\gamma=1/2$

### Generalized-α (for dynamics)
Second-order accurate, controllable numerical dissipation:
$$\alpha_m = \frac{2\rho_\infty - 1}{\rho_\infty + 1}, \quad \alpha_f = \frac{\rho_\infty}{\rho_\infty + 1}$$

where $\rho_\infty \in [0,1]$ controls high-frequency damping.

## 7. Boundary Conditions

### Dirichlet (Essential)
Apply directly to displacement DOFs:
```python
# Modify residual
for node in dirichlet_nodes:
    u[node] = u_prescribed
    R[node] = 0  # Zero out residual row

# Modify tangent (for implicit)
K[node, :] = 0
K[:, node] = 0  # Off-diagonals
K[node, node] = 1
```

### Neumann (Natural)
Add to external force vector:
$$f_{ext,a}^i = \int_{\Gamma_N} t_i N_a\,dA$$

### Periodic
Tie displacement DOFs on opposite faces:
$$\mathbf{u}^+ - \mathbf{u}^- = \bar{\mathbf{F}}\cdot(\mathbf{X}^+ - \mathbf{X}^-)$$

## 8. Convergence Monitoring

### Residual Norm
$$\|\mathbf{R}\|_2 / \|\mathbf{R}_0\|_2 < tol$$

### Energy Norm
$$\Delta\mathbf{u}^T\mathbf{K}\Delta\mathbf{u} < tol \cdot \mathbf{u}^T\mathbf{K}\mathbf{u}$$

### Displacement Increment
$$\|\Delta\mathbf{u}\|_2 / \|\mathbf{u}\|_2 < tol$$

### Typical Tolerances
- Nonlinear solve: $10^{-6}$ to $10^{-8}$
- Linear solve: $10^{-10}$ to $10^{-12}$
- Stagger iterations: $10^{-4}$ to $10^{-6}$
