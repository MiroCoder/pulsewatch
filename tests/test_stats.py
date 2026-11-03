from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_unknown_route():
    response = client.get("/nonexistent")
    assert response.status_code == 404