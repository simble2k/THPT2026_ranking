import pytest
from httpx import AsyncClient

from backend.main import app

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_candidate_not_found():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/candidate/99999999")
    assert response.status_code == 404
