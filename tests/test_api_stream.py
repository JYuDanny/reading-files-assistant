import pytest
from backend.session_manager import session_manager


@pytest.mark.asyncio
async def test_stream_nonexistent_session(client):
    resp = await client.get("/api/sessions/notexist/stream")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stream_returns_404_for_nonexistent(client):
    resp = await client.get("/api/sessions/notexist/stream")
    assert resp.status_code == 404
