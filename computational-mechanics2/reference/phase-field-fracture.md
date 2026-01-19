# Phase-field fracture (brittle)

## Core ingredients
- Phase-field: phi in [0,1] (0 intact, 1 broken)
- Degradation: g(phi) = (1-phi)^2 + k, k small
- Regularization length: l (controls crack width ~ 2l)
- Crack surface term: phi^2/(2l) + (l/2)*|grad_X phi|^2

## Driving energy and history
To prevent cracking in compression, split the elastic energy:
- psi = psi_plus + psi_minus
- Only psi_plus is degraded by g(phi)

Irreversibility via history field:
- H(t) = max_{s<=t} psi_plus(s)
- Use H in the phase-field equation so cracks do not heal

## Solution strategy (default)
Staggered alternate minimization:
1) Fix phi, solve mechanics for u (nonlinear)
2) Fix u, solve phase-field for phi (linear/quadratic)
3) Enforce phi_{n+1} >= phi_n pointwise

## Implementation checks
- k not too large (keeps residual stiffness small)
- No crack growth under hydrostatic compression (test)
- Energy balance: elastic release ~= fracture + plastic dissipation (if coupled)
