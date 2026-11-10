"""A provider-neutral contract for AERIS scientific tools.

This module keeps scientific operations independent of any provider protocol so
an MCP host, Codex, Claude, Gemini, or another harness can use the same tools
and session state.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

from aeris.agent.state import SessionState
from aeris.agent.tools import TOOL_DISPATCH, TOOL_SCHEMAS
from aeris.exposure.recovery import classify_error


@dataclass(frozen=True)
class ToolDefinition:
    """A provider-neutral description of one AERIS operation."""

    name: str
    description: str
    input_schema: dict[str, Any]
    requires_researcher_approval: bool = False


# Filesystem mutation and arbitrary code execution stay outside the public
# scientific tool surface until workspace isolation and approval policy exist.
CORE_TOOL_NAMES = frozenset(
    {
        "load_cohort",
        "plan_exposure",
        "approve_exposure_plan",
        "estimate_exposure",
        "estimate_boundary_exposure",
        "estimate_boundary_exposure_batch",
        "get_exposure_summary",
        "get_raw_data",
        "get_daily_data",
        "compare_metrics",
        "convert_to_aqi",
        "get_accuweather_air_quality",
        "export_results",
        "get_station_info",
        "web_search",
        "record_study_design",
        "lock_exposure_contract",
        "update_research_notebook",
        "get_decision_log",
        "list_artifacts",
        "describe_artifact",
        "sample_artifact",
        "query_artifact",
    }
)
REANALYSIS_TOOL_NAMES = frozenset({
    "lock_reanalysis_invariants", "record_reanalysis_fidelity", "amend_exposure_contract"
})
PUBLIC_TOOL_NAMES = CORE_TOOL_NAMES | REANALYSIS_TOOL_NAMES


def active_tool_names() -> frozenset[str]:
    """Expose reanalysis-only operations only when that profile is active."""
    if os.getenv("AERIS_PROFILE", "exposure") == "reanalysis":
        return PUBLIC_TOOL_NAMES - {"lock_exposure_contract"}
    return CORE_TOOL_NAMES

def tool_definitions() -> list[ToolDefinition]:
    """Return the canonical public tool definitions in stable order."""
    definitions: list[ToolDefinition] = []
    for schema in TOOL_SCHEMAS:
        if schema["name"] not in active_tool_names():
            continue
        definitions.append(
            ToolDefinition(
                name=schema["name"],
                description=schema["description"],
                input_schema=schema["input_schema"],
                requires_researcher_approval=schema["name"]
                in {
                    "record_study_design",
                    "estimate_exposure",
                    "estimate_boundary_exposure",
                    "estimate_boundary_exposure_batch",
                },
            )
        )
    return definitions


def tool_schemas() -> list[dict[str, Any]]:
    """Return JSON-serializable schemas suitable for a host adapter."""
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
            "requires_researcher_approval": tool.requires_researcher_approval,
        }
        for tool in tool_definitions()
    ]


def execute(state: SessionState, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a public tool against one study session.

    Hosts must call ``estimate_exposure`` with ``researcher_approved=True``
    after displaying the intended estimand and configuration to the researcher.
    """
    if name not in active_tool_names():
        return _envelope(state, name, {"error": f"Tool is not part of the public AERIS contract: {name}"})

    try:
        policy = state.execution_policy.authorize(name, arguments)
    except PermissionError as exc:
        return _envelope(state, name, {"error": str(exc), "error_category": "authorization"})

    function = TOOL_DISPATCH.get(name)
    if function is None:
        return _envelope(state, name, {"error": f"Unknown AERIS tool: {name}"})

    try:
        result = function(state=state, **arguments)
        result.setdefault("execution_policy", policy)
        return _envelope(state, name, result)
    except TypeError as exc:
        return _envelope(state, name, {"error": f"Invalid arguments for {name}: {exc}", "error_category": "invalid_input"})
    except Exception as exc:
        return _envelope(state, name, {"error": str(exc), "error_category": classify_error(exc).value})


def _envelope(state: SessionState, name: str, result: dict[str, Any]) -> dict[str, Any]:
    """Add stable, compact execution metadata without breaking legacy fields."""
    result.setdefault("status", "error" if "error" in result else "ok")
    result.setdefault("warnings", [])
    result["contract"] = {
        "tool": name,
        "workspace_id": state.workspace.workspace_id if state.workspace else None,
        "artifact_id": result.get("artifact_id"),
        "run_id": result.get("run_id") or result.get("plan_id"),
        **state.execution_policy.metadata(),
    }
    return result
