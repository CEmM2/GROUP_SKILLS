# FFT-Galerkin micromechanics (periodic RVEs)

## Problem statement
Solve equilibrium on a periodic cell:
- div(sigma(x)) = 0
- strain is compatible and periodic
- prescribe either macroscopic strain E, macroscopic stress Sigma, or mixed control

## Lippmann-Schwinger (LS) form
Pick a reference medium C0.
Define polarization tau(x) = sigma(x) - C0:epsilon(x).
Then:
epsilon(x) = E - Gamma0 * tau(x)
where Gamma0 is the Green operator (in Fourier space, a projection operator).

## Fourier space essentials
- Convolution becomes pointwise multiplication in Fourier space.
- k=0 (DC component): handle separately to impose macroscopic control.

## Iterative solvers
### Fixed-point (Moulinec-Suquet)
Repeat:
1) sigma = constitutive(epsilon)
2) tau = sigma - C0:epsilon
3) epsilon = E - invFFT( Gamma0_hat : FFT(tau) )
Convergence deteriorates for high contrast or strong nonlinearity.

### Newton-Krylov / CG (recommended)
Define residual R(eps) = eps - E + Gamma0 * tau(eps).
Use a Krylov solver with matrix-free JVPs (directional derivatives) for the Jacobian action.

## Nonlinear constitutive laws
At each voxel:
- store internal variables (Fp, hardening, phi, etc.)
- update stress via implicit local integration
- return consistent tangent or JVP

## Failure/localization in FFT
- Use projection to enforce compatibility.
- For strain localization, Newton-Krylov is usually mandatory.
- If coupling phase-field, solve (u/phi) in a staggered way or monolithically with block preconditioning.

## Verification
- Patch test: homogeneous material should return uniform strain/stress.
- Inclusion benchmark: convergence vs contrast.
- Check equilibrium norm in Fourier space: ||k · sigma_hat|| -> 0 for all k != 0.
