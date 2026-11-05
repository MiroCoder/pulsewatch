from app.main import app
from fastapi.testclient import TestClient
import pytest

client = TestClient(app)

def test_create_monitor():
    response = client.post("/monitors", json = {"name": "Google", "url" : "https://google.com", "interval_seconds" : 60})
    data = response.json()

    assert response.status_code == 201
    assert data["name"] == "Google"
    assert data["url"] == "https://google.com/"
    assert data["interval_seconds"] == 60
    assert isinstance(data["id"],int)

def test_get_monitor_by_id():
    response = client.post("/monitors", json = {"name": "GitHub", "url" : "https://github.com", "interval_seconds" : 50})
    monitor_id = response.json()["id"]

    response2 = client.get(f"/monitors/{monitor_id}")
    data = response2.json()
    assert response2.status_code == 200
    assert isinstance(data["id"], int)
    assert data["name"] == "GitHub"
    assert data["id"] == monitor_id

def test_update_monitor():
    response = client.post("/monitors", json = {"name": "GitHub", "url" : "https://github.com", "interval_seconds" : 50})
    monitor_id = response.json()["id"]

    response2 = client.patch(f"/monitors/{monitor_id}", json={
        "name": "Updated GitHub",
        "interval_seconds": 120
    })

    data = response2.json()
    assert response2.status_code == 200

    response3 = client.get(f"/monitors/{monitor_id}")
    data2 = response3.json()
    assert data2["name"] == "Updated GitHub"
    assert data2["interval_seconds"] == 120
    assert data2["url"] == "https://github.com/"

def test_delete_monitor():
    response = client.post("/monitors", json={"name": "GitHub", "url": "https://github.com", "interval_seconds": 50})
    monitor_id = response.json()["id"]

    response2 = client.delete(f"/monitors/{monitor_id}")

    assert response2.status_code == 204

    response3 = client.get(f"/monitors/{monitor_id}")
    assert response3.status_code == 404

@pytest.mark.parametrize("interval", [-5, 0, -100, "invalid"])
def test_post_validation(interval):
    response = client.post("/monitors", json={"name": "Invalid", "url": "https://example.com", "interval_seconds": interval})
    assert response.status_code == 422

async def fake_check_url(url):
    return {
        "status_code": 200,
        "latency_ms": 42.5,
        "error": None
    }

def test_check_monitor(monkeypatch):
    response = client.post("/monitors", json={"name": "GitHub", "url": "https://github.com", "interval_seconds": 50})
    monitor_id = response.json()["id"]
    monkeypatch.setattr("app.main.check_url", fake_check_url)

    response2 = client.post(f"/monitors/{monitor_id}/check")
    data = response2.json()

    assert response2.status_code == 200
    assert data["status_code"] == 200
    assert data["latency_ms"] == 42.5
    assert isinstance(data["check_id"], int)

    history = client.get(f"/monitors/{monitor_id}/history")
    history_data = history.json()

    assert history.status_code == 200
    assert len(history_data) == 1
    assert history_data[0]["status_code"] == 200

def test_patch_idempotency():
    response = client.post("/monitors", json={"name": "GitHub", "url": "https://github.com", "interval_seconds": 50})
    monitor_id = response.json()["id"]

    response2 = client.patch(f"/monitors/{monitor_id}", json={"is_active": False})
    response3 = client.patch(f"/monitors/{monitor_id}", json={"is_active": False})
    response4 = client.get(f"/monitors/{monitor_id}")
    data = response4.json()

    assert response2.status_code == 200
    assert response3.status_code == 200
    assert data["is_active"] == False