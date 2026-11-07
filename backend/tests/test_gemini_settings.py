"""
Unit tests for Gemini 3.8 Flash model selection and settings API
"""

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.gemini_service import gemini_service, DEFAULT_MODEL, AVAILABLE_MODELS


def test_gemini_default_model():
    assert gemini_service.model == "gemini-3.8-flash"
    assert "gemini-3.8-flash" in AVAILABLE_MODELS


def test_gemini_model_switching():
    assert gemini_service.set_model("gemini-3.5-flash-lite") is True
    assert gemini_service.model == "gemini-3.5-flash-lite"

    # Invalid model rejection
    assert gemini_service.set_model("invalid-model-xyz") is False

    # Switch back to 3.8 Flash
    assert gemini_service.set_model("gemini-3.8-flash") is True
    assert gemini_service.model == "gemini-3.8-flash"


def test_gemini_settings_api():
    client = TestClient(app)

    # 1. Get settings
    res = client.get("/api/settings/gemini")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["model"] == "gemini-3.8-flash"
    assert "gemini-3.8-flash" in data["available_models"]

    # 2. Update model via API
    post_res = client.post("/api/settings/gemini", json={"model": "gemini-3.5-flash-lite"})
    assert post_res.status_code == 200
    p_data = post_res.json()
    assert p_data["status"] == "success"
    assert p_data["model"] == "gemini-3.5-flash-lite"

    # Reset back to 3.8 flash
    gemini_service.set_model("gemini-3.8-flash")
