"""miehe_spectral_split.py

Miehe-type spectral decomposition for tension/compression split.

Given a symmetric strain tensor eps (3x3), compute:
- eps_plus, eps_minus
- psi_plus, psi_minus for linear isotropic elasticity

This is used in phase-field fracture to avoid crack growth in compression.
"""

from __future__ import annotations

import numpy as np

from .tensor_ops import sym_eigh


def positive_part(x: np.ndarray) -> np.ndarray:
    return np.maximum(x, 0.0)


def negative_part(x: np.ndarray) -> np.ndarray:
    return np.minimum(x, 0.0)


def spectral_split(eps: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (eps_plus, eps_minus)."""
    vals, vecs = sym_eigh(eps)
    vals_p = positive_part(vals)
    vals_m = negative_part(vals)
    eps_p = vecs @ np.diag(vals_p) @ vecs.T
    eps_m = vecs @ np.diag(vals_m) @ vecs.T
    # symmetrize for safety
    eps_p = (eps_p + eps_p.T) * 0.5
    eps_m = (eps_m + eps_m.T) * 0.5
    return eps_p, eps_m


def miehe_energy_split(eps: np.ndarray, lam: float, mu: float) -> tuple[float, float, dict]:
    """Compute psi_plus and psi_minus for linear isotropic elasticity.

    psi_plus  = 0.5*lam*<tr(eps)>_+^2 + mu*tr(eps_plus^2)
    psi_minus = 0.5*lam*<tr(eps)>_-^2 + mu*tr(eps_minus^2)
    """
    eps_p, eps_m = spectral_split(eps)
    tr = np.trace(eps)
    tr_p = max(tr, 0.0)
    tr_m = min(tr, 0.0)

    psi_p = 0.5 * lam * tr_p**2 + mu * float(np.tensordot(eps_p, eps_p))
    psi_m = 0.5 * lam * tr_m**2 + mu * float(np.tensordot(eps_m, eps_m))

    aux = {
        "eps_plus": eps_p,
        "eps_minus": eps_m,
        "trace": float(tr),
        "trace_plus": float(tr_p),
        "trace_minus": float(tr_m),
    }
    return float(psi_p), float(psi_m), aux
