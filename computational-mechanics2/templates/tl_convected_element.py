"""tl_convected_element.py

Template: Total Lagrangian element kinematics using convected coordinates.

This is *not* a full FE element implementation. It just shows the data flow:
- compute convected basis vectors and metrics
- compute Green strain E_ij = 0.5*(g_ij - G_ij)
- expose hooks for constitutive law and internal force integration

Porting notes
- For Taichi kernels, keep the same operations but switch arrays to ti.Matrix/ti.Vector.
"""

from __future__ import annotations

import numpy as np


def covariant_basis(xa: np.ndarray, dN_dxi: np.ndarray) -> np.ndarray:
    """Compute covariant basis vectors g_i = sum_a x_a * dN_a/dxi^i.

    Parameters
    - xa: nodal coordinates (nnode,3) in current configuration
    - dN_dxi: derivatives of shape functions in convected coords (nnode,3)
      where the second axis corresponds to i=0..2 for xi^1..xi^3

    Returns
    - g: (3,3) with rows g_i (i=0..2)
    """
    xa = np.asarray(xa)
    dN_dxi = np.asarray(dN_dxi)
    assert xa.shape[1] == 3
    assert dN_dxi.shape[1] == 3

    g = np.zeros((3, 3), dtype=xa.dtype)
    for a in range(xa.shape[0]):
        # outer product: (3,) (3,) -> (3,3)
        g += np.outer(dN_dxi[a], xa[a])
    return g


def metric_from_basis(g: np.ndarray) -> np.ndarray:
    """Metric g_ij = g_i · g_j."""
    return g @ g.T


def green_strain_convected(g_cov: np.ndarray, G_cov: np.ndarray) -> np.ndarray:
    """Green strain in convected basis: E_ij = 0.5*(g_ij - G_ij)."""
    return 0.5 * (g_cov - G_cov)


def pullback_kirchhoff_to_pk2(F: np.ndarray, tau: np.ndarray) -> np.ndarray:
    """S = F^{-1} tau F^{-T}."""
    Finv = np.linalg.inv(F)
    return Finv @ tau @ Finv.T


def pk2_to_kirchhoff(F: np.ndarray, S: np.ndarray) -> np.ndarray:
    """tau = F S F^T."""
    return F @ S @ F.T


def element_kinematics(xa_ref: np.ndarray, xa_cur: np.ndarray, dN_dxi: np.ndarray) -> dict:
    """Compute reference/current metrics and convected Green strain at a quadrature point."""
    G = covariant_basis(xa_ref, dN_dxi)
    g = covariant_basis(xa_cur, dN_dxi)
    G_cov = metric_from_basis(G)
    g_cov = metric_from_basis(g)
    E_cov = green_strain_convected(g_cov, G_cov)

    return {
        "G_basis": G,
        "g_basis": g,
        "G_cov": G_cov,
        "g_cov": g_cov,
        "E_cov": E_cov,
    }
