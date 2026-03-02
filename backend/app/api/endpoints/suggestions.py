"""Team suggestion endpoints: substitute swaps and transfer recommendations.

Provides two POST endpoints:
- /substitutes  – identify bench players who should start over current starters
- /transfers    – identify the best players to bring in from the wider pool
"""

from __future__ import annotations

import logging
from collections import defaultdict

from fastapi import APIRouter, HTTPException

from app.api.schemas.suggestions import (
    SubstituteRequest,
    SubstituteResponse,
    SubstituteSuggestion,
    TransferRequest,
    TransferResponse,
    TransferSuggestion,
)
from app.data.fpl_client import get_fpl_client
from app.data.models import Player, Position

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Formation parsing
# ---------------------------------------------------------------------------

# Valid FPL formations mapped to (DEF, MID, FWD) counts.
# GKP is always 1 for the starting XI.
FORMATION_MAP: dict[str, tuple[int, int, int]] = {
    "3-4-3": (3, 4, 3),
    "3-5-2": (3, 5, 2),
    "4-3-3": (4, 3, 3),
    "4-4-2": (4, 4, 2),
    "4-5-1": (4, 5, 1),
    "5-2-3": (5, 2, 3),
    "5-3-2": (5, 3, 2),
    "5-4-1": (5, 4, 1),
}


def _parse_formation(formation: str) -> dict[Position, int]:
    """Return how many starters each position requires for a formation.

    Returns:
        Mapping from Position -> required starter count.

    Raises:
        ValueError: if the formation string is unrecognised.
    """
    key = formation.strip()
    if key not in FORMATION_MAP:
        raise ValueError(
            f"Unsupported formation '{key}'. "
            f"Supported: {', '.join(sorted(FORMATION_MAP))}."
        )
    d, m, f = FORMATION_MAP[key]
    return {
        Position.GKP: 1,
        Position.DEF: d,
        Position.MID: m,
        Position.FWD: f,
    }


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _predicted_score(player: Player) -> float:
    """Compute a simple predicted-points heuristic for a player.

    Uses ``form`` (recent average) as the primary signal.  Falls back to
    ``points_per_game`` (season-long average).  If both are zero, returns
    a tiny value so comparisons still work.
    """
    form = player.form
    ppg = player.points_per_game

    if form > 0 and ppg > 0:
        # Weighted blend: recent form matters more
        return round(0.65 * form + 0.35 * ppg, 2)
    if form > 0:
        return round(form, 2)
    if ppg > 0:
        return round(ppg, 2)
    return 0.01


def _availability_ok(player: Player) -> bool:
    """Return True if the player is likely available for the next match."""
    if player.status in ("i", "s", "u"):
        return False
    if player.chance_of_playing_next_round is not None and player.chance_of_playing_next_round < 50:
        return False
    return True


# ---------------------------------------------------------------------------
# Substitute suggestions
# ---------------------------------------------------------------------------

@router.post("/substitutes", response_model=SubstituteResponse)
async def suggest_substitutes(
    request: SubstituteRequest,
) -> SubstituteResponse:
    """Identify bench players who should start ahead of current starters.

    Algorithm:
    1. Fetch all FPL players and filter to the provided squad IDs.
    2. Parse the formation to determine position quotas for the starting XI.
    3. Within each position, rank squad members by predicted points and
       assign the top N as starters and the rest as bench.
    4. For every bench player, check if they outscore any starter in the
       *same position* -- if so, emit a swap suggestion.
    5. Return suggestions ordered by descending point gain.
    """
    client = get_fpl_client()

    try:
        all_players = await client.get_players()
    except Exception as exc:
        logger.error("Failed to fetch FPL data: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch live FPL data: {exc}",
        )

    # Build lookup of squad players
    player_map: dict[int, Player] = {p.id: p for p in all_players}
    squad_players: list[Player] = []
    missing: list[int] = []

    for pid in request.squad_player_ids:
        if pid in player_map:
            squad_players.append(player_map[pid])
        else:
            missing.append(pid)

    if missing:
        logger.warning("Player IDs not found: %s", missing)
        raise HTTPException(
            status_code=404,
            detail=f"Player IDs not found in FPL data: {missing}",
        )

    # Parse formation
    try:
        position_slots = _parse_formation(request.formation)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Group squad by position
    by_position: dict[Position, list[Player]] = defaultdict(list)
    for p in squad_players:
        by_position[p.position].append(p)

    # Within each position, sort by predicted score descending and split
    # into starters vs bench.
    starters: list[Player] = []
    bench: list[Player] = []

    for pos in (Position.GKP, Position.DEF, Position.MID, Position.FWD):
        group = by_position.get(pos, [])
        group.sort(key=_predicted_score, reverse=True)
        n_start = position_slots.get(pos, 0)
        starters.extend(group[:n_start])
        bench.extend(group[n_start:])

    # Compute predicted scores
    starter_scores = {p.id: _predicted_score(p) for p in starters}
    bench_scores = {p.id: _predicted_score(p) for p in bench}

    # For each bench player, see if they outscore any starter in the same
    # position.  Only emit swaps where bench > starter.
    suggestions: list[SubstituteSuggestion] = []

    for bench_player in bench:
        bench_pred = bench_scores[bench_player.id]
        # Find the weakest starter in the same position
        same_pos_starters = [s for s in starters if s.position == bench_player.position]
        if not same_pos_starters:
            continue
        # Sort ascending so weakest is first
        same_pos_starters.sort(key=lambda s: starter_scores[s.id])
        weakest = same_pos_starters[0]
        weakest_pred = starter_scores[weakest.id]

        point_gain = round(bench_pred - weakest_pred, 2)
        if point_gain <= 0:
            continue

        # Build a human-readable reason
        reason_parts: list[str] = []
        reason_parts.append(
            f"{bench_player.web_name} has predicted {bench_pred:.1f} pts "
            f"vs {weakest.web_name}'s {weakest_pred:.1f} pts"
        )
        if bench_player.form > weakest.form:
            reason_parts.append(
                f"higher recent form ({bench_player.form:.1f} vs {weakest.form:.1f})"
            )
        if not _availability_ok(weakest):
            reason_parts.append(
                f"{weakest.web_name} has availability concerns"
                + (f" ({weakest.news})" if weakest.news else "")
            )

        suggestions.append(
            SubstituteSuggestion(
                bench_player_id=bench_player.id,
                bench_player_name=bench_player.web_name,
                bench_player_position=bench_player.position.value,
                bench_predicted_points=bench_pred,
                starter_player_id=weakest.id,
                starter_player_name=weakest.web_name,
                starter_player_position=weakest.position.value,
                starter_predicted_points=weakest_pred,
                point_gain=point_gain,
                reason="; ".join(reason_parts),
            )
        )

    # Sort by highest point gain first
    suggestions.sort(key=lambda s: s.point_gain, reverse=True)

    return SubstituteResponse(suggestions=suggestions)


# ---------------------------------------------------------------------------
# Transfer suggestions
# ---------------------------------------------------------------------------

@router.post("/transfers", response_model=TransferResponse)
async def suggest_transfers(
    request: TransferRequest,
) -> TransferResponse:
    """Recommend the best transfers to improve the squad.

    Algorithm:
    1. Fetch all FPL players.  Identify squad members and the wider pool.
    2. For each position, find the weakest squad player (by predicted pts).
    3. Scan all available players NOT in the squad for upgrades that:
       - Are in the same position as the weakest squad member.
       - Are affordable: ``player_in_price - player_out_price <= budget``.
       - Are available (not injured/suspended).
       - Have a higher predicted score.
    4. Rank candidate swaps by point gain and return the top N where
       ``N = free_transfers``.
    """
    client = get_fpl_client()

    try:
        all_players = await client.get_players()
        teams_map = await client.get_teams_map()
    except Exception as exc:
        logger.error("Failed to fetch FPL data: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch live FPL data: {exc}",
        )

    # Build lookups
    player_map: dict[int, Player] = {p.id: p for p in all_players}
    squad_ids = set(request.squad_player_ids)

    squad_players: list[Player] = []
    missing: list[int] = []
    for pid in request.squad_player_ids:
        if pid in player_map:
            squad_players.append(player_map[pid])
        else:
            missing.append(pid)

    if missing:
        logger.warning("Player IDs not found: %s", missing)
        raise HTTPException(
            status_code=404,
            detail=f"Player IDs not found in FPL data: {missing}",
        )

    # Existing team counts to enforce the 3-per-team rule
    team_counts: dict[int, int] = defaultdict(int)
    for p in squad_players:
        team_counts[p.team] += 1

    # Pool of available players NOT already in the squad
    available_pool = [
        p
        for p in all_players
        if p.id not in squad_ids
        and _availability_ok(p)
        and p.minutes > 0  # must have some playing time
    ]

    # Group squad by position, find the weakest in each
    squad_by_position: dict[Position, list[Player]] = defaultdict(list)
    for p in squad_players:
        squad_by_position[p.position].append(p)

    # Build all candidate transfer pairs: (player_out, player_in, gain)
    candidates: list[tuple[Player, Player, float]] = []
    budget = request.budget_remaining

    for pos in (Position.GKP, Position.DEF, Position.MID, Position.FWD):
        pos_squad = squad_by_position.get(pos, [])
        if not pos_squad:
            continue

        # Sort ascending by predicted score so weakest is first
        pos_squad_sorted = sorted(pos_squad, key=_predicted_score)

        # Pool players in this position, sorted descending by predicted
        pos_pool = [p for p in available_pool if p.position == pos]
        pos_pool.sort(key=_predicted_score, reverse=True)

        # For each weak squad player, find the best affordable upgrade
        for squad_player in pos_squad_sorted:
            squad_pred = _predicted_score(squad_player)

            for candidate in pos_pool:
                cand_pred = _predicted_score(candidate)
                if cand_pred <= squad_pred:
                    # Pool is sorted desc; no further candidates will beat this
                    break

                net_cost = candidate.now_cost - squad_player.now_cost
                if net_cost > budget:
                    continue

                # Enforce max 3 players per team
                # After removing squad_player and adding candidate, check limit
                incoming_team = candidate.team
                current_count = team_counts.get(incoming_team, 0)
                # If squad_player is from the same team, removing them frees a slot
                adjustment = -1 if squad_player.team == incoming_team else 0
                if current_count + adjustment >= 3:
                    continue

                gain = round(cand_pred - squad_pred, 2)
                candidates.append((squad_player, candidate, gain))
                # Only keep the best candidate per squad player (first hit
                # in the desc-sorted pool).
                break

    # Sort by gain descending and take top free_transfers
    candidates.sort(key=lambda c: c[2], reverse=True)
    top = candidates[: request.free_transfers]

    suggestions: list[TransferSuggestion] = []
    total_gain = 0.0
    total_cost_change = 0

    for player_out, player_in, gain in top:
        net_cost = player_in.now_cost - player_out.now_cost
        total_gain += gain
        total_cost_change += net_cost

        # Build reason
        reason_parts: list[str] = []
        in_pred = _predicted_score(player_in)
        out_pred = _predicted_score(player_out)
        reason_parts.append(
            f"{player_in.web_name} predicted {in_pred:.1f} pts "
            f"vs {player_out.web_name}'s {out_pred:.1f} pts"
        )
        if player_in.form > player_out.form:
            reason_parts.append(
                f"better form ({player_in.form:.1f} vs {player_out.form:.1f})"
            )
        if net_cost < 0:
            reason_parts.append(
                f"saves {abs(net_cost) / 10:.1f}m budget"
            )
        elif net_cost > 0:
            reason_parts.append(
                f"costs extra {net_cost / 10:.1f}m"
            )
        if not _availability_ok(player_out):
            reason_parts.append(
                f"{player_out.web_name} has availability concerns"
            )

        team_name = teams_map.get(player_in.team, f"Team {player_in.team}")

        suggestions.append(
            TransferSuggestion(
                player_out_id=player_out.id,
                player_out_name=player_out.web_name,
                player_out_position=player_out.position.value,
                player_out_price=player_out.now_cost,
                player_out_predicted=out_pred,
                player_in_id=player_in.id,
                player_in_name=player_in.web_name,
                player_in_position=player_in.position.value,
                player_in_price=player_in.now_cost,
                player_in_predicted=in_pred,
                player_in_team=team_name,
                point_gain=gain,
                net_cost=net_cost,
                reason="; ".join(reason_parts),
            )
        )

    return TransferResponse(
        suggestions=suggestions,
        total_point_gain=round(total_gain, 2),
        total_cost_change=total_cost_change,
        transfers_used=len(suggestions),
    )
