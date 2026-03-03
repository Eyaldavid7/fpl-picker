"""Async FPL API client with httpx.

Features:
- Connection pooling via a long-lived ``httpx.AsyncClient``
- Rate limiting (default 1 req/sec via asyncio.Semaphore)
- File-based caching with per-endpoint TTL
- Typed helper methods that return Pydantic model instances
"""

from __future__ import annotations

import asyncio
import logging
import time
from functools import lru_cache

import httpx

from app.config import get_settings
from app.data.cache import FileCache
from app.data.models import (
    Fixture,
    Gameweek,
    Player,
    PlayerHistory,
    Team,
)

logger = logging.getLogger(__name__)


class FPLClient:
    """Async HTTP client for the official Fantasy Premier League API.

    Implements rate limiting, caching, and error handling for all
    major FPL API endpoints.
    """

    ENDPOINTS = {
        "bootstrap": "/bootstrap-static/",
        "element_summary": "/element-summary/{id}/",
        "fixtures": "/fixtures/",
        "live": "/event/{gw}/live/",
        "entry": "/entry/{id}/",
        "entry_history": "/entry/{id}/history/",
        "entry_picks": "/entry/{id}/event/{gw}/picks/",
        "entry_transfers": "/entry/{id}/transfers/",
        "dream_team": "/dream-team/{gw}/",
    }

    # Map endpoint names to cache TTL categories (used by FileCache.ttl_for)
    _TTL_CATEGORIES = {
        "bootstrap": "bootstrap-static",
        "element_summary": "element-summary",
        "fixtures": "fixtures",
        "live": "live",
        "entry": "entry",
    }

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url: str = settings.fpl_base_url
        self.rate_limit: float = settings.fpl_rate_limit
        self.cache = FileCache()

        # Rate-limiting state
        self._semaphore = asyncio.Semaphore(1)
        self._last_request_time: float = 0.0

        # Reusable connection-pooled client (created lazily)
        self._http_client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Connection pool management
    # ------------------------------------------------------------------

    def _get_http_client(self) -> httpx.AsyncClient:
        """Return (and lazily create) a long-lived httpx client with pooling."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                limits=httpx.Limits(
                    max_connections=10,
                    max_keepalive_connections=5,
                    keepalive_expiry=30.0,
                ),
                headers={
                    "User-Agent": "FPL-Team-Picker/0.1",
                    "Accept": "application/json",
                },
                follow_redirects=True,
            )
        return self._http_client

    async def close(self) -> None:
        """Close the underlying HTTP client (call on app shutdown)."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    # ------------------------------------------------------------------
    # Low-level request helpers
    # ------------------------------------------------------------------

    async def _rate_limited_request(self, url: str) -> dict | list:
        """Make a rate-limited HTTP request to the FPL API.

        Enforces a minimum interval of ``1 / rate_limit`` seconds between
        consecutive requests by sleeping inside a semaphore.
        """
        async with self._semaphore:
            now = time.time()
            elapsed = now - self._last_request_time
            min_interval = 1.0 / self.rate_limit
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)

            client = self._get_http_client()
            logger.debug("FPL API request: %s", url)

            try:
                response = await client.get(url)
                self._last_request_time = time.time()
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "FPL API HTTP %s for %s: %s",
                    exc.response.status_code,
                    url,
                    exc.response.text[:200],
                )
                raise
            except httpx.RequestError as exc:
                logger.error("FPL API request failed for %s: %s", url, exc)
                raise

    async def _get_cached_or_fetch(
        self, cache_key: str, url: str, ttl_category: str
    ) -> dict | list:
        """Check cache first; if miss, fetch from API and cache the result."""
        cached = self.cache.get(cache_key)
        if cached is not None:
            logger.debug("Cache hit: %s", cache_key)
            return cached

        logger.info("Cache miss, fetching: %s", url)
        data = await self._rate_limited_request(url)

        ttl = self.cache.ttl_for(ttl_category)
        self.cache.set(cache_key, data, ttl=ttl)
        return data

    # ------------------------------------------------------------------
    # Raw API endpoint methods (return dicts/lists)
    # ------------------------------------------------------------------

    async def get_bootstrap(self) -> dict:
        """Fetch bootstrap-static data: all players, teams, gameweeks.

        Returns a dict with keys:
        - elements: all players with current stats
        - teams: all Premier League clubs
        - events: all gameweeks with deadlines and scores
        - element_types: position definitions (GKP, DEF, MID, FWD)
        - element_stats: available stat categories
        """
        url = f"{self.base_url}{self.ENDPOINTS['bootstrap']}"
        return await self._get_cached_or_fetch(
            "bootstrap_static", url, "bootstrap-static"
        )

    async def get_player_summary(self, player_id: int) -> dict:
        """Fetch detailed player history and upcoming fixtures.

        Returns dict with keys: history, fixtures, history_past.
        """
        url = f"{self.base_url}{self.ENDPOINTS['element_summary'].format(id=player_id)}"
        cache_key = f"element_summary_{player_id}"
        return await self._get_cached_or_fetch(cache_key, url, "element-summary")

    async def get_fixtures(self, gameweek: int | None = None) -> list[dict]:
        """Fetch fixture data, optionally filtered by gameweek."""
        url = f"{self.base_url}{self.ENDPOINTS['fixtures']}"
        if gameweek:
            url += f"?event={gameweek}"

        cache_key = f"fixtures_gw{gameweek}" if gameweek else "fixtures_all"
        data = await self._get_cached_or_fetch(cache_key, url, "fixtures")

        if isinstance(data, list):
            return data
        return data.get("fixtures", data) if isinstance(data, dict) else []

    async def get_live_gameweek(self, gameweek: int) -> dict:
        """Fetch live gameweek data (during matches)."""
        url = f"{self.base_url}{self.ENDPOINTS['live'].format(gw=gameweek)}"
        cache_key = f"live_gw{gameweek}"
        return await self._get_cached_or_fetch(cache_key, url, "live")

    async def get_entry(self, entry_id: int) -> dict:
        """Fetch manager (entry) information."""
        url = f"{self.base_url}{self.ENDPOINTS['entry'].format(id=entry_id)}"
        cache_key = f"entry_{entry_id}"
        return await self._get_cached_or_fetch(cache_key, url, "entry")

    async def get_entry_history(self, entry_id: int) -> dict:
        """Fetch manager season history."""
        url = f"{self.base_url}{self.ENDPOINTS['entry_history'].format(id=entry_id)}"
        cache_key = f"entry_history_{entry_id}"
        return await self._get_cached_or_fetch(cache_key, url, "entry")

    async def get_entry_picks(self, entry_id: int, gameweek: int) -> dict:
        """Fetch manager picks for a specific gameweek."""
        url = f"{self.base_url}{self.ENDPOINTS['entry_picks'].format(id=entry_id, gw=gameweek)}"
        cache_key = f"entry_picks_{entry_id}_gw{gameweek}"
        return await self._get_cached_or_fetch(cache_key, url, "entry")

    async def get_entry_transfers(self, entry_id: int) -> list[dict]:
        """Fetch all transfers for a manager."""
        url = f"{self.base_url}{self.ENDPOINTS['entry_transfers'].format(id=entry_id)}"
        cache_key = f"entry_transfers_{entry_id}"
        return await self._get_cached_or_fetch(cache_key, url, "entry")

    # ------------------------------------------------------------------
    # Convenience: current gameweek
    # ------------------------------------------------------------------

    async def get_current_gameweek(self) -> int:
        """Determine the current gameweek number from bootstrap data."""
        bootstrap = await self.get_bootstrap()
        for event in bootstrap.get("events", []):
            if event.get("is_current"):
                return event["id"]
        for event in bootstrap.get("events", []):
            if not event.get("finished"):
                return event["id"]
        return 1

    # ------------------------------------------------------------------
    # Typed extraction helpers (return Pydantic models)
    # ------------------------------------------------------------------

    async def get_players(self) -> list[Player]:
        """Return all players as typed ``Player`` models."""
        bootstrap = await self.get_bootstrap()
        return [
            Player.from_api_element(el)
            for el in bootstrap.get("elements", [])
        ]

    async def get_player_by_id(self, player_id: int) -> Player | None:
        """Find a specific player from bootstrap data."""
        bootstrap = await self.get_bootstrap()
        for element in bootstrap.get("elements", []):
            if element["id"] == player_id:
                return Player.from_api_element(element)
        return None

    async def get_player_history(self, player_id: int) -> list[PlayerHistory]:
        """Return typed history records for a player."""
        summary = await self.get_player_summary(player_id)
        return [
            PlayerHistory.from_api_history(h)
            for h in summary.get("history", [])
        ]

    async def get_teams(self) -> list[Team]:
        """Return all teams as typed ``Team`` models."""
        bootstrap = await self.get_bootstrap()
        return [
            Team.from_api_team(t)
            for t in bootstrap.get("teams", [])
        ]

    async def get_teams_map(self) -> dict[int, str]:
        """Return a mapping of team ID -> short name."""
        bootstrap = await self.get_bootstrap()
        return {
            team["id"]: team["short_name"]
            for team in bootstrap.get("teams", [])
        }

    async def get_typed_fixtures(
        self, gameweek: int | None = None
    ) -> list[Fixture]:
        """Return fixtures as typed ``Fixture`` models."""
        raw = await self.get_fixtures(gameweek=gameweek)
        return [Fixture.from_api_fixture(f) for f in raw]

    async def get_gameweeks(self) -> list[Gameweek]:
        """Return all gameweeks as typed ``Gameweek`` models."""
        bootstrap = await self.get_bootstrap()
        return [
            Gameweek.from_api_event(ev)
            for ev in bootstrap.get("events", [])
        ]

    async def get_current_gameweek_info(self) -> Gameweek | None:
        """Return the current gameweek as a ``Gameweek`` model."""
        gameweeks = await self.get_gameweeks()
        for gw in gameweeks:
            if gw.is_current:
                return gw
        # Fallback: first unfinished
        for gw in gameweeks:
            if not gw.finished:
                return gw
        return gameweeks[-1] if gameweeks else None


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

@lru_cache
def get_fpl_client() -> FPLClient:
    """Return a singleton FPL client instance."""
    return FPLClient()
