"""Launch AERIS through a local CLI coding agent.

The launcher owns only host setup: it gives a CLI agent the AERIS skill and a
stdio MCP configuration. Scientific state and tool execution stay in the MCP
server, so no model-provider SDK is part of the AERIS runtime.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path

from .instructions import host_prompt, initial_prompt, load_instructions, skill_path

HOST_NAMES = {
    "codex": "Codex CLI",
    "claude": "Claude Code",
    "gemini": "Gemini CLI",
    "antigravity": "Antigravity CLI",
    "custom": "your MCP host",
}


def welcome_message(agent: str, workspace: Path, mode: str = "interactive") -> str:
    """Describe the configured research session before launching the host."""
    host_name = HOST_NAMES[agent]
    return (
        f"AERIS is ready in {host_name}.\n"
        "Start with a study question or a cohort file. AERIS will help define "
        "the exposure, inspect coverage, and create a reviewable analysis record.\n"
        f"Execution mode: {mode}\nWorkspace: {workspace}"
    )


def mcp_spec() -> dict[str, object]:
    """Return a portable stdio MCP declaration for the current environment."""
    return {"command": sys.executable, "args": ["-m", "aeris.mcp.server"]}


def build_codex_command(workspace: Path, prompt: str) -> list[str]:
    """Build an ephemeral Codex CLI configuration without changing user config."""
    spec = mcp_spec()
    return [
        "codex",
        "-c",
        f"mcp_servers.aeris.command={json.dumps(spec['command'])}",
        "-c",
        f"mcp_servers.aeris.args={json.dumps(spec['args'])}",
        "-C",
        str(workspace),
        prompt,
    ]


def create_claude_config(directory: Path) -> Path:
    """Write the short-lived Claude Code MCP configuration."""
    path = directory / "aeris-mcp.json"
    path.write_text(json.dumps({"mcpServers": {"aeris": mcp_spec()}}), encoding="utf-8")
    return path


def build_claude_command(workspace: Path, config_path: Path, prompt: str) -> list[str]:
    """Build a Claude Code command with only the AERIS MCP server enabled."""
    return [
        "claude",
        "--mcp-config",
        str(config_path),
        "--strict-mcp-config",
        "--append-system-prompt",
        load_instructions(),
        prompt,
    ]


def gemini_settings_path(workspace: Path) -> Path:
    """Return Gemini CLI's project settings path for a study workspace."""
    return workspace / ".gemini" / "settings.json"


def add_gemini_mcp(settings_path: Path) -> bytes | None:
    """Temporarily add the AERIS MCP server to Gemini's project settings.

    Returns the original file bytes, or ``None`` when the file did not exist,
    so callers can restore the workspace exactly when Gemini exits.
    """
    original = settings_path.read_bytes() if settings_path.exists() else None
    try:
        settings = json.loads(original) if original else {}
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Gemini settings are not valid JSON: {settings_path}: {exc}") from exc
    servers = settings.setdefault("mcpServers", {})
    if "aeris" in servers:
        raise SystemExit(
            f"Gemini workspace already defines an 'aeris' MCP server: {settings_path}. "
            "Remove or rename that entry before launching AERIS."
        )
    servers["aeris"] = mcp_spec()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return original


def restore_gemini_settings(settings_path: Path, original: bytes | None) -> None:
    """Restore settings changed by :func:`add_gemini_mcp`."""
    if original is None:
        settings_path.unlink(missing_ok=True)
        with suppress(OSError):
            settings_path.parent.rmdir()
        return
    settings_path.write_bytes(original)


def build_gemini_command(prompt: str) -> list[str]:
    """Build Gemini CLI's interactive prompt command."""
    return ["gemini", "--prompt-interactive", prompt, "--allowed-mcp-server-names", "aeris"]


def antigravity_config_path(workspace: Path) -> Path:
    """Return Antigravity CLI's workspace MCP configuration path."""
    return workspace / ".agents" / "mcp_config.json"


def add_antigravity_mcp(config_path: Path) -> bytes | None:
    """Temporarily add AERIS to Antigravity's workspace MCP configuration."""
    original = config_path.read_bytes() if config_path.exists() else None
    try:
        config = json.loads(original) if original else {}
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Antigravity MCP configuration is not valid JSON: {config_path}: {exc}"
        ) from exc
    servers = config.setdefault("mcpServers", {})
    if "aeris" in servers:
        raise SystemExit(
            f"Antigravity workspace already defines an 'aeris' MCP server: {config_path}. "
            "Remove or rename that entry before launching AERIS."
        )
    servers["aeris"] = mcp_spec()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return original


def restore_antigravity_config(config_path: Path, original: bytes | None) -> None:
    """Restore Antigravity configuration changed by :func:`add_antigravity_mcp`."""
    if original is None:
        config_path.unlink(missing_ok=True)
        with suppress(OSError):
            config_path.parent.rmdir()
        return
    config_path.write_bytes(original)


def build_antigravity_command(prompt: str) -> list[str]:
    """Build Antigravity CLI's interactive prompt command."""
    return ["agy", "--prompt-interactive", prompt]


def custom_environment() -> dict[str, str]:
    """Expose integration details for a host that the launcher cannot configure."""
    environment = os.environ.copy()
    environment["AERIS_MCP_COMMAND"] = f"{sys.executable} -m aeris.mcp.server"
    environment["AERIS_SKILL_PATH"] = str(skill_path())
    environment["AERIS_INITIAL_PROMPT"] = initial_prompt()
    return environment


def _require_executable(name: str) -> None:
    if shutil.which(name) is None:
        raise SystemExit(
            f"{name!r} was not found on PATH. Install the CLI agent or use "
            "--agent custom --command '<your host command>'."
        )


def _run(command: Sequence[str], workspace: Path, environment: dict[str, str] | None = None) -> int:
    return subprocess.run(command, cwd=workspace, env=environment, check=False).returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Launch a provider-neutral AERIS MCP session in a local CLI agent."
    )
    parser.add_argument(
        "--mode",
        choices=("interactive", "self-driving"),
        default=os.environ.get("AERIS_EXECUTION_MODE", "interactive"),
        help="Approval policy (default: interactive).",
    )
    parser.add_argument(
        "--study-contract",
        type=Path,
        help="Prescribed JSON study contract for controlled self-driving execution.",
    )
    parser.add_argument(
        "--safety-envelope",
        type=Path,
        help="Study-independent limits for an agent-authored self-driving contract.",
    )
    parser.add_argument(
        "--agent",
        choices=("codex", "claude", "gemini", "antigravity", "custom"),
        default=os.environ.get("AERIS_AGENT", "codex"),
        help="CLI host to launch (default: codex; AERIS_AGENT also works).",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(os.environ.get("AERIS_DEFAULT_WORKSPACE", Path.cwd())),
        help="Study workspace provided to the CLI host (default: current directory).",
    )
    parser.add_argument(
        "--command",
        help="Command for --agent custom. AERIS_MCP_COMMAND and AERIS_SKILL_PATH are exported.",
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="Optional initial request for the research session.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Run the requested CLI host or the low-level exposure command."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "exposure":
        from aeris.exposure.cli import main_cli

        sys.argv = [sys.argv[0], *arguments[1:]]
        main_cli()
        return

    args = build_parser().parse_args(arguments)
    workspace = args.workspace.expanduser().resolve()
    if not workspace.is_dir():
        raise SystemExit(f"Workspace does not exist or is not a directory: {workspace}")

    host_name = HOST_NAMES[args.agent]
    environment = os.environ.copy()
    environment["AERIS_EXECUTION_MODE"] = args.mode
    if args.study_contract:
        environment["AERIS_STUDY_CONTRACT"] = str(args.study_contract.expanduser().resolve())
    if args.safety_envelope:
        environment["AERIS_SAFETY_ENVELOPE"] = str(args.safety_envelope.expanduser().resolve())
    if (
        args.mode == "self-driving"
        and "AERIS_STUDY_CONTRACT" not in environment
        and "AERIS_SAFETY_ENVELOPE" not in environment
    ):
        raise SystemExit("--mode self-driving requires --study-contract or --safety-envelope.")
    print(welcome_message(args.agent, workspace, args.mode), flush=True)
    prompt = " ".join(args.prompt).strip() or initial_prompt(host_name)
    if args.agent == "codex":
        _require_executable("codex")
        raise SystemExit(_run(build_codex_command(workspace, host_prompt(prompt)), workspace, environment))

    if args.agent == "claude":
        _require_executable("claude")
        with tempfile.TemporaryDirectory(prefix="aeris-mcp-") as directory:
            config_path = create_claude_config(Path(directory))
            raise SystemExit(_run(build_claude_command(workspace, config_path, prompt), workspace, environment))

    if args.agent == "gemini":
        _require_executable("gemini")
        settings_path = gemini_settings_path(workspace)
        original = add_gemini_mcp(settings_path)
        try:
            raise SystemExit(_run(build_gemini_command(host_prompt(prompt)), workspace, environment))
        finally:
            restore_gemini_settings(settings_path, original)

    if args.agent == "antigravity":
        _require_executable("agy")
        config_path = antigravity_config_path(workspace)
        original = add_antigravity_mcp(config_path)
        try:
            raise SystemExit(_run(build_antigravity_command(host_prompt(prompt)), workspace, environment))
        finally:
            restore_antigravity_config(config_path, original)

    if not args.command:
        raise SystemExit("--agent custom requires --command '<your host command>'.")
    command = shlex.split(args.command)
    if not command:
        raise SystemExit("--command must not be empty.")
    raise SystemExit(_run(command, workspace, custom_environment()))
