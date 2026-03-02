"""Endpoint for importing a squad from a screenshot using Gemini Vision."""

import json
import logging
from difflib import SequenceMatcher

import google.generativeai as genai
from fastapi import APIRouter, HTTPException, UploadFile

from app.api.schemas.squad_import import (
    MatchedPlayer,
    ScreenshotImportResponse,
)
from app.config import get_settings
from app.data.fpl_client import FPLClient

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
    client = FPLClient()
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
