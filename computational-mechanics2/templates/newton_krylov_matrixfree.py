"""newton_krylov_matrixfree.py

A minimal, dependency-light Newton-Krylov scaffold.

This is meant as a *pattern* for FEM or FFT solvers:
- You provide residual(x) -> r
- You provide jvp(x,v) -> J(x)@v   (preferred)
  OR a finite-difference JVP fallback is used
- Inner linear solves via GMRES (simple implementation)

This is not optimized. In production, use scipy.sparse.linalg.gmres / PETSc / custom GPU Krylov.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np


ResidualFn = Callable[[np.ndarray], np.ndarray]
JvpFn = Callable[[np.ndarray, np.ndarray], np.ndarray]


@dataclass
class NewtonKrylovOptions:
    max_newton: int = 25
    tol_res: float = 1e-8
    tol_dx: float = 1e-10
    max_gmres: int = 200
    gmres_restart: int = 50
    fd_eps: float = 1e-7
    line_search: bool = True
    ls_c1: float = 1e-4
    ls_max_steps: int = 10


def fd_jvp(residual: ResidualFn, x: np.ndarray, v: np.ndarray, eps: float) -> np.ndarray:
    return (residual(x + eps * v) - residual(x)) / eps


def gmres(matvec: Callable[[np.ndarray], np.ndarray], b: np.ndarray, restart: int, maxit: int, tol: float) -> np.ndarray:
    """Restarted GMRES (very small, for templates/tests).

    Solves A x = b with matvec implementing A@x.
    """
    n = b.size
    x = np.zeros_like(b)
    r0 = b - matvec(x)
    beta0 = np.linalg.norm(r0)
    if beta0 == 0.0:
        return x

    it = 0
    while it < maxit:
        r = b - matvec(x)
        beta = np.linalg.norm(r)
        if beta <= tol * beta0:
            break

        # Arnoldi basis
        V = np.zeros((n, restart + 1), dtype=b.dtype)
        H = np.zeros((restart + 1, restart), dtype=b.dtype)
        V[:, 0] = r / beta
        g = np.zeros((restart + 1,), dtype=b.dtype)
        g[0] = beta

        for j in range(restart):
            w = matvec(V[:, j])
            for i in range(j + 1):
                H[i, j] = np.dot(V[:, i], w)
                w = w - H[i, j] * V[:, i]
            H[j + 1, j] = np.linalg.norm(w)
            if H[j + 1, j] != 0.0:
                V[:, j + 1] = w / H[j + 1, j]

            # Least squares solve min||g - H y||
            y, *_ = np.linalg.lstsq(H[: j + 2, : j + 1], g[: j + 2], rcond=None)
            x_new = x + V[:, : j + 1] @ y
            r_new = b - matvec(x_new)
            if np.linalg.norm(r_new) <= tol * beta0:
                x = x_new
                return x

        # restart update
        y, *_ = np.linalg.lstsq(H[: restart + 1, : restart], g[: restart + 1], rcond=None)
        x = x + V[:, :restart] @ y
        it += restart

    return x


def newton_krylov(
    x0: np.ndarray,
    residual: ResidualFn,
    jvp: Optional[JvpFn] = None,
    opts: NewtonKrylovOptions = NewtonKrylovOptions(),
) -> tuple[np.ndarray, dict]:
    """Solve R(x)=0.

    Returns (x, info) where info contains iteration counts and final norms.
    """
    x = x0.copy()
    r = residual(x)
    r0 = np.linalg.norm(r)

    info = {
        "newton_iters": 0,
        "gmres_iters_est": 0,
        "r_norm": float(np.linalg.norm(r)),
        "r0_norm": float(r0),
        "converged": False,
    }

    for k in range(opts.max_newton):
        r = residual(x)
        r_norm = np.linalg.norm(r)
        info["r_norm"] = float(r_norm)
        info["newton_iters"] = k

        if r_norm <= opts.tol_res * (r0 if r0 > 0 else 1.0):
            info["converged"] = True
            break

        def matvec(v: np.ndarray) -> np.ndarray:
            if jvp is not None:
                return jvp(x, v)
            return fd_jvp(residual, x, v, opts.fd_eps)

        dx = gmres(matvec, b=-r, restart=opts.gmres_restart, maxit=opts.max_gmres, tol=1e-6)
        dx_norm = np.linalg.norm(dx)
        if dx_norm <= opts.tol_dx * (np.linalg.norm(x) if np.linalg.norm(x) > 0 else 1.0):
            info["converged"] = True
            break

        # optional backtracking line search (Armijo on residual norm)
        alpha = 1.0
        if opts.line_search:
            for _ in range(opts.ls_max_steps):
                x_try = x + alpha * dx
                r_try = residual(x_try)
                if np.linalg.norm(r_try) <= (1 - opts.ls_c1 * alpha) * r_norm:
                    break
                alpha *= 0.5

        x = x + alpha * dx

    return x, info
