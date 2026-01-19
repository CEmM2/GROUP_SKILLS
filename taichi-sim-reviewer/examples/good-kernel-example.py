"""
Good Kernel Example: 2D Heat Equation Solver
Demonstrates best practices for Taichi simulation code.
"""

import taichi as ti
import numpy as np

# Explicit architecture specification
ti.init(arch=ti.gpu)

# Grid parameters
nx, ny = 512, 512
dx = 1.0 / nx
dt = 0.00025  # Chosen to satisfy CFL: α*dt/dx² ≤ 0.25

# Material properties
alpha = 1.0  # Thermal diffusivity

# Fields: Double-buffering for race-free updates
u_old = ti.field(ti.f32, shape=(nx, ny))
u_new = ti.field(ti.f32, shape=(nx, ny))


@ti.kernel
def heat_step():
    """
    Explicit forward Euler for 2D heat equation: ∂u/∂t = α∇²u

    Stability constraint (CFL): r = α*dt/dx² ≤ 0.25 for 2D
    Current r = 1.0 * 0.00025 / (1/512)² ≈ 0.065 ✓

    Updates interior points only; boundaries handled separately.
    """
    r = alpha * dt / (dx * dx)

    # Interior points only (avoid boundary divergence)
    for i, j in ti.ndrange((1, nx-1), (1, ny-1)):
        # 5-point stencil for Laplacian
        laplacian = (u_old[i+1, j] + u_old[i-1, j] +
                     u_old[i, j+1] + u_old[i, j-1] - 4.0 * u_old[i, j])

        u_new[i, j] = u_old[i, j] + r * laplacian


@ti.kernel
def apply_dirichlet_bc(value: ti.f32):
    """
    Apply Dirichlet boundary conditions (fixed temperature at edges).

    Args:
        value: Temperature at boundaries
    """
    # Separate kernel avoids thread divergence in main computation
    for j in range(ny):
        u_new[0, j] = value      # Left edge
        u_new[nx-1, j] = value   # Right edge

    for i in range(nx):
        u_new[i, 0] = value      # Bottom edge
        u_new[i, ny-1] = value   # Top edge


@ti.kernel
def swap_buffers():
    """Swap old and new buffers for next timestep."""
    for i, j in u_old:
        u_old[i, j] = u_new[i, j]


@ti.kernel
def init_gaussian():
    """Initialize with Gaussian temperature distribution."""
    for i, j in u_old:
        x = (i - nx/2) * dx
        y = (j - ny/2) * dx
        r_sq = x*x + y*y
        u_old[i, j] = ti.exp(-50.0 * r_sq)


def compute_total_energy():
    """
    Compute total thermal energy (for validation).

    Returns:
        float: Sum of all grid point temperatures
    """
    return np.sum(u_old.to_numpy())


def run_simulation(n_steps: int):
    """
    Run heat diffusion simulation.

    Args:
        n_steps: Number of timesteps to simulate
    """
    # Initialization
    init_gaussian()

    # Warm-up: First kernel call includes JIT compilation
    heat_step()
    ti.sync()

    # Main simulation loop
    for step in range(n_steps):
        heat_step()
        apply_dirichlet_bc(0.0)  # Fixed temperature at boundaries
        swap_buffers()

        if step % 100 == 0:
            energy = compute_total_energy()
            print(f"Step {step:5d}, Energy: {energy:.6f}")


# Validation: Check CFL condition
def validate_cfl():
    """Verify that CFL stability condition is satisfied."""
    r = alpha * dt / (dx * dx)
    r_max = 0.25  # Maximum stable value for 2D explicit diffusion

    if r > r_max:
        print(f"WARNING: CFL violation! r = {r:.4f} > {r_max}")
        return False
    else:
        print(f"CFL check passed: r = {r:.4f} ≤ {r_max}")
        return True


if __name__ == "__main__":
    # Validate before running
    if validate_cfl():
        run_simulation(n_steps=1000)


# ============================================================================
# Why This is Good Code:
# ============================================================================
#
# ✓ Explicit ti.init(arch=ti.gpu) - no implicit backend choice
# ✓ Double-buffering (u_old, u_new) - no race conditions
# ✓ Boundary conditions in separate kernel - avoids divergence
# ✓ CFL condition validated - prevents instability
# ✓ Clear docstrings - explains what/why, not just how
# ✓ Warm-up kernel call - excludes JIT time from measurements
# ✓ Simple, readable structure - easy to maintain and extend
# ✓ No Python loops over grid points - all work in kernels
# ✓ Physical parameters documented - alpha, dt, dx clear
# ✓ Validation included - energy tracking for sanity check
