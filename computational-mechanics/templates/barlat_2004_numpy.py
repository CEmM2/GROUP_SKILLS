"""
Barlat 2004-18p Anisotropic Yield Function - NumPy Reference Implementation.

This constitutive model uses two linear transformations of the stress
deviator to capture high-fidelity anisotropy in metals (e.g., Aluminum).

Framework-agnostic pure NumPy implementation for maximum portability.

Reference:
    Barlat, F., et al. "Linear transfomation-based anisotropic yield functions."
    Int. J. Plasticity 21 (2005) 1009-1039.

Voigt Notation Convention:
    stress_voigt = [σ11, σ22, σ33, σ23, σ13, σ12]
    Engineering shear strains: use γ (not tensor shear ε)
"""

import numpy as np
from typing import Union, Tuple


def stress_deviator(stress_voigt: np.ndarray) -> np.ndarray:
    """
    Extract deviatoric part of stress tensor in Voigt notation.

    Args:
        stress_voigt: Stress in Voigt notation [σ11, σ22, σ33, σ23, σ13, σ12]
                     Can be single vector (6,) or batch (N, 6)

    Returns:
        Deviatoric stress in Voigt notation (same shape as input)
    """
    stress_voigt = np.atleast_2d(stress_voigt)
    p = np.mean(stress_voigt[:, :3], axis=1, keepdims=True)
    s = stress_voigt.copy()
    s[:, :3] -= p

    return s.squeeze() if stress_voigt.shape[0] == 1 else s


def cardano_eigenvalues(s_vec: np.ndarray) -> np.ndarray:
    """
    Analytical eigenvalue solver for symmetric 3x3 matrix using Cardano's formula.

    The stress deviator (from 6-vector) has eigenvalues that sum to zero.
    Numerically stable for typical stress tensors.

    Args:
        s_vec: Transformed deviator [s11, s22, s33, s23, s13, s12]
               Can be single vector (6,) or batch (N, 6)

    Returns:
        Array of 3 eigenvalues (sorted descending)
        Shape: (3,) for single input, (N, 3) for batch
    """
    s_vec = np.atleast_2d(s_vec)
    batch_size = s_vec.shape[0]

    # Reconstruct 3x3 symmetric matrix components
    s00, s11, s22 = s_vec[:, 0], s_vec[:, 1], s_vec[:, 2]
    s12, s02, s01 = s_vec[:, 3], s_vec[:, 4], s_vec[:, 5]  # off-diagonal: yz, xz, xy

    # Invariants of the matrix
    I1 = s00 + s11 + s22
    I2 = s00*s11 + s11*s22 + s22*s00 - s01**2 - s02**2 - s12**2
    I3 = (s00*s11*s22 + 2*s01*s02*s12
          - s00*s12**2 - s11*s02**2 - s22*s01**2)

    # For Cardano's formula: characteristic eq is λ³ - I₁λ² + I₂λ - I₃ = 0
    # Substitute λ = μ + I₁/3 to eliminate quadratic term: μ³ + pμ + q = 0
    p = I2 - I1**2 / 3.0
    q = I3 - I1*I2/3.0 + 2.0*I1**3/27.0

    eig = np.zeros((batch_size, 3))

    # Check if matrix is essentially diagonal (p ≈ 0)
    diagonal_mask = np.abs(p) < 1e-14

    # Handle diagonal case
    if np.any(diagonal_mask):
        eig[diagonal_mask, 0] = s00[diagonal_mask]
        eig[diagonal_mask, 1] = s11[diagonal_mask]
        eig[diagonal_mask, 2] = s22[diagonal_mask]

    # Handle non-diagonal case (Cardano's trigonometric solution)
    non_diag = ~diagonal_mask & (p < 0)
    if np.any(non_diag):
        r = np.sqrt(np.abs(p[non_diag]) / 3.0)

        # Clamp argument for numerical stability
        cos_arg = -q[non_diag] / (2.0 * r**3)
        cos_arg = np.clip(cos_arg, -1.0, 1.0)

        theta = np.arccos(cos_arg) / 3.0
        shift = I1[non_diag] / 3.0

        # Three roots
        eig[non_diag, 0] = 2.0 * r * np.cos(theta) + shift
        eig[non_diag, 1] = 2.0 * r * np.cos(theta + 2.0*np.pi/3.0) + shift
        eig[non_diag, 2] = 2.0 * r * np.cos(theta + 4.0*np.pi/3.0) + shift

    # Handle degenerate case (p >= 0, non-diagonal)
    degenerate = ~diagonal_mask & (p >= 0)
    if np.any(degenerate):
        eig[degenerate, 0] = s00[degenerate]
        eig[degenerate, 1] = s11[degenerate]
        eig[degenerate, 2] = s22[degenerate]

    # Sort descending
    eig = -np.sort(-eig, axis=1)

    return eig.squeeze() if batch_size == 1 else eig


def barlat_equivalent_stress(
    stress_voigt: np.ndarray,
    L1: np.ndarray,
    L2: np.ndarray,
    a: float = 8.0
) -> Union[float, np.ndarray]:
    """
    Compute equivalent stress according to Barlat 2004-18p criterion.

    Yield criterion:
        Φ = [1/4 Σᵢⱼ |λ'ᵢ - λ''ⱼ|^a]^(1/a)

    where λ', λ'' are eigenvalues of linearly transformed stress deviators.

    Args:
        stress_voigt: Cauchy stress in Voigt notation [σ11, σ22, σ33, σ23, σ13, σ12]
                     Can be single vector (6,) or batch (N, 6)
        L1: First 6x6 linear transformation matrix
        L2: Second 6x6 linear transformation matrix
        a: Yield exponent (8 for FCC metals, 6 for BCC)

    Returns:
        Equivalent stress σ_eq (scalar for single input, array for batch)
    """
    stress_voigt = np.atleast_2d(stress_voigt)

    # Get deviatoric stress
    s = stress_deviator(stress_voigt)

    # Apply linear transformations
    s_prime = s @ L1.T
    s_double_prime = s @ L2.T

    # Compute eigenvalues
    lam_prime = cardano_eigenvalues(s_prime)
    lam_double_prime = cardano_eigenvalues(s_double_prime)

    # Barlat 18p summation: Σᵢⱼ |λ'ᵢ - λ''ⱼ|^a
    lam_prime = np.atleast_2d(lam_prime)
    lam_double_prime = np.atleast_2d(lam_double_prime)

    phi_sum = 0.0
    for i in range(3):
        for j in range(3):
            diff = lam_prime[:, i] - lam_double_prime[:, j]
            phi_sum += np.abs(diff)**a

    # Equivalent stress
    sigma_eq = (phi_sum / 4.0)**(1.0 / a)

    return float(sigma_eq) if stress_voigt.shape[0] == 1 else sigma_eq


def barlat_yield_function(
    stress_voigt: np.ndarray,
    L1: np.ndarray,
    L2: np.ndarray,
    sigma_y: float,
    a: float = 8.0
) -> Union[float, np.ndarray]:
    """
    Evaluate yield function: f = σ_eq - σ_y

    Args:
        stress_voigt: Cauchy stress in Voigt notation
        L1: First 6x6 linear transformation matrix
        L2: Second 6x6 linear transformation matrix
        sigma_y: Initial yield stress
        a: Yield exponent (8 for FCC, 6 for BCC)

    Returns:
        Yield function value (f ≤ 0 for elastic, f > 0 for plastic)
    """
    sigma_eq = barlat_equivalent_stress(stress_voigt, L1, L2, a)
    return sigma_eq - sigma_y


# ============================================================================
# Helper Functions for Transformation Matrices
# ============================================================================

def get_isotropic_L_matrices() -> Tuple[np.ndarray, np.ndarray]:
    """
    Return L1 and L2 matrices that recover isotropic von Mises yield.

    For isotropic case: L1 = L2 = deviatoric projection operator

    Returns:
        Tuple of (L1, L2) 6x6 matrices
    """
    # Identity on deviatoric subspace (Voigt notation)
    L_iso = np.array([
        [ 2/3, -1/3, -1/3, 0, 0, 0],
        [-1/3,  2/3, -1/3, 0, 0, 0],
        [-1/3, -1/3,  2/3, 0, 0, 0],
        [   0,    0,    0, 1, 0, 0],
        [   0,    0,    0, 0, 1, 0],
        [   0,    0,    0, 0, 0, 1]
    ], dtype=np.float64)
    return L_iso, L_iso


def get_example_aluminum_matrices() -> Tuple[np.ndarray, np.ndarray]:
    """
    Example anisotropy matrices for 2008-T4 aluminum alloy.

    These are illustrative values - real calibration requires experimental data
    from tension/compression tests at multiple orientations.

    Returns:
        Tuple of (L1, L2) 6x6 matrices
    """
    L1 = np.array([
        [ 0.069,  0.936, -0.079, 0, 0, 0],
        [ 0.079,  0.931, -0.082, 0, 0, 0],
        [ 0.005, -0.010,  1.005, 0, 0, 0],
        [     0,      0,      0, 1, 0, 0],
        [     0,      0,      0, 0, 1, 0],
        [     0,      0,      0, 0, 0, 1]
    ], dtype=np.float64)

    L2 = np.array([
        [ 0.981,  0.028,  0.029, 0, 0, 0],
        [ 0.030,  0.992,  0.051, 0, 0, 0],
        [-0.008, -0.020,  0.972, 0, 0, 0],
        [     0,      0,      0, 1, 0, 0],
        [     0,      0,      0, 0, 1, 0],
        [     0,      0,      0, 0, 0, 1]
    ], dtype=np.float64)

    return L1, L2


# ============================================================================
# Test / Demonstration
# ============================================================================
if __name__ == "__main__":
    print("Testing Barlat 2004-18p with isotropic matrices...")

    L1, L2 = get_isotropic_L_matrices()
    sigma_y = 250.0  # MPa
    a = 8  # FCC exponent

    # Test cases
    # Uniaxial tension
    stress_uniaxial = np.array([sigma_y, 0, 0, 0, 0, 0])
    f_uniaxial = barlat_yield_function(stress_uniaxial, L1, L2, sigma_y, a)

    # Pure shear (τ = σ_y/√3 for von Mises)
    tau_y = sigma_y / np.sqrt(3.0)
    stress_shear = np.array([0, 0, 0, 0, 0, tau_y])
    f_shear = barlat_yield_function(stress_shear, L1, L2, sigma_y, a)

    print(f"Uniaxial tension: f = {f_uniaxial:.6f} (expect ≈ 0)")
    print(f"Pure shear:       f = {f_shear:.6f} (expect ≈ 0)")

    # Test anisotropic response
    print("\nTesting with anisotropic aluminum matrices...")
    L1_al, L2_al = get_example_aluminum_matrices()

    # Test yield stress at different angles
    angles = np.array([0.0, 45.0, 90.0])

    for angle in angles:
        theta = angle * np.pi / 180.0
        c, s = np.cos(theta), np.sin(theta)

        # Uniaxial stress at angle theta (simplified 2D rotation in xy plane)
        sig_xx = sigma_y * c * c
        sig_yy = sigma_y * s * s
        sig_xy = sigma_y * c * s

        stress = np.array([sig_xx, sig_yy, 0, 0, 0, sig_xy])
        sigma_eq = barlat_equivalent_stress(stress, L1_al, L2_al, a)

        print(f"Angle {angle:.0f}°: σ_eq/σ_y = {sigma_eq/sigma_y:.4f}")

    # Test batch processing
    print("\nTesting batch processing...")
    stress_batch = np.array([
        [sigma_y, 0, 0, 0, 0, 0],
        [0, sigma_y, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, tau_y]
    ])
    sigma_eq_batch = barlat_equivalent_stress(stress_batch, L1, L2, a)
    print(f"Batch equivalent stresses: {sigma_eq_batch}")

    print("\n✓ Barlat 2004-18p NumPy tests completed")
