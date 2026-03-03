"""File-based cache with per-endpoint TTL support.

Stores JSON-serialisable data on disk with configurable time-to-live
per cache key category. Designed for caching FPL API responses without
requiring Redis or any external service.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default TTL values (seconds) per endpoint category
# ---------------------------------------------------------------------------
DEFAULT_TTLS: dict[str, int] = {
    "bootstrap-static": 3600,       # 1 hour
    "fixtures": 86400,              # 24 hours
    "element-summary": 7200,        # 2 hours
    "live": 60,                     # 1 minute
    "entry": 7200,                  # 2 hours
    "historical": 604800,           # 7 days (downloaded CSVs rarely change)
}


class FileCache:
    """File-based cache with TTL (time-to-live) expiration.

    Stores JSON-serializable data on disk with per-key TTL.
    Suitable for caching FPL API responses without needing Redis.
    """

    def __init__(self, cache_dir: str | None = None):
        settings = get_settings()
        self.cache_dir = Path(cache_dir or settings.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Build TTL map from settings (overrides defaults where set)
        self._ttl_map: dict[str, int] = {
            **DEFAULT_TTLS,
            "bootstrap-static": settings.cache_bootstrap_ttl,
            "element-summary": settings.cache_element_ttl,
            "fixtures": settings.cache_fixtures_ttl,
            "live": settings.cache_live_ttl,
        }

    # ------------------------------------------------------------------
    # Public helpers for TTL look-up
    # ------------------------------------------------------------------

    def ttl_for(self, category: str) -> int:
        """Return the TTL in seconds for a named endpoint category.

        Falls back to 3600 s (1 hour) if the category is unknown.
        """
        return self._ttl_map.get(category, 3600)

    # ------------------------------------------------------------------
    # Core CRUD
    # ------------------------------------------------------------------

    def _key_to_path(self, key: str) -> Path:
        """Convert a cache key to a safe file path."""
        safe_key = key.replace("/", "_").replace(":", "_").replace("?", "_")
        return self.cache_dir / f"{safe_key}.json"

    def get(self, key: str) -> Any | None:
        """Retrieve a value from cache, returning None if expired or missing."""
        path = self._key_to_path(key)
        if not path.exists():
            return None

        try:
            with open(path, "r") as f:
                entry = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

        # Check TTL
        expires_at = entry.get("expires_at")
        if expires_at is not None and time.time() > expires_at:
            # Expired -- remove the file
            try:
                path.unlink()
            except OSError:
                pass
            return None

        return entry.get("data")

    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Store a value in cache with the specified TTL in seconds.

        A *ttl* of ``0`` means the entry never expires.
        """
        path = self._key_to_path(key)
        entry = {
            "data": value,
            "created_at": time.time(),
            "expires_at": time.time() + ttl if ttl > 0 else None,
            "ttl": ttl,
        }

        try:
            with open(path, "w") as f:
                json.dump(entry, f)
        except (OSError, TypeError) as exc:
            logger.warning("Cache write failed for %s: %s", key, exc)

    def invalidate(self, key: str) -> bool:
        """Remove a specific key from cache. Returns True if removed."""
        path = self._key_to_path(key)
        if path.exists():
            try:
                path.unlink()
                return True
            except OSError:
                return False
        return False

    def invalidate_all(self) -> int:
        """Remove all cached entries. Returns the number of entries removed."""
        count = 0
        for path in self.cache_dir.glob("*.json"):
            try:
                path.unlink()
                count += 1
            except OSError:
                pass
        return count

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns the number removed."""
        count = 0
        now = time.time()
        for path in self.cache_dir.glob("*.json"):
            try:
                with open(path, "r") as f:
                    entry = json.load(f)
                if entry.get("expires_at") and now > entry["expires_at"]:
                    path.unlink()
                    count += 1
            except (json.JSONDecodeError, OSError):
                pass
        return count

    def stats(self) -> dict:
        """Return cache statistics."""
        total = 0
        expired = 0
        valid = 0
        total_size = 0
        now = time.time()

        for path in self.cache_dir.glob("*.json"):
            total += 1
            total_size += path.stat().st_size
            try:
                with open(path, "r") as f:
                    entry = json.load(f)
                if entry.get("expires_at") and now > entry["expires_at"]:
                    expired += 1
                else:
                    valid += 1
            except (json.JSONDecodeError, OSError):
                expired += 1

        return {
            "total_entries": total,
            "valid_entries": valid,
            "expired_entries": expired,
            "total_size_bytes": total_size,
            "cache_dir": str(self.cache_dir),
        }
