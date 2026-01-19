"""fft_lippmann_schwinger.py

Minimal Lippmann-Schwinger (LS) fixed-point skeleton.

This is a teaching template, not a full solver.
You provide:
- constitutive(eps, state) -> sigma, state
- green_operator_hat(k) -> Gamma0_hat (6x6 in Voigt)

Important: handle k=0 (DC component) separately to enforce macroscopic control.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Tuple

import numpy as np


ConstitutiveFn = Callable[[np.ndarray, object], Tuple[np.ndarray, object]]
GreenOpFn = Callable[[np.ndarray], np.ndarray]


@dataclass
class LSOptions:
    max_iter: int = 2000
    tol: float = 1e-8
    relaxation: float = 1.0


def lippmann_schwinger_fixed_point(
    E_macro: np.ndarray,
    eps: np.ndarray,
    state: object,
    constitutive: ConstitutiveFn,
    green_op_hat: GreenOpFn,
    C0: np.ndarray,
    kgrid: np.ndarray,
    opts: LSOptions = LSOptions(),
):
    """Solve eps(x) with a fixed-point LS iteration.

    Shapes
    - eps: (Nx,Ny,Nz,6) Voigt strain field
    - E_macro: (6,) macro strain
    - C0: (6,6) reference stiffness
    - kgrid: (Nx,Ny,Nz,3) wavevectors

    Returns (eps, state, info)
    """
    Nx, Ny, Nz, _ = eps.shape

    def fft_field(f):
        return np.fft.fftn(f, axes=(0, 1, 2))

    def ifft_field(F):
        return np.fft.ifftn(F, axes=(0, 1, 2)).real

    info = {"iters": 0, "converged": False}

    for it in range(opts.max_iter):
        # 1) constitutive update at each voxel
        sigma = np.zeros_like(eps)
        for ix in range(Nx):
            for iy in range(Ny):
                for iz in range(Nz):
                    sigma[ix, iy, iz], state = constitutive(eps[ix, iy, iz], state)

        # 2) polarization tau = sigma - C0:eps
        tau = sigma - np.einsum("ij,xyzj->xyzi", C0, eps)

        # 3) eps = E - invFFT(Gamma_hat : FFT(tau))
        tau_hat = fft_field(tau)
        corr_hat = np.zeros_like(tau_hat)

        for ix in range(Nx):
            for iy in range(Ny):
                for iz in range(Nz):
                    k = kgrid[ix, iy, iz]
                    if np.allclose(k, 0.0):
                        continue  # DC mode: keep macro strain
                    Gamma = green_op_hat(k)  # (6,6)
                    corr_hat[ix, iy, iz] = Gamma @ tau_hat[ix, iy, iz]

        corr = ifft_field(corr_hat)
        eps_new = E_macro[None, None, None, :] - corr

        # 4) relaxation
        eps = (1.0 - opts.relaxation) * eps + opts.relaxation * eps_new

        # 5) convergence (simple norm on change)
        d = np.linalg.norm(eps_new - eps) / max(1.0, np.linalg.norm(eps))
        info["iters"] = it + 1
        if d < opts.tol:
            info["converged"] = True
            break

    return eps, state, info
