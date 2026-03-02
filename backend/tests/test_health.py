"""Tests for the health check endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_health_check():
    """Test that the health endpoint returns a healthy status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == "FPL Team Picker"
    assert "version" in data
    assert "timestamp" in data


@pytest.mark.anyio
async def test_health_check_version():
    """Test that health endpoint returns the correct version."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    data = response.json()
    assert data["version"] == "0.1.0"
