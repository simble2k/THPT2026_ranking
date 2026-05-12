from unittest.mock import AsyncMock, MagicMock

import pytest
from api.index import app
from core.database import get_db
from core.redis_client import get_redis
from httpx import ASGITransport, AsyncClient


# Mock Database Dependency
async def override_get_db():
    mock_session = AsyncMock()
    # Mock result for test_candidate_not_found
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_session.execute.return_value = mock_result
    yield mock_session


# Mock Redis Dependency
async def override_get_redis():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.hget.return_value = None
    return mock_redis


@pytest.mark.asyncio
async def test_health_check():
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        response = await ac.get("/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_candidate_not_found():
    # Override dependencies for this test
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        response = await ac.get("/api/candidate/99999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Candidate not found"}

    # Clear overrides
    app.dependency_overrides.clear()
