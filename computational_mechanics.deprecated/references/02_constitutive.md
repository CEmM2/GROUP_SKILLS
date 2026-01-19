# Constitutive Modeling

## 1. Rate-Dependent Plasticity

### Perzyna Viscoplasticity (Overstress Model)
Classic regularization for rate effects:

$$\dot{\bar{\varepsilon}}^p = \frac{1}{\eta}\langle\Phi(f)\rangle$$

where:
- $\eta$: viscosity parameter
- $f = \sigma_{eq}/\sigma_y - 1$: overstress ratio
- $\langle\cdot\rangle$: Macaulay bracket ($\langle x \rangle = x$ if $x > 0$, else $0$)
- $\Phi(f)$: overstress function

**Common choices for $\Phi$**:
```
Power law:      Φ(f) = f^m
Exponential:    Φ(f) = exp(f/f₀) - 1
Sinh law:       Φ(f) = A·sinh(f/f₀)^n
```

### Duvaut-Lions Model
Alternative rate formulation based on elastic-viscoplastic split:

$$\dot{\boldsymbol{\sigma}} = \mathbb{C}^e : \dot{\boldsymbol{\varepsilon}} - \frac{1}{\tau}(\boldsymbol{\sigma} - \boldsymbol{\sigma}^{inv})$$

where $\boldsymbol{\sigma}^{inv}$ is the inviscid (rate-independent) plastic solution.

### Consistency Model
Stress remains on yield surface (unlike overstress models):

$$\dot{\lambda} \geq 0, \quad f \leq 0, \quad \dot{\lambda}f = 0, \quad \dot{\lambda}\dot{f} = 0$$

Rate-dependence enters through rate-dependent hardening:
$$\sigma_y = \sigma_y(\bar{\varepsilon}^p, \dot{\bar{\varepsilon}}^p, T)$$

## 2. Anisotropic Yield: Barlat 2004-18p

High-fidelity yield surface for textured metals (especially aluminum alloys).

### Formulation
Two linear transformations of the stress deviator:
$$\mathbf{s}' = \mathbf{L}'\mathbf{s}, \quad \mathbf{s}'' = \mathbf{L}''\mathbf{s}$$

where $\mathbf{L}'$, $\mathbf{L}''$ are 6×6 anisotropy matrices (18 parameters total).

### Yield Function
$$\Phi = \left[\frac{1}{4}\sum_{i=1}^{3}\sum_{j=1}^{3}|\lambda'_i - \lambda''_j|^a\right]^{1/a} - \sigma_y = 0$$

- $\lambda'_i$: eigenvalues of $\mathbf{s}'$
- $\lambda''_j$: eigenvalues of $\mathbf{s}''$
- $a$: yield exponent (8 for FCC, 6 for BCC metals)

### Eigenvalue Computation
For GPU: use analytical Cardano's formula (cubic characteristic equation), not iterative methods.

**Invariants of symmetric 3×3 matrix** $\mathbf{A}$:
```
I₁ = tr(A)
I₂ = ½[(tr A)² - tr(A²)]
I₃ = det(A)

p = I₁/3
q = (I₂ - I₁²/3)/3
r = ½(2I₁³/27 - I₁I₂/3 + I₃)

φ = (1/3)arccos(r/(-q³)^0.5)

λ₁ = 2√(-q)cos(φ) + p
λ₂ = 2√(-q)cos(φ + 2π/3) + p
λ₃ = 2√(-q)cos(φ + 4π/3) + p
```

### Transformation Matrices
$\mathbf{L}'$ and $\mathbf{L}''$ contain anisotropy coefficients derived from:
- Uniaxial tension/compression tests at various angles
- Biaxial tests (e.g., bulge test, plane strain)
- r-values (Lankford coefficients)

## 3. Return Mapping Algorithm

### Radial Return (J₂ Plasticity)
**Trial state** (elastic predictor):
$$\boldsymbol{\sigma}^{trial} = \boldsymbol{\sigma}_n + \mathbb{C}^e : \Delta\boldsymbol{\varepsilon}$$

**Check yield**:
$$f^{trial} = \sigma_{eq}^{trial} - \sigma_y(\bar{\varepsilon}^p_n)$$

**If** $f^{trial} > 0$: Plastic corrector
$$\boldsymbol{\sigma}_{n+1} = \boldsymbol{\sigma}^{trial} - \Delta\lambda\frac{\partial f}{\partial\boldsymbol{\sigma}}$$

For J₂: radial return in deviatoric plane:
$$\mathbf{s}_{n+1} = \frac{\sigma_y}{\sigma_{eq}^{trial}}\mathbf{s}^{trial}$$

### Viscoplastic Extension
Replace yield condition with:
$$\Delta\lambda = \Delta t \cdot \dot{\lambda}(\sigma_{eq}, \bar{\varepsilon}^p, T)$$

where $\dot{\lambda}$ comes from Perzyna or consistency model.

### Consistent Tangent
Critical for Newton convergence. For rate-dependent:

$$\mathbb{C}^{ep} = \mathbb{C}^e - \frac{2\mu^2\Delta\lambda}{\sigma_{eq}^{trial}}\mathbf{P}_{dev} + \frac{4\mu^2}{\sigma_{eq}^{trial}}\frac{\Delta\lambda - \beta\partial\lambda/\partial\sigma_{eq}}{1 + \beta\partial\lambda/\partial\bar{\varepsilon}^p}\mathbf{n}\otimes\mathbf{n}$$

where $\mathbf{n} = \mathbf{s}/\|\mathbf{s}\|$ and $\beta = \sqrt{2/3}\cdot 2\mu\Delta t$.

## 4. Temperature Coupling

### Adiabatic Heating
At high strain rates, plastic work converts to heat:
$$\rho C_p \dot{T} = \chi\boldsymbol{\sigma}:\mathbf{D}^p$$

- $\chi$: Taylor-Quinney coefficient (~0.9 for metals)
- $C_p$: specific heat capacity
- $\rho$: density

### Temperature-Dependent Properties
```
σ_y(T) = σ_y0 [1 - (T/T_m)^q]        (thermal softening)
E(T) = E_0 [1 - α(T - T_ref)]         (elastic modulus)
```

### Thermomechanical Coupling
**Fully coupled**: Solve mechanical and thermal equations simultaneously
**Staggered**: Solve sequentially (simpler, requires iteration for strong coupling)

## 5. Phase-Field Fracture

### Energy Functional
$$\mathcal{E}(\mathbf{u}, \phi) = \int_\Omega \psi_e(\boldsymbol{\varepsilon}, \phi)\,dV + \int_\Omega G_c\gamma(\phi, \nabla\phi)\,dV$$

- $\psi_e$: degraded elastic strain energy
- $G_c$: critical energy release rate (fracture toughness)
- $\gamma$: crack surface density

### AT-2 Formulation (Miehe)
Crack surface density:
$$\gamma(\phi, \nabla\phi) = \frac{1}{2\ell}\phi^2 + \frac{\ell}{2}|\nabla\phi|^2$$

Length scale $\ell$ controls regularization width (crack bandwidth ~ $2\ell$).

### Spectral Energy Split (Miehe)
Decompose strain energy to prevent cracking under compression:

**Principal strain decomposition**:
$$\boldsymbol{\varepsilon} = \sum_{a=1}^{3}\varepsilon_a\mathbf{n}_a\otimes\mathbf{n}_a$$

$$\boldsymbol{\varepsilon}^+ = \sum_{a=1}^{3}\langle\varepsilon_a\rangle_+\mathbf{n}_a\otimes\mathbf{n}_a, \quad \boldsymbol{\varepsilon}^- = \boldsymbol{\varepsilon} - \boldsymbol{\varepsilon}^+$$

**Split energies**:
$$\psi^+ = \frac{\lambda}{2}\langle\text{tr}(\boldsymbol{\varepsilon})\rangle_+^2 + \mu\,\text{tr}((\boldsymbol{\varepsilon}^+)^2)$$
$$\psi^- = \frac{\lambda}{2}\langle\text{tr}(\boldsymbol{\varepsilon})\rangle_-^2 + \mu\,\text{tr}((\boldsymbol{\varepsilon}^-)^2)$$

### Degradation Function
$$g(\phi) = (1-\phi)^2 + k$$

where $k \sim 10^{-6}$ for numerical stability (prevents zero stiffness).

### Degraded Stress
$$\boldsymbol{\sigma} = g(\phi)\frac{\partial\psi^+}{\partial\boldsymbol{\varepsilon}} + \frac{\partial\psi^-}{\partial\boldsymbol{\varepsilon}}$$

### Phase-Field Evolution (Allen-Cahn type)
$$g'(\phi)\mathcal{H} + G_c\left(\frac{\phi}{\ell} - \ell\nabla^2\phi\right) = 0$$

where $\mathcal{H}$ is history variable enforcing irreversibility:
$$\mathcal{H}(t) = \max_{\tau \in [0,t]}\psi^+(\tau)$$

### Irreversibility Constraint
At each time step:
$$\phi_{new} = \max(\phi_{new}, \phi_{old})$$

## 6. Ductile Fracture Coupling

### Gurson-Tvergaard-Needleman (GTN) Model
Incorporates void growth for ductile materials:

$$\Phi = \frac{\sigma_{eq}^2}{\sigma_y^2} + 2q_1 f^* \cosh\left(\frac{3q_2 p}{2\sigma_y}\right) - (1 + q_3(f^*)^2) = 0$$

- $f^*$: effective void volume fraction
- $p$: hydrostatic pressure
- $q_1, q_2, q_3$: calibration parameters

### Phase-Field + Ductile
Couple GTN void evolution with phase-field:
- Porosity $f$ drives damage nucleation
- Phase-field $\phi$ models final coalescence and rupture
- Degradation depends on both: $g(\phi, f)$

## 7. Implementation Notes

### Local vs Global Iteration
- **Stress update**: Local Newton at each integration point
- **Equilibrium**: Global Newton-Raphson
- **Phase-field**: Often linear (can be direct solve)

### Convergence Criteria
```
Local:  |Δλ| < tol_local (typically 1e-10)
Global: |R| / |R₀| < tol_global (typically 1e-6)
```

### Time Stepping for Fracture
Phase-field is sensitive to loading rate. Use:
- Adaptive time stepping based on $\Delta\phi_{max}$
- Staggered iterations between $\mathbf{u}$ and $\phi$ until convergence
