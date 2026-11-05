"""Unit tests for NOVA Reminders & Alarms System."""

import time
import pytest
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.reminders.time_parser import parse_time_expression
from backend.app.reminders.scheduler import reminder_scheduler
from backend.app.tools import default_registry

client = TestClient(app)


def test_time_parser_relative():
    # Seconds
    secs, title, expr = parse_time_expression("remind me to drink water in 10 seconds")
    assert secs == 10
    assert "drink water" in title.lower()

    # Minutes
    secs, title, expr = parse_time_expression("5 minute baad meeting attend karna hai")
    assert secs == 300
    assert "meeting" in title.lower()

    # Hours
    secs, title, expr = parse_time_expression("2 hours me break lena hai")
    assert secs == 7200
    assert "break" in title.lower()


def test_time_parser_colloquial_hinglish():
    # Aadha ghanta (30 mins)
    secs, title, expr = parse_time_expression("aadha ghanta baad walk pe jana hai")
    assert secs == 1800
    assert "walk" in title.lower()

    # Ek ghanta (60 mins)
    secs, title, expr = parse_time_expression("1 ghanta baad code review karna hai")
    assert secs == 3600
    assert "code review" in title.lower()


def test_reminder_scheduler_crud():
    # Create reminder
    item = reminder_scheduler.create_reminder(
        title="Test Water Break",
        due_seconds=30,
        source="TEST",
    )
    assert item.title == "Test Water Break"
    assert item.status == "PENDING"
    assert item.id is not None

    # Get active
    active = reminder_scheduler.get_active_reminders()
    assert any(r.id == item.id for r in active)

    # Cancel reminder
    cancelled = reminder_scheduler.cancel_reminder(item.id)
    assert cancelled is True

    # Delete reminder
    deleted = reminder_scheduler.delete_reminder(item.id)
    assert deleted is True


def test_safe_tools_reminder():
    # SetReminderTool
    res = default_registry.execute("set_reminder", {
        "title": "Drink Coffee",
        "due_seconds": 60,
    })
    assert res.success is True
    assert "Reminder scheduled" in res.output
    assert res.verification.verified is True
    rem_id = res.data["id"]

    # ListRemindersTool
    list_res = default_registry.execute("list_reminders", {"active_only": True})
    assert list_res.success is True
    assert list_res.verification.verified is True
    assert any(r["id"] == rem_id for r in list_res.data["reminders"])

    # Clean up
    reminder_scheduler.delete_reminder(rem_id)


def test_api_reminder_endpoints():
    # POST /api/reminders
    create_res = client.post("/api/reminders", json={
        "title": "API Test Reminder",
        "due_seconds": 120,
    })
    assert create_res.status_code == 200
    data = create_res.json()
    assert data["status"] == "success"
    rem_id = data["reminder"]["id"]

    # GET /api/reminders
    get_res = client.get("/api/reminders")
    assert get_res.status_code == 200
    reminders = get_res.json()["reminders"]
    assert any(r["id"] == rem_id for r in reminders)

    # DELETE /api/reminders/{id}
    del_res = client.delete(f"/api/reminders/{rem_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True


def test_command_reminder_flow():
    # Test natural language command routing to REMINDER
    res = client.post("/api/command", json={"text": "remind me to submit report in 5 minutes"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "REMINDER"
    assert data["executed_tool"] == "set_reminder"
    assert "Reminder scheduled" in data["live_response"]
    assert data["tool_result"]["success"] is True

    # Clean up test created reminder
    created_id = data["tool_result"]["data"]["id"]
    reminder_scheduler.delete_reminder(created_id)
