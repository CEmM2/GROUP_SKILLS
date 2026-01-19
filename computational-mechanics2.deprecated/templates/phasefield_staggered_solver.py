"""phasefield_staggered_solver.py

Template for staggered (alternate minimization) phase-field fracture.

Unknowns
- u: displacement DOFs
- phi: phase-field DOFs

You provide:
- solve_mechanics(u0, phi) -> u
- solve_phasefield(phi0, u, H) -> phi
- update_history(H, u) -> H

The template enforces irreversibility: phi_{n+1} >= phi_n.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Tuple

import numpy as np


SolveMech = Callable[[np.ndarray, np.ndarray], np.ndarray]
SolvePhi = Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray]
UpdateH = Callable[[np.ndarray, np.ndarray], np.ndarray]


@dataclass
class StaggeredOptions:
    max_outer: int = 50
    tol_u: float = 1e-8
    tol_phi: float = 1e-8


def staggered_solve(
    u0: np.ndarray,
    phi0: np.ndarray,
    H0: np.ndarray,
    solve_mechanics: SolveMech,
    solve_phasefield: SolvePhi,
    update_history: UpdateH,
    opts: StaggeredOptions = StaggeredOptions(),
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    u = u0.copy()
    phi = phi0.copy()
    H = H0.copy()

    info = {"outer_iters": 0, "converged": False}

    for k in range(opts.max_outer):
        u_old = u.copy()
        phi_old = phi.copy()

        # 1) mechanics
        u = solve_mechanics(u, phi)

        # 2) history (irreversibility)
        H = update_history(H, u)

        # 3) phase-field
        phi_new = solve_phasefield(phi, u, H)
        phi = np.maximum(phi_new, phi_old)  # enforce phi_{n+1} >= phi_n

        du = np.linalg.norm(u - u_old)
        dphi = np.linalg.norm(phi - phi_old)

        info["outer_iters"] = k + 1
        if du <= opts.tol_u * max(1.0, np.linalg.norm(u)) and dphi <= opts.tol_phi * max(1.0, np.linalg.norm(phi)):
            info["converged"] = True
            break

    return u, phi, H, info
