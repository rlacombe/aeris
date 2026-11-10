"""Host-agnostic instructions supplied with the AERIS skill."""

from __future__ import annotations

from pathlib import Path


def skill_path() -> Path:
    """Return the portable skill path for a source checkout or package install."""
    repository_skill = Path(__file__).resolve().parents[2] / "skills" / "aeris" / "SKILL.md"
    if repository_skill.exists():
        return repository_skill
    return Path(__file__).with_name("skill.md")


def load_instructions() -> str:
    """Load the skill body, omitting its YAML front matter when present."""
    content = skill_path().read_text(encoding="utf-8")
    if content.startswith("---"):
        _, _, content = content.split("---", 2)
    return content.strip()


def initial_prompt(host_name: str | None = None) -> str:
    """Return a short opening instruction for an interactive AERIS session."""
    host_context = f" through {host_name}" if host_name else ""
    return f"""You are starting an AERIS environmental-health research session{host_context}.
The AERIS MCP tools are available. Follow the AERIS instructions supplied in
your system context. Begin by establishing the study question and inspecting
the available study data; do not run exposure estimation until the researcher
    has approved the pollutant, spatial assignment, time window, and coverage
    policy."""


def host_prompt(request: str) -> str:
    """Combine portable workflow instructions with a session-specific request."""
    return f"{load_instructions()}\n\n## Session request\n{request}"
