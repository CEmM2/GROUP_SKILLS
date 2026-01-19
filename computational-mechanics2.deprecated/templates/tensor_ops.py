"""tensor_ops.py

Small, boring tensor utilities used across FEM/FFT constitutive kernels.

Conventions
- 3D symmetric tensors use Voigt ordering: [11,22,33,23,13,12].
- All arrays are NumPy (float64 by default). Porting to Taichi/JAX/PyTorch should be straightforward.
"""

from __future__ import annotations

import numpy as np


VOIGT_DIM = 6


def sym_to_voigt(A: np.ndarray) -> np.ndarray:
    """Map 3x3 symmetric tensor -> 6-vector [11,22,33,23,13,12]."""
    A = np.asarray(A)
    assert A.shape == (3, 3)
    return np.array([A[0, 0], A[1, 1], A[2, 2], A[1, 2], A[0, 2], A[0, 1]], dtype=A.dtype)


def voigt_to_sym(v: np.ndarray) -> np.ndarray:
    """Map 6-vector [11,22,33,23,13,12] -> 3x3 symmetric tensor."""
    v = np.asarray(v)
    assert v.shape == (6,)
    A = np.zeros((3, 3), dtype=v.dtype)
    A[0, 0], A[1, 1], A[2, 2] = v[0], v[1], v[2]
    A[1, 2] = A[2, 1] = v[3]
    A[0, 2] = A[2, 0] = v[4]
    A[0, 1] = A[1, 0] = v[5]
    return A


def trace(A: np.ndarray) -> float:
    A = np.asarray(A)
    return float(A[0, 0] + A[1, 1] + A[2, 2])


def deviator(A: np.ndarray) -> np.ndarray:
    """Deviatoric part: dev(A) = A - tr(A)/3 * I."""
    A = np.asarray(A)
    trA = trace(A)
    return A - (trA / 3.0) * np.eye(3, dtype=A.dtype)


def mises_q(sigma: np.ndarray) -> float:
    """Von Mises equivalent stress q = sqrt(3/2 * s:s)."""
    s = deviator(sigma)
    return float(np.sqrt(1.5 * np.tensordot(s, s)))


def detF(F: np.ndarray) -> float:
    F = np.asarray(F)
    assert F.shape == (3, 3)
    return float(np.linalg.det(F))


def polar_decomposition(F: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Right polar decomposition: F = R U.

    Returns
    - R: proper rotation (det ~ +1)
    - U: symmetric stretch
    """
    F = np.asarray(F)
    C = F.T @ F
    eigvals, eigvecs = np.linalg.eigh(C)
    # Guard small/negative eigenvalues from numerical noise
    eigvals = np.clip(eigvals, 0.0, None)
    U = eigvecs @ np.diag(np.sqrt(eigvals)) @ eigvecs.T
    R = F @ np.linalg.inv(U)
    return R, U


def sym_eigh(A: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Eigen-decomposition for symmetric 3x3.

    Returns (vals, vecs) where A = vecs @ diag(vals) @ vecs.T.
    """
    A = np.asarray(A)
    assert A.shape == (3, 3)
    return np.linalg.eigh((A + A.T) * 0.5)
