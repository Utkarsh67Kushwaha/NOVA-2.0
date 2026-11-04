import pytest
from starlette.testclient import TestClient
from backend.app.main import app
from backend.app.services.intent_service import intent_service


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_intent_service_is_ready():
    """Verify ML model bundle is loaded and operational."""
    assert intent_service.is_ready() is True
    assert intent_service.model is not None
    assert intent_service.vectorizer is not None
    assert len(intent_service.bundle["intents"]) == 8


@pytest.mark.parametrize(
    "query,expected_intent",
    [
        ("open chrome browser", "OPEN_APP"),
        ("launch visual studio code", "OPEN_APP"),
        ("play some lofi music", "PLAY_MUSIC"),
        ("pause the song", "PLAY_MUSIC"),
        ("find resume.pdf in downloads", "FILE_SEARCH"),
        ("search for budget excel sheet", "FILE_SEARCH"),
        ("search weather in mumbai on google", "BROWSER_ACTION"),
        ("how much ram is used right now", "SYSTEM_INFO"),
        ("what is my battery percentage", "SYSTEM_INFO"),
        ("remind me to drink water at 5pm", "REMINDER"),
        ("summarize this uploaded pdf report", "DOCUMENT_ANALYSIS"),
        ("review this python code for bugs", "CODE_ANALYSIS"),
    ],
)
def test_english_command_classification(query, expected_intent):
    """Test accuracy on English desktop commands."""
    res = intent_service.predict(query)
    assert res["raw_intent"] == expected_intent
    assert res["confidence"] >= 0.5


@pytest.mark.parametrize(
    "query,expected_intent",
    [
        ("chrome kholo please", "OPEN_APP"),
        ("vscode start karo", "OPEN_APP"),
        ("arijit singh ke gaane chalao", "PLAY_MUSIC"),
        ("lofi gana bajao", "PLAY_MUSIC"),
        ("downloads me marksheet pdf dhoondo", "FILE_SEARCH"),
        ("youtube par ai tutorial search karo", "BROWSER_ACTION"),
        ("battery kitne percent bachi hai", "SYSTEM_INFO"),
        ("ram kitna khali hai", "SYSTEM_INFO"),
        ("shaam ko 5 baje paani peene ka reminder lagao", "REMINDER"),
        ("is document ki summary bana do", "DOCUMENT_ANALYSIS"),
        ("is python function me bug dhoond kar fix karo", "CODE_ANALYSIS"),
    ],
)
def test_hinglish_command_classification(query, expected_intent):
    """Test accuracy on authentic Hinglish desktop commands."""
    res = intent_service.predict(query)
    assert res["raw_intent"] == expected_intent
    assert res["confidence"] >= 0.45


def test_unknown_intent_thresholding():
    """Verify confidence thresholding correctly marks gibberish as UNKNOWN_INTENT."""
    gibberish = "quantum gravity non-euclidean manifold synthesis experiment"
    res = intent_service.predict(gibberish)
    assert res["intent"] == "UNKNOWN_INTENT"
    assert res["needs_clarification"] is True
    assert "clarification_message" in res


def test_api_command_endpoint(client):
    """Verify POST /api/command endpoint returns valid prediction and latency."""
    response = client.post("/api/command", json={"text": "open chrome browser"})
    assert response.status_code == 200
    data = response.json()
    assert data["raw_intent"] == "OPEN_APP"
    assert "confidence" in data
    assert "latency_ms" in data
    assert data["latency_ms"] < 25.0  # Ultra-fast local ML inference


def test_api_ml_report_endpoint(client):
    """Verify GET /api/ml/report returns comprehensive benchmark comparisons."""
    response = client.get("/api/ml/report")
    assert response.status_code == 200
    data = response.json()
    assert "selected_model" in data
    assert "model_comparisons" in data
    assert len(data["model_comparisons"]) >= 3
