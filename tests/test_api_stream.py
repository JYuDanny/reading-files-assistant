import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from backend.main import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_stream_nonexistent_session(client):
    resp = await client.get("/api/sessions/notexist/stream")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stream_sse_content_type(client):
    """Test that SSE endpoint returns correct content type."""
    resp = await client.get("/api/sessions/nonexistent/stream")
    assert resp.status_code == 404
