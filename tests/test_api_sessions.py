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
async def test_create_session_empty_body(client):
    resp = await client.post("/api/sessions", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_session_with_image(client):
    resp = await client.post("/api/sessions", json={
        "image": "data:image/png;base64,abc123"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert "chat_url" in data
    assert data["chat_url"].endswith(f"/chat/{data['session_id']}")


@pytest.mark.asyncio
async def test_create_session_no_image_field(client):
    resp = await client.post("/api/sessions", json={"foo": "bar"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_send_message_to_existing_session(client):
    create_resp = await client.post("/api/sessions", json={
        "image": "data:image/png;base64,abc"
    })
    sid = create_resp.json()["session_id"]

    resp = await client.post(f"/api/sessions/{sid}/messages", json={
        "content": "这是什么？"
    })
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_send_message_to_nonexistent_session(client):
    resp = await client.post("/api/sessions/notexist/messages", json={
        "content": "hello"
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_send_message_empty_content(client):
    create_resp = await client.post("/api/sessions", json={
        "image": "data:image/png;base64,abc"
    })
    sid = create_resp.json()["session_id"]

    resp = await client.post(f"/api/sessions/{sid}/messages", json={
        "content": ""
    })
    assert resp.status_code == 422
