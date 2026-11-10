"""Tests for host command construction without launching an interactive CLI."""

from __future__ import annotations

import json

from aeris.agent.instructions import host_prompt
from aeris.agent.launcher import (
    add_antigravity_mcp,
    add_gemini_mcp,
    antigravity_config_path,
    build_antigravity_command,
    build_codex_command,
    build_gemini_command,
    build_parser,
    create_claude_config,
    main,
    restore_gemini_settings,
    restore_antigravity_config,
    welcome_message,
)


def test_codex_command_configures_ephemeral_aeris_mcp(tmp_path):
    command = build_codex_command(tmp_path, "start a study")

    assert command[0] == "codex"
    assert "mcp_servers.aeris.command" in command[2]
    assert "mcp_servers.aeris.args" in command[4]
    assert command[-1] == "start a study"


def test_claude_configuration_contains_aeris_stdio_server(tmp_path):
    config_path = create_claude_config(tmp_path)
    config = json.loads(config_path.read_text())

    assert config["mcpServers"]["aeris"]["args"] == ["-m", "aeris.mcp.server"]


def test_gemini_settings_are_restored_after_session(tmp_path):
    settings_path = tmp_path / ".gemini" / "settings.json"
    settings_path.parent.mkdir()
    original = b'{"general": {"vimMode": true}}\n'
    settings_path.write_bytes(original)

    saved = add_gemini_mcp(settings_path)
    assert json.loads(settings_path.read_text())["mcpServers"]["aeris"]["command"]

    restore_gemini_settings(settings_path, saved)
    assert settings_path.read_bytes() == original


def test_gemini_command_is_interactive_and_limits_mcp_server():
    command = build_gemini_command("start a study")

    assert command == [
        "gemini",
        "--prompt-interactive",
        "start a study",
        "--allowed-mcp-server-names",
        "aeris",
    ]


def test_host_prompt_includes_scientific_workflow_and_session_request():
    prompt = host_prompt("Assess PM2.5 for this cohort.")

    assert "AERIS exposure workflow" in prompt
    assert "## Session request" in prompt
    assert prompt.endswith("Assess PM2.5 for this cohort.")


def test_antigravity_configuration_is_restored_after_session(tmp_path):
    config_path = antigravity_config_path(tmp_path)
    config_path.parent.mkdir()
    original = b'{"mcpServers": {"existing": {"command": "example"}}}\n'
    config_path.write_bytes(original)

    saved = add_antigravity_mcp(config_path)
    config = json.loads(config_path.read_text())
    assert config["mcpServers"]["aeris"]["args"] == ["-m", "aeris.mcp.server"]
    assert "existing" in config["mcpServers"]

    restore_antigravity_config(config_path, saved)
    assert config_path.read_bytes() == original


def test_antigravity_command_uses_agy_interactive_prompt():
    command = build_antigravity_command("start a study")

    assert command == ["agy", "--prompt-interactive", "start a study"]


def test_welcome_message_names_host_and_workspace(tmp_path):
    message = welcome_message("claude", tmp_path)

    assert "Claude Code" in message
    assert str(tmp_path) in message
    assert "cohort file" in message


def test_exposure_subcommand_delegates_to_exposure_cli(monkeypatch):
    called = []

    monkeypatch.setattr("aeris.exposure.cli.main_cli", lambda: called.append(True))
    main(["exposure", "--help"])

    assert called == [True]
