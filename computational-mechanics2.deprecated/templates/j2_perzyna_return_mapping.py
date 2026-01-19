"""j2_perzyna_return_mapping.py

Implicit backward-Euler Perzyna J2 viscoplasticity (small strain kernel).

This template is intentionally small-strain to keep the algebra readable.
For finite strain, wrap it in a corotational frame or embed in a multiplicative update (Fp).

State
- ep_p: plastic strain tensor (3x3 sym)
- kappa: equivalent plastic strain

Material
- E, nu: elastic moduli
- sig0, H: yield and isotropic hardening
- eta_v, m: viscosity and rate exponent

Conventions
- input strain increment is total small-strain increment dE (3x3 sym)
"""

from __future__ import annotations

import numpy as np

from .tensor_ops import deviator, mises_q


def elastic_stiffness(E: float, nu: float) -> tuple[float, float]:
    """Return Lamé parameters (lam, mu)."""
    mu = E / (2.0 * (1.0 + nu))
    lam = E * nu / ((1.0 + nu) * (1.0 - 2.0 * nu))
    return lam, mu


def hooke_stress(dE: np.ndarray, lam: float, mu: float) -> np.ndarray:
    """Linear elastic stress for strain tensor dE."""
    return 2.0 * mu * dE + lam * np.trace(dE) * np.eye(3)


def perzyna_update(
    sigma_n: np.ndarray,
    ep_p_n: np.ndarray,
    kappa_n: float,
    dE: np.ndarray,
    dt: float,
    *,
    E: float,
    nu: float,
    sig0: float,
    H: float,
    eta_v: float,
    m: float,
    sigma_ref: float = 1.0,
    newton_max: int = 30,
    newton_tol: float = 1e-10,
) -> dict:
    """Implicit BE update.

    Returns dict with keys: sigma, ep_p, kappa, dgamma, converged
    """
    lam, mu = elastic_stiffness(E, nu)

    # Elastic predictor
    sigma_tr = sigma_n + hooke_stress(dE, lam, mu)
    s_tr = deviator(sigma_tr)
    q_tr = np.sqrt(1.5 * np.tensordot(s_tr, s_tr))

    sig_y = sig0 + H * kappa_n
    Phi_tr = q_tr - sig_y

    if Phi_tr <= 0.0:
        return {
            "sigma": sigma_tr,
            "ep_p": ep_p_n,
            "kappa": kappa_n,
            "dgamma": 0.0,
            "converged": True,
        }

    # Solve for dgamma from Perzyna law (implicit): dgamma/dt = (1/eta_v) <Phi/sigma_ref>^m
    # Need Phi(dgamma) because q decreases with plastic flow.
    # For J2 radial return in small strain: q = q_tr - 3*mu*dgamma

    def Phi_of(dgamma: float) -> float:
        kappa = kappa_n + np.sqrt(2.0 / 3.0) * dgamma
        sig_y_loc = sig0 + H * kappa
        q = q_tr - 3.0 * mu * dgamma
        return q - sig_y_loc

    def g(dgamma: float) -> float:
        Phi = Phi_of(dgamma)
        Phi_pos = max(Phi, 0.0)
        rhs = dt * (1.0 / eta_v) * (Phi_pos / sigma_ref) ** m
        return dgamma - rhs

    dgamma = 0.0
    converged = False
    for _ in range(newton_max):
        val = g(dgamma)
        if abs(val) < newton_tol:
            converged = True
            break
        # finite difference derivative (template). In production, derive analytic.
        h = 1e-8 * max(1.0, abs(dgamma))
        der = (g(dgamma + h) - val) / h
        der = der if abs(der) > 1e-14 else 1e-14
        dgamma = max(0.0, dgamma - val / der)

    # Update direction
    n = s_tr / (np.linalg.norm(s_tr) + 1e-30)

    sigma = sigma_tr - 2.0 * mu * dgamma * (3.0 / 2.0) * n
    ep_p = ep_p_n + dgamma * (3.0 / 2.0) * n
    kappa = kappa_n + np.sqrt(2.0 / 3.0) * dgamma

    return {
        "sigma": sigma,
        "ep_p": ep_p,
        "kappa": kappa,
        "dgamma": float(dgamma),
        "converged": converged,
        "Phi_final": float(Phi_of(dgamma)),
    }
