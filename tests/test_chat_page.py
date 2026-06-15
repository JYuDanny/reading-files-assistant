import pytest


@pytest.mark.asyncio
async def test_chat_page_returns_html(client):
    resp = await client.get("/chat/abc123")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_chat_page_contains_session_id(client):
    resp = await client.get("/chat/test123")
    assert "test123" in resp.text
