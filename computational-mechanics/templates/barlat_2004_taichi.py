"""
Barlat 2004-18p Anisotropic Yield Function Implementation in Taichi.

This constitutive model uses two linear transformations of the stress
deviator to capture high-fidelity anisotropy in metals (e.g., Aluminum).

Reference:
    Barlat, F., et al. "Linear transformation-based anisotropic yield functions."
    Int. J. Plasticity 21 (2005) 1009-1039.
"""

import taichi as ti
import numpy as np

@ti.data_oriented
class Barlat04:
    """
    Barlat 2004-18p yield function with analytical eigenvalue solver.
    
    Yield criterion:
        Φ = [1/4 Σᵢⱼ |λ'ᵢ - λ''ⱼ|^a]^(1/a) - σ_y = 0
    
    where λ', λ'' are eigenvalues of linearly transformed stress deviators.
    """
    
    def __init__(self, a: float, L1: np.ndarray, L2: np.ndarray, sigma_y: float = 1.0):
        """
        Initialize Barlat 2004-18p model.
        
        Args:
            a: Yield exponent (8 for FCC metals, 6 for BCC)
            L1: First 6x6 linear transformation matrix (numpy array)
            L2: Second 6x6 linear transformation matrix (numpy array)
            sigma_y: Initial yield stress
        """
        self.a = a
        self.sigma_y = ti.field(dtype=ti.f64, shape=())
        self.sigma_y[None] = sigma_y
        
        # Store transformation matrices as Taichi fields
        self.L1 = ti.Matrix.field(6, 6, dtype=ti.f64, shape=())
        self.L2 = ti.Matrix.field(6, 6, dtype=ti.f64, shape=())
        self.L1[None] = ti.Matrix(L1.tolist())
        self.L2[None] = ti.Matrix(L2.tolist())
        
    @ti.func
    def stress_deviator(self, stress_voigt: ti.template()) -> ti.template():
        """
        Extract deviatoric part of stress tensor in Voigt notation.
        
        Args:
            stress_voigt: [σ11, σ22, σ33, σ23, σ13, σ12]
            
        Returns:
            Deviatoric stress in Voigt notation
        """
        p = (stress_voigt[0] + stress_voigt[1] + stress_voigt[2]) / 3.0
        s = ti.Vector([
            stress_voigt[0] - p,
            stress_voigt[1] - p,
            stress_voigt[2] - p,
            stress_voigt[3],
            stress_voigt[4],
            stress_voigt[5]
        ], dt=ti.f64)
        return s
    
    @ti.func
    def cardano_eigenvalues(self, s_vec: ti.template()) -> ti.template():
        """
        Analytical eigenvalue solver for symmetric 3x3 matrix using Cardano's formula.
        
        The stress deviator (from 6-vector) has eigenvalues that sum to zero.
        
        Args:
            s_vec: Transformed deviator [s11, s22, s33, s23, s13, s12]
            
        Returns:
            Vector of 3 eigenvalues (sorted descending)
        """
        # Reconstruct 3x3 symmetric matrix components
        s00, s11, s22 = s_vec[0], s_vec[1], s_vec[2]
        s12, s02, s01 = s_vec[3], s_vec[4], s_vec[5]  # off-diagonal: yz, xz, xy
        
        # Invariants of the matrix
        I1 = s00 + s11 + s22
        I2 = s00*s11 + s11*s22 + s22*s00 - s01**2 - s02**2 - s12**2
        I3 = (s00*s11*s22 + 2*s01*s02*s12 
              - s00*s12**2 - s11*s02**2 - s22*s01**2)
        
        # For Cardano's formula: characteristic eq is λ³ - I₁λ² + I₂λ - I₃ = 0
        # Substitute λ = μ + I₁/3 to eliminate quadratic term:
        # μ³ + pμ + q = 0
        p = I2 - I1**2 / 3.0
        q = I3 - I1*I2/3.0 + 2.0*I1**3/27.0
        
        # Default result
        eig = ti.Vector([0.0, 0.0, 0.0], dt=ti.f64)
        
        # Check if matrix is essentially diagonal (p ≈ 0)
        discriminant = -(4*p**3 + 27*q**2)
        
        if ti.abs(p) < 1e-14:
            # Nearly diagonal - eigenvalues are diagonal entries
            eig[0] = s00
            eig[1] = s11
            eig[2] = s22
        else:
            # Cardano's trigonometric solution for 3 real roots
            # r = √(-p/3), cos(3θ) = 3q/(2p) * √(-3/p)
            r = ti.sqrt(ti.abs(p) / 3.0)
            
            # Clamp argument for numerical stability
            cos_arg = -q / (2.0 * r**3)
            cos_arg = ti.max(-1.0, ti.min(1.0, cos_arg))
            
            theta = ti.acos(cos_arg) / 3.0
            
            # Three roots
            PI = 3.14159265358979323846
            shift = I1 / 3.0
            
            if p < 0:
                eig[0] = 2.0 * r * ti.cos(theta) + shift
                eig[1] = 2.0 * r * ti.cos(theta + 2.0*PI/3.0) + shift
                eig[2] = 2.0 * r * ti.cos(theta + 4.0*PI/3.0) + shift
            else:
                # p > 0: use hyperbolic solution (shouldn't happen for deviatoric)
                eig[0] = s00
                eig[1] = s11
                eig[2] = s22
        
        # Sort descending (bubble sort for 3 elements)
        if eig[0] < eig[1]:
            eig[0], eig[1] = eig[1], eig[0]
        if eig[1] < eig[2]:
            eig[1], eig[2] = eig[2], eig[1]
        if eig[0] < eig[1]:
            eig[0], eig[1] = eig[1], eig[0]
            
        return eig
    
    @ti.func
    def get_equivalent_stress(self, stress_voigt: ti.template()) -> ti.f64:
        """
        Compute equivalent stress according to Barlat 2004-18p criterion.
        
        Args:
            stress_voigt: Cauchy stress in Voigt notation [σ11, σ22, σ33, σ23, σ13, σ12]
            
        Returns:
            Equivalent stress σ_eq
        """
        # Get deviatoric stress
        s = self.stress_deviator(stress_voigt)
        
        # Apply linear transformations
        s_prime = self.L1[None] @ s
        s_double_prime = self.L2[None] @ s
        
        # Compute eigenvalues
        lam_prime = self.cardano_eigenvalues(s_prime)
        lam_double_prime = self.cardano_eigenvalues(s_double_prime)
        
        # Barlat 18p summation: Σᵢⱼ |λ'ᵢ - λ''ⱼ|^a
        phi_sum = 0.0
        for i in ti.static(range(3)):
            for j in ti.static(range(3)):
                diff = lam_prime[i] - lam_double_prime[j]
                phi_sum += ti.pow(ti.abs(diff), self.a)
        
        # Equivalent stress
        sigma_eq = ti.pow(phi_sum / 4.0, 1.0 / self.a)
        
        return sigma_eq
    
    @ti.func
    def yield_function(self, stress_voigt: ti.template()) -> ti.f64:
        """
        Evaluate yield function: f = σ_eq - σ_y
        
        Args:
            stress_voigt: Cauchy stress in Voigt notation
            
        Returns:
            Yield function value (f ≤ 0 for elastic, f > 0 for plastic)
        """
        sigma_eq = self.get_equivalent_stress(stress_voigt)
        return sigma_eq - self.sigma_y[None]


def get_isotropic_L_matrices():
    """
    Return L1 and L2 matrices that recover isotropic von Mises yield.
    
    For isotropic case: L1 = L2 = deviatoric projection operator
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


def get_example_aluminum_matrices():
    """
    Example anisotropy matrices for 2008-T4 aluminum alloy.
    
    These are illustrative values - real calibration requires experimental data.
    """
    # Simplified transformation matrices (not fully calibrated)
    # Real applications need fitting to tension/compression tests at multiple angles
    
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
    ti.init(arch=ti.cpu, default_fp=ti.f64)
    
    # Test with isotropic matrices (should recover von Mises)
    print("Testing Barlat 2004-18p with isotropic matrices...")
    
    L1, L2 = get_isotropic_L_matrices()
    sigma_y = 250.0  # MPa
    a = 8  # FCC exponent
    
    model = Barlat04(a=a, L1=L1, L2=L2, sigma_y=sigma_y)
    
    # Test cases
    @ti.kernel
    def test_yield() -> ti.f64:
        # Uniaxial tension
        stress_uniaxial = ti.Vector([sigma_y, 0, 0, 0, 0, 0], dt=ti.f64)
        f_uniaxial = model.yield_function(stress_uniaxial)
        
        # Pure shear (τ = σ_y/√3 for von Mises)
        tau_y = sigma_y / ti.sqrt(3.0)
        stress_shear = ti.Vector([0, 0, 0, 0, 0, tau_y], dt=ti.f64)
        f_shear = model.yield_function(stress_shear)
        
        # Print results (should both be ≈ 0 at yield)
        print(f"Uniaxial tension: f = {f_uniaxial:.6f} (expect ≈ 0)")
        print(f"Pure shear:       f = {f_shear:.6f} (expect ≈ 0)")
        
        return f_uniaxial
    
    test_yield()
    
    # Test anisotropic response
    print("\nTesting with anisotropic aluminum matrices...")
    L1_al, L2_al = get_example_aluminum_matrices()
    model_aniso = Barlat04(a=8, L1=L1_al, L2=L2_al, sigma_y=sigma_y)
    
    @ti.kernel
    def test_anisotropy():
        # Test yield stress at different angles
        angles = ti.Vector([0.0, 45.0, 90.0], dt=ti.f64)
        
        for idx in ti.static(range(3)):
            theta = angles[idx] * 3.14159265 / 180.0
            c, s = ti.cos(theta), ti.sin(theta)
            
            # Uniaxial stress at angle theta (simplified 2D rotation in xy plane)
            sig_xx = sigma_y * c * c
            sig_yy = sigma_y * s * s
            sig_xy = sigma_y * c * s
            
            stress = ti.Vector([sig_xx, sig_yy, 0, 0, 0, sig_xy], dt=ti.f64)
            sigma_eq = model_aniso.get_equivalent_stress(stress)
            
            print(f"Angle {angles[idx]:.0f}°: σ_eq/σ_y = {sigma_eq/sigma_y:.4f}")
    
    test_anisotropy()
    
    print("\n✓ Barlat 2004-18p tests completed")
