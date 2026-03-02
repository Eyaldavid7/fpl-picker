"""Data models for optimization inputs and outputs."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OptimizationResult:
    """Result of a squad optimization run."""

    squad: list[dict] = field(default_factory=list)  # 15 player dicts
    starting_xi: list[dict] = field(default_factory=list)  # 11 player dicts
    bench: list[dict] = field(default_factory=list)  # 4 player dicts
    captain: dict | None = None
    vice_captain: dict | None = None
    total_cost: float = 0.0  # in real-money units (e.g. 100.0 = 100m)
    predicted_points: float = 0.0
    formation: str = ""
    solve_time: float = 0.0  # seconds
    method: str = ""

    def to_dict(self) -> dict:
        """Serialise to a plain dictionary."""
        return {
            "squad": self.squad,
            "starting_xi": self.starting_xi,
            "bench": self.bench,
            "captain": self.captain,
            "vice_captain": self.vice_captain,
            "total_cost": self.total_cost,
            "predicted_points": self.predicted_points,
            "formation": self.formation,
            "solve_time": self.solve_time,
            "method": self.method,
        }


@dataclass
class OptimizationRequest:
    """Parameters for an optimization run."""

    budget: float = 100.0  # real-money units
    formation: str | None = None
    locked_players: list[int] = field(default_factory=list)
    excluded_players: list[int] = field(default_factory=list)
    method: str = "ilp"  # "ilp" | "ga"
