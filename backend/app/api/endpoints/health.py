"""Health check endpoints.

Provides liveness, readiness, and detailed health probes for the
FPL Team Picker backend.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Liveness / readiness probe.

    Returns:
        A dict containing application status, name, version, and UTC timestamp.
    """
    settings = get_settings()
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/ready")
async def readiness_check() -> dict[str, Any]:
    """Readiness check -- verifies external dependencies are reachable.

    Returns:
        A dict with overall status, per-dependency checks, and UTC timestamp.
    """
    checks: dict[str, str] = {}

    # Check FPL API reachability
    import httpx

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{get_settings().fpl_base_url}/bootstrap-static/"
            )
            checks["fpl_api"] = "ok" if resp.status_code == 200 else "degraded"
    except Exception:
        checks["fpl_api"] = "unreachable"

    overall = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
    return {
        "status": overall,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/detailed")
async def detailed_health_check() -> dict[str, Any]:
    """Detailed health check for all backend dependencies.

    Checks:
    - FPL API reachability via HEAD request
    - Cache directory is writable
    - PuLP solver is available and importable
    - Python version information

    Returns:
        A dict with overall status, individual dependency statuses,
        Python version, and UTC timestamp.
    """
    settings = get_settings()
    checks: dict[str, dict[str, Any]] = {}

    # 1. FPL API reachability (HEAD request)
    import httpx

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.head(
                f"{settings.fpl_base_url}/bootstrap-static/"
            )
            checks["fpl_api"] = {
                "status": "ok" if resp.status_code == 200 else "degraded",
                "status_code": resp.status_code,
            }
    except Exception as exc:
        checks["fpl_api"] = {
            "status": "unreachable",
            "error": str(exc),
        }

    # 2. Cache directory writable
    cache_dir = settings.cache_dir
    try:
        os.makedirs(cache_dir, exist_ok=True)
        test_file = os.path.join(cache_dir, ".health_check_test")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        checks["cache_directory"] = {
            "status": "ok",
            "path": cache_dir,
        }
    except Exception as exc:
        checks["cache_directory"] = {
            "status": "error",
            "path": cache_dir,
            "error": str(exc),
        }

    # 3. PuLP solver available
    try:
        import pulp

        pulp.PULP_CBC_CMD(msg=0)
        checks["pulp_solver"] = {
            "status": "ok",
            "solver": "PULP_CBC_CMD",
            "pulp_version": pulp.VERSION,
        }
    except Exception as exc:
        checks["pulp_solver"] = {
            "status": "error",
            "error": str(exc),
        }

    # 4. Python version
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    checks["python"] = {
        "status": "ok",
        "version": python_version,
        "implementation": sys.implementation.name,
    }

    # Overall status: healthy only if all checks pass
    statuses = [c.get("status", "unknown") for c in checks.values()]
    if all(s == "ok" for s in statuses):
        overall = "healthy"
    elif any(s == "error" or s == "unreachable" for s in statuses):
        overall = "unhealthy"
    else:
        overall = "degraded"

    return {
        "status": overall,
        "checks": checks,
        "app": settings.app_name,
        "version": settings.app_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
