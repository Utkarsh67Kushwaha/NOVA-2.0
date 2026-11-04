import pytest
from starlette.testclient import TestClient
from backend.app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_check(client):
    """Verify /health returns 200 and healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "uptime_seconds" in data


def test_system_status(client):
    """Verify /api/status returns valid system and resource metrics."""
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "system" in data
    assert "resources" in data
    assert "cpu_percent" in data["resources"]
    assert "ram_total_gb" in data["resources"]
    assert data["resources"]["ram_total_gb"] > 0
