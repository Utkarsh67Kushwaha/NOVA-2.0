"""
Unit & Integration Tests for NOVA 2.0 Smart Voice Notes & Scratchpad Feature
Tests NoteManager persistence, NoteTool safe execution, intent classification,
and REST/voice dispatcher flows.
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile

from backend.app.main import app
from backend.app.notes.note_manager import NoteManager
from backend.app.notes.note_model import NoteItem
from backend.app.services.intent_service import intent_service
from backend.app.tools import default_registry

client = TestClient(app)


@pytest.fixture
def temp_note_manager(tmp_path):
    """Provides a fresh isolated NoteManager instance for unit testing."""
    test_file = tmp_path / "test_notes.json"
    manager = NoteManager(storage_path=test_file)
    return manager


def test_note_manager_crud(temp_note_manager):
    """Verify create, list, latest, delete, and clear operations."""
    # 1. Initially empty
    assert len(temp_note_manager.list_notes()) == 0
    assert temp_note_manager.get_latest_note() is None

    # 2. Create notes
    note1 = temp_note_manager.create_note("Call Utkarsh at 6pm", title="Call Utkarsh")
    assert note1.id is not None
    assert note1.title == "Call Utkarsh"
    assert note1.content == "Call Utkarsh at 6pm"

    note2 = temp_note_manager.create_note("Prepare slide deck for architecture review")
    # Title auto-generated from first words
    assert "Prepare slide deck" in note2.title

    # 3. List notes (most recent first)
    all_notes = temp_note_manager.list_notes()
    assert len(all_notes) == 2
    assert all_notes[0].id == note2.id

    # 4. Get latest note
    latest = temp_note_manager.get_latest_note()
    assert latest.id == note2.id

    # 5. Delete single note
    deleted = temp_note_manager.delete_note(note1.id)
    assert deleted is True
    assert len(temp_note_manager.list_notes()) == 1

    # 6. Clear all notes
    count = temp_note_manager.clear_all_notes()
    assert count == 1
    assert len(temp_note_manager.list_notes()) == 0


def test_note_tool_in_registry():
    """Verify note_tool is registered in Safe Tools Framework."""
    tool = default_registry.get_tool("note_tool")
    assert tool is not None
    assert tool.category == "desktop"

    # Execute note creation
    res = default_registry.execute("note_tool", {"action": "create", "content": "Test safe tool note"})
    assert res.success is True
    assert "Note saved" in res.output

    # Execute note listing
    res_list = default_registry.execute("note_tool", {"action": "list"})
    assert res_list.success is True
    assert "note(s) saved" in res_list.output

    # Execute read latest
    res_latest = default_registry.execute("note_tool", {"action": "read_latest"})
    assert res_latest.success is True
    assert "Latest note" in res_latest.output


@pytest.mark.parametrize(
    "cmd,expected_action",
    [
        ("note likho: kal 4 baje meeting hai", "create"),
        ("take a note buy milk on way home", "create"),
        ("ek note banao project submit karna hai", "create"),
        ("show my notes", "list"),
        ("notes dikhao", "list"),
        ("read my notes", "list"),
        ("read latest note", "read_latest"),
        ("aakhri note kya tha", "read_latest"),
        ("clear notes", "clear"),
        ("notes saaf karo", "clear"),
        ("notes notepad me kholo", "open_notepad"),
    ],
)
def test_voice_note_intent_rules(cmd, expected_action):
    """Verify natural voice note commands classify to NOTE_ACTION with correct sub-action."""
    res = intent_service.predict(cmd)
    assert res["intent"] == "NOTE_ACTION", f"Failed for {cmd}: got {res['intent']}"
    assert res["entities"].get("action") == expected_action


def test_api_notes_crud_endpoints():
    """Verify /api/notes REST endpoints."""
    # 1. Create note via API
    res_create = client.post("/api/notes", json={"content": "REST API Test Note", "title": "API Note"})
    assert res_create.status_code == 200
    data = res_create.json()
    assert data["status"] == "success"
    note_id = data["note"]["id"]

    # 2. List notes via API
    res_list = client.get("/api/notes")
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert list_data["status"] == "success"
    assert list_data["count"] >= 1

    # 3. Delete note via API
    res_del = client.delete(f"/api/notes/{note_id}")
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "success"


def test_command_voice_note_flow():
    """Verify /api/command end-to-end routing for voice note creation and query."""
    res = client.post("/api/command", json={"text": "note likho kal subah 10 baje gym jana hai"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "NOTE_ACTION"
    assert data["executed_tool"] == "note_tool"
    assert "Note saved" in data["live_response"]


def test_document_and_code_analysis_routing():
    """Verify DOCUMENT_ANALYSIS and CODE_ANALYSIS route to AI Brain with live intelligent responses."""
    # Document analysis query
    res_doc = client.post("/api/command", json={"text": "is document ki summary bana do"})
    assert res_doc.status_code == 200
    data_doc = res_doc.json()
    assert data_doc["intent"] == "DOCUMENT_ANALYSIS"
    assert data_doc["executed_tool"] == "gemini_service"
    assert len(data_doc["live_response"]) > 10

    # Code analysis query
    res_code = client.post("/api/command", json={"text": "review this python code for bugs"})
    assert res_code.status_code == 200
    data_code = res_code.json()
    assert data_code["intent"] == "CODE_ANALYSIS"
    assert data_code["executed_tool"] == "gemini_service"
    assert len(data_code["live_response"]) > 10
