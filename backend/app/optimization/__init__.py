"""FPL squad optimisation package.

Public API:
    OptimizationEngine  - facade over ILP and GA solvers
    OptimizationResult  - result dataclass
    OptimizationRequest - request dataclass
    ILPSolver           - exact solver (PuLP/CBC)
    GASolver            - genetic algorithm solver
    VALID_FORMATIONS    - list of legal formation strings
"""

from app.optimization.constraints import VALID_FORMATIONS
from app.optimization.engine import OptimizationEngine
from app.optimization.genetic_algorithm import GASolver
from app.optimization.ilp_solver import ILPSolver
from app.optimization.models import OptimizationRequest, OptimizationResult

__all__ = [
    "OptimizationEngine",
    "OptimizationResult",
    "OptimizationRequest",
    "ILPSolver",
    "GASolver",
    "VALID_FORMATIONS",
]
