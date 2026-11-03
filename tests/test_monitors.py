from app.main import app
from fastapi.testclient import TestClient

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

def test_post_validation():
    response = client.post("/monitors", json={"name": "Invalid", "url": "https://example.com", "interval_seconds": -5})
    assert response.status_code == 422