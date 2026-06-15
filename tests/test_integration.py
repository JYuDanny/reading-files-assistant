import pytest
from backend.session_manager import session_manager


@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_full_flow_create_and_page(client):
    resp = await client.post("/api/sessions", json={
        "image": "data:image/png;base64,abc"
    })
    assert resp.status_code == 200
    data = resp.json()
    sid = data["session_id"]

    resp = await client.get(f"/chat/{sid}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_session_info_endpoint(client):
    resp = await client.post("/api/sessions", json={
        "image": "data:image/png;base64,abc"
    })
    sid = resp.json()["session_id"]

    resp = await client.get(f"/api/sessions/{sid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == sid
    assert data["has_image"] is True
    assert data["message_count"] == 0


@pytest.mark.asyncio
async def test_session_info_not_found(client):
    resp = await client.get("/api/sessions/nonexistent")
    assert resp.status_code == 404
