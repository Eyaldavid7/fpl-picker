"""Optimization engine orchestrator for FPL squad selection.

Provides a unified facade over the ILP (exact) and GA (heuristic) solvers,
plus convenience methods for comparing the two approaches.
"""

from __future__ import annotations

import logging
import time

from app.optimization.constraints import VALID_FORMATIONS
from app.optimization.genetic_algorithm import GASolver
from app.optimization.ilp_solver import ILPSolver
from app.optimization.models import OptimizationResult

logger = logging.getLogger(__name__)


class OptimizationEngine:
    """Orchestrates squad optimization using ILP or GA solvers."""

    def __init__(self) -> None:
        self._ilp_solver = ILPSolver()
        self._ga_solver = GASolver()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def optimize(
        self,
        players: list[dict],
        predictions: dict[int, float],
        method: str = "ilp",
        **kwargs,
    ) -> OptimizationResult | list[OptimizationResult]:
        """Run optimisation.

        Parameters
        ----------
        players:
            Player dicts (must include ``id``, ``position``, ``now_cost``,
            ``team``/``team_id``).
        predictions:
            Mapping of player id -> predicted points.
        method:
            ``"ilp"`` for exact ILP or ``"ga"`` for Genetic Algorithm.
        **kwargs:
            Forwarded to the chosen solver's ``solve()`` method.

        Returns
        -------
        A single ``OptimizationResult`` for ILP, or a list for GA.
        """
        method = method.lower()
        if method == "ilp":
            return self._ilp_solver.solve(
                players=players,
                predicted_points=predictions,
                budget=kwargs.get("budget", 100.0),
                formation=kwargs.get("formation"),
                locked=kwargs.get("locked_players") or kwargs.get("locked"),
                excluded=kwargs.get("excluded_players") or kwargs.get("excluded"),
            )
        elif method == "ga":
            return self._ga_solver.solve(
                players=players,
                predicted_points=predictions,
                budget=kwargs.get("budget", 100.0),
                n_squads=kwargs.get("n_squads", 5),
                population_size=kwargs.get("population_size", 200),
                generations=kwargs.get("generations", 100),
            )
        else:
            raise ValueError(f"Unknown optimization method '{method}'. Use 'ilp' or 'ga'.")

    def compare_methods(
        self,
        players: list[dict],
        predictions: dict[int, float],
        budget: float = 100.0,
        formation: str | None = None,
    ) -> dict:
        """Run both ILP and GA, return a comparison dict.

        Returns
        -------
        Dictionary with keys ``ilp``, ``ga``, and ``summary``.
        """
        ilp_result = self._ilp_solver.solve(
            players=players,
            predicted_points=predictions,
            budget=budget,
            formation=formation,
        )

        ga_results = self._ga_solver.solve(
            players=players,
            predicted_points=predictions,
            budget=budget,
            n_squads=1,
            population_size=200,
            generations=100,
        )
        ga_best = ga_results[0] if ga_results else OptimizationResult(method="ga")

        return {
            "ilp": ilp_result.to_dict(),
            "ga": ga_best.to_dict(),
            "summary": {
                "ilp_points": ilp_result.predicted_points,
                "ga_points": ga_best.predicted_points,
                "point_difference": ilp_result.predicted_points - ga_best.predicted_points,
                "ilp_solve_time": ilp_result.solve_time,
                "ga_solve_time": ga_best.solve_time,
                "ilp_cost": ilp_result.total_cost,
                "ga_cost": ga_best.total_cost,
                "ilp_formation": ilp_result.formation,
                "ga_formation": ga_best.formation,
            },
        }

    @staticmethod
    def get_available_formations() -> list[str]:
        """Return all valid FPL formation strings."""
        return list(VALID_FORMATIONS)
