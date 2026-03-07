"""Optimization endpoints for squad selection, captain, bench, and formation."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas.optimization import (
    BenchOrderRequest,
    BenchOrderResponse,
    BenchPlayerDetail,
    CaptainRanking,
    CaptainRequest,
    CaptainResponse,
    FormationRequest,
    FormationResponse,
    SensitivityRequest,
    SensitivityResponse,
    SquadOptimizationRequest,
    SquadOptimizationResponse,
    SquadPlayer,
    CompareRequest,
    CompareResponse,
)
import app.data.fpl_client as _fpl_client_module
from app.optimization.engine import OptimizationEngine
from app.optimization.models import OptimizationResult
from app.prediction.fixture_scorer import (
    build_fixture_lookup,
    get_fixture_scorer,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Singleton engine instance (stateless, so safe to share)
_engine = OptimizationEngine()

# Map FPL element_type to position string the solver understands
_ELEMENT_TYPE_TO_POS: dict[int, str] = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _player_dict_to_squad_player(
    p: dict,
    is_starter: bool,
    is_captain: bool,
    is_vice: bool,
    pred: float,
) -> SquadPlayer:
    """Convert a raw player dict to the API response model."""
    return SquadPlayer(
        player_id=p.get("id", 0),
        web_name=p.get("web_name", ""),
        position=p.get("position", ""),
        team_id=p.get("team") or p.get("team_id") or 0,
        cost=p.get("now_cost", 0),
        predicted_points=pred,
        is_starter=is_starter,
        is_captain=is_captain,
        is_vice_captain=is_vice,
        status=p.get("status", "a"),
        chance_of_playing=p.get("chance_of_playing"),
        news=p.get("news", ""),
    )


def _result_to_response(
    result: OptimizationResult,
    predictions: dict[int, float],
) -> SquadOptimizationResponse:
    """Map an OptimizationResult to the API response schema."""
    captain_id = result.captain["id"] if result.captain else None
    vc_id = result.vice_captain["id"] if result.vice_captain else None

    squad_players: list[SquadPlayer] = []
    xi_ids = {p["id"] for p in result.starting_xi}
    for p in result.squad:
        pid = p["id"]
        squad_players.append(
            _player_dict_to_squad_player(
                p,
                is_starter=pid in xi_ids,
                is_captain=pid == captain_id,
                is_vice=pid == vc_id,
                pred=predictions.get(pid, 0.0),
            )
        )

    return SquadOptimizationResponse(
        squad=squad_players,
        starting_xi=[p["id"] for p in result.starting_xi],
        bench=[p["id"] for p in result.bench],
        captain_id=captain_id,
        vice_captain_id=vc_id,
        total_predicted_points=result.predicted_points,
        total_cost=int(result.total_cost * 10),  # back to 0.1m units
        method=result.method,
        solve_time_ms=int(result.solve_time * 1000),
        formation=result.formation,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/squad", response_model=SquadOptimizationResponse)
async def optimize_squad(
    request: SquadOptimizationRequest,
) -> SquadOptimizationResponse:
    """Select optimal 15-player squad using ILP or GA solver.

    Maximizes expected points subject to FPL constraints:
    budget, formation, max 3 per club, position limits.

    If ``players`` and ``predictions`` are omitted, the endpoint fetches
    live data from the FPL API and uses each player's *form* stat
    (average points over the last ~5 gameweeks) as the prediction.
    """
    players = request.players
    predictions = request.predictions

    if not players or not predictions:
        # Auto-fetch live FPL data
        client = _fpl_client_module.get_fpl_client()
        try:
            bootstrap = await client.get_bootstrap()
        except Exception as exc:
            logger.error("Failed to fetch FPL data: %s", exc)
            raise HTTPException(
                status_code=502,
                detail=f"Could not fetch live FPL data: {exc}",
            )

        raw_elements = bootstrap.get("elements", [])
        players = []
        predictions = {}

        for el in raw_elements:
            # Skip injured / suspended / unavailable players
            status = el.get("status", "a")
            if status in ("i", "s", "u"):
                continue
            # Skip players with 0 minutes (haven't played)
            if (el.get("minutes") or 0) == 0:
                continue
            # Skip players unlikely to play next round
            chance = el.get("chance_of_playing_next_round")
            if chance is not None and chance < 50:
                continue

            pid = el["id"]
            # Build a clean player dict for the solver (don't mutate cache)
            player = {
                "id": pid,
                "web_name": el.get("web_name", ""),
                "position": _ELEMENT_TYPE_TO_POS.get(
                    el.get("element_type", 3), "MID"
                ),
                "now_cost": el.get("now_cost", 0),
                "team": el.get("team", 0),
                "team_id": el.get("team", 0),
                "status": status,
                "chance_of_playing": chance,
                "news": el.get("news", ""),
            }
            players.append(player)

        # Use fixture-aware scoring for predictions
        try:
            scorer = get_fixture_scorer()
            all_pids = [p["id"] for p in players]
            scored = await scorer.score_squad(all_pids, request.gameweek)
            for p in players:
                pid = p["id"]
                sp = scored.get(pid)
                if sp and sp.final_score > 0:
                    pred = sp.final_score
                else:
                    # Fallback to base form/ppg if scorer returns 0 (BGW)
                    pred = 0.01
                # Discount prediction for doubtful players
                chance = p.get("chance_of_playing")
                if chance is not None and chance < 100:
                    pred = round(pred * (chance / 100), 2)
                predictions[pid] = pred
        except Exception as exc:
            logger.warning(
                "Fixture-aware scoring failed, falling back to form/ppg: %s", exc
            )
            # Fallback: raw form/ppg predictions
            for el in raw_elements:
                pid = el.get("id")
                if pid not in {p["id"] for p in players}:
                    continue
                form = float(el.get("form") or 0)
                ppg = float(el.get("points_per_game") or 0)
                if form > 0 and ppg > 0:
                    pred = round(0.5 * form + 0.5 * ppg, 2)
                elif form > 0:
                    pred = round(form, 2)
                elif ppg > 0:
                    pred = round(ppg, 2)
                else:
                    pred = 0.01
                chance = el.get("chance_of_playing_next_round")
                if chance is not None and chance < 100:
                    pred = round(pred * (chance / 100), 2)
                predictions[pid] = pred

        logger.info(
            "Auto-fetched %d eligible players from FPL API (fixture-aware)", len(players)
        )

    budget = request.budget / 10.0  # 0.1m units -> real money
    method = (request.method or "ilp").lower()

    try:
        result = _engine.optimize(
            players=players,
            predictions=predictions,
            method=method,
            budget=budget,
            formation=request.formation,
            locked_players=request.locked_players,
            excluded_players=request.excluded_players,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # For GA, take the best result
    if isinstance(result, list):
        if not result or not result[0].squad:
            raise HTTPException(
                status_code=422,
                detail="Optimisation produced no result. The budget or constraints may be too restrictive to form a valid squad.",
            )
        result = result[0]

    if not result.squad:
        raise HTTPException(
            status_code=422,
            detail="Optimisation produced no result. The budget or constraints may be too restrictive to form a valid squad.",
        )

    response = _result_to_response(result, predictions)

    # --- Enrich squad players with next-GW fixture info (post-processing) ---
    try:
        client = _fpl_client_module.get_fpl_client()
        current_gw = await client.get_current_gameweek()
        next_gw = min(current_gw + 1, 38)
        next_fixtures = await client.get_typed_fixtures(next_gw)
        teams_map = await client.get_teams_map()

        # Build DGW-aware fixture lookup using canonical helper
        fixture_lookup = build_fixture_lookup(next_fixtures, teams_map)

        # Enrich each squad player with fixture data
        for player in response.squad:
            fix_list = fixture_lookup.get(player.team_id, [])
            if fix_list:
                parts = []
                for fix_info in fix_list:
                    venue = "(H)" if fix_info["is_home"] else "(A)"
                    parts.append(f"{fix_info['opponent_name']} {venue}")
                player.next_opponent = ", ".join(parts)
                player.fdr = fix_list[0]["fdr"]  # Use first fixture's FDR
    except Exception as exc:
        logger.warning(
            "Could not enrich squad with fixture data; returning without "
            "opponent info: %s",
            exc,
        )

    return response


@router.get("/formations")
async def list_formations() -> dict:
    """Return all valid FPL formations."""
    return {"formations": _engine.get_available_formations()}


@router.post("/compare", response_model=CompareResponse)
async def compare_methods(request: CompareRequest) -> CompareResponse:
    """Run both ILP and GA solvers and compare results."""
    if not request.players:
        raise HTTPException(status_code=400, detail="'players' list is required.")
    if not request.predictions:
        raise HTTPException(status_code=400, detail="'predictions' map is required.")

    budget = request.budget / 10.0
    comparison = _engine.compare_methods(
        players=request.players,
        predictions=request.predictions,
        budget=budget,
        formation=request.formation,
    )
    return CompareResponse(**comparison)


# ---------------------------------------------------------------------------
# Existing stubs (kept for backward compatibility)
# ---------------------------------------------------------------------------

@router.post("/captain", response_model=CaptainResponse)
async def select_captain(request: CaptainRequest) -> CaptainResponse:
    """Select optimal captain and vice-captain from given XI.

    Uses fixture-aware scoring to rank candidates. If ``differential``
    is True, applies an ownership penalty to favor low-ownership picks.
    """
    scorer = get_fixture_scorer()

    # Resolve gameweek (default to next unfinished GW)
    if request.gameweek is None:
        client = _fpl_client_module.get_fpl_client()
        gw = await client.get_current_gameweek()
        gameweek = min(gw + 1, 38)
    else:
        gameweek = request.gameweek

    try:
        scores = await scorer.score_squad(request.player_ids, gameweek)
    except Exception as exc:
        logger.error("Failed to score squad for captain: %s", exc)
        raise HTTPException(status_code=502, detail=f"Scoring failed: {exc}")

    if not scores:
        raise HTTPException(status_code=404, detail="No players found for given IDs")

    # Fetch teams map for display names
    client = _fpl_client_module.get_fpl_client()
    teams_name_map = await client.get_teams_map()

    # Determine effective mode (backward-compat: differential=True maps to "differential")
    effective_mode = request.mode
    if request.differential and effective_mode == "safe":
        effective_mode = "differential"

    # Fetch ownership data only when needed
    player_map: dict = {}
    if effective_mode == "differential":
        all_players = await client.get_players()
        player_map = {p.id: p for p in all_players}

    # Variance factor by position for aggressive mode
    _VARIANCE_FACTOR: dict[str, float] = {"FWD": 1.3, "MID": 1.2, "DEF": 1.0, "GKP": 0.9}

    # Build rankings
    rankings: list[CaptainRanking] = []
    for pid, sp in scores.items():
        ownership = 0.0
        ceiling_score = 0.0

        if effective_mode == "differential":
            player = player_map.get(pid)
            ownership = player.selected_by_percent if player else 0.0
            effective_score = sp.final_score * (1 - ownership / 200)
        elif effective_mode == "aggressive":
            variance_factor = _VARIANCE_FACTOR.get(sp.position, 1.0)
            ceiling_score = sp.final_score * variance_factor
            effective_score = ceiling_score
        else:
            # "safe" (default): rank by expected points, no ownership penalty
            effective_score = sp.final_score

        # Build opponent string from first fixture
        opponent_str = ""
        fdr_val = None
        if sp.fixtures:
            parts = []
            for f in sp.fixtures:
                venue = "H" if f.is_home else "A"
                parts.append(f"{f.opponent_name} ({venue})")
                if fdr_val is None:
                    fdr_val = f.fdr
            opponent_str = ", ".join(parts)

        team_name = teams_name_map.get(sp.team_id, "")
        reasoning = "; ".join(sp.reasoning) if sp.reasoning else ""

        rankings.append(CaptainRanking(
            player_id=pid,
            web_name=sp.web_name,
            position=sp.position,
            team_name=team_name,
            predicted_points=round(effective_score, 2),
            effective_ownership=round(ownership, 1),
            opponent=opponent_str,
            fdr=fdr_val,
            reasoning=reasoning,
            ceiling_score=round(ceiling_score, 2),
        ))

    # Sort by predicted points descending
    rankings.sort(key=lambda r: r.predicted_points, reverse=True)

    captain = rankings[0] if rankings else None
    vice = rankings[1] if len(rankings) > 1 else None

    return CaptainResponse(
        captain_id=captain.player_id if captain else 0,
        vice_captain_id=vice.player_id if vice else 0,
        captain_xpts=captain.predicted_points if captain else 0.0,
        vice_captain_xpts=vice.predicted_points if vice else 0.0,
        rankings=rankings,
    )


@router.post("/bench", response_model=BenchOrderResponse)
async def optimize_bench(request: BenchOrderRequest) -> BenchOrderResponse:
    """Optimize bench order given starting XI and substitutes.

    Scores bench players using fixture-aware predictions and orders them
    by expected auto-sub value. GKP is always placed first (FPL rule:
    bench slot 0 is the backup keeper).
    """
    scorer = get_fixture_scorer()

    # Resolve gameweek
    if request.gameweek is None:
        client = _fpl_client_module.get_fpl_client()
        gw = await client.get_current_gameweek()
        gameweek = min(gw + 1, 38)
    else:
        gameweek = request.gameweek

    # Score all bench players
    try:
        scores = await scorer.score_squad(request.bench_ids, gameweek)
    except Exception as exc:
        logger.error("Failed to score bench players: %s", exc)
        raise HTTPException(status_code=502, detail=f"Scoring failed: {exc}")

    # Fetch teams map for opponent display
    client = _fpl_client_module.get_fpl_client()
    teams_name_map = await client.get_teams_map()

    # Separate GKP from outfield bench players
    gkp_ids: list[int] = []
    outfield: list[tuple[int, float]] = []

    for pid in request.bench_ids:
        sp = scores.get(pid)
        if sp is None:
            continue
        if sp.position == "GKP":
            gkp_ids.append(pid)
        else:
            outfield.append((pid, sp.final_score))

    # Sort outfield by score descending (highest auto-sub value first)
    outfield.sort(key=lambda x: x[1], reverse=True)

    # FPL bench order: GKP first, then outfield by score
    bench_order = gkp_ids + [pid for pid, _ in outfield]

    # Calculate expected auto-sub points (sum of all bench scores,
    # weighted by likelihood of being subbed on — approximate as
    # 15% for first sub, 5% for second, 2% for third)
    sub_weights = [0.15, 0.05, 0.02]
    expected_auto_sub = 0.0
    outfield_scores = [s for _, s in outfield]
    for i, score in enumerate(outfield_scores):
        weight = sub_weights[i] if i < len(sub_weights) else 0.01
        expected_auto_sub += score * weight

    # Build bench player details
    bench_players: list[BenchPlayerDetail] = []
    for pid in bench_order:
        sp = scores.get(pid)
        if sp is None:
            continue
        opponent_str = ""
        if sp.fixtures:
            parts = []
            for f in sp.fixtures:
                venue = "H" if f.is_home else "A"
                parts.append(f"{f.opponent_name} ({venue})")
            opponent_str = ", ".join(parts)

        bench_players.append(BenchPlayerDetail(
            player_id=pid,
            web_name=sp.web_name,
            position=sp.position,
            final_score=round(sp.final_score, 2),
            opponent=opponent_str,
            reasoning="; ".join(sp.reasoning) if sp.reasoning else "",
        ))

    return BenchOrderResponse(
        bench_order=bench_order,
        expected_auto_sub_points=round(expected_auto_sub, 2),
        bench_players=bench_players,
    )


@router.post("/formation", response_model=FormationResponse)
async def optimize_formation(request: FormationRequest) -> FormationResponse:
    """Find optimal formation for a given squad."""
    # TODO: Implement
    return FormationResponse(
        formation="3-4-3",
        starting_xi=[],
        bench=[],
        total_predicted_points=0.0,
    )


@router.post("/sensitivity", response_model=SensitivityResponse)
async def sensitivity_analysis(request: SensitivityRequest) -> SensitivityResponse:
    """Analyze how much each swap would affect total expected points."""
    # TODO: Implement
    return SensitivityResponse(
        analyses=[],
        gameweek=request.gameweek,
    )
