"""Fixture-aware scoring module.

Adjusts base player predictions using fixture context: opponent strength,
home/away venue, FDR, and positional matchups (xG/xA per 90).

Supports DGW (double gameweek — 2 fixtures), SGW (single — 1 fixture),
and BGW (blank — 0 fixtures).

This is the single scoring function consumed by:
- Captain picker
- Bench optimizer
- Transfer advisor
- Squad optimization (ILP/GA)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.data.fpl_client import get_fpl_client
from app.data.models import Fixture, Player, Position, Team

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

# Maps team_id -> list of fixture dicts for that GW.
# DGW teams have 2 entries; BGW teams have 0; SGW teams have 1.
FixtureLookup = dict[int, list[dict]]


@dataclass
class FixtureDetail:
    """Scoring breakdown for a single fixture."""

    opponent_name: str
    opponent_id: int
    is_home: bool
    fdr: int
    fixture_multiplier: float
    positional_factor: float
    fixture_score: float  # base_score * fixture_multiplier * positional_factor
    reasoning: str


@dataclass
class ScoredPlayer:
    """A player scored with fixture-aware expected points."""

    player_id: int
    web_name: str
    position: str
    team_id: int
    base_score: float
    fixtures: list[FixtureDetail] = field(default_factory=list)
    final_score: float = 0.0
    reasoning: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FDR_FACTORS: dict[int, float] = {
    1: 1.15,
    2: 1.08,
    3: 1.0,
    4: 0.92,
    5: 0.85,
}

HOME_FACTOR = 1.05
AWAY_FACTOR = 0.95

# Multiplier clamp range
MULTIPLIER_MIN = 0.75
MULTIPLIER_MAX = 1.35

# Opponent strength factor clamp
OPP_STRENGTH_MIN = 0.90
OPP_STRENGTH_MAX = 1.10

# Positional factor clamp
POSITIONAL_MIN = 0.90
POSITIONAL_MAX = 1.15

# Approximate PL per-90 baselines
POSITIONAL_BASELINES: dict[str, dict[str, float]] = {
    "FWD": {"xg_baseline": 0.35, "xa_baseline": 0.12},
    "MID": {"xg_baseline": 0.15, "xa_baseline": 0.15},
    "DEF": {"xgc_baseline": 1.20},
    "GKP": {"xgc_baseline": 1.20},
}


# ---------------------------------------------------------------------------
# Fixture-Aware Scorer
# ---------------------------------------------------------------------------

class FixtureAwareScorer:
    """Adjusts base predictions using fixture context.

    Scoring formula (fully multiplicative):
        per_fixture_score = base_score * fixture_multiplier * positional_factor

    For DGW, per-fixture scores are summed. For BGW, final_score = 0.0.
    """

    def _compute_base_score(self, player: Player) -> float:
        """Compute base score with form regression (0.5/0.5 weighting)."""
        form = player.form
        ppg = player.points_per_game

        if form > 0 and ppg > 0:
            return round(0.5 * form + 0.5 * ppg, 2)
        if form > 0:
            return round(form, 2)
        if ppg > 0:
            return round(ppg, 2)
        return 0.01

    def _compute_opponent_strength_factor(
        self,
        player: Player,
        opponent: Team,
        is_home: bool,
        league_avgs: dict[str, float],
    ) -> float:
        """Compute opponent strength factor from team strength metrics.

        Attackers (FWD/MID) care about opponent's defensive strength.
        Defenders (DEF/GKP) care about opponent's attacking strength.

        Returns a factor clamped to [0.90, 1.10].
        """
        if player.position in (Position.FWD, Position.MID):
            if is_home:
                opp_strength = opponent.strength_defence_away
                league_avg = league_avgs["defence_away"]
            else:
                opp_strength = opponent.strength_defence_home
                league_avg = league_avgs["defence_home"]
        else:  # DEF, GKP
            if is_home:
                opp_strength = opponent.strength_attack_away
                league_avg = league_avgs["attack_away"]
            else:
                opp_strength = opponent.strength_attack_home
                league_avg = league_avgs["attack_home"]

        if opp_strength > 0:
            raw = league_avg / opp_strength
        else:
            raw = 1.0

        return max(OPP_STRENGTH_MIN, min(OPP_STRENGTH_MAX, raw))

    def _compute_positional_factor(self, player: Player) -> float:
        """Compute positional xG/xA factor using per-90 rates.

        Compares the player's per-90 output against positional baselines.
        Returns a multiplicative factor clamped to [0.90, 1.15].
        """
        minutes = max(player.minutes, 90)  # floor to avoid div-by-zero
        appearances = minutes / 90

        pos_key = player.position.value
        baselines = POSITIONAL_BASELINES.get(pos_key)
        if baselines is None:
            return 1.0

        if player.position in (Position.FWD, Position.MID):
            xg_per_90 = player.expected_goals / appearances
            xa_per_90 = player.expected_assists / appearances

            xg_baseline = baselines["xg_baseline"]
            xa_baseline = baselines["xa_baseline"]

            xg_ratio = xg_per_90 / xg_baseline if xg_baseline > 0 else 1.0
            xa_ratio = xa_per_90 / xa_baseline if xa_baseline > 0 else 1.0

            if player.position == Position.FWD:
                blended = 0.6 * xg_ratio + 0.4 * xa_ratio
            else:
                blended = 0.5 * xg_ratio + 0.5 * xa_ratio

            return max(POSITIONAL_MIN, min(POSITIONAL_MAX, blended))

        else:  # DEF, GKP
            xgc_per_90 = player.expected_goals_conceded / appearances
            xgc_baseline = baselines["xgc_baseline"]

            # Lower xGC = better CS probability = higher factor
            xgc_ratio = xgc_baseline / xgc_per_90 if xgc_per_90 > 0 else 1.0
            return max(POSITIONAL_MIN, min(POSITIONAL_MAX, xgc_ratio))

    def _precompute_league_avgs(self, teams: dict[int, Team]) -> dict[str, float]:
        """Pre-compute league average strength metrics (hoisted out of loop)."""
        all_teams = list(teams.values())
        n = len(all_teams) or 1
        return {
            "defence_away": sum(t.strength_defence_away for t in all_teams) / n,
            "defence_home": sum(t.strength_defence_home for t in all_teams) / n,
            "attack_away": sum(t.strength_attack_away for t in all_teams) / n,
            "attack_home": sum(t.strength_attack_home for t in all_teams) / n,
        }

    def score_player(
        self,
        player: Player,
        fixture_lookup: FixtureLookup,
        teams: dict[int, Team],
        teams_name_map: dict[int, str] | None = None,
        league_avgs: dict[str, float] | None = None,
    ) -> ScoredPlayer:
        """Score a single player with fixture-aware expected points.

        Handles DGW (multiple fixtures) by scoring each independently and
        summing. Handles BGW (no fixtures) by returning final_score = 0.0.
        """
        if league_avgs is None:
            league_avgs = self._precompute_league_avgs(teams)

        base_score = self._compute_base_score(player)
        positional_factor = self._compute_positional_factor(player)

        player_fixtures = fixture_lookup.get(player.team, [])
        fixture_details: list[FixtureDetail] = []
        reasoning_parts: list[str] = []

        for fix_info in player_fixtures:
            fdr = fix_info["fdr"]
            is_home = fix_info["is_home"]
            opponent_id = fix_info["opponent_id"]
            opponent_name = fix_info.get("opponent_name", f"Team {opponent_id}")

            # FDR factor
            fdr_factor = FDR_FACTORS.get(fdr, 1.0)

            # Home/away factor
            ha_factor = HOME_FACTOR if is_home else AWAY_FACTOR

            # Opponent strength factor
            opponent_team = teams.get(opponent_id)
            if opponent_team:
                opp_factor = self._compute_opponent_strength_factor(
                    player, opponent_team, is_home, league_avgs
                )
            else:
                opp_factor = 1.0

            # Combined fixture multiplier (clamped)
            raw_multiplier = fdr_factor * ha_factor * opp_factor
            fixture_multiplier = max(MULTIPLIER_MIN, min(MULTIPLIER_MAX, raw_multiplier))

            # Per-fixture score (fully multiplicative)
            fixture_score = round(base_score * fixture_multiplier * positional_factor, 2)

            # Build reasoning
            venue = "home" if is_home else "away"
            reason = f"{opponent_name} ({venue.upper()[0]}, FDR {fdr})"
            if fdr <= 2:
                reason += " - easy fixture"
            elif fdr >= 4:
                reason += " - tough fixture"

            fixture_details.append(
                FixtureDetail(
                    opponent_name=opponent_name,
                    opponent_id=opponent_id,
                    is_home=is_home,
                    fdr=fdr,
                    fixture_multiplier=fixture_multiplier,
                    positional_factor=positional_factor,
                    fixture_score=fixture_score,
                    reasoning=reason,
                )
            )
            reasoning_parts.append(reason)

        # Aggregate across fixtures
        if not fixture_details:
            final_score = 0.0
            reasoning_parts.append("No fixture this gameweek (BGW)")
        elif len(fixture_details) == 1:
            final_score = fixture_details[0].fixture_score
        else:
            # DGW: sum scores (player plays twice)
            final_score = round(sum(fd.fixture_score for fd in fixture_details), 2)
            reasoning_parts.insert(0, f"Double gameweek ({len(fixture_details)} fixtures)")

        return ScoredPlayer(
            player_id=player.id,
            web_name=player.web_name,
            position=player.position.value,
            team_id=player.team,
            base_score=base_score,
            fixtures=fixture_details,
            final_score=final_score,
            reasoning=reasoning_parts,
        )

    async def score_squad(
        self,
        player_ids: list[int],
        gameweek: int | None = None,
    ) -> dict[int, ScoredPlayer]:
        """Score all players in a squad for the given gameweek.

        If gameweek is None, uses the next unfinished gameweek.
        Fetches all required data (players, teams, fixtures) from the FPL API.
        """
        client = get_fpl_client()

        # Resolve gameweek
        if gameweek is None:
            current_gw = await client.get_current_gameweek()
            gameweek = min(current_gw + 1, 38)

        # Fetch data
        all_players = await client.get_players()
        all_teams = await client.get_teams()
        next_fixtures = await client.get_typed_fixtures(gameweek)
        teams_name_map = await client.get_teams_map()

        # Build lookups
        player_map = {p.id: p for p in all_players}
        teams_map = {t.id: t for t in all_teams}

        # Build DGW-aware fixture lookup
        fixture_lookup = build_fixture_lookup(next_fixtures, teams_name_map)

        # Pre-compute league averages (once, not per-player)
        league_avgs = self._precompute_league_avgs(teams_map)

        # Score each player
        results: dict[int, ScoredPlayer] = {}
        for pid in player_ids:
            player = player_map.get(pid)
            if player is None:
                logger.warning("Player ID %d not found in FPL data", pid)
                continue
            results[pid] = self.score_player(
                player, fixture_lookup, teams_map, teams_name_map, league_avgs
            )

        return results

    async def score_all_players(
        self,
        gameweek: int | None = None,
    ) -> dict[int, ScoredPlayer]:
        """Score ALL available players for the given gameweek.

        Used by the squad optimizer to get fixture-aware predictions for
        the entire player pool.
        """
        client = get_fpl_client()

        if gameweek is None:
            current_gw = await client.get_current_gameweek()
            gameweek = min(current_gw + 1, 38)

        all_players = await client.get_players()
        all_teams = await client.get_teams()
        next_fixtures = await client.get_typed_fixtures(gameweek)
        teams_name_map = await client.get_teams_map()

        player_map = {p.id: p for p in all_players}
        teams_map = {t.id: t for t in all_teams}
        fixture_lookup = build_fixture_lookup(next_fixtures, teams_name_map)
        league_avgs = self._precompute_league_avgs(teams_map)

        results: dict[int, ScoredPlayer] = {}
        for player in all_players:
            results[player.id] = self.score_player(
                player, fixture_lookup, teams_map, teams_name_map, league_avgs
            )

        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_fixture_lookup(
    fixtures: list[Fixture],
    teams_name_map: dict[int, str],
) -> FixtureLookup:
    """Build a DGW-aware fixture lookup from typed Fixture models.

    Returns dict mapping team_id -> list of fixture info dicts.
    DGW teams will have 2 entries; BGW teams will have 0.
    Fixes the overwrite bug in the old code that used direct assignment.
    """
    lookup: FixtureLookup = {}
    for fix in fixtures:
        # Home team entry
        lookup.setdefault(fix.team_h, []).append({
            "opponent_name": teams_name_map.get(fix.team_a, f"Team {fix.team_a}"),
            "opponent_id": fix.team_a,
            "is_home": True,
            "fdr": fix.team_h_difficulty,
        })
        # Away team entry
        lookup.setdefault(fix.team_a, []).append({
            "opponent_name": teams_name_map.get(fix.team_h, f"Team {fix.team_h}"),
            "opponent_id": fix.team_h,
            "is_home": False,
            "fdr": fix.team_a_difficulty,
        })
    return lookup


def get_fixture_scorer() -> FixtureAwareScorer:
    """Return a FixtureAwareScorer instance."""
    return FixtureAwareScorer()
