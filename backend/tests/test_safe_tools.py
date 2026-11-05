"""
Unit & Integration Tests for NOVA Safe Tools Framework
Verifies tool allowlisting, argument schemas, security sandboxing,
confirmation tokens for high-risk actions, audit logging, and post-action verification.
"""

import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.tools import (
    default_registry,
    audit_logger,
    permissions_manager,
    RiskLevel,
)
from backend.app.tools.file_tools import validate_sandboxed_path


client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_audit_and_permissions():
    """Reset audit entries before each test."""
    audit_logger.clear()
    yield


def test_tool_registry_discovery():
    """Ensure all required safe tools are registered with schemas."""
    tools = default_registry.list_tools()
    tool_names = {t["name"] for t in tools}

    expected_tools = {
        "launch_app",
        "system_status",
        "manage_window",
        "open_url",
        "web_search",
        "list_files",
        "search_files",
        "read_text_file",
        "create_file",
    }
    assert expected_tools.issubset(tool_names)

    # Check categories
    categories = {t["category"] for t in tools}
    assert {"desktop", "browser", "file"}.issubset(categories)


def test_unregistered_tool_rejection():
    """Verify executing an unallowlisted tool is rejected and recorded as BLOCKED."""
    result = default_registry.execute("malicious_shell_execute", {"cmd": "rm -rf /"})
    assert not result.success
    assert "Security rejection" in result.output

    # Check audit log
    entries = audit_logger.get_entries(limit=10)
    assert len(entries) >= 1
    assert entries[0].status == "BLOCKED"
    assert entries[0].tool_name == "malicious_shell_execute"


def test_launch_app_security_rejection():
    """Verify that launching unapproved applications is strictly blocked."""
    result = default_registry.execute("launch_app", {"app_name": "cmd_injection_hack"})
    assert not result.success
    assert "Security rejection" in result.output
    assert "approved allowlist" in result.output


def test_system_status_tool():
    """Verify system status tool returns valid metrics and passes verification."""
    result = default_registry.execute("system_status", {"metric_filter": "all"})
    assert result.success
    assert result.data is not None
    assert "cpu_percent" in result.data
    assert "memory" in result.data
    assert "disk_c" in result.data
    assert result.verification is not None
    assert result.verification.verified


def test_browser_url_security():
    """Verify URL validation blocks dangerous schemes and metadata endpoints."""
    # Disallowed scheme
    res_bad_scheme = default_registry.execute("open_url", {"url": "file:///C:/Windows/System32"})
    assert not res_bad_scheme.success
    assert "Security rejection" in res_bad_scheme.output

    # Disallowed metadata host
    res_bad_host = default_registry.execute("open_url", {"url": "http://169.254.169.254/latest/meta-data"})
    assert not res_bad_host.success
    assert "Security rejection" in res_bad_host.output


def test_file_sandbox_path_traversal():
    """Verify path validator prevents directory traversal outside allowed roots."""
    with pytest.raises(PermissionError):
        validate_sandboxed_path("C:\\Windows\\System32\\cmd.exe")

    with pytest.raises(PermissionError):
        validate_sandboxed_path("../../../../../../../Windows")


def test_list_and_read_files_in_workspace():
    """Test safe file listing and reading within a test directory inside workspace."""
    test_dir = Path.cwd() / "backend" / "tests" / "_test_scratch"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / "test_sample.txt"
    try:
        test_file.write_text("Hello from NOVA safe tools test!", encoding="utf-8")

        # Read file
        read_res = default_registry.execute(
            "read_text_file",
            {"file_path": str(test_file), "max_lines": 10},
        )
        assert read_res.success
        assert "Hello from NOVA" in read_res.data["content"]
        assert read_res.verification.verified
    finally:
        if test_file.exists():
            test_file.unlink()
        if test_dir.exists():
            test_dir.rmdir()


def test_create_file_confirmation_flow():
    """Verify high-risk overwrite requires confirmation token, and validate execution."""
    test_dir = Path.cwd() / "backend" / "tests" / "_test_scratch_conf"
    test_dir.mkdir(parents=True, exist_ok=True)
    target_file = test_dir / "protected_doc.txt"
    try:
        target_file.write_text("Initial original content", encoding="utf-8")

        # Attempt to overwrite without confirmation token
        res1 = default_registry.execute(
            "create_file",
            {"file_path": str(target_file), "content": "New overwriting content"},
        )
        assert not res1.success
        assert res1.requires_confirmation
        assert res1.confirmation_token is not None
        token = res1.confirmation_token

        # Verify original file content was NOT overwritten yet
        assert target_file.read_text(encoding="utf-8") == "Initial original content"

        # Now execute with confirmation token
        res2 = default_registry.execute(
            "create_file",
            {"file_path": str(target_file), "content": "New overwriting content"},
            confirmed_token=token,
        )
        assert res2.success
        assert target_file.read_text(encoding="utf-8") == "New overwriting content"
        assert res2.verification.verified
    finally:
        if target_file.exists():
            target_file.unlink()
        if test_dir.exists():
            test_dir.rmdir()


def test_api_tool_endpoints():
    """Verify FastAPI endpoints for tool listing, execution, and audit trail."""
    # GET /api/tools
    res_list = client.get("/api/tools")
    assert res_list.status_code == 200
    data = res_list.json()
    assert data["status"] == "success"
    assert data["count"] >= 9

    # POST /api/tools/execute (system_status)
    res_exec = client.post(
        "/api/tools/execute",
        json={"tool_name": "system_status", "args": {"metric_filter": "cpu"}},
    )
    assert res_exec.status_code == 200
    exec_data = res_exec.json()
    assert exec_data["status"] == "success"
    assert "CPU" in exec_data["result"]["output"]

    # GET /api/tools/audit
    res_audit = client.get("/api/tools/audit")
    assert res_audit.status_code == 200
    audit_data = res_audit.json()
    assert audit_data["count"] >= 1
    assert audit_data["entries"][0]["tool_name"] == "system_status"


def test_api_command_intent_tool_routing():
    """Verify POST /api/command triggers safe tools directly."""
    # Test SYSTEM_INFO intent routing to system_status tool
    res = client.post("/api/command", json={"text": "battery kitne percent hai"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "SYSTEM_INFO"
    assert data["executed_tool"] == "system_status"
    assert data["tool_result"]["success"] is True
    assert "Battery" in data["live_response"]



def test_system_control_hardware_tool():
    """Verify system_control safe tool executes volume, brightness and status actions."""
    # Test status
    res = client.post(
        "/api/tools/execute",
        json={"tool_name": "system_control", "args": {"action": "status"}},
    )
    assert res.status_code == 200
    data = res.json()["result"]
    assert data["success"] is True
    assert "Volume" in data["output"]

    # Test set_volume
    res_vol = client.post(
        "/api/tools/execute",
        json={"tool_name": "system_control", "args": {"action": "set_volume", "value": 75}},
    )
    assert res_vol.status_code == 200
    assert "75%" in res_vol.json()["result"]["output"]

    # Test command routing for volume
    res_cmd = client.post("/api/command", json={"text": "volume 60 percent karo"})
    assert res_cmd.status_code == 200
    cmd_data = res_cmd.json()
    assert cmd_data["intent"] == "SYSTEM_CONTROL"
    assert cmd_data["executed_tool"] == "system_control"
    assert "60%" in cmd_data["live_response"]


def test_take_screenshot_tool():
    """Verify take_screenshot captures real desktop image and verifies file on disk."""
    res = default_registry.execute("take_screenshot", {"open_snipping_tool": False})
    assert res.success is True
    assert res.verification.verified is True
    path_str = res.data.get("screenshot_path")
    assert path_str is not None
    p = Path(path_str)
    assert p.exists()
    assert p.stat().st_size > 1000

    # Clean up generated screenshot
    try:
        p.unlink()
    except Exception:
        pass

    # Test /api/command routing for Hinglish screenshot
    res_cmd = client.post("/api/command", json={"text": "screenshot le lo"})
    assert res_cmd.status_code == 200
    cmd_data = res_cmd.json()
    assert cmd_data["executed_tool"] == "take_screenshot"
    assert cmd_data["tool_result"]["success"] is True
    sc_path = cmd_data["tool_result"]["data"].get("screenshot_path")
    if sc_path and Path(sc_path).exists():
        try:
            Path(sc_path).unlink()
        except Exception:
            pass


def test_close_app_tool():
    """Verify close_app tool allowlist enforcement and safe execution."""
    # Test unallowlisted app rejection
    res_bad = default_registry.execute("close_app", {"app_name": "malicious_virus.exe"})
    assert res_bad.success is False
    assert "not in the security allowlist" in res_bad.output

    # Test allowlisted app execution (notepad)
    res_good = default_registry.execute("close_app", {"app_name": "notepad"})
    assert res_good.success is True

    # Test /api/command routing
    res_cmd = client.post("/api/command", json={"text": "close notepad"})
    assert res_cmd.status_code == 200
    cmd_data = res_cmd.json()
    assert cmd_data["intent"] == "CLOSE_APP"
    assert cmd_data["executed_tool"] == "close_app"


def test_clipboard_tool():
    """Verify clipboard_tool can set, read, and clear clipboard contents safely."""
    # Set text
    res_set = default_registry.execute("clipboard_tool", {"action": "set", "content": "NOVA 2.0 Test Clipboard Text"})
    assert res_set.success is True

    # Read text
    res_read = default_registry.execute("clipboard_tool", {"action": "read"})
    assert res_read.success is True
    assert "NOVA 2.0" in res_read.output

    # Clear text
    res_clear = default_registry.execute("clipboard_tool", {"action": "clear"})
    assert res_clear.success is True

    # Test /api/command routing
    res_cmd = client.post("/api/command", json={"text": "read clipboard"})
    assert res_cmd.status_code == 200
    cmd_data = res_cmd.json()
    assert cmd_data["intent"] == "CLIPBOARD_ACTION"
    assert cmd_data["executed_tool"] == "clipboard_tool"
