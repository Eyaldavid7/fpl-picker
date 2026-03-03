"""Historical FPL data loader.

Downloads per-gameweek CSV files from the community-maintained repository
at https://github.com/vaastav/Fantasy-Premier-League and merges them into
pandas DataFrames for use in training ML models.

Downloaded files are cached locally so that subsequent runs do not re-fetch.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Sequence

import httpx
import pandas as pd

from app.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_RAW_URL = (
    "https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data"
)

# Supported seasons (folder names in the GitHub repo)
SUPPORTED_SEASONS: list[str] = [
    "2024-25",
    "2023-24",
    "2022-23",
]

# Maximum gameweeks per season (38 in a normal PL season)
MAX_GAMEWEEKS = 38

# Local cache directory for downloaded CSVs
_HISTORICAL_CACHE_DIR = ".cache/historical"


def _cache_dir() -> Path:
    """Return the local directory for cached historical CSVs."""
    settings = get_settings()
    base = Path(settings.cache_dir) / "historical"
    base.mkdir(parents=True, exist_ok=True)
    return base


# ---------------------------------------------------------------------------
# Low-level download helpers
# ---------------------------------------------------------------------------


async def _download_csv(url: str) -> str | None:
    """Download a CSV file from ``url`` and return its text content.

    Returns ``None`` on any network or HTTP error (e.g. 404 when a
    gameweek CSV does not yet exist).
    """
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.text
            logger.debug("HTTP %s for %s", resp.status_code, url)
            return None
    except httpx.RequestError as exc:
        logger.warning("Download failed for %s: %s", url, exc)
        return None


def _local_path(season: str, gw: int) -> Path:
    """Return the local cache path for a season/gameweek CSV."""
    return _cache_dir() / f"{season}_gw{gw}.csv"


async def _get_gw_csv(season: str, gw: int) -> pd.DataFrame | None:
    """Return a single gameweek CSV as a DataFrame, using local cache.

    If the file is already cached locally it is read from disk; otherwise
    it is downloaded from GitHub and saved.
    """
    local = _local_path(season, gw)

    # Try local cache first
    if local.exists():
        try:
            return pd.read_csv(local, encoding="utf-8")
        except Exception:
            # Corrupt file -- re-download
            local.unlink(missing_ok=True)

    url = f"{BASE_RAW_URL}/{season}/gws/gw{gw}.csv"
    text = await _download_csv(url)
    if text is None:
        return None

    # Persist to local cache
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(text, encoding="utf-8")

    try:
        return pd.read_csv(io.StringIO(text), encoding="utf-8")
    except Exception as exc:
        logger.error("Failed to parse CSV for %s GW%d: %s", season, gw, exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def load_season(
    season: str,
    max_gw: int = MAX_GAMEWEEKS,
) -> pd.DataFrame:
    """Load all available gameweek CSVs for a single season.

    Parameters
    ----------
    season : str
        Season identifier, e.g. ``"2023-24"``.
    max_gw : int
        Maximum gameweek number to attempt downloading (default 38).

    Returns
    -------
    pd.DataFrame
        Concatenated DataFrame with an added ``season`` column.
        Returns an empty DataFrame if no data could be downloaded.
    """
    frames: list[pd.DataFrame] = []
    consecutive_misses = 0

    for gw in range(1, max_gw + 1):
        df = await _get_gw_csv(season, gw)
        if df is not None and not df.empty:
            df["GW"] = gw
            frames.append(df)
            consecutive_misses = 0
        else:
            consecutive_misses += 1
            # If we miss 3 consecutive gameweeks after GW 1 we assume
            # the rest of the season hasn't been played yet.
            if consecutive_misses >= 3 and gw > 3:
                logger.info(
                    "Stopping season %s at GW %d (3 consecutive misses)",
                    season, gw,
                )
                break

    if not frames:
        logger.warning("No data found for season %s", season)
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined["season"] = season
    logger.info(
        "Loaded season %s: %d rows across %d gameweeks",
        season, len(combined), len(frames),
    )
    return combined


async def load_multiple_seasons(
    seasons: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Load and concatenate data from multiple seasons.

    Parameters
    ----------
    seasons : list of str, optional
        Season identifiers to load. Defaults to ``SUPPORTED_SEASONS``.

    Returns
    -------
    pd.DataFrame
        Combined DataFrame with ``season`` and ``GW`` columns.
    """
    seasons = seasons or SUPPORTED_SEASONS
    frames: list[pd.DataFrame] = []

    for season in seasons:
        df = await load_season(season)
        if not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    logger.info(
        "Loaded %d seasons: %d total rows",
        len(frames), len(combined),
    )
    return combined


async def merge_with_current(
    historical: pd.DataFrame,
    current_elements: list[dict],
) -> pd.DataFrame:
    """Merge historical data with current-season bootstrap elements.

    Attempts to join on the ``name`` / ``web_name`` column to link
    players across seasons. Players not found in the current season
    are kept as-is (outer join).

    Parameters
    ----------
    historical : pd.DataFrame
        Output of ``load_multiple_seasons``.
    current_elements : list of dict
        The ``elements`` list from the bootstrap-static API response.

    Returns
    -------
    pd.DataFrame
        Historical data augmented with current-season ``element_id``
        and ``now_cost`` where a match is found.
    """
    if historical.empty:
        return historical

    current_df = pd.DataFrame(current_elements)
    if current_df.empty:
        return historical

    # Build a lookup from web_name -> current element id & cost
    if "web_name" in current_df.columns:
        lookup = (
            current_df[["id", "web_name", "now_cost"]]
            .rename(columns={"id": "current_element_id", "now_cost": "current_cost"})
        )
        # The historical CSVs use a "name" column
        name_col = "name" if "name" in historical.columns else "web_name"
        if name_col in historical.columns:
            merged = historical.merge(
                lookup,
                left_on=name_col,
                right_on="web_name",
                how="left",
            )
            # Drop the duplicate web_name column from the merge
            if "web_name_y" in merged.columns:
                merged.drop(columns=["web_name_y"], inplace=True)
                merged.rename(columns={"web_name_x": "web_name"}, inplace=True)
            return merged

    return historical


def clear_historical_cache() -> int:
    """Delete all locally cached historical CSV files.

    Returns the number of files removed.
    """
    cache = _cache_dir()
    count = 0
    for path in cache.glob("*.csv"):
        try:
            path.unlink()
            count += 1
        except OSError:
            pass
    return count
