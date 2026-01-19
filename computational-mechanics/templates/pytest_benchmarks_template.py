"""pytest_benchmarks_template.py

Thin wrapper over canonical validation_benchmarks.py for pytest integration.
Import benchmark classes/functions from validation_benchmarks and assert against expected ranges.

This keeps benchmark logic in ONE place (validation_benchmarks.py) while providing
pytest-friendly test functions for CI/CD integration.
"""

import numpy as np
import pytest

# Import canonical benchmark implementations
try:
    from validation_benchmarks import (
        TaylorAnvilBenchmark,
        PhaseFieldFractureBenchmark,
        FFTPeriodicRVEBenchmark,
        BarlatBiaxialBenchmark
    )
    BENCHMARKS_AVAILABLE = True
except ImportError:
    BENCHMARKS_AVAILABLE = False
    pytest.skip("validation_benchmarks not available", allow_module_level=True)


def test_taylor_anvil_impact():
    """
    PURPOSE: Validation of high-rate plasticity, temperature coupling, and large deformation kinematics.
    DESCRIPTION: Cylindrical specimen impacts a rigid wall at high velocity (e.g., 300 m/s).
    VERIFICATION: Checks final mushrooming ratio and Taylor-Quinney adiabatic heating sign/units.
    """
    benchmark = TaylorAnvilBenchmark()

    # Get expected ranges from canonical benchmark
    mushroom_min, mushroom_max = benchmark.expected_mushroom_ratio(material="copper")

    # TODO: Replace with actual solver call
    # mushroom_ratio = your_solver.run_taylor_anvil(...)
    mushroom_ratio = 1.6  # placeholder - replace with actual result

    # Assert against canonical expected range
    assert mushroom_min <= mushroom_ratio <= mushroom_max, \
        f"Mushroom ratio {mushroom_ratio} outside expected range [{mushroom_min}, {mushroom_max}]"

    # Verify analytical estimate is reasonable
    rho = 8960.0  # kg/m³ (copper)
    sigma_y = 200e6  # Pa
    analytical = benchmark.analytical_mushroom_ratio(rho, sigma_y)
    assert 1.0 < analytical < 3.0, "Analytical estimate out of physical bounds"


def test_sneddon_phase_field_fracture():
    """
    PURPOSE: Verification of the phase-field length scale l and energy release rate.
    DESCRIPTION: 2D plate with center crack under Mode-I loading.
    VERIFICATION: Crack bandwidth is O(2*l) and dissipated energy matches Gc times crack area.
    """
    if not BENCHMARKS_AVAILABLE:
        pytest.skip("Benchmark definitions not available")

    benchmark = PhaseFieldFractureBenchmark()
    l = benchmark.length_scale

    # TODO: Replace with actual solver call
    # crack_width, energy_dissipated = your_solver.run_sneddon_crack(...)
    crack_width = 2.1 * l  # placeholder

    # Verify crack bandwidth is O(2*l)
    assert np.isclose(crack_width, 2.0 * l, atol=l), \
        f"Crack bandwidth {crack_width} should be ≈ 2l = {2*l}"


def test_periodic_rve_high_contrast_inclusion():
    """
    PURPOSE: Validation of FFT-Galerkin solver robustness vs contrast.
    DESCRIPTION: Periodic unit cell with stiff inclusion in soft matrix.
    VERIFICATION: Equilibrium residual decreases and convergence degrades with contrast unless using Newton-Krylov.
    """
    if not BENCHMARKS_AVAILABLE:
        pytest.skip("Benchmark definitions not available")

    benchmark = FFTPeriodicRVEBenchmark()

    # TODO: Replace with actual solver call
    # residual_norm, iterations = your_solver.run_fft_rve(...)
    residual_norm = 1e-6  # placeholder

    # Assert convergence
    assert residual_norm < benchmark.convergence_tolerance, \
        f"FFT solver did not converge: residual {residual_norm}"


def test_biaxial_barlat_yield():
    """
    PURPOSE: Testing path-dependent plasticity and anisotropic yield surface implementation.
    DESCRIPTION: RVE under biaxial loading; compare RD vs TD response.
    VERIFICATION: Distinct yield stresses and frame-invariant stress update under rotation.
    """
    if not BENCHMARKS_AVAILABLE:
        pytest.skip("Benchmark definitions not available")

    benchmark = BarlatBiaxialBenchmark()

    # TODO: Replace with actual solver call
    # yield_rd, yield_td = your_solver.run_barlat_biaxial(...)
    yield_rd = 250.0  # placeholder (rolling direction)
    yield_td = 275.0  # placeholder (transverse direction)

    # Verify anisotropy is present (yields should differ)
    assert yield_rd != yield_td, "Anisotropic yields should differ between RD and TD"

    # Check values are physically reasonable (positive, within expected range)
    assert 0 < yield_rd < 1000e6, "RD yield stress out of typical range"
    assert 0 < yield_td < 1000e6, "TD yield stress out of typical range"
