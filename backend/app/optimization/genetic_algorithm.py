"""Genetic Algorithm solver for FPL squad optimisation.

Pure-Python implementation (no external GA libraries) that evolves a
population of 15-player squads towards the maximum predicted points while
respecting all FPL constraints (budget, club limits, positional composition).
"""

from __future__ import annotations

import logging
import random
import time
from collections import Counter, defaultdict
from copy import deepcopy

from app.optimization.constraints import (
    FORMATION_RULES,
    MAX_PER_CLUB,
    SQUAD_COMPOSITION,
    SQUAD_SIZE,
    VALID_FORMATIONS,
)
from app.optimization.models import OptimizationResult

logger = logging.getLogger(__name__)

_POS_ALIAS: dict[str, str] = {"GKP": "GK"}


def _norm_pos(pos: str) -> str:
    return _POS_ALIAS.get(pos, pos)


# ---------------------------------------------------------------------------
# Helper: pick the best starting XI & captain from a 15-player squad
# ---------------------------------------------------------------------------

def _best_xi_and_captain(
    squad_indices: list[int],
    positions: list[str],
    preds: list[float],
) -> tuple[list[int], int, int, str]:
    """Given 15 player indices, choose the best XI, captain, vice-captain.

    Tries every valid formation and picks the one that maximises total
    predicted points (including captain bonus).

    Returns (xi_indices, captain_idx, vc_idx, formation_str).
    """
    best_pts = -1.0
    best_xi: list[int] = []
    best_cap = -1
    best_vc = -1
    best_form = ""

    # Group by position
    pos_groups: dict[str, list[int]] = defaultdict(list)
    for j in squad_indices:
        pos_groups[positions[j]].append(j)

    # Sort each group by predicted points descending
    for pos in pos_groups:
        pos_groups[pos].sort(key=lambda j: preds[j], reverse=True)

    for formation, rules in FORMATION_RULES.items():
        # Check we have enough players for this formation
        feasible = True
        for pos, need in rules.items():
            if len(pos_groups.get(pos, [])) < need:
                feasible = False
                break
        if not feasible:
            continue

        xi: list[int] = []
        for pos, need in rules.items():
            xi.extend(pos_groups[pos][:need])

        # Points with captain bonus (best player gets double)
        xi_preds = [(j, preds[j]) for j in xi]
        xi_preds.sort(key=lambda t: t[1], reverse=True)
        cap_idx = xi_preds[0][0]
        vc_idx = xi_preds[1][0] if len(xi_preds) > 1 else cap_idx

        total = sum(p for _, p in xi_preds) + xi_preds[0][1]  # captain bonus

        if total > best_pts:
            best_pts = total
            best_xi = xi
            best_cap = cap_idx
            best_vc = vc_idx
            best_form = formation

    return best_xi, best_cap, best_vc, best_form


# ---------------------------------------------------------------------------
# GA Solver
# ---------------------------------------------------------------------------

class GASolver:
    """Genetic Algorithm solver producing diverse high-quality squads.

    Chromosome representation: a list of 15 indices into the ``players``
    array, obeying position composition (2 GK, 5 DEF, 5 MID, 3 FWD).

    Fitness: total predicted points of the best starting XI (including
    captain bonus).
    """

    def solve(
        self,
        players: list[dict],
        predicted_points: dict[int, float],
        budget: float = 100.0,
        n_squads: int = 5,
        population_size: int = 200,
        generations: int = 100,
    ) -> list[OptimizationResult]:
        """Evolve squads and return the top *n_squads* diverse results.

        Parameters
        ----------
        players:
            Player dicts with ``id``, ``position``, ``now_cost``, ``team``/``team_id``.
        predicted_points:
            player id -> predicted points.
        budget:
            Budget cap in real-money units.
        n_squads:
            Number of distinct squads to return.
        population_size:
            Size of the GA population.
        generations:
            Number of GA generations.
        """
        start = time.time()

        n = len(players)
        ids = [p["id"] for p in players]
        costs = [p["now_cost"] / 10.0 for p in players]
        preds = [predicted_points.get(pid, 0.0) for pid in ids]
        positions = [_norm_pos(p.get("position", "")) for p in players]
        teams = [p.get("team") or p.get("team_id") or 0 for p in players]

        # Group player indices by position
        pos_pool: dict[str, list[int]] = defaultdict(list)
        for i in range(n):
            pos_pool[positions[i]].append(i)

        # Sort each pool by predicted points desc for seeding
        for pos in pos_pool:
            pos_pool[pos].sort(key=lambda j: preds[j], reverse=True)

        # ------------------------------------------------------------------
        # Initialisation
        # ------------------------------------------------------------------
        population: list[list[int]] = []
        for _ in range(population_size):
            chrom = self._random_chromosome(pos_pool, costs, teams, budget)
            if chrom is not None:
                population.append(chrom)

        # If we couldn't generate enough, pad with duplicates of the best
        if len(population) == 0:
            logger.error("GA: could not generate any feasible chromosome")
            return [OptimizationResult(method="ga", solve_time=time.time() - start)]

        while len(population) < population_size:
            population.append(deepcopy(random.choice(population)))

        # ------------------------------------------------------------------
        # Evolution loop
        # ------------------------------------------------------------------
        mutation_rate = 0.1
        for gen in range(generations):
            # Evaluate fitness
            fitness = [
                self._fitness(chrom, positions, preds)
                for chrom in population
            ]

            # Build next generation
            new_pop: list[list[int]] = []

            # Elitism: keep top 10 %
            elite_n = max(2, population_size // 10)
            ranked = sorted(
                range(len(population)),
                key=lambda i: fitness[i],
                reverse=True,
            )
            for i in ranked[:elite_n]:
                new_pop.append(deepcopy(population[i]))

            # Fill the rest via crossover + mutation
            while len(new_pop) < population_size:
                p1 = self._tournament_select(population, fitness, k=3)
                p2 = self._tournament_select(population, fitness, k=3)
                child = self._crossover(p1, p2, positions, pos_pool)
                if random.random() < mutation_rate:
                    child = self._mutate(child, positions, pos_pool)
                child = self._repair(child, costs, teams, budget, pos_pool, positions)
                if child is not None:
                    new_pop.append(child)

            population = new_pop[:population_size]

        # ------------------------------------------------------------------
        # Extract diverse top results
        # ------------------------------------------------------------------
        fitness = [self._fitness(chrom, positions, preds) for chrom in population]
        ranked = sorted(range(len(population)), key=lambda i: fitness[i], reverse=True)

        results: list[OptimizationResult] = []
        seen_squads: list[set[int]] = []

        for idx in ranked:
            chrom = population[idx]
            chrom_set = set(chrom)

            # Diversity check: require at least 3 different players from any
            # previously selected squad.
            diverse = all(
                len(chrom_set.symmetric_difference(prev)) >= 6
                for prev in seen_squads
            )
            if not diverse and len(seen_squads) > 0:
                continue

            seen_squads.append(chrom_set)

            xi, cap, vc, form = _best_xi_and_captain(chrom, positions, preds)
            bench = [j for j in chrom if j not in set(xi)]
            bench.sort(key=lambda j: preds[j], reverse=True)

            total_cost = sum(costs[j] for j in chrom)
            total_pred = sum(preds[j] for j in xi) + preds[cap]

            results.append(
                OptimizationResult(
                    squad=[players[j] for j in chrom],
                    starting_xi=[players[j] for j in xi],
                    bench=[players[j] for j in bench],
                    captain=players[cap],
                    vice_captain=players[vc],
                    total_cost=total_cost,
                    predicted_points=total_pred,
                    formation=form,
                    solve_time=time.time() - start,
                    method="ga",
                )
            )
            if len(results) >= n_squads:
                break

        # If we didn't get enough diverse squads, relax diversity
        if len(results) < n_squads:
            for idx in ranked:
                if len(results) >= n_squads:
                    break
                chrom = population[idx]
                chrom_set = set(chrom)
                if chrom_set in seen_squads:
                    continue
                seen_squads.append(chrom_set)

                xi, cap, vc, form = _best_xi_and_captain(chrom, positions, preds)
                bench = [j for j in chrom if j not in set(xi)]
                bench.sort(key=lambda j: preds[j], reverse=True)
                total_cost = sum(costs[j] for j in chrom)
                total_pred = sum(preds[j] for j in xi) + preds[cap]

                results.append(
                    OptimizationResult(
                        squad=[players[j] for j in chrom],
                        starting_xi=[players[j] for j in xi],
                        bench=[players[j] for j in bench],
                        captain=players[cap],
                        vice_captain=players[vc],
                        total_cost=total_cost,
                        predicted_points=total_pred,
                        formation=form,
                        solve_time=time.time() - start,
                        method="ga",
                    )
                )

        solve_time = time.time() - start
        logger.info(
            "GA solved in %.3fs | %d generations | %d squads returned",
            solve_time,
            generations,
            len(results),
        )
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _random_chromosome(
        pos_pool: dict[str, list[int]],
        costs: list[float],
        teams: list[int],
        budget: float,
        max_attempts: int = 200,
    ) -> list[int] | None:
        """Generate a random feasible chromosome (15 player indices)."""
        for _ in range(max_attempts):
            chrom: list[int] = []
            for pos, need in SQUAD_COMPOSITION.items():
                pool = pos_pool.get(pos, [])
                if len(pool) < need:
                    break
                chrom.extend(random.sample(pool, need))
            else:
                # Check budget and club limits
                total = sum(costs[j] for j in chrom)
                if total > budget + 1e-6:
                    continue
                club_cnt: Counter[int] = Counter(teams[j] for j in chrom)
                if any(v > MAX_PER_CLUB for v in club_cnt.values()):
                    continue
                return chrom
        return None

    @staticmethod
    def _fitness(
        chrom: list[int],
        positions: list[str],
        preds: list[float],
    ) -> float:
        """Evaluate fitness of a chromosome (best XI + captain bonus)."""
        _, _, _, _ = _best_xi_and_captain(chrom, positions, preds)
        xi, cap, _, _ = _best_xi_and_captain(chrom, positions, preds)
        return sum(preds[j] for j in xi) + preds[cap]

    @staticmethod
    def _tournament_select(
        population: list[list[int]],
        fitness: list[float],
        k: int = 3,
    ) -> list[int]:
        """Tournament selection: pick k random individuals, return best."""
        candidates = random.sample(range(len(population)), min(k, len(population)))
        best = max(candidates, key=lambda i: fitness[i])
        return deepcopy(population[best])

    @staticmethod
    def _crossover(
        p1: list[int],
        p2: list[int],
        positions: list[str],
        pos_pool: dict[str, list[int]],
    ) -> list[int]:
        """Position-aware crossover: for each position group, randomly pick
        the required number from the union of both parents' players."""
        child: list[int] = []
        for pos, need in SQUAD_COMPOSITION.items():
            parent_players = list(
                {j for j in p1 if positions[j] == pos}
                | {j for j in p2 if positions[j] == pos}
            )
            if len(parent_players) >= need:
                child.extend(random.sample(parent_players, need))
            else:
                # Not enough from parents, fill from pool
                child.extend(parent_players)
                remaining = [
                    j for j in pos_pool.get(pos, []) if j not in set(child)
                ]
                shortfall = need - len(parent_players)
                if len(remaining) >= shortfall:
                    child.extend(random.sample(remaining, shortfall))
                else:
                    child.extend(remaining)
        return child

    @staticmethod
    def _mutate(
        chrom: list[int],
        positions: list[str],
        pos_pool: dict[str, list[int]],
    ) -> list[int]:
        """Mutate by swapping one random player with another of the same position."""
        chrom = list(chrom)
        if not chrom:
            return chrom
        idx = random.randrange(len(chrom))
        old_j = chrom[idx]
        pos = positions[old_j]
        candidates = [j for j in pos_pool.get(pos, []) if j not in set(chrom)]
        if candidates:
            chrom[idx] = random.choice(candidates)
        return chrom

    @staticmethod
    def _repair(
        chrom: list[int],
        costs: list[float],
        teams: list[int],
        budget: float,
        pos_pool: dict[str, list[int]],
        positions: list[str],
        max_attempts: int = 50,
    ) -> list[int] | None:
        """Attempt to repair constraint violations by swapping expensive or
        over-represented players with cheaper/different-team alternatives."""
        chrom = list(chrom)

        for _ in range(max_attempts):
            total = sum(costs[j] for j in chrom)
            club_cnt: Counter[int] = Counter(teams[j] for j in chrom)
            violations = []

            # Over-budget?
            if total > budget + 1e-6:
                violations.append("budget")

            # Club limit violations?
            over_clubs = [t for t, cnt in club_cnt.items() if cnt > MAX_PER_CLUB]
            if over_clubs:
                violations.append("club")

            if not violations:
                return chrom

            if "club" in violations and over_clubs:
                # Find a player from an over-represented club and swap
                club = over_clubs[0]
                club_players = [j for j in chrom if teams[j] == club]
                # Pick the one with worst predicted points
                victim_idx = min(range(len(chrom)), key=lambda i: (
                    0 if teams[chrom[i]] != club else -costs[chrom[i]]
                ))
                # Actually pick a club player
                for ci, cj in enumerate(chrom):
                    if teams[cj] == club:
                        victim_idx = ci
                        break
                old_j = chrom[victim_idx]
                pos = positions[old_j]
                candidates = [
                    j for j in pos_pool.get(pos, [])
                    if j not in set(chrom) and teams[j] != club
                ]
                if candidates:
                    chrom[victim_idx] = random.choice(candidates)
                    continue
                else:
                    return None

            if "budget" in violations:
                # Swap the most expensive player with a cheaper alternative
                most_expensive_idx = max(range(len(chrom)), key=lambda i: costs[chrom[i]])
                old_j = chrom[most_expensive_idx]
                pos = positions[old_j]
                candidates = [
                    j for j in pos_pool.get(pos, [])
                    if j not in set(chrom) and costs[j] < costs[old_j]
                ]
                if candidates:
                    chrom[most_expensive_idx] = random.choice(candidates)
                    continue
                else:
                    return None

        return None  # could not repair
