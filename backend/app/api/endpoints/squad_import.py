"""Endpoint for importing a squad from a screenshot using Gemini Vision."""

import json
import logging
import warnings
from difflib import SequenceMatcher

# google.generativeai is deprecated in favour of google-genai, but we keep
# using it here for backwards compatibility.  Suppress the deprecation warning
# so it doesn't clutter logs.
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=FutureWarning)
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    import google.generativeai as genai  # noqa: E402
from fastapi import APIRouter, HTTPException, UploadFile

import httpx

from app.api.schemas.squad_import import (
    MatchedPlayer,
    ScreenshotImportResponse,
    TeamIdImportRequest,
    TeamIdImportResult,
)
from app.config import get_settings
from app.data.fpl_client import get_fpl_client
from app.data.models import POSITION_MAP

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


async def _extract_names_from_image(image_bytes: bytes, mime_type: str) -> list[str]:
    """Send image to Gemini Vision and extract player names."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise HTTPException(status_code=500, detail="Gemini API key not configured")

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = (
        "This is a screenshot of a Fantasy Premier League (FPL) team. "
        "Extract all player names visible in the image. "
        "Return ONLY a JSON array of strings with the player names, nothing else. "
        'Example: ["Salah", "Haaland", "Saka"]\n'
        "If you cannot identify any players, return an empty array []."
    )

    response = model.generate_content(
        [
            prompt,
            {"mime_type": mime_type, "data": image_bytes},
        ]
    )

    text = response.text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        names = json.loads(text)
        if not isinstance(names, list):
            raise ValueError("Expected a JSON array")
        return [str(n).strip() for n in names if str(n).strip()]
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to parse Gemini response: %s — raw: %s", exc, text)
        raise HTTPException(
            status_code=502,
            detail=f"Could not parse player names from image. Gemini returned: {text[:200]}",
        ) from exc


def _fuzzy_match_player(
    name: str,
    players: list[dict],
    team_map: dict[int, str],
    used_ids: set[int],
) -> MatchedPlayer:
    """Match an extracted name to the best FPL player using fuzzy matching."""
    best_score = 0.0
    best_player = None
    name_lower = name.lower()

    for p in players:
        if p["id"] in used_ids:
            continue

        candidates = [
            p.get("web_name", ""),
            p.get("second_name", ""),
            f"{p.get('first_name', '')} {p.get('second_name', '')}",
        ]

        for candidate in candidates:
            candidate_lower = candidate.lower()
            ratio = SequenceMatcher(None, name_lower, candidate_lower).ratio()

            # Boost score if the extracted name is a substring of the candidate or vice versa
            if name_lower in candidate_lower or candidate_lower in name_lower:
                ratio = min(ratio + 0.15, 1.0)

            if ratio > best_score:
                best_score = ratio
                best_player = p

    if best_player and best_score >= 0.35:
        # Position is a Position enum — get its .value string
        pos = best_player.get("position")
        pos_str = pos.value if hasattr(pos, "value") else str(pos) if pos else None

        return MatchedPlayer(
            extracted_name=name,
            player_id=best_player["id"],
            web_name=best_player.get("web_name"),
            position=pos_str,
            team_name=team_map.get(best_player.get("team", 0)),
            confidence=round(best_score, 3),
        )

    return MatchedPlayer(extracted_name=name, confidence=0.0)


@router.post("/screenshot", response_model=ScreenshotImportResponse)
async def import_screenshot(file: UploadFile):
    """Import a squad from a screenshot using Gemini Vision OCR + fuzzy matching."""

    # Validate content type
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Use PNG, JPEG, or WebP.",
        )

    # Read & validate size
    image_bytes = await file.read()
    if len(image_bytes) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10 MB.")

    # Extract player names via Gemini
    names = await _extract_names_from_image(image_bytes, file.content_type)
    if not names:
        return ScreenshotImportResponse(players=[], extracted_count=0, matched_count=0)

    # Fetch FPL player data and team names for matching
    client = get_fpl_client()
    all_players = await client.get_players()
    team_map = await client.get_teams_map()  # {team_id: short_name}

    # Convert Pydantic Player models to dicts for matching
    player_dicts = [p.model_dump() for p in all_players]

    # Fuzzy-match each extracted name
    used_ids: set[int] = set()
    matched: list[MatchedPlayer] = []

    for extracted_name in names:
        result = _fuzzy_match_player(extracted_name, player_dicts, team_map, used_ids)
        if result.player_id is not None:
            used_ids.add(result.player_id)
        matched.append(result)

    matched_count = sum(1 for m in matched if m.player_id is not None)

    return ScreenshotImportResponse(
        players=matched,
        extracted_count=len(names),
        matched_count=matched_count,
    )


@router.post("/team-id", response_model=TeamIdImportResult)
async def import_by_team_id(request: TeamIdImportRequest):
    """Import a squad by FPL team ID.

    Fetches the manager's current gameweek picks from the official FPL API
    and returns full player details with lineup structure.
    """
    client = get_fpl_client()

    # --- Fetch team/entry info ---
    try:
        entry = await client.get_entry(request.team_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"FPL team with ID {request.team_id} not found.",
            ) from exc
        raise HTTPException(
            status_code=502,
            detail=f"FPL API error while fetching team info: {exc.response.status_code}",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach FPL API: {exc}",
        ) from exc

    # --- Get the current gameweek ---
    try:
        current_gw = await client.get_current_gameweek()
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"FPL API error while fetching current gameweek: {exc}",
        ) from exc

    # --- Fetch picks for the current gameweek ---
    try:
        picks_data = await client.get_entry_picks(request.team_id, current_gw)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"No picks found for team {request.team_id} in gameweek {current_gw}.",
            ) from exc
        raise HTTPException(
            status_code=502,
            detail=f"FPL API error while fetching picks: {exc.response.status_code}",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach FPL API: {exc}",
        ) from exc

    # --- Fetch bootstrap data for player lookups ---
    try:
        bootstrap = await client.get_bootstrap()
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"FPL API error while fetching player data: {exc}",
        ) from exc

    # Build lookup maps
    elements_by_id: dict[int, dict] = {
        el["id"]: el for el in bootstrap.get("elements", [])
    }
    team_map: dict[int, str] = {
        t["id"]: t["short_name"] for t in bootstrap.get("teams", [])
    }

    # --- Process picks ---
    picks = picks_data.get("picks", [])
    starting_xi: list[int] = []
    bench: list[int] = []
    captain_id: int | None = None
    vice_captain_id: int | None = None
    matched_players: list[MatchedPlayer] = []

    for pick in picks:
        player_id = pick["element"]
        position = pick["position"]  # 1-15
        is_captain = pick.get("is_captain", False)
        is_vice_captain = pick.get("is_vice_captain", False)

        if is_captain:
            captain_id = player_id
        if is_vice_captain:
            vice_captain_id = player_id

        if position <= 11:
            starting_xi.append(player_id)
        else:
            bench.append(player_id)

        # Build MatchedPlayer from bootstrap element data
        element = elements_by_id.get(player_id)
        if element:
            pos_enum = POSITION_MAP.get(element.get("element_type", 3))
            pos_str = pos_enum.value if pos_enum else None
            matched_players.append(
                MatchedPlayer(
                    extracted_name=element.get("web_name", ""),
                    player_id=player_id,
                    web_name=element.get("web_name"),
                    position=pos_str,
                    team_name=team_map.get(element.get("team", 0)),
                    confidence=1.0,
                )
            )
        else:
            matched_players.append(
                MatchedPlayer(
                    extracted_name=f"Unknown ({player_id})",
                    player_id=player_id,
                    confidence=0.0,
                )
            )

    # --- Extract team/manager metadata ---
    team_name = entry.get("name", "")
    first_name = entry.get("player_first_name", "")
    last_name = entry.get("player_last_name", "")
    manager_name = f"{first_name} {last_name}".strip()

    overall_points = entry.get("summary_overall_points", 0) or 0
    overall_rank = entry.get("summary_overall_rank", 0) or 0

    # Bank and team value come from the picks endpoint (entry_history within picks)
    entry_history = picks_data.get("entry_history", {})
    bank = (entry_history.get("bank", 0) or 0) / 10  # convert from 0.1m units
    team_value = (entry_history.get("value", 0) or 0) / 10  # convert from 0.1m units

    # Adjust bank for pending transfers (made after current GW deadline)
    try:
        transfers = await client.get_entry_transfers(request.team_id)
        for t in transfers:
            if t.get("event", 0) > current_gw:
                # Pending transfer: subtract net cost (in_cost - out_cost, in 0.1m units)
                bank -= (t.get("element_in_cost", 0) - t.get("element_out_cost", 0)) / 10
    except (httpx.HTTPStatusError, httpx.RequestError):
        pass  # Non-critical: fall back to deadline bank

    return TeamIdImportResult(
        team_name=team_name,
        manager_name=manager_name,
        gameweek=current_gw,
        players=matched_players,
        starting_xi=starting_xi,
        bench=bench,
        captain_id=captain_id,
        vice_captain_id=vice_captain_id,
        overall_points=overall_points,
        overall_rank=overall_rank,
        bank=bank,
        team_value=team_value,
    )
