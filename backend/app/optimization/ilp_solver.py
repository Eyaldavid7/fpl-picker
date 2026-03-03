"""Integer Linear Programming solver for FPL squad optimisation using PuLP."""

from __future__ import annotations

import logging
import time
from collections import defaultdict

import pulp

from app.optimization.constraints import (
    FORMATION_RULES,
    MAX_PER_CLUB,
    SQUAD_COMPOSITION,
    SQUAD_SIZE,
    VALID_FORMATIONS,
)
from app.optimization.models import OptimizationResult

logger = logging.getLogger(__name__)

# Normalise GKP -> GK
_POS_ALIAS: dict[str, str] = {"GKP": "GK"}


def _norm_pos(pos: str) -> str:
    return _POS_ALIAS.get(pos, pos)


class ILPSolver:
    """Exact solver for FPL squad selection via Integer Linear Programming.

    Decision variables (all binary):
        x[j] -- player j is in the 15-player squad
        s[j] -- player j is in the starting XI (11 players)
        c[j] -- player j is captain
        vc[j] -- player j is vice-captain

    Objective:
        Maximise  sum(pred[j] * s[j]) + sum(pred[j] * c[j])
        (Captain's points are doubled, i.e. counted once via s and once via c.)
    """

    def solve(
        self,
        players: list[dict],
        predicted_points: dict[int, float],
        budget: float = 100.0,
        formation: str | None = None,
        locked: list[int] | None = None,
        excluded: list[int] | None = None,
    ) -> OptimizationResult:
        """Run the ILP solver.

        Parameters
        ----------
        players:
            List of player dicts.  Each must have ``id`` (int),
            ``position`` (str, GK/GKP/DEF/MID/FWD), ``now_cost`` (int, 0.1m),
            ``team`` or ``team_id`` (int).
        predicted_points:
            Mapping of player id -> predicted points for the horizon.
        budget:
            Budget cap in real-money units (default 100.0).
        formation:
            Optional formation string (e.g. ``"4-4-2"``).
            ``None`` means flexible positional constraints.
        locked:
            Player IDs that *must* be in the squad.
        excluded:
            Player IDs that *must not* be in the squad.

        Returns
        -------
        OptimizationResult
        """
        locked = locked or []
        excluded = excluded or []
        start = time.time()

        # Validate formation if provided
        if formation is not None and formation not in VALID_FORMATIONS:
            raise ValueError(
                f"Invalid formation '{formation}'. "
                f"Choose from: {', '.join(VALID_FORMATIONS)}"
            )

        # ------------------------------------------------------------------
        # Index helpers
        # ------------------------------------------------------------------
        n = len(players)
        ids = [p["id"] for p in players]
        set(ids)
        idx_of: dict[int, int] = {pid: i for i, pid in enumerate(ids)}

        costs = [p["now_cost"] / 10.0 for p in players]  # real-money
        preds = [predicted_points.get(p["id"], 0.0) for p in players]
        positions = [_norm_pos(p.get("position", "")) for p in players]
        teams = [p.get("team") or p.get("team_id") or 0 for p in players]

        # Group indices by position and by team
        pos_indices: dict[str, list[int]] = defaultdict(list)
        team_indices: dict[int, list[int]] = defaultdict(list)
        for i in range(n):
            pos_indices[positions[i]].append(i)
            team_indices[teams[i]].append(i)

        # ------------------------------------------------------------------
        # Create the LP problem
        # ------------------------------------------------------------------
        prob = pulp.LpProblem("FPL_Squad_Optimization", pulp.LpMaximize)

        # Binary decision variables
        x = pulp.LpVariable.dicts("x", range(n), cat=pulp.LpBinary)  # squad
        s = pulp.LpVariable.dicts("s", range(n), cat=pulp.LpBinary)  # XI
        c = pulp.LpVariable.dicts("c", range(n), cat=pulp.LpBinary)  # captain
        vc = pulp.LpVariable.dicts("vc", range(n), cat=pulp.LpBinary)  # vice-cap

        # ------------------------------------------------------------------
        # Objective
        # ------------------------------------------------------------------
        # Captain bonus: captain effectively gets double points.
        # Points = sum(pred * s) + sum(pred * c)
        prob += (
            pulp.lpSum(preds[j] * s[j] for j in range(n))
            + pulp.lpSum(preds[j] * c[j] for j in range(n))
        ), "Total_Predicted_Points"

        # ------------------------------------------------------------------
        # Constraints
        # ------------------------------------------------------------------

        # 1. Squad size = 15
        prob += pulp.lpSum(x[j] for j in range(n)) == SQUAD_SIZE, "Squad_Size"

        # 2. Starting XI = 11
        prob += pulp.lpSum(s[j] for j in range(n)) == 11, "Starting_XI_Size"

        # 3. Starters must be in squad:  s[j] <= x[j]
        for j in range(n):
            prob += s[j] <= x[j], f"Starter_In_Squad_{j}"

        # 4. Captain must be a starter:  c[j] <= s[j]
        for j in range(n):
            prob += c[j] <= s[j], f"Captain_Is_Starter_{j}"

        # 5. Vice-captain must be a starter:  vc[j] <= s[j]
        for j in range(n):
            prob += vc[j] <= s[j], f"ViceCaptain_Is_Starter_{j}"

        # 6. Exactly one captain
        prob += pulp.lpSum(c[j] for j in range(n)) == 1, "One_Captain"

        # 7. Exactly one vice-captain
        prob += pulp.lpSum(vc[j] for j in range(n)) == 1, "One_Vice_Captain"

        # 8. Captain != vice-captain
        for j in range(n):
            prob += c[j] + vc[j] <= 1, f"Captain_Not_ViceCaptain_{j}"

        # 9. Budget
        prob += (
            pulp.lpSum(costs[j] * x[j] for j in range(n)) <= budget
        ), "Budget"

        # 10. Max 3 per club
        for team_id, indices in team_indices.items():
            prob += (
                pulp.lpSum(x[j] for j in indices) <= MAX_PER_CLUB
            ), f"Club_Limit_{team_id}"

        # 11. Full-squad positional composition (2 GK, 5 DEF, 5 MID, 3 FWD)
        for pos, required in SQUAD_COMPOSITION.items():
            indices = pos_indices.get(pos, [])
            prob += (
                pulp.lpSum(x[j] for j in indices) == required
            ), f"Squad_Position_{pos}"

        # 12. Formation constraints for starting XI
        if formation is not None:
            rules = FORMATION_RULES[formation]
            for pos, required in rules.items():
                indices = pos_indices.get(pos, [])
                prob += (
                    pulp.lpSum(s[j] for j in indices) == required
                ), f"XI_Formation_{pos}"
        else:
            # Flexible: GK=1, 3<=DEF<=5, 3<=MID<=5, 1<=FWD<=3, DEF+MID+FWD=10
            gk_idx = pos_indices.get("GK", [])
            def_idx = pos_indices.get("DEF", [])
            mid_idx = pos_indices.get("MID", [])
            fwd_idx = pos_indices.get("FWD", [])

            prob += pulp.lpSum(s[j] for j in gk_idx) == 1, "XI_Flex_GK"
            prob += pulp.lpSum(s[j] for j in def_idx) >= 3, "XI_Flex_DEF_Min"
            prob += pulp.lpSum(s[j] for j in def_idx) <= 5, "XI_Flex_DEF_Max"
            prob += pulp.lpSum(s[j] for j in mid_idx) >= 3, "XI_Flex_MID_Min"
            prob += pulp.lpSum(s[j] for j in mid_idx) <= 5, "XI_Flex_MID_Max"
            prob += pulp.lpSum(s[j] for j in fwd_idx) >= 1, "XI_Flex_FWD_Min"
            prob += pulp.lpSum(s[j] for j in fwd_idx) <= 3, "XI_Flex_FWD_Max"

        # 13. Locked players
        for pid in locked:
            if pid in idx_of:
                j = idx_of[pid]
                prob += x[j] == 1, f"Locked_{pid}"

        # 14. Excluded players
        for pid in excluded:
            if pid in idx_of:
                j = idx_of[pid]
                prob += x[j] == 0, f"Excluded_{pid}"

        # ------------------------------------------------------------------
        # Solve
        # ------------------------------------------------------------------
        solver = pulp.PULP_CBC_CMD(msg=0)
        prob.solve(solver)

        status = pulp.LpStatus[prob.status]
        if status != "Optimal":
            logger.warning("ILP solver status: %s", status)
            return OptimizationResult(
                method="ilp",
                solve_time=time.time() - start,
            )

        # ------------------------------------------------------------------
        # Extract solution
        # ------------------------------------------------------------------
        squad_indices = [j for j in range(n) if pulp.value(x[j]) > 0.5]
        xi_indices = [j for j in range(n) if pulp.value(s[j]) > 0.5]
        bench_indices = [j for j in squad_indices if j not in set(xi_indices)]
        captain_idx = next(
            (j for j in range(n) if pulp.value(c[j]) > 0.5),
            xi_indices[0] if xi_indices else 0,
        )
        vc_idx = next(
            (j for j in range(n) if pulp.value(vc[j]) > 0.5),
            xi_indices[1] if len(xi_indices) > 1 else xi_indices[0] if xi_indices else 0,
        )

        # Sort bench by predicted points descending (best sub first)
        bench_indices.sort(key=lambda j: preds[j], reverse=True)

        squad_players = [players[j] for j in squad_indices]
        xi_players = [players[j] for j in xi_indices]
        bench_players = [players[j] for j in bench_indices]
        captain_player = players[captain_idx]
        vc_player = players[vc_idx]

        total_cost = sum(costs[j] for j in squad_indices)
        total_pred = sum(preds[j] for j in xi_indices) + preds[captain_idx]

        # Determine actual formation used
        xi_pos_counts: dict[str, int] = defaultdict(int)
        for j in xi_indices:
            xi_pos_counts[positions[j]] += 1
        actual_formation = (
            f"{xi_pos_counts.get('DEF', 0)}-"
            f"{xi_pos_counts.get('MID', 0)}-"
            f"{xi_pos_counts.get('FWD', 0)}"
        )

        solve_time = time.time() - start
        logger.info(
            "ILP solved in %.3fs | status=%s | points=%.1f | cost=%.1f",
            solve_time,
            status,
            total_pred,
            total_cost,
        )

        return OptimizationResult(
            squad=squad_players,
            starting_xi=xi_players,
            bench=bench_players,
            captain=captain_player,
            vice_captain=vc_player,
            total_cost=total_cost,
            predicted_points=total_pred,
            formation=actual_formation,
            solve_time=solve_time,
            method="ilp",
        )
