# Mathematical Baseline & Kinematics

## 1. Coordinate Systems & Basis Vectors

### Material vs Spatial Coordinates
- **Material (Reference)**: $\mathbf{X} \in \Omega_0$, particles labeled at $t=0$
- **Spatial (Current)**: $\mathbf{x} \in \Omega_t$, fixed points in space

### Convected Coordinates
In convected systems, basis vectors deform with the body—this automatically ensures objectivity.

**Covariant basis** (tangent to coordinate curves):
$$\mathbf{g}_i = \frac{\partial \mathbf{x}}{\partial \xi^i}$$

**Contravariant basis** (reciprocal):
$$\mathbf{g}^i \cdot \mathbf{g}_j = \delta^i_j$$

**Metric tensors**:
$$g_{ij} = \mathbf{g}_i \cdot \mathbf{g}_j, \quad g^{ij} = \mathbf{g}^i \cdot \mathbf{g}^j$$

**Reference metric**: $G_{IJ} = \mathbf{G}_I \cdot \mathbf{G}_J$ (in undeformed configuration)

### Basis Transformations
```
gᵢ = gᵢⱼ gʲ     (lower index)
gⁱ = gⁱʲ gⱼ     (raise index)
```

## 2. Deformation Gradient

$$\mathbf{F} = \frac{\partial \mathbf{x}}{\partial \mathbf{X}} = \mathbf{g}_i \otimes \mathbf{G}^I \frac{\partial x^i}{\partial X^I}$$

**Key relations**:
- Maps material vectors to spatial: $d\mathbf{x} = \mathbf{F} \cdot d\mathbf{X}$
- Jacobian (volume ratio): $J = \det(\mathbf{F}) > 0$ (must remain positive)
- In convected coords: $\mathbf{g}_i = \mathbf{F} \cdot \mathbf{G}_I$ (basis vector push-forward)

### Polar Decomposition
$$\mathbf{F} = \mathbf{R}\mathbf{U} = \mathbf{V}\mathbf{R}$$
- $\mathbf{R}$: orthogonal rotation
- $\mathbf{U} = \sqrt{\mathbf{F}^T\mathbf{F}}$: right stretch (material)
- $\mathbf{V} = \sqrt{\mathbf{F}\mathbf{F}^T}$: left stretch (spatial)

## 3. Strain Measures

### Green-Lagrange Strain (Reference Config)
$$\mathbf{E} = \frac{1}{2}(\mathbf{C} - \mathbf{I}) = \frac{1}{2}(\mathbf{F}^T\mathbf{F} - \mathbf{I})$$

**In convected coordinates**:
$$E_{ij} = \frac{1}{2}(g_{ij} - G_{ij})$$

This is the natural strain for Total Lagrangian formulation.

### Almansi Strain (Current Config)
$$\mathbf{e} = \frac{1}{2}(\mathbf{I} - \mathbf{b}^{-1}) = \frac{1}{2}(\mathbf{I} - \mathbf{F}^{-T}\mathbf{F}^{-1})$$

### Logarithmic (Hencky) Strain
$$\mathbf{H} = \ln(\mathbf{U}) = \frac{1}{2}\ln(\mathbf{C})$$

Preferred for large strains due to additive decomposition property.

### Strain Rate
**Rate of deformation** (symmetric part of velocity gradient):
$$\mathbf{d} = \frac{1}{2}(\mathbf{L} + \mathbf{L}^T), \quad \mathbf{L} = \dot{\mathbf{F}}\mathbf{F}^{-1}$$

**Green-Lagrange rate** (convected):
$$\dot{E}_{ij} = \frac{1}{2}\dot{g}_{ij}$$

## 4. Push-Forward & Pull-Back Operations

### Push-Forward (Reference → Spatial)
| Tensor Type | Operation |
|-------------|-----------|
| Vector | $\mathbf{v} = \mathbf{F}\mathbf{V}$ |
| Covariant 2-tensor | $\boldsymbol{\sigma} = J^{-1}\mathbf{F}\mathbf{S}\mathbf{F}^T$ |
| Contravariant 2-tensor | $\mathbf{b} = \mathbf{F}\mathbf{C}^{-1}\mathbf{F}^T$ |

### Pull-Back (Spatial → Reference)
| Tensor Type | Operation |
|-------------|-----------|
| Vector | $\mathbf{V} = \mathbf{F}^{-1}\mathbf{v}$ |
| Covariant 2-tensor | $\mathbf{S} = J\mathbf{F}^{-1}\boldsymbol{\sigma}\mathbf{F}^{-T}$ |

### Piola Transformation
For area elements: $\mathbf{n}da = J\mathbf{F}^{-T}\mathbf{N}dA$ (Nanson's formula)

## 5. Objective Rates

For spatial formulations, time derivatives of tensors must be **frame-invariant** (objective).

### Lie Derivative (Truesdell Rate)
$$\mathcal{L}_v(\boldsymbol{\tau}) = \mathbf{F} \frac{D}{Dt}(\mathbf{F}^{-1}\boldsymbol{\tau}\mathbf{F}^{-T})\mathbf{F}^T = \dot{\boldsymbol{\tau}} - \mathbf{L}\boldsymbol{\tau} - \boldsymbol{\tau}\mathbf{L}^T$$

This is the natural rate in convected coordinates—pulling back, differentiating, pushing forward.

### Jaumann (Corotational) Rate
$$\boldsymbol{\tau}^{\nabla J} = \dot{\boldsymbol{\tau}} - \mathbf{W}\boldsymbol{\tau} + \boldsymbol{\tau}\mathbf{W}$$

where $\mathbf{W} = \frac{1}{2}(\mathbf{L} - \mathbf{L}^T)$ is the spin tensor.

### Convected Rate Advantage
In convected coordinates, objective rates are automatic:
$$\dot{\boldsymbol{\tau}}^{obj} = \dot{\tau}^{ij}\mathbf{g}_i \otimes \mathbf{g}_j$$

The components $\dot{\tau}^{ij}$ are simply time derivatives—no rotation corrections needed.

## 6. Multiplicative Decomposition

For finite plasticity: $\mathbf{F} = \mathbf{F}^e\mathbf{F}^p$

**Intermediate configuration**: stress-free, obtained by elastic unloading

**Velocity gradient decomposition**:
$$\mathbf{L} = \mathbf{L}^e + \mathbf{F}^e\mathbf{L}^p(\mathbf{F}^e)^{-1}$$

**Elastic quantities** (on intermediate config):
- $\mathbf{C}^e = (\mathbf{F}^e)^T\mathbf{F}^e$
- $\mathbf{E}^e = \frac{1}{2}(\mathbf{C}^e - \mathbf{I})$

**Mandel stress** (work-conjugate to $\mathbf{L}^p$):
$$\mathbf{M} = \mathbf{C}^e\mathbf{S}^e = (\mathbf{F}^e)^T\boldsymbol{\tau}(\mathbf{F}^e)^{-T}$$

## 7. Voigt Notation

### 3D Stress/Strain Vectors (6 components)
```
σ = [σ₁₁, σ₂₂, σ₃₃, σ₂₃, σ₁₃, σ₁₂]ᵀ
ε = [ε₁₁, ε₂₂, ε₃₃, 2ε₂₃, 2ε₁₃, 2ε₁₂]ᵀ    (engineering shear)
```

**Note**: Factor of 2 on shear strains ensures $\boldsymbol{\sigma}:\boldsymbol{\varepsilon} = \sigma^T\varepsilon$

### 4th-Order Tensor to 6×6 Matrix
For $\mathbb{C}_{ijkl}$, use Voigt mapping:
```
Index map: 11→1, 22→2, 33→3, 23→4, 13→5, 12→6

C_voigt[I,J] = C[i,j,k,l]  where I=map(i,j), J=map(k,l)
For shear rows/cols, multiply by 2 or 4 depending on strain convention
```

### Isotropic Elasticity (Voigt)
```python
# Lamé parameters: λ, μ
C = [
    [λ+2μ,   λ,     λ,     0,   0,   0  ],
    [λ,      λ+2μ,  λ,     0,   0,   0  ],
    [λ,      λ,     λ+2μ,  0,   0,   0  ],
    [0,      0,     0,     μ,   0,   0  ],
    [0,      0,     0,     0,   μ,   0  ],
    [0,      0,     0,     0,   0,   μ  ]
]
```

## 8. Common Implementation Pitfalls

1. **Forgetting shear factor**: Engineering strain has factor 2 on off-diagonal terms
2. **Mixed configurations**: Computing $\nabla_x$ when $\nabla_X$ is needed
3. **Non-objective rates**: Using $\dot{\boldsymbol{\sigma}}$ instead of objective rate in spatial formulations
4. **Index confusion**: Covariant vs contravariant indices in convected systems
5. **Jacobian sign**: Not checking $J > 0$ leads to element inversion

## 9. Computational Formulas

### Deformation Gradient from Displacements
$$F_{iJ} = \delta_{iJ} + \frac{\partial u_i}{\partial X_J}$$

### Green-Lagrange from Deformation Gradient
$$E_{IJ} = \frac{1}{2}(F_{kI}F_{kJ} - \delta_{IJ})$$

### Right Cauchy-Green
$$C_{IJ} = F_{kI}F_{kJ}$$

### Determinant (3D)
$$J = \det(\mathbf{F}) = \frac{1}{6}\epsilon_{ijk}\epsilon_{IJK}F_{iI}F_{jJ}F_{kK}$$

Or use standard determinant formula for 3×3 matrix.
