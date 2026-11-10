"""
Tool implementations and schemas for the AERIS agent.

Tools across 4 categories: Data, Research, File, and Analysis.
Each tool function takes ``state`` as first keyword argument plus
the tool-specific inputs, and returns a result dict.
"""

from __future__ import annotations

import base64
import logging
import os
import re
import subprocess
from html import unescape
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

import pandas as pd

if TYPE_CHECKING:
    from .state import SessionState

from .decision_log import Decision
from .reanalysis_tools import record_reanalysis_fidelity

log = logging.getLogger(__name__)


def _article_evidence_text(article_evidence: list[dict], limit: int = 2_000_000) -> str:
    """Read bounded text from cited article artifacts and adjacent text exports."""
    chunks: list[str] = []
    remaining = limit
    for item in article_evidence:
        if remaining <= 0 or not isinstance(item, dict):
            break
        path = Path(str(item.get("artifact", "")))
        candidates = [path]
        if path.suffix.lower() == ".pdf":
            candidates.insert(0, path.with_suffix(".txt"))
        for candidate in candidates:
            if remaining <= 0 or not candidate.is_file():
                continue
            if candidate.suffix.lower() == ".pdf":
                try:
                    result = subprocess.run(
                        ["pdftotext", str(candidate), "-"],
                        capture_output=True, text=True, timeout=20, check=False,
                    )
                    text = result.stdout
                except (OSError, subprocess.SubprocessError):
                    text = ""
            else:
                try:
                    text = candidate.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    text = ""
            if text:
                chunks.append(text[:remaining])
                remaining -= len(chunks[-1])
                break
    return " ".join(chunks)


# ---------------------------------------------------------------------------
# Tool schemas used by the provider-neutral AERIS contract.
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict] = [
    # --- Data Tools ---
    {
        "name": "load_cohort",
        "description": (
            "Load a cohort CSV file, auto-detect static/dynamic mode, "
            "and return summary statistics (size, columns, date range, "
            "geographic coverage)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the CSV file",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "plan_exposure",
        "description": (
            "Return a no-download OpenAQ workload plan for the loaded static cohort. "
            "Call this before requesting researcher approval for an exposure run."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pollutant": {"type": "string", "enum": ["pm25", "pm10", "no2", "o3", "so2", "co"]},
                "country": {"type": "string", "description": "ISO alpha-2 country code (default: us)."},
                "n_stations": {"type": "integer", "minimum": 1},
                "temporal_resolution": {"type": "string", "enum": ["daily", "hourly"]},
                "location_strategy": {"type": "string", "enum": ["auto", "per_subject", "catalog"]},
                "search_radius_km": {"type": "number", "exclusiveMinimum": 0, "maximum": 200},
            },
            "required": ["pollutant"],
        },
    },
    {
        "name": "estimate_exposure",
        "description": (
            "Run exposure estimation for the loaded cohort. For static mode, "
            "specify a pollutant (pm25, pm10, no2, o3, so2, co, or 'all'). "
            "For dynamic mode, specify the backend (gmaps or xgb). "
            "Supports IDW multi-station averaging, outlier detection, and "
            "completeness QC for static mode."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pollutant": {
                    "type": "string",
                    "description": "Pollutant to estimate (static mode). One of: pm25, pm10, no2, o3, so2, co, or 'all'",
                },
                "backend": {
                    "type": "string",
                    "description": "Dynamic mode backend: 'gmaps' (default) or 'xgb'",
                    "enum": ["gmaps", "xgb"],
                },
                "country": {
                    "type": "string",
                    "description": "ISO country code for geocoding (default: 'us')",
                },
                "n_stations": {
                    "type": "integer",
                    "description": "Number of stations for IDW averaging (default: 1, nearest only)",
                },
                "outlier_detection": {
                    "type": "boolean",
                    "description": "Enable IQR outlier removal before computing metrics (default: false)",
                },
                "min_completeness": {
                    "type": "number",
                    "description": "Minimum completeness percentage (0-100) for QC flagging",
                },
                "temporal_resolution": {
                    "type": "string",
                    "enum": ["daily", "hourly"],
                    "description": "OpenAQ retrieval resolution. Use daily for daily health analyses to reduce API volume; hourly is retained for sub-daily analyses.",
                },
                "location_strategy": {
                    "type": "string",
                    "enum": ["auto", "per_subject", "catalog"],
                    "description": "Station-discovery strategy. Auto can use a cached country catalog for large single-country cohorts and otherwise uses per-subject queries.",
                },
                "search_radius_km": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "maximum": 200,
                    "description": "Maximum city-to-monitor search distance in kilometres.",
                },
                "approved_plan_id": {
                    "type": "string",
                    "description": "Immutable plan identifier approved by the researcher in interactive mode.",
                },
            },
        },
    },
    {
        "name": "approve_exposure_plan",
        "description": "Bind explicit researcher approval to one immutable exposure plan.",
        "input_schema": {
            "type": "object",
            "properties": {
                "plan_id": {"type": "string"},
                "researcher_approved": {"type": "boolean"},
            },
            "required": ["plan_id", "researcher_approved"],
        },
    },
    {
        "name": "estimate_boundary_exposure",
        "description": (
            "Estimate an ambient pollutant record for an explicit administrative boundary. "
            "Use either a researcher-supplied GeoJSON file or geoBoundaries ISO3/ADM selection. "
            "The result is an unweighted mean of monitor-level means within the polygon, "
            "with station coverage and boundary provenance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pollutant": {"type": "string", "enum": ["pm25", "pm10", "no2", "o3", "so2", "co"]},
                "start_date": {"type": "string", "description": "Inclusive ISO date."},
                "end_date": {"type": "string", "description": "Inclusive ISO date."},
                "iso3": {"type": "string", "description": "ISO-3166 alpha-3 country code for geoBoundaries."},
                "adm_level": {"type": "integer", "minimum": 0, "maximum": 5},
                "boundary_name": {"type": "string", "description": "Administrative unit name or GeoJSON feature name."},
                "boundary_geojson_path": {"type": "string", "description": "Local GeoJSON path; preferred for a study-specific boundary."},
                "min_completeness": {"type": "number", "minimum": 0, "maximum": 100},
                "temporal_resolution": {
                    "type": "string",
                    "enum": ["daily", "hourly"],
                    "description": "OpenAQ retrieval resolution. Use daily when the health outcome and intended analysis are daily.",
                },
                "researcher_approved": {"type": "boolean"},
            },
            "required": ["pollutant", "start_date", "end_date"],
        },
    },
    {
        "name": "estimate_boundary_exposure_batch",
        "description": (
            "Estimate one pollutant for every selected feature in a boundary GeoJSON. "
            "Uses deterministic ordering, atomic per-unit checkpoints, and combined daily output. "
            "In self-driving mode, use deterministic chunks of at most 5 named boundaries."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pollutant": {"type": "string", "enum": ["pm25", "pm10", "no2", "o3", "so2", "co"]},
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "boundary_geojson_path": {"type": "string"},
                "boundary_names": {"type": "array", "items": {"type": "string"}},
                "min_completeness": {"type": "number", "minimum": 0, "maximum": 100},
                "temporal_resolution": {"type": "string", "enum": ["daily", "hourly"]},
                "checkpoint_path": {"type": "string"},
                "max_stations": {"type": "integer", "minimum": 1},
                "researcher_approved": {"type": "boolean"}
            },
            "required": ["pollutant", "start_date", "end_date", "boundary_geojson_path"]
        }
    },
    {
        "name": "get_exposure_summary",
        "description": (
            "Get summary statistics for the current exposure results: "
            "mean, SD, range, n with data, distance distribution."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pollutant": {
                    "type": "string",
                    "description": "Which pollutant results to summarize (defaults to first available)",
                },
            },
        },
    },
    {
        "name": "get_raw_data",
        "description": (
            "Get raw hourly air quality measurements. A subject_id is required for point exposure "
            "and omitted for an administrative-boundary record."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "subject_id": {
                    "type": "string",
                    "description": "The subject identifier",
                },
                "pollutant": {
                    "type": "string",
                    "description": "Pollutant (defaults to first available)",
                },
            },
        },
    },
    {
        "name": "get_daily_data",
        "description": (
            "Get daily aggregated air quality data. A subject_id is required for point exposure "
            "and omitted for an administrative-boundary record."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "subject_id": {
                    "type": "string",
                    "description": "The subject identifier",
                },
                "pollutant": {
                    "type": "string",
                    "description": "Pollutant (defaults to first available)",
                },
            },
        },
    },
    {
        "name": "compare_metrics",
        "description": (
            "Compare exposure metrics (mean, median, p75, p95) across "
            "pollutants or between different estimation approaches."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pollutants": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of pollutants to compare (defaults to all available)",
                },
            },
        },
    },
    {
        "name": "convert_to_aqi",
        "description": (
            "Convert a pollutant concentration to EPA AQI value and category."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pollutant": {
                    "type": "string",
                    "description": "One of: pm25, pm10, no2, o3, so2, co",
                },
                "concentration": {
                    "type": "number",
                    "description": "Concentration value to convert",
                },
            },
            "required": ["pollutant", "concentration"],
        },
    },
    {
        "name": "get_accuweather_air_quality",
        "description": (
            "Retrieve AccuWeather's current/forecast air-quality index, category, and "
            "dominant-pollutant information for a coordinate. The response is a provider "
            "index and must not be used as a pollutant concentration."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
            },
            "required": ["latitude", "longitude"],
        },
    },
    {
        "name": "export_results",
        "description": (
            "Export exposure results to a file. Supports CSV, GeoJSON, "
            "and long-format tidy CSV."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Output file path",
                },
                "format": {
                    "type": "string",
                    "enum": ["csv", "geojson", "long_format"],
                    "description": "Export format (default: csv)",
                },
                "pollutant": {
                    "type": "string",
                    "description": "Which pollutant results to export (defaults to first available)",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "get_station_info",
        "description": (
            "Get monitoring station metadata for the exposure results. "
            "Static mode only."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "subject_id": {
                    "type": "string",
                    "description": "Optional: filter to a specific subject",
                },
            },
        },
    },
    # --- Research Tools ---
    {
        "name": "web_search",
        "description": (
            "Search the web for scientific literature, exposure guidelines, "
            "or methodological references."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (e.g., 'PM2.5 childhood asthma epidemiology')",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (default 5, max 10)",
                },
            },
            "required": ["query"],
        },
    },
    # --- File Tools ---
    {
        "name": "open_folder",
        "description": (
            "Open a project folder as the working directory. All subsequent "
            "file operations (load_cohort, read_file, etc.) will resolve "
            "relative paths from this folder. Returns a listing of the "
            "folder contents. Use this first when the user points you to "
            "a directory containing their data and scripts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to the folder",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "read_file",
        "description": (
            "Read the contents of a file. Use this to inspect the user's "
            "data files, analysis scripts (R or Python), or configuration."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read",
                },
                "max_lines": {
                    "type": "integer",
                    "description": "Maximum number of lines to read (default 200)",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_directory",
        "description": ("List files in a directory, optionally filtered by glob pattern."),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path (defaults to current directory)",
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to filter (e.g., '*.csv', '*.R')",
                },
            },
        },
    },
    {
        "name": "write_file",
        "description": (
            "Write content to a file. Use for saving modified analysis scripts "
            "or exporting results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to write",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write",
                },
            },
            "required": ["path", "content"],
        },
    },
    # --- Analysis Tools ---
    {
        "name": "run_code",
        "description": (
            "Execute Python or R code in a subprocess with a 60-second timeout. "
            "Returns stdout and stderr."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The code to execute",
                },
                "language": {
                    "type": "string",
                    "enum": ["python", "r"],
                    "description": "Programming language (default: python)",
                },
            },
            "required": ["code"],
        },
    },
    {
        "name": "get_decision_log",
        "description": (
            "Return the current analytical decision log."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]

TOOL_SCHEMAS.extend(
    [
        {
            "name": "lock_reanalysis_invariants",
            "description": (
                "Lock only the scientific invariants and safety bounds for a self-driving "
                "reanalysis; leave retrieval and implementation choices open."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "study_id": {"type": "string"},
                    "research_question": {"type": "string"},
                    "target_outcome_and_population": {"type": "string"},
                    "pollutants": {"type": "array", "items": {"type": "string"}},
                    "principal_contrast": {"type": "string"},
                    "principal_variants": {
                        "type": "array", "minItems": 1, "items": {"type": "string"},
                        "description": (
                            "The explicit fitted comparison selected as the reanalysis target. "
                            "Ordinarily provide one label anchored to a table, figure, model, or "
                            "results sentence. Include another variant only when it forms part of "
                            "the same prespecified target and will receive its own fitted result."
                        ),
                    },
                    "broad_geography": {"type": "string"},
                    "target_geographic_units": {
                        "type": ["integer", "null"], "minimum": 1,
                        "description": (
                            "Article-reported count of geographic units, when stated. "
                            "Leave null when the article gives no count."
                        ),
                    },
                    "target_geographic_unit_type": {
                        "type": ["string", "null"],
                        "description": "Article-reported unit type, such as county or municipality.",
                    },
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "prohibited_evidence": {"type": "array", "items": {"type": "string"}},
                    "article_evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "artifact": {
                                    "type": "string",
                                    "description": "Saved article or supplement path.",
                                },
                                "finding": {
                                    "type": "string",
                                    "description": "Scientific specification supported by the artifact.",
                                },
                            },
                            "required": ["artifact", "finding"],
                            "additionalProperties": False,
                        },
                    },
                    "article_evidence_map": {
                        "type": "object",
                        "description": (
                            "Optional structured notes from article inspection. This is evidence, "
                            "not a compliance checklist, and may be partial when full text is unavailable."
                        ),
                    },
                },
                "required": ["study_id", "research_question", "target_outcome_and_population",
                             "pollutants", "principal_contrast", "principal_variants",
                             "broad_geography", "start_date",
                             "end_date", "prohibited_evidence", "article_evidence"],
            },
        },
        {
            "name": "update_research_notebook",
            "description": "Persist restart-safe research state: evidence, decisions, blockers, and next actions.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "phase": {
                        "type": "string",
                        "enum": ["specify", "recover", "fit", "audit", "complete"],
                    },
                    "objective": {"type": "string"},
                    "invariants": {"type": "array", "items": {"type": "string"}},
                    "evidence": {"type": "array", "items": {"type": "object"}},
                    "hypotheses": {"type": "array", "items": {"type": "string"}},
                    "routes_attempted": {"type": "array", "items": {"type": "object"}},
                    "decisions": {"type": "array", "items": {"type": "object"}},
                    "unresolved_blockers": {"type": "array", "items": {"type": "object"}},
                    "next_actions": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["phase", "objective", "invariants", "evidence", "hypotheses",
                             "routes_attempted", "decisions", "unresolved_blockers", "next_actions"],
            },
        },
        {
            "name": "amend_exposure_contract",
            "description": (
                "Append an evidence-backed execution amendment without rewriting prior "
                "contracts. In the reanalysis profile, call this after feasibility probes "
                "to record the executable exposure design before full retrieval or finalization. "
                "The first amendment's changed_dimensions must contain the complete design: "
                "geographic_representation, assignment_method, source_strategy, exposure_metric, "
                "daily_aggregation, analysis_aggregation, coverage_policy, and intended_use. "
                "Cite the returned contract_path in the final result."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "changed_dimensions": {
                        "type": "object",
                        "description": (
                            "On the first amendment, include the executable exposure fields. "
                            "Later amendments contain only evidence-backed dimensions that changed."
                        ),
                    },
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "artifact": {"type": "string"},
                                "finding": {"type": "string"},
                            },
                            "required": ["artifact", "finding"],
                            "additionalProperties": False,
                        },
                    },
                    "scientific_justification": {"type": "string"},
                    "fidelity_impact": {"type": "string", "enum": [
                        "none", "source_substitution", "coverage_subset", "covariate_omission",
                        "construct_change", "supported_sensitivity"
                    ]},
                    "agreement_independent": {"type": "boolean"},
                },
                "required": ["changed_dimensions", "evidence", "scientific_justification",
                             "fidelity_impact", "agreement_independent"],
            },
        },
        {
            "name": "lock_exposure_contract",
            "description": (
                "In self-driving mode, validate and lock an exposure estimand before retrieval."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "study_id": {"type": "string"},
                    "research_question": {"type": "string"},
                    "pollutants": {"type": "array", "items": {"type": "string"}},
                    "location_unit": {"type": "string"},
                    "geographic_representation": {"type": "string", "enum": [
                        "fixed_location", "mobility_trajectory", "administrative_area"
                    ]},
                    "assignment_method": {"type": "string", "enum": [
                        "nearest_monitor", "idw_monitors", "within_boundary_monitor_mean",
                        "nearest_monitor_to_unit_reference", "provider_coordinate_model",
                        "hyperlocal_model"
                    ]},
                    "representative_location_rule": {"type": "string"},
                    "maximum_monitor_distance_km": {
                        "type": "number", "exclusiveMinimum": 0, "maximum": 200
                    },
                    "monitor_distance_evidence": {"type": "string"},
                    "source_strategy": {"type": "string", "enum": [
                        "public_monitor_network", "provider_api", "local_model"
                    ]},
                    "exposure_metric": {"type": "string"},
                    "daily_aggregation": {"type": "string"},
                    "analysis_aggregation": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "temporal_resolutions": {
                        "type": "array", "items": {"type": "string", "enum": ["daily", "hourly"]}
                    },
                    "coverage_policy": {
                        "type": "object",
                        "properties": {
                            "mode": {"type": "string", "enum": ["report_only", "threshold"]},
                            "minimum_percent": {"type": ["number", "null"], "minimum": 0, "maximum": 100},
                            "threshold_source": {"type": "string", "enum": [
                                "none", "article", "researcher", "source_standard"
                            ]},
                            "evidence": {"type": "string"},
                        },
                        "required": ["mode", "minimum_percent", "threshold_source", "evidence"],
                    },
                    "assignment_rule": {"type": "string"},
                    "aggregation_rule": {"type": "string"},
                    "intended_use": {"type": "string"},
                    "comparison_target": {
                        "type": "object",
                        "description": "Required in reanalysis mode; the article's principal fitted comparison.",
                        "properties": {
                            "reference": {"type": "string"},
                            "exposure_definition": {"type": "string"},
                            "pollutants": {"type": "array", "items": {"type": "string"}},
                            "effect_measure": {"type": "string"},
                            "model": {"type": "string"},
                            "covariates": {"type": "array", "items": {"type": "string"}},
                            "evidence": {"type": "string"},
                            "analytic_sample_definition": {"type": "string"},
                            "analytic_sample_source": {"type": "string"},
                            "analytic_sample_evidence_artifact": {"type": "string"},
                        },
                        "required": ["reference", "exposure_definition", "pollutants",
                                     "effect_measure", "model", "covariates", "evidence",
                                     "analytic_sample_definition", "analytic_sample_source",
                                     "analytic_sample_evidence_artifact"],
                    },
                    "decision_rationale": {"type": "string"},
                    "evidence_basis": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "study_id", "research_question", "pollutants", "location_unit",
                    "geographic_representation", "assignment_method", "source_strategy",
                    "exposure_metric", "daily_aggregation", "analysis_aggregation",
                    "start_date", "end_date", "temporal_resolutions", "coverage_policy",
                    "assignment_rule", "aggregation_rule", "intended_use",
                    "decision_rationale", "evidence_basis"
                ],
            },
        },
        {
            "name": "lock_agent_study_contract",
            "description": (
                "In self-driving bootstrap mode, validate and irreversibly lock the agent's "
                "study design before any exposure retrieval."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "study_id": {"type": "string"},
                    "research_question": {"type": "string"},
                    "outcome": {"type": "string"},
                    "pollutants": {"type": "array", "items": {"type": "string"}},
                    "location_unit": {"type": "string"},
                    "principal_analysis_reference": {"type": "string"},
                    "principal_effect_measure": {"type": "string"},
                    "geographic_representation": {"type": "string", "enum": [
                        "fixed_location", "mobility_trajectory", "administrative_area"
                    ]},
                    "assignment_method": {"type": "string", "enum": [
                        "nearest_monitor", "idw_monitors", "within_boundary_monitor_mean",
                        "nearest_monitor_to_unit_reference",
                        "provider_coordinate_model", "hyperlocal_model"
                    ]},
                    "representative_location_rule": {
                        "type": "string",
                        "description": (
                            "For a city or administrative-area reference-point assignment, state "
                            "how each coordinate is obtained and how monitor distance is reported."
                        ),
                    },
                    "maximum_monitor_distance_km": {
                        "type": "number", "exclusiveMinimum": 0, "maximum": 200,
                        "description": "Maximum allowed reference-point-to-monitor distance.",
                    },
                    "monitor_distance_evidence": {
                        "type": "string",
                        "description": "Evidence supporting the monitor search-distance choice.",
                    },
                    "source_strategy": {"type": "string", "enum": [
                        "public_monitor_network", "provider_api", "local_model"
                    ]},
                    "exposure_metric": {"type": "string"},
                    "daily_aggregation": {"type": "string"},
                    "analysis_aggregation": {"type": "string"},
                    "pollutant_combination": {"type": "string", "enum": [
                        "single", "separate", "union", "intersection"
                    ]},
                    "exceedance_thresholds": {"type": "array", "items": {"type": "object"}},
                    "design_evidence": {
                        "type": "object",
                        "properties": {
                            "exposure": {"type": "string"},
                            "outcome": {"type": "string"},
                            "model": {"type": "string"},
                            "covariates": {"type": "string"},
                            "contrast": {"type": "string"},
                            "published_estimate": {
                                "type": "string",
                                "description": (
                                    "Exact article location and transcription of the target point "
                                    "estimate and its uncertainty or significance information."
                                ),
                            },
                        },
                        "required": [
                            "exposure", "outcome", "model", "covariates", "contrast",
                            "published_estimate"
                        ],
                    },
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "temporal_resolutions": {
                        "type": "array",
                        "description": (
                            "AERIS retrieval resolution only: daily or hourly. Put annual, "
                            "monthly, threshold-count, and other analytic aggregation in "
                            "aggregation_rule."
                        ),
                        "items": {"type": "string", "enum": ["daily", "hourly"]},
                    },
                    "coverage_policy": {
                        "type": "object",
                        "description": (
                            "Controls whether temporal coverage is descriptive or excludes records. "
                            "Use report_only when the study provides no supported cutoff."
                        ),
                        "properties": {
                            "mode": {"type": "string", "enum": ["report_only", "threshold"]},
                            "minimum_percent": {"type": ["number", "null"], "minimum": 0, "maximum": 100},
                            "threshold_source": {
                                "type": "string",
                                "enum": ["none", "article", "researcher", "source_standard"],
                            },
                            "evidence": {"type": "string"},
                        },
                        "required": ["mode", "minimum_percent", "threshold_source", "evidence"],
                    },
                    "assignment_rule": {"type": "string"},
                    "aggregation_rule": {"type": "string"},
                    "covariates": {"type": "array", "items": {"type": "string"}},
                    "model": {"type": "string"},
                    "comparison_contrasts": {"type": "array", "items": {"type": "string"}},
                    "decision_rationale": {"type": "string"},
                    "evidence_basis": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "study_id", "research_question", "outcome", "pollutants",
                    "principal_analysis_reference", "principal_effect_measure",
                    "geographic_representation", "assignment_method", "source_strategy",
                    "exposure_metric", "daily_aggregation", "analysis_aggregation",
                    "pollutant_combination", "design_evidence",
                    "location_unit", "start_date", "end_date", "temporal_resolutions",
                    "coverage_policy", "assignment_rule", "aggregation_rule",
                    "model", "comparison_contrasts", "decision_rationale", "evidence_basis"
                ],
            },
        },
        {
            "name": "record_reanalysis_fidelity",
            "description": "Persist the fidelity class, deviations, and evidence for a completed or stopped reanalysis.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "study_id": {"type": "string"},
                    "fidelity_class": {"type": "string", "enum": [
                        "matched_fit", "source_substitution_fit", "reduced_coverage_fit",
                        "reduced_adjustment_fit", "bounded_fit", "supported_sensitivity_fit",
                        "bounded_proxy_fit", "unsupported_fit", "evidenced_stop"
                    ]},
                    "status": {"type": "string", "enum": ["fitted", "stopped"]},
                    "preserved_dimensions": {"type": "array", "items": {"type": "string"}},
                    "deviations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "dimension": {"type": "string"},
                                "change_type": {"type": "string", "enum": [
                                    "source", "coverage_subset", "covariate_omission",
                                    "construct_change"
                                ]},
                                "published": {"type": "string"},
                                "reanalysis": {"type": "string"},
                                "reason": {"type": "string"},
                            },
                            "required": ["dimension", "change_type"],
                        },
                    },
                    "evidence_artifacts": {"type": "array", "items": {"type": "string"}},
                    "reported_variants": {"type": "array", "items": {"type": "string"}},
                    "recovery_checklist": {
                        "type": "object",
                        "description": (
                            "For bounded or construct-changing fits, include "
                            "author_repository_applicable, author_repository_attempted, and "
                            "author_repository_evidence. The evidence value must name a saved "
                            "artifact. Stopped runs also require the complete recovery checklist."
                            " The stop checklist must state whether an article-named regulator "
                            "applies, preserve evidence, inspect the portal interface, and attempt "
                            "at least three distinct public recovery routes. It must also preserve "
                            "at least two discovery searches, follow plausible results, and inspect "
                            "a public client or source implementation when one exists. If an official bulk "
                            "endpoint failed, it must also preserve an exact-file mirror search."
                            " Search results and applicable public clients must be inspected, not merely listed."
                            " It must list concrete stop_counterexamples_tested and saved "
                            "stop_counterexample_evidence."
                        ),
                        "properties": {
                            "executable_attempts": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "request_url": {"type": "string"},
                                        "command": {"type": "string"},
                                        "source_role": {
                                            "type": "string",
                                            "enum": ["outcome", "exposure", "covariate", "article"],
                                        },
                                        "response_status": {},
                                        "captured_error": {"type": "string"},
                                        "bytes_returned": {"type": "integer"},
                                        "records_returned": {"type": "integer"},
                                        "schema_or_format_inspection": {"type": "string"},
                                        "evidence_artifact": {"type": "string"},
                                        "attempt_count": {"type": "integer", "minimum": 1},
                                    },
                                    "required": [
                                        "source_role", "schema_or_format_inspection", "evidence_artifact",
                                        "attempt_count"
                                    ],
                                },
                            },
                            "target_specification_complete": {"type": "boolean"},
                            "complete_article_checked": {"type": "boolean"},
                            "outcome_routes_attempted": {"type": "integer", "minimum": 0},
                            "normal_exposure_source_tested": {"type": "boolean"},
                            "historical_fallback_applicable": {"type": "boolean"},
                            "historical_fallback_tested": {"type": "boolean"},
                            "article_named_regulator_applicable": {"type": "boolean"},
                            "article_named_regulator_attempted": {"type": "boolean"},
                            "article_named_regulator_evidence": {"type": "string"},
                            "article_named_regulator_interface_inspected": {"type": "boolean"},
                            "article_named_regulator_routes_attempted": {"type": "integer", "minimum": 0},
                            "article_named_regulator_search_queries": {"type": "integer", "minimum": 0},
                            "article_named_regulator_search_evidence": {"type": "string"},
                            "article_named_regulator_results_followed": {"type": "boolean"},
                            "article_named_regulator_public_client_inspected": {"type": "boolean"},
                            "article_named_regulator_client_evidence": {"type": "string"},
                            "article_named_regulator_applicability_evidence": {"type": "string"},
                            "official_bulk_endpoint_failed": {"type": "boolean"},
                            "bulk_public_client_inspected": {"type": "boolean"},
                            "bulk_public_client_evidence": {"type": "string"},
                            "exact_file_mirror_search_attempted": {"type": "boolean"},
                            "exact_file_mirror_search_evidence": {"type": "string"},
                            "exact_file_mirror_route_types": {
                                "type": "array", "items": {"type": "string"}
                            },
                            "exact_file_search_results_followed": {"type": "boolean"},
                            "geographic_batching_applicable": {"type": "boolean"},
                            "geographic_batching_attempted": {"type": "boolean"},
                            "geographic_batches_exhausted": {"type": "boolean"},
                            "eligible_units": {"type": "integer", "minimum": 1},
                            "exposure_units_attempted": {"type": "integer", "minimum": 0},
                            "fidelity_levels_evaluated": {"type": "array", "items": {"type": "string"}},
                            "pending_requests": {"type": "integer", "minimum": 0},
                            "evidence_artifacts": {"type": "array", "items": {"type": "string"}},
                            "stop_counterexamples_tested": {"type": "array", "items": {"type": "string"}},
                            "stop_counterexample_evidence": {"type": "string"},
                            "public_dataset_search_attempts": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "query": {"type": "string"},
                                        "source_role": {
                                            "type": "string",
                                            "enum": ["outcome", "exposure", "covariate", "article"],
                                        },
                                        "query_strategy": {
                                            "type": "string",
                                            "enum": [
                                                "artifact_exact", "source_ecosystem",
                                                "native_language", "package_registry",
                                            ],
                                        },
                                        "route_type": {
                                            "type": "string",
                                            "enum": ["dataset_catalog", "code_repository", "web_search", "package_registry"],
                                        },
                                        "evidence_artifact": {"type": "string"},
                                        "candidates": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "url": {"type": "string"},
                                                    "disposition": {
                                                        "type": "string",
                                                        "enum": ["exercised_usable", "exercised_unusable", "irrelevant"],
                                                    },
                                                    "evidence_artifact": {"type": "string"},
                                                    "request_url": {"type": "string"},
                                                    "command": {"type": "string"},
                                                    "response_status": {"type": "integer"},
                                                    "captured_error": {"type": "string"},
                                                    "bytes_returned": {"type": "integer"},
                                                    "records_returned": {"type": "integer"},
                                                    "schema_or_format_inspection": {"type": "string"},
                                                    "rationale": {"type": "string"},
                                                },
                                                "required": ["url", "disposition", "evidence_artifact"],
                                            },
                                        },
                                    },
                                    "required": [
                                        "query", "source_role", "query_strategy", "route_type",
                                        "evidence_artifact", "candidates"
                                    ],
                                },
                            },
                        },
                    },
                    "final_analysis_checklist": {
                        "type": "object",
                        "description": (
                            "For fitted autonomous runs, include analysis_adequacy, outcome_accounting, "
                            "design_fidelity, and scientific_review. Adequacy records observations, "
                            "parameters, eligible and included geographic units, coverage, variation, "
                            "justification, and evidence. Outcome accounting reconciles source records, "
                            "analysis events, and any article-reported total. Design "
                            "fidelity records the article and final model logic and contrasts, "
                            "comparison status, preserved and changed dimensions, threshold "
                            "and sample-selection provenance, and evidence. The scientific review records issues, "
                            "repairs, unresolved limits, and whether this is the strongest "
                            "supported analysis."
                        ),
                    },
                    "notes": {"type": "string"},
                },
                "required": ["study_id", "fidelity_class", "status", "preserved_dimensions",
                             "deviations", "evidence_artifacts", "reported_variants"],
            },
        },
        {
            "name": "record_study_design",
            "description": "Validate and persist a researcher-approved study-design record before exposure estimation.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "research_question": {"type": "string"},
                    "outcome": {"type": "string"},
                    "pollutant": {"type": "string"},
                    "location_unit": {"type": "string"},
                    "time_window": {"type": "string"},
                    "temporal_aggregation": {"type": "string"},
                    "assignment_rule": {"type": "string"},
                    "covariates": {"type": "array", "items": {"type": "string"}},
                    "analysis_handoff": {"type": "string"},
                    "sensitivity_analyses": {"type": "array", "items": {"type": "string"}},
                    "researcher_approved": {"type": "boolean"},
                },
                "required": [
                    "research_question", "outcome", "pollutant", "location_unit", "time_window",
                    "assignment_rule", "researcher_approved"
                ],
            },
        },
        {
            "name": "list_artifacts",
            "description": "List durable study datasets and result artifacts with compact metadata.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "describe_artifact",
            "description": "Describe a durable artifact without returning its full table.",
            "input_schema": {
                "type": "object",
                "properties": {"artifact_id": {"type": "string"}},
                "required": ["artifact_id"],
            },
        },
        {
            "name": "sample_artifact",
            "description": "Return a bounded sample from a durable artifact.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "artifact_id": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                    "columns": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["artifact_id"],
            },
        },
        {
            "name": "query_artifact",
            "description": "Compute a bounded row count, missingness, value-count, or numeric summary.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "artifact_id": {"type": "string"},
                    "operation": {"type": "string", "enum": ["row_count", "missingness", "value_counts", "numeric_summary"]},
                    "column": {"type": "string"},
                },
                "required": ["artifact_id", "operation"],
            },
        },
    ]
)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def open_folder(*, state: SessionState, path: str) -> dict:
    """Set the working directory and return a listing of its contents."""
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return {"error": f"Folder not found: {path}"}
        if not p.is_dir():
            return {"error": f"Not a directory: {path}"}

        state.working_directory = str(p)
        os.chdir(p)

        entries = []
        for entry in sorted(p.iterdir()):
            if entry.name.startswith("."):
                continue
            entries.append(
                {
                    "name": entry.name,
                    "type": "dir" if entry.is_dir() else "file",
                    "size": entry.stat().st_size if entry.is_file() else None,
                }
            )

        return {
            "status": "ok",
            "path": str(p),
            "entries": entries[:100],
        }
    except Exception as e:
        return {"error": f"Failed to open folder: {e}"}


def load_cohort(*, state: SessionState, path: str) -> dict:
    """Load a cohort CSV and return summary."""
    try:
        summary = state.load_cohort(path)
        return {
            "status": "ok",
            "workspace_id": state.workspace.workspace_id if state.workspace else None,
            "dataset_id": state.artifacts.get("cohort"),
            "summary": summary,
            **summary,
        }
    except Exception as e:
        return {"error": str(e)}


def _try_cached_exposure(state: SessionState, pollutant: str) -> dict | None:
    """Load pre-cached exposure results for demo data."""
    import pandas as pd

    if not state.input_path:
        return None

    input_name = Path(state.input_path).name
    if input_name != "cohort.csv":
        return None

    demo_dir = Path(state.input_path).parent
    cached_path = demo_dir / f"cached_{pollutant}_results.csv"
    if not cached_path.is_file():
        return None

    try:
        result_df = pd.read_csv(cached_path)
        state.results[pollutant] = result_df

        valid = result_df.dropna(subset=["mean"]) if "mean" in result_df.columns else result_df
        summary: dict = {
            "status": "ok",
            "source": "cached demo data",
            "n_results": len(result_df),
            "n_with_data": len(valid),
        }
        if "mean" in result_df.columns and not valid.empty:
            summary["exposure_mean"] = round(float(valid["mean"].mean()), 3)
            summary["exposure_sd"] = round(float(valid["mean"].std()), 3)
            summary["exposure_min"] = round(float(valid["mean"].min()), 3)
            summary["exposure_max"] = round(float(valid["mean"].max()), 3)
        if "distance_m" in result_df.columns:
            summary["median_distance_km"] = round(float(result_df["distance_m"].median() / 1000), 1)
        return summary
    except Exception:
        return None


def estimate_exposure(
    *,
    state: SessionState,
    pollutant: str | None = None,
    backend: str = "gmaps",
    country: str = "us",
    n_stations: int = 1,
    outlier_detection: bool = False,
    min_completeness: float | None = None,
    researcher_approved: bool = False,
    temporal_resolution: str = "daily",
    location_strategy: str = "auto",
    approved_plan_id: str | None = None,
    search_radius_km: float | None = None,
) -> dict:
    """Run exposure estimation after explicit researcher approval when needed."""
    country = country.strip().lower()
    if state.execution_policy.mode == "self-driving" and state.cohort is not None:
        limits = (
            state.execution_policy.contract.payload.get("resource_limits", {})
            if state.execution_policy.contract is not None
            else {}
        )
        maximum = limits.get("maximum_static_units_per_call")
        if maximum is not None and len(state.cohort) > maximum:
            return {
                "error": (
                    f"One self-driving exposure call may contain at most {maximum} static "
                    "units; split the deterministic cohort into chunks, export each result, "
                    "and merge the retained artifacts."
                )
            }
    if state.execution_policy.mode == "interactive":
        approved = state.exposure_plans.get(approved_plan_id or "")
        requested = {
            "pollutant": pollutant,
            "country": country,
            "n_stations": n_stations,
            "temporal_resolution": temporal_resolution,
            "location_strategy": location_strategy,
            "search_radius_km": search_radius_km,
        }
        if not approved or not approved.get("approved"):
            return {"error": "Interactive estimation requires an approved exposure plan ID."}
        if approved["configuration"] != requested:
            return {"error": "The estimation configuration differs from the approved exposure plan."}

    # Try cached demo results first
    if pollutant and state.mode == "static":
        cached = _try_cached_exposure(state, pollutant)
        if cached is not None:
            result_df = state.results[pollutant]
            artifact_id = state.register_result_artifact(
                pollutant,
                result_df,
                {"dataset_id": state.artifacts.get("cohort"), "source": "cached demo data", "pollutant": pollutant},
            )
            run_id = state.register_run(
                "exposure",
                {
                    "artifact_id": artifact_id,
                    "summary": cached,
                    "decision_log": state.decision_log.to_dict_list(),
                },
            )
            return {
                **cached,
                "workspace_id": state.workspace.workspace_id if state.workspace else None,
                "artifact_id": artifact_id,
                "run_id": run_id,
                "warnings": [],
            }

    try:
        result_df = state.run_estimation(
            pollutant=pollutant,
            backend=backend,
            country=country,
            n_stations=n_stations,
            outlier_detection=outlier_detection,
            min_completeness=min_completeness,
            skip_confirm=researcher_approved,
            temporal_resolution=temporal_resolution,
            location_strategy=location_strategy,
            search_radius_km=search_radius_km,
        )
        summary: dict = {
            "status": "ok",
            "n_results": len(result_df),
        }
        if "mean" in result_df.columns:
            valid = result_df.dropna(subset=["mean"])
            summary["n_with_data"] = len(valid)
            if not valid.empty:
                summary["exposure_mean"] = round(float(valid["mean"].mean()), 3)
                summary["exposure_sd"] = round(float(valid["mean"].std()), 3)
                summary["exposure_min"] = round(float(valid["mean"].min()), 3)
                summary["exposure_max"] = round(float(valid["mean"].max()), 3)
        if pollutant == "all":
            summary["pollutants_estimated"] = list(state.results.keys())
        artifact_id = state.register_result_artifact(
            pollutant or backend,
            result_df,
            {
                "dataset_id": state.artifacts.get("cohort"),
                "pollutant": pollutant,
                "backend": backend,
                "country": country,
                "n_stations": n_stations,
                "temporal_resolution": temporal_resolution,
                "location_strategy": location_strategy,
                "search_radius_km": search_radius_km,
                "min_completeness": min_completeness,
            },
        )
        daily_artifact_id = None
        daily_records = 0
        warnings = []
        if (
            temporal_resolution == "daily"
            and pollutant not in {None, "all"}
            and state.estimator is not None
            and hasattr(state.estimator, "get_daily_data")
        ):
            try:
                daily_df = state.estimator.get_daily_data()
                if daily_df is not None and not daily_df.empty:
                    daily_records = len(daily_df)
                    daily_artifact_id = state.register_result_artifact(
                        f"{pollutant}-daily-observations",
                        daily_df,
                        {
                            "dataset_id": state.artifacts.get("cohort"),
                            "summary_artifact_id": artifact_id,
                            "pollutant": pollutant,
                            "backend": backend,
                            "country": country,
                            "temporal_resolution": "daily",
                            "location_strategy": location_strategy,
                            "search_radius_km": search_radius_km,
                        },
                    )
            except Exception as exc:
                warnings.append(f"Daily observations could not be persisted: {exc}")
        run_id = state.register_run(
            "exposure",
            {
                "artifact_id": artifact_id,
                "daily_artifact_id": daily_artifact_id,
                "daily_records": daily_records,
                "summary": summary,
                "decision_log": state.decision_log.to_dict_list(),
            },
        )
        return {
            **summary,
            "workspace_id": state.workspace.workspace_id if state.workspace else None,
            "artifact_id": artifact_id,
            "daily_artifact_id": daily_artifact_id,
            "daily_records": daily_records,
            "run_id": run_id,
            "warnings": warnings,
        }
    except Exception as e:
        return {"error": str(e)}


def estimate_boundary_exposure(
    *,
    state: SessionState,
    pollutant: str,
    start_date: str,
    end_date: str,
    iso3: str | None = None,
    adm_level: int | None = None,
    boundary_name: str | None = None,
    boundary_geojson_path: str | None = None,
    min_completeness: float | None = None,
    researcher_approved: bool = False,
    temporal_resolution: str = "daily",
) -> dict:
    """Run area-level exposure estimation after explicit researcher approval."""
    if not researcher_approved:
        return {
            "error": (
                "Boundary estimation requires explicit researcher approval after reviewing the "
                "boundary, pollutant, time window, aggregation, and completeness policy."
            )
        }
    try:
        result_df = state.run_boundary_estimation(
            pollutant=pollutant,
            start_date=start_date,
            end_date=end_date,
            iso3=iso3,
            adm_level=adm_level,
            boundary_name=boundary_name,
            boundary_geojson_path=boundary_geojson_path,
            min_completeness=min_completeness,
            temporal_resolution=temporal_resolution,
        )
        artifact_id = state.register_result_artifact(
            pollutant,
            result_df,
            {
                "pollutant": pollutant,
                "start_date": start_date,
                "end_date": end_date,
                "boundary_name": boundary_name,
                "iso3": iso3,
                "adm_level": adm_level,
                "temporal_resolution": temporal_resolution,
                "min_completeness": min_completeness,
            },
        )
        run_id = state.register_run(
            "boundary-exposure",
            {
                "artifact_id": artifact_id,
                "decision_log": state.decision_log.to_dict_list(),
            },
        )
        return {
            "status": "ok",
            "result": result_df.to_dict(orient="records")[0],
            "workspace_id": state.workspace.workspace_id if state.workspace else None,
            "artifact_id": artifact_id,
            "run_id": run_id,
            "warnings": [],
        }
    except Exception as e:
        return {"error": str(e)}


def estimate_boundary_exposure_batch(
    *, state: SessionState, pollutant: str, start_date: str, end_date: str,
    boundary_geojson_path: str, boundary_names: list[str] | None = None,
    min_completeness: float | None = None, researcher_approved: bool = False,
    temporal_resolution: str = "daily", checkpoint_path: str | None = None,
    max_stations: int | None = None,
) -> dict:
    """Run a resumable administrative-area batch."""
    if not researcher_approved:
        return {"error": "Boundary batch estimation requires explicit researcher approval."}
    try:
        state.ensure_workspace()
        summaries, daily, errors = state.run_boundary_batch_estimation(
            pollutant=pollutant, start_date=start_date, end_date=end_date,
            boundary_geojson_path=boundary_geojson_path, boundary_names=boundary_names,
            min_completeness=min_completeness, temporal_resolution=temporal_resolution,
            checkpoint_path=checkpoint_path,
            max_stations=max_stations,
        )
        provenance = {
            "pollutant": pollutant, "start_date": start_date, "end_date": end_date,
            "boundary_geojson_path": str(Path(boundary_geojson_path).resolve()),
            "min_completeness": min_completeness,
            "max_stations": max_stations,
        }
        summary_artifact = state.register_result_artifact(
            f"{pollutant}-boundary-batch-summary", summaries, provenance,
        )
        daily_artifact = (
            state.register_result_artifact(
                f"{pollutant}-boundary-batch-daily", daily,
                {**provenance, "summary_artifact_id": summary_artifact},
            )
            if not daily.empty else None
        )
        status = "completed" if len(errors) == 0 else "partial" if len(summaries) else "error"
        result_records = summaries.head(20).to_dict(orient="records")
        return {
            "status": status,
            "n_requested": len(boundary_names) if boundary_names else len(summaries) + len(errors),
            "n_completed": len(summaries), "n_errors": len(errors),
            "summary_artifact_id": summary_artifact, "daily_artifact_id": daily_artifact,
            "checkpoint_path": checkpoint_path,
            "summary_csv_path": (
                str(Path(checkpoint_path).with_suffix(Path(checkpoint_path).suffix + ".summary.csv"))
                if checkpoint_path else None
            ),
            "daily_csv_path": (
                str(Path(checkpoint_path).with_suffix(Path(checkpoint_path).suffix + ".daily.csv"))
                if checkpoint_path else None
            ),
            "daily_rows": len(daily), "errors": errors,
            "results": result_records,
            "results_truncated": len(summaries) > len(result_records),
            "warnings": [],
        }
    except Exception as exc:
        return {"error": str(exc)}


def get_exposure_summary(*, state: SessionState, pollutant: str | None = None) -> dict:
    """Get summary stats for current results."""
    if not state.results:
        return {"error": "No exposure results available. Run estimate_exposure first."}

    key = pollutant or next(iter(state.results))
    df = state.results.get(key)
    if df is None or df.empty:
        return {"error": f"No results for '{key}'."}

    summary: dict = {"pollutant": key, "n_rows": len(df), "columns": df.columns.tolist()}
    if "mean" in df.columns:
        valid = df.dropna(subset=["mean"])
        summary["n_with_data"] = len(valid)
        if not valid.empty:
            summary["mean"] = round(float(valid["mean"].mean()), 3)
            summary["sd"] = round(float(valid["mean"].std()), 3)
            summary["median"] = round(float(valid["mean"].median()), 3)
            summary["p25"] = round(float(valid["mean"].quantile(0.25)), 3)
            summary["p75"] = round(float(valid["mean"].quantile(0.75)), 3)
            summary["p95"] = round(float(valid["mean"].quantile(0.95)), 3)
            summary["min"] = round(float(valid["mean"].min()), 3)
            summary["max"] = round(float(valid["mean"].max()), 3)
    if "distance_m" in df.columns:
        dist_km = df["distance_m"].dropna() / 1000
        if not dist_km.empty:
            summary["median_distance_km"] = round(float(dist_km.median()), 1)
            summary["max_distance_km"] = round(float(dist_km.max()), 1)
    return summary


def get_raw_data(*, state: SessionState, subject_id: str | None = None, pollutant: str | None = None) -> dict:
    """Get raw hourly measurements for a subject or boundary record."""
    if not state.results:
        return {"error": "No exposure results available."}
    key = pollutant or next(iter(state.results))
    if state.estimator is not None and hasattr(state.estimator, "get_raw_data"):
        try:
            raw_df = (
                state.estimator.get_raw_data()
                if state.mode == "boundary"
                else state.estimator.get_raw_data(subject_id=subject_id)
            )
            if raw_df is not None and not raw_df.empty:
                return {
                    "subject_id": subject_id,
                    "pollutant": key,
                    "n_records": len(raw_df),
                    "data": raw_df.head(500).to_dict(orient="records"),
                }
        except Exception:
            pass
    df = state.results.get(key)
    if df is None:
        return {"error": f"No results for '{key}'."}
    if subject_id is None:
        return {"error": "subject_id is required for point exposure results."}
    subject_rows = df[df["subject_id"].astype(str) == str(subject_id)]
    if subject_rows.empty:
        return {"error": f"No data for subject '{subject_id}'."}
    return {"subject_id": subject_id, "pollutant": key, "data": subject_rows.to_dict(orient="records")}


def get_daily_data(*, state: SessionState, subject_id: str | None = None, pollutant: str | None = None) -> dict:
    """Get daily aggregated data for a subject or boundary record."""
    if not state.results:
        return {"error": "No exposure results available."}
    key = pollutant or next(iter(state.results))
    if state.estimator is not None and hasattr(state.estimator, "get_daily_data"):
        try:
            daily_df = (
                state.estimator.get_daily_data()
                if state.mode == "boundary"
                else state.estimator.get_daily_data(subject_id=subject_id)
            )
            if daily_df is not None and not daily_df.empty:
                return {
                    "subject_id": subject_id,
                    "pollutant": key,
                    "n_records": len(daily_df),
                    "data": daily_df.head(500).to_dict(orient="records"),
                }
        except Exception:
            pass
    if state.mode == "boundary":
        return {"subject_id": None, "pollutant": key, "n_records": 0, "data": []}
    df = state.results.get(key)
    if df is None:
        return {"error": f"No results for '{key}'."}
    if subject_id is None:
        return {"error": "subject_id is required for point exposure results."}
    subject_rows = df[df["subject_id"].astype(str) == str(subject_id)]
    if subject_rows.empty:
        return {"error": f"No data for subject '{subject_id}'."}
    return {"subject_id": subject_id, "pollutant": key, "data": subject_rows.to_dict(orient="records")}


def compare_metrics(*, state: SessionState, pollutants: list[str] | None = None) -> dict:
    """Compare exposure metrics across pollutants."""
    if not state.results:
        return {"error": "No exposure results available."}
    keys = pollutants or list(state.results.keys())
    comparison: list[dict] = []
    for key in keys:
        df = state.results.get(key)
        if df is None or df.empty or "mean" not in df.columns:
            continue
        valid = df.dropna(subset=["mean"])
        if valid.empty:
            continue
        comparison.append({
            "pollutant": key,
            "n": len(valid),
            "mean": round(float(valid["mean"].mean()), 3),
            "median": round(float(valid["mean"].median()), 3),
            "p75": round(float(valid["mean"].quantile(0.75)), 3),
            "p95": round(float(valid["mean"].quantile(0.95)), 3),
            "sd": round(float(valid["mean"].std()), 3),
            "iqr": round(float(valid["mean"].quantile(0.75) - valid["mean"].quantile(0.25)), 3),
        })
    if not comparison:
        return {"error": "No valid data to compare."}
    return {"comparison": comparison}


def web_search(*, state: SessionState, query: str, num_results: int = 5) -> dict:
    """Search general web and public code repositories, then deduplicate results."""
    num_results = min(num_results, 10)
    result_groups: list[list[dict]] = []
    routes = []
    try:
        from googlesearch import search as gsearch
        google_results = [
            {"url": url, "result_type": "general_web", "search_route": "google"}
            for url in gsearch(query, num_results=num_results)
        ]
        if google_results:
            routes.append("google")
            result_groups.append(google_results)
    except Exception as exc:
        log.info("Google search route failed: %s", exc)

    try:
        import requests
        from bs4 import BeautifulSoup

        response = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (compatible; AERIS/0.1)"},
            timeout=30,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        duckduckgo_results = []
        for anchor in soup.select("a.result__a"):
            href = unescape(anchor.get("href", ""))
            parsed = urlparse(href)
            target = parse_qs(parsed.query).get("uddg", [href])[0]
            if target.startswith(("http://", "https://")):
                duckduckgo_results.append({
                    "url": target, "title": anchor.get_text(" ", strip=True),
                })
            if len(duckduckgo_results) >= num_results:
                break
        if duckduckgo_results:
            routes.append("duckduckgo_html")
            for item in duckduckgo_results:
                item.update(result_type="general_web", search_route="duckduckgo_html")
            result_groups.append(duckduckgo_results)

        response = requests.get(
            "https://www.bing.com/search",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (compatible; AERIS/0.1)"},
            timeout=30,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        bing_results = []
        for anchor in soup.select("li.b_algo h2 a"):
            target = anchor.get("href", "")
            if urlparse(target).netloc.endswith("bing.com"):
                encoded = parse_qs(urlparse(target).query).get("u", [""])[0]
                if encoded.startswith("a1"):
                    try:
                        target = base64.b64decode(encoded[2:] + "===").decode()
                    except (ValueError, UnicodeDecodeError):
                        pass
            if target.startswith(("http://", "https://")):
                bing_results.append({"url": target, "title": anchor.get_text(" ", strip=True)})
            if len(bing_results) >= num_results:
                break
        if bing_results:
            routes.append("bing_html")
            for item in bing_results:
                item.update(result_type="general_web", search_route="bing_html")
            result_groups.append(bing_results)

        # Repository search is a useful public discovery route for data clients,
        # parsers, legacy endpoints, and request schemas. It also gives the agent
        # relevant results when general-purpose HTML search is degraded.
        github_results = []
        words = [
            word for word in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", query)
            if word.lower() not in {
                "the", "and", "for", "from", "with", "full", "text", "pdf",
                "data", "dados", "download", "historical", "historicos",
            }
        ]
        repository_queries = [query]
        if len(words) > 2:
            repository_queries.append(" ".join(words[:2]))
        for repository_query in repository_queries:
            github = requests.get(
                "https://api.github.com/search/repositories",
                params={"q": repository_query, "per_page": min(num_results, 5)},
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "AERIS/0.1",
                },
                timeout=30,
            )
            if not github.ok:
                continue
            for item in github.json().get("items", []):
                github_results.append({
                    "url": item.get("html_url"),
                    "title": item.get("full_name"),
                    "description": item.get("description"),
                    "result_type": "public_source_repository",
                    "repository_query": repository_query,
                })
            if github_results:
                break
        if github_results:
            routes.append("github_repository")
            result_groups.append(github_results)

        # Preserve route diversity. Repository hits must not hide a mirror or
        # archive returned by a general web index.
        combined = []
        for rank in range(num_results):
            for group in result_groups:
                if rank < len(group):
                    combined.append(group[rank])
        deduplicated = []
        seen = set()
        for item in combined:
            url = item.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            deduplicated.append(item)
            if len(deduplicated) >= num_results:
                break
        return {
            "query": query,
            "results": deduplicated,
            "route": "+".join(routes) if routes else "no_results",
        }
    except Exception as exc:
        return {"error": f"Search failed across Google and public HTML fallback: {exc}"}


def read_file(*, state: SessionState, path: str, max_lines: int = 200) -> dict:
    """Read file contents."""
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return {"error": f"File not found: {path}"}
        if not p.is_file():
            return {"error": f"Not a file: {path}"}
        text = p.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        truncated = len(lines) > max_lines
        if truncated:
            lines = lines[:max_lines]
        return {"path": str(p), "content": "\n".join(lines), "total_lines": len(text.splitlines()), "truncated": truncated}
    except Exception as e:
        return {"error": f"Failed to read file: {e}"}


def list_directory(*, state: SessionState, path: str = ".", pattern: str | None = None) -> dict:
    """List directory contents."""
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return {"error": f"Directory not found: {path}"}
        if not p.is_dir():
            return {"error": f"Not a directory: {path}"}
        if pattern:
            entries = sorted(p.glob(pattern))
        else:
            entries = sorted(p.iterdir())
        files = []
        for entry in entries[:100]:
            files.append({"name": entry.name, "type": "dir" if entry.is_dir() else "file", "size": entry.stat().st_size if entry.is_file() else None})
        return {"path": str(p), "entries": files, "total": len(list(entries))}
    except Exception as e:
        return {"error": f"Failed to list directory: {e}"}


def write_file(*, state: SessionState, path: str, content: str) -> dict:
    """Write content to a file."""
    try:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"status": "ok", "path": str(p), "bytes_written": len(content)}
    except Exception as e:
        return {"error": f"Failed to write file: {e}"}


def run_code(*, state: SessionState, code: str, language: str = "python") -> dict:
    """Execute code in a subprocess with timeout."""
    timeout = 60
    if language == "r":
        cmd = ["Rscript", "-e", code]
    else:
        # Use the same Python that's running the server (venv-aware)
        import sys
        cmd = [sys.executable, "-c", code]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=os.getcwd())
        return {"stdout": result.stdout[:8000] if result.stdout else "", "stderr": result.stderr[:4000] if result.stderr else "", "returncode": result.returncode}
    except subprocess.TimeoutExpired:
        return {"error": f"Code execution timed out after {timeout}s"}
    except FileNotFoundError:
        interpreter = "Rscript" if language == "r" else "python"
        return {"error": f"{interpreter} not found on this system"}
    except Exception as e:
        return {"error": f"Execution failed: {e}"}


def convert_to_aqi(*, state: SessionState, pollutant: str, concentration: float) -> dict:
    """Convert a concentration to EPA AQI."""
    try:
        from aeris.exposure.utils import concentration_to_aqi
        aqi_value, category = concentration_to_aqi(concentration, pollutant)
        return {"pollutant": pollutant, "concentration": concentration, "aqi": aqi_value, "category": category}
    except Exception as e:
        return {"error": str(e)}


def get_accuweather_air_quality(*, state: SessionState, latitude: float, longitude: float) -> dict:
    """Retrieve an AccuWeather air-quality index with explicit source semantics."""
    if not state.config.accuweather_api_key:
        return {"error": "Missing AccuWeather API key (set ACCUWEATHER_API_KEY)."}
    try:
        from aeris.exposure.api_clients import AccuWeatherAirQualityClient

        result = AccuWeatherAirQualityClient(
            api_key=state.config.accuweather_api_key
        ).daily_air_quality(float(latitude), float(longitude))
        artifact_id = None
        if state.workspace is not None:
            artifact_id = state.workspace.register_json(
                "accuweather-air-quality",
                result,
                kind="source-observation",
                provenance={"source": result["source"], "source_type": result["source_type"]},
            )
            state.artifacts["accuweather_air_quality"] = artifact_id
        state.decision_log.record(
            Decision(
                category="data_source",
                choice="AccuWeather Air Quality API",
                rationale="Retrieved a provider air-quality index for source inspection.",
                data_context={
                    "source_type": result["source_type"],
                    "dominant_pollutant": result.get("dominant_pollutant"),
                },
            )
        )
        return {"status": "ok", "artifact_id": artifact_id, **result}
    except Exception as exc:
        return {"error": str(exc)}


def export_results(*, state: SessionState, path: str, format: str = "csv", pollutant: str | None = None) -> dict:
    """Export exposure results to a file."""
    if not state.results:
        return {"error": "No exposure results available."}
    key = pollutant or next(iter(state.results))
    df = state.results.get(key)
    if df is None or df.empty:
        return {"error": f"No results for '{key}'."}
    try:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        if format == "geojson":
            if "latitude" not in df.columns or "longitude" not in df.columns:
                return {"error": "GeoJSON export requires latitude/longitude columns."}
            try:
                import geopandas as gpd
                from shapely.geometry import Point
                geometry = [Point(lon, lat) for lon, lat in zip(df["longitude"], df["latitude"])]
                gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
                gdf.to_file(str(p), driver="GeoJSON")
            except ImportError:
                return {"error": "GeoJSON export requires geopandas: pip install geopandas"}
        elif format == "long_format":
            if state.estimator is not None and hasattr(state.estimator, "get_raw_data"):
                raw = state.estimator.get_raw_data()
                if raw is not None and not raw.empty:
                    raw.to_csv(str(p), index=False)
                else:
                    df.to_csv(str(p), index=False)
            else:
                df.to_csv(str(p), index=False)
        else:
            df.to_csv(str(p), index=False)
        return {"status": "ok", "path": str(p), "format": format, "n_rows": len(df), "pollutant": key}
    except Exception as e:
        return {"error": str(e)}


def get_station_info(*, state: SessionState, subject_id: str | None = None) -> dict:
    """Get station metadata from exposure results."""
    if not state.results:
        return {"error": "No exposure results available."}
    key = next(iter(state.results))
    if state.mode == "boundary" and state.estimator is not None:
        station_info = state.estimator.get_station_info()
        return {
            "n_entries": len(station_info),
            "columns": station_info.columns.tolist(),
            "data": station_info.head(200).to_dict(orient="records"),
        }
    df = state.results[key]
    if subject_id is not None:
        df = df[df["subject_id"].astype(str) == str(subject_id)]
        if df.empty:
            return {"error": f"No data for subject '{subject_id}'."}
    station_cols = ["station_id", "station_name", "distance_m", "n_stations_idw"]
    available = [c for c in station_cols if c in df.columns]
    if not available:
        return {"error": "No station metadata in results. Static mode only."}
    info = df[["subject_id", *available]].drop_duplicates()
    return {"n_entries": len(info), "columns": info.columns.tolist(), "data": info.head(200).to_dict(orient="records")}


def get_decision_log(*, state: SessionState) -> dict:
    """Return the current decision log."""
    return {"n_decisions": len(state.decision_log), "decisions": state.decision_log.to_dict_list()}


def record_study_design(
    *,
    state: SessionState,
    research_question: str,
    outcome: str,
    pollutant: str,
    location_unit: str,
    time_window: str,
    assignment_rule: str,
    researcher_approved: bool,
    temporal_aggregation: str = "",
    covariates: list[str] | None = None,
    analysis_handoff: str = "",
    sensitivity_analyses: list[str] | None = None,
) -> dict:
    """Persist researcher-supplied design choices without inferring scientific validity."""
    required = {
        "research_question": research_question,
        "outcome": outcome,
        "pollutant": pollutant,
        "location_unit": location_unit,
        "time_window": time_window,
        "assignment_rule": assignment_rule,
    }
    blank = [name for name, value in required.items() if not value.strip()]
    if blank:
        return {"error": f"Study design requires: {', '.join(blank)}"}
    if not researcher_approved:
        return {"error": "Study design requires explicit researcher approval."}

    design = {
        **required,
        "temporal_aggregation": temporal_aggregation,
        "covariates": covariates or [],
        "analysis_handoff": analysis_handoff,
        "sensitivity_analyses": sensitivity_analyses or [],
        "researcher_approved": True,
    }
    try:
        if state.execution_policy.mode == "self-driving":
            state.ensure_workspace()
        artifact_id = state.record_study_design(design)
    except RuntimeError as exc:
        return {"error": str(exc)}
    state.decision_log.record(
        Decision(
            category="study_design",
            choice=f"Study design for: {research_question}",
            rationale="Researcher-approved study design record.",
            data_context={"study_design_id": artifact_id, **design},
        )
    )
    return {"status": "ok", "artifact_id": artifact_id, "study_design": design}


def lock_agent_study_contract(
    *,
    state: SessionState,
    study_id: str,
    research_question: str,
    outcome: str,
    pollutants: list[str],
    location_unit: str,
    principal_analysis_reference: str,
    principal_effect_measure: str,
    geographic_representation: str,
    assignment_method: str,
    source_strategy: str,
    exposure_metric: str,
    daily_aggregation: str,
    analysis_aggregation: str,
    pollutant_combination: str,
    design_evidence: dict,
    start_date: str,
    end_date: str,
    temporal_resolutions: list[str],
    coverage_policy: dict,
    assignment_rule: str,
    aggregation_rule: str,
    model: str,
    comparison_contrasts: list[str],
    decision_rationale: str,
    evidence_basis: list[str],
    monitor_distance_evidence: str = "",
    representative_location_rule: str | None = None,
    maximum_monitor_distance_km: float | None = None,
    covariates: list[str] | None = None,
    exceedance_thresholds: list[dict] | None = None,
) -> dict:
    """Lock one agent-authored design before exposure data are retrieved."""
    text_fields = {
        "study_id": study_id,
        "research_question": research_question,
        "outcome": outcome,
        "location_unit": location_unit,
        "principal_analysis_reference": principal_analysis_reference,
        "principal_effect_measure": principal_effect_measure,
        "geographic_representation": geographic_representation,
        "assignment_method": assignment_method,
        "source_strategy": source_strategy,
        "exposure_metric": exposure_metric,
        "daily_aggregation": daily_aggregation,
        "analysis_aggregation": analysis_aggregation,
        "pollutant_combination": pollutant_combination,
        "assignment_rule": assignment_rule,
        "aggregation_rule": aggregation_rule,
        "model": model,
        "decision_rationale": decision_rationale,
    }
    blank = [name for name, value in text_fields.items() if not str(value).strip()]
    if blank or not pollutants or not temporal_resolutions or not comparison_contrasts or not evidence_basis:
        return {"error": "Agent-authored study contract is incomplete."}
    policy = state.execution_policy
    if policy.safety_envelope is None:
        return {"error": "No self-driving safety envelope is active."}
    envelope = policy.safety_envelope.payload
    from .execution import validate_coverage_policy

    try:
        normalized_coverage_policy = validate_coverage_policy(coverage_policy)
    except ValueError as exc:
        return {"error": str(exc)}
    minimum_completeness = normalized_coverage_policy["minimum_percent"]
    design = {
        "study_id": study_id,
        "research_question": research_question,
        "outcome": outcome,
        "pollutants": pollutants,
        "location_unit": location_unit,
        "principal_analysis_reference": principal_analysis_reference,
        "principal_effect_measure": principal_effect_measure,
        "geographic_representation": geographic_representation,
        "assignment_method": assignment_method,
        "representative_location_rule": representative_location_rule,
        "maximum_monitor_distance_km": maximum_monitor_distance_km,
        "monitor_distance_evidence": monitor_distance_evidence,
        "source_strategy": source_strategy,
        "exposure_metric": exposure_metric,
        "daily_aggregation": daily_aggregation,
        "analysis_aggregation": analysis_aggregation,
        "pollutant_combination": pollutant_combination,
        "exceedance_thresholds": exceedance_thresholds or [],
        "design_evidence": design_evidence,
        "date_window": {"start": start_date, "end": end_date},
        "temporal_resolutions": temporal_resolutions,
        "minimum_completeness": minimum_completeness,
        "coverage_policy": normalized_coverage_policy,
        "assignment_rule": assignment_rule,
        "aggregation_rule": aggregation_rule,
        "covariates": covariates or [],
        "model": model,
        "comparison_contrasts": comparison_contrasts,
        "decision_rationale": decision_rationale,
        "evidence_basis": evidence_basis,
        "locked_before_exposure": True,
    }
    payload = {
        "schema_version": "aeris-study-contract/v1",
        "profile": "reanalysis",
        "contract_id": f"{study_id}-agent-authored",
        "approved": True,
        "author": "agent",
        "objective": research_question,
        "allowed_tools": sorted(policy.safety_envelope.payload.get(
            "allowed_estimation_tools",
            ["estimate_exposure", "estimate_boundary_exposure", "estimate_boundary_exposure_batch"],
        )),
        "pollutants": pollutants,
        "date_window": {"start": start_date, "end": end_date},
        "temporal_resolutions": temporal_resolutions,
        "minimum_completeness": minimum_completeness,
        "coverage_policy": normalized_coverage_policy,
        "allowed_fidelity_levels": envelope.get("allowed_fidelity_levels", []),
        "resource_limits": envelope.get("resource_ceilings", {}),
        "agent_design": design,
    }
    try:
        workspace = state.ensure_workspace()
        contract_path = workspace.root / "contracts" / "agent-study-contract.json"
        contract = policy.lock_agent_contract(contract_path, payload)
        artifact_id = workspace.register_json(
            "agent-study-contract",
            payload,
            kind="study-contract",
            provenance={
                "safety_envelope_id": envelope["envelope_id"],
                "safety_envelope_sha256": policy.safety_envelope.digest,
            },
        )
    except (PermissionError, ValueError, OSError) as exc:
        return {"error": str(exc)}
    state.artifacts["study_contract"] = artifact_id
    state.decision_log.record(
        Decision(
            category="study_design",
            choice=f"Locked agent-authored contract for {study_id}",
            rationale=decision_rationale,
            data_context={
                "artifact_id": artifact_id,
                "contract_sha256": contract.digest,
                "evidence_basis": evidence_basis,
                "locked_before_exposure": True,
            },
        )
    )
    design_provenance = {
        "contract_id": contract.payload["contract_id"],
        "contract_sha256": contract.digest,
        "contract_author": contract.payload["author"],
        "minimum_completeness": contract.payload["minimum_completeness"],
        "coverage_policy": contract.payload["coverage_policy"],
        "principal_analysis_reference": design["principal_analysis_reference"],
        "principal_effect_measure": design["principal_effect_measure"],
        "geographic_representation": design["geographic_representation"],
        "assignment_method": design["assignment_method"],
        "representative_location_rule": design["representative_location_rule"],
        "maximum_monitor_distance_km": design["maximum_monitor_distance_km"],
        "exposure_metric": design["exposure_metric"],
        "pollutant_combination": design["pollutant_combination"],
        "decision_rationale": design["decision_rationale"],
        "evidence_basis": design["evidence_basis"],
        "locked_before_exposure": design["locked_before_exposure"],
    }
    return {
        "status": "ok",
        "artifact_id": artifact_id,
        "contract_path": str(contract.path),
        "contract_id": contract.payload["contract_id"],
        "contract_sha256": contract.digest,
        "study_design": design,
        "design_provenance": design_provenance,
    }


def lock_exposure_contract(
    *, state: SessionState, study_id: str, research_question: str,
    pollutants: list[str], location_unit: str, geographic_representation: str,
    assignment_method: str, source_strategy: str, exposure_metric: str,
    daily_aggregation: str, analysis_aggregation: str, start_date: str,
    end_date: str, temporal_resolutions: list[str], coverage_policy: dict,
    assignment_rule: str, aggregation_rule: str, intended_use: str,
    decision_rationale: str, evidence_basis: list[str],
    representative_location_rule: str | None = None,
    maximum_monitor_distance_km: float | None = None,
    monitor_distance_evidence: str = "",
    comparison_target: dict | None = None,
) -> dict:
    """Lock an autonomous exposure design without downstream model fields."""
    from .execution import validate_coverage_policy

    required = {
        "study_id": study_id, "research_question": research_question,
        "location_unit": location_unit,
        "geographic_representation": geographic_representation,
        "assignment_method": assignment_method, "source_strategy": source_strategy,
        "exposure_metric": exposure_metric, "daily_aggregation": daily_aggregation,
        "analysis_aggregation": analysis_aggregation, "assignment_rule": assignment_rule,
        "aggregation_rule": aggregation_rule, "intended_use": intended_use,
        "decision_rationale": decision_rationale,
    }
    if any(not str(value).strip() for value in required.values()):
        return {"error": "Agent-authored exposure contract is incomplete."}
    if not pollutants or not temporal_resolutions or not evidence_basis:
        return {"error": "Agent-authored exposure contract is incomplete."}
    if os.getenv("AERIS_PROFILE", "exposure").strip().lower() == "reanalysis":
        required_target = {
            "reference", "exposure_definition", "pollutants", "effect_measure",
            "model", "covariates", "evidence", "analytic_sample_definition",
            "analytic_sample_source", "analytic_sample_evidence_artifact",
        }
        if not isinstance(comparison_target, dict) or not required_target.issubset(comparison_target):
            return {"error": "Reanalysis requires a complete principal comparison target."}
        target_pollutants = [str(value).lower() for value in comparison_target["pollutants"]]
        if target_pollutants != [str(value).lower() for value in pollutants]:
            return {"error": "Exposure pollutants must exactly match the principal comparison target."}
        sample_evidence = Path(str(comparison_target["analytic_sample_evidence_artifact"]))
        if not sample_evidence.is_file():
            return {"error": "Principal comparison sample evidence must name an existing artifact."}
    try:
        normalized_coverage = validate_coverage_policy(coverage_policy)
    except ValueError as exc:
        return {"error": str(exc)}
    policy = state.execution_policy
    if policy.safety_envelope is None:
        return {"error": "No self-driving safety envelope is active."}
    design = {
        **required, "pollutants": pollutants,
        "representative_location_rule": representative_location_rule,
        "maximum_monitor_distance_km": maximum_monitor_distance_km,
        "monitor_distance_evidence": monitor_distance_evidence,
        "date_window": {"start": start_date, "end": end_date},
        "temporal_resolutions": temporal_resolutions,
        "coverage_policy": normalized_coverage,
        "minimum_completeness": normalized_coverage["minimum_percent"],
        "comparison_target": comparison_target,
        "evidence_basis": evidence_basis, "locked_before_exposure": True,
    }
    envelope = policy.safety_envelope.payload
    payload = {
        "schema_version": "aeris-study-contract/v1", "profile": "exposure",
        "contract_id": f"{study_id}-exposure-agent-authored",
        "approved": True, "author": "agent", "objective": research_question,
        "allowed_tools": sorted(envelope.get("allowed_estimation_tools", [])),
        "pollutants": pollutants, "date_window": {"start": start_date, "end": end_date},
        "temporal_resolutions": temporal_resolutions,
        "minimum_completeness": normalized_coverage["minimum_percent"],
        "coverage_policy": normalized_coverage,
        "resource_limits": envelope.get("resource_ceilings", {}),
        "agent_design": design,
    }
    if comparison_target:
        payload["scientific_invariants"] = {
            "research_question": research_question,
            "outcome": comparison_target.get("analytic_sample_definition"),
            "pollutants": pollutants,
            "principal_contrast": comparison_target.get("effect_measure"),
            "broad_geography": location_unit,
            "period": {"start": start_date, "end": end_date},
            "prohibited_evidence": "author-provided exposure values and derived exposure fields",
        }
    try:
        workspace = state.ensure_workspace()
        contract_path = workspace.root / "contracts" / "agent-exposure-contract.json"
        contract = policy.lock_agent_contract(contract_path, payload)
        artifact_id = workspace.register_json(
            "agent-exposure-contract", payload, kind="exposure-contract",
            provenance={"safety_envelope_id": envelope["envelope_id"],
                        "safety_envelope_sha256": policy.safety_envelope.digest},
        )
    except (PermissionError, ValueError, OSError) as exc:
        return {"error": str(exc)}
    state.artifacts["exposure_contract"] = artifact_id
    state.decision_log.record(Decision(
        category="exposure_design",
        choice=f"Locked agent-authored exposure contract for {study_id}",
        rationale=decision_rationale,
        data_context={"artifact_id": artifact_id, "contract_sha256": contract.digest},
    ))
    design_provenance = {
        "contract_id": contract.payload["contract_id"],
        "contract_sha256": contract.digest,
        "contract_author": contract.payload["author"],
        "geographic_representation": design["geographic_representation"],
        "assignment_method": design["assignment_method"],
        "representative_location_rule": design["representative_location_rule"],
        "maximum_monitor_distance_km": design["maximum_monitor_distance_km"],
        "monitor_distance_evidence": design["monitor_distance_evidence"],
        "source_strategy": design["source_strategy"],
        "exposure_metric": design["exposure_metric"],
        "coverage_policy": design["coverage_policy"],
        "decision_rationale": design["decision_rationale"],
        "evidence_basis": design["evidence_basis"],
        "locked_before_exposure": True,
    }
    return {
        "status": "ok", "artifact_id": artifact_id,
        "contract_path": str(contract.path), "contract_id": contract.payload["contract_id"],
        "contract_sha256": contract.digest, "exposure_design": design,
        "design_provenance": design_provenance,
    }


def lock_reanalysis_invariants(
    *, state: SessionState, study_id: str, research_question: str,
    target_outcome_and_population: str, pollutants: list[str], principal_contrast: str,
    broad_geography: str, start_date: str, end_date: str,
    prohibited_evidence: list[str], article_evidence: list[dict],
    article_evidence_map: dict | None = None,
    principal_variants: list[str] | None = None,
    target_geographic_units: int | None = None,
    target_geographic_unit_type: str | None = None,
) -> dict:
    """Lock scientific meaning and safety limits while leaving execution choices open."""
    required = {
        "study_id": study_id, "research_question": research_question,
        "target_outcome_and_population": target_outcome_and_population,
        "principal_contrast": principal_contrast, "broad_geography": broad_geography,
        "start_date": start_date, "end_date": end_date,
    }
    if any(not str(value).strip() for value in required.values()):
        return {"error": "Reanalysis invariants are incomplete."}
    principal_variants = principal_variants or []
    if not pollutants or not principal_variants or not prohibited_evidence or not article_evidence:
        return {"error": (
            "Reanalysis invariants require pollutants, every principal variant, "
            "prohibited evidence, and article evidence."
        )}
    if any(not isinstance(item, str) or not item.strip() for item in principal_variants):
        return {"error": "Every principal variant requires a nonempty descriptive label."}
    if len(set(principal_variants)) != len(principal_variants):
        return {"error": "Principal variant labels must be unique."}
    if not all(isinstance(item, dict) and item.get("artifact") and item.get("finding")
               for item in article_evidence):
        return {"error": "Article evidence requires saved artifacts and findings."}
    policy = state.execution_policy
    if policy.safety_envelope is None:
        return {"error": "No self-driving safety envelope is active."}
    envelope = policy.safety_envelope.payload
    payload = {
        "schema_version": "aeris-study-contract/v3", "profile": "reanalysis",
        "contract_id": f"{study_id}-reanalysis-invariants", "approved": True,
        "author": "agent", "objective": research_question,
        "allowed_tools": sorted(envelope.get("allowed_estimation_tools", [])),
        "pollutants": pollutants,
        "date_window": {"start": start_date, "end": end_date},
        "temporal_resolutions": envelope.get("allowed_temporal_resolutions", []),
        "allowed_fidelity_levels": envelope.get("allowed_fidelity_levels", []),
        "resource_limits": envelope.get("resource_ceilings", {}),
        "scientific_invariants": {
            "research_question": research_question,
            "target_outcome_and_population": target_outcome_and_population,
            "pollutants": pollutants, "principal_contrast": principal_contrast,
            "principal_variants": principal_variants,
            "broad_geography": broad_geography,
            "target_geographic_units": target_geographic_units,
            "target_geographic_unit_type": target_geographic_unit_type,
            "period": {"start": start_date, "end": end_date},
            "prohibited_evidence": prohibited_evidence,
        },
        "article_evidence": article_evidence,
        "article_evidence_map": article_evidence_map or {},
        "execution_design": {}, "amendments": [],
    }
    try:
        workspace = state.ensure_workspace()
        path = workspace.root / "contracts" / "reanalysis-invariants.json"
        contract = policy.lock_agent_contract(path, payload)
        artifact_id = workspace.register_json(
            "reanalysis-invariants", payload, kind="study-contract",
            provenance={"safety_envelope_id": envelope["envelope_id"],
                        "safety_envelope_sha256": policy.safety_envelope.digest},
        )
    except (PermissionError, ValueError, OSError) as exc:
        return {"error": str(exc)}
    state.artifacts["study_contract"] = artifact_id
    return {"status": "ok", "artifact_id": artifact_id, "contract_path": str(contract.path),
            "contract_id": contract.payload["contract_id"],
            "contract_sha256": contract.digest,
            "scientific_invariants": contract.invariants}


def update_research_notebook(
    *, state: SessionState, phase: str, objective: str, invariants: list[str], evidence: list[dict],
    hypotheses: list[str], routes_attempted: list[dict], decisions: list[dict],
    unresolved_blockers: list[dict], next_actions: list[str],
) -> dict:
    """Persist one coherent research-state snapshot for recovery after restarts."""
    if phase not in {"specify", "recover", "fit", "audit", "complete"}:
        return {"error": "Research phase must be specify, recover, fit, audit, or complete."}
    if not objective.strip() or not invariants or (phase != "complete" and not next_actions):
        return {"error": "The notebook requires an objective, invariants, and next actions."}
    payload = {
        "schema_version": "aeris-research-notebook/v2", "phase": phase, "objective": objective,
        "invariants": invariants, "evidence": evidence, "hypotheses": hypotheses,
        "routes_attempted": routes_attempted, "decisions": decisions,
        "unresolved_blockers": unresolved_blockers, "next_actions": next_actions,
    }
    workspace = state.ensure_workspace()
    notebook_path = workspace.root / "research-notebook.json"
    import json
    import tempfile
    descriptor, temporary_name = tempfile.mkstemp(prefix=".research-notebook.", dir=workspace.root)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, notebook_path)
    finally:
        Path(temporary_name).unlink(missing_ok=True)
    artifact_id = workspace.register_json(
        "research-notebook", payload, kind="research-notebook",
        provenance=state.execution_policy.metadata(),
    )
    state.artifacts["research_notebook"] = artifact_id
    return {"status": "ok", "artifact_id": artifact_id, "path": str(notebook_path)}


def amend_exposure_contract(
    *, state: SessionState, changed_dimensions: dict, evidence: list[dict],
    scientific_justification: str, fidelity_impact: str, agreement_independent: bool,
) -> dict:
    """Append an evidence-backed contract amendment and retain prior versions."""
    policy = state.execution_policy
    try:
        workspace = state.ensure_workspace()
        current_design = (
            policy.contract.payload.get("execution_design", {})
            if policy.contract else {}
        )
        if not current_design:
            required_design = {
                "geographic_representation", "assignment_method", "source_strategy",
                "exposure_metric", "daily_aggregation", "analysis_aggregation",
                "coverage_policy", "intended_use",
            }
            missing = sorted(required_design.difference(changed_dimensions))
            if missing:
                raise ValueError(
                    "The first amendment must define the complete executable exposure design; "
                    "missing: " + ", ".join(missing)
                )
        sequence = len(policy.contract.payload.get("amendments", [])) + 1 if policy.contract else 1
        path = workspace.root / "contracts" / f"agent-contract-amendment-{sequence:03d}.json"
        contract = policy.amend_agent_contract(
            path, changed_dimensions=changed_dimensions, evidence=evidence,
            scientific_justification=scientific_justification,
            fidelity_impact=fidelity_impact, agreement_independent=agreement_independent,
        )
        artifact_id = workspace.register_json(
            f"agent-contract-amendment-{sequence:03d}", contract.payload,
            kind="study-contract-amendment",
            provenance={"parent_contract_sha256": contract.payload["parent_contract_sha256"]},
        )
    except (PermissionError, ValueError, OSError) as exc:
        return {"error": str(exc)}
    state.artifacts["study_contract"] = artifact_id
    state.decision_log.record(Decision(
        category="study_design", choice=f"Applied contract amendment {sequence}",
        rationale=scientific_justification,
        data_context={"fidelity_impact": fidelity_impact,
                      "changed_dimensions": sorted(changed_dimensions),
                      "contract_sha256": contract.digest},
    ))
    return {"status": "ok", "artifact_id": artifact_id,
            "contract_path": str(contract.path), "contract_sha256": contract.digest,
            "amendment": contract.payload["amendments"][-1]}


def list_artifacts(*, state: SessionState) -> dict:
    """List compact metadata for datasets and results in the study workspace."""
    if state.workspace is None:
        return {"error": "No workspace exists. Load a cohort first."}
    return {"workspace_id": state.workspace.workspace_id, "artifacts": state.workspace.list_artifacts()}


def describe_artifact(*, state: SessionState, artifact_id: str) -> dict:
    """Describe a durable artifact without loading its table into model context."""
    if state.workspace is None:
        return {"error": "No workspace exists. Load a cohort first."}
    try:
        return {"workspace_id": state.workspace.workspace_id, "artifact": state.workspace.artifact_manifest(artifact_id)}
    except (KeyError, FileNotFoundError) as exc:
        return {"error": str(exc)}


def sample_artifact(
    *, state: SessionState, artifact_id: str, limit: int = 20, columns: list[str] | None = None
) -> dict:
    """Return a bounded sample of a durable dataset or result table."""
    if state.workspace is None:
        return {"error": "No workspace exists. Load a cohort first."}
    try:
        frame = state.workspace.read_artifact(artifact_id)
        if columns:
            unknown = sorted(set(columns).difference(frame.columns))
            if unknown:
                return {"error": f"Unknown columns: {', '.join(unknown)}"}
            frame = frame.loc[:, columns]
        limit = max(1, min(int(limit), 200))
        return {
            "workspace_id": state.workspace.workspace_id,
            "artifact_id": artifact_id,
            "total_rows": len(frame),
            "columns": list(frame.columns),
            "rows": frame.head(limit).to_dict(orient="records"),
            "truncated": len(frame) > limit,
        }
    except (KeyError, FileNotFoundError) as exc:
        return {"error": str(exc)}


def query_artifact(
    *, state: SessionState, artifact_id: str, operation: str, column: str | None = None
) -> dict:
    """Compute a bounded summary over one artifact; no arbitrary query language."""
    if state.workspace is None:
        return {"error": "No workspace exists. Load a cohort first."}
    try:
        frame = state.workspace.read_artifact(artifact_id)
        if operation == "row_count":
            result: dict = {"row_count": len(frame)}
        elif operation == "missingness":
            result = {"missingness": {key: int(value) for key, value in frame.isna().sum().items()}}
        elif operation == "value_counts" and column and column in frame.columns:
            result = {"value_counts": frame[column].value_counts(dropna=False).head(50).to_dict()}
        elif operation == "numeric_summary" and column and column in frame.columns:
            values = pd.to_numeric(frame[column], errors="coerce").dropna()
            result = {"numeric_summary": {"n": len(values), "mean": float(values.mean()), "min": float(values.min()), "max": float(values.max())}}
        else:
            return {"error": "Use row_count, missingness, value_counts with a valid column, or numeric_summary with a valid column."}
        return {"workspace_id": state.workspace.workspace_id, "artifact_id": artifact_id, "operation": operation, "result": result}
    except (KeyError, FileNotFoundError) as exc:
        return {"error": str(exc)}


def plan_exposure(
    *,
    state: SessionState,
    pollutant: str,
    country: str = "us",
    temporal_resolution: str = "daily",
    location_strategy: str = "auto",
    n_stations: int = 1,
    search_radius_km: float | None = None,
) -> dict:
    """Return an auditable, no-download workload plan for a static cohort."""
    country = country.strip().lower()
    try:
        plan = state.plan_exposure(
            pollutant=pollutant,
            country=country,
            temporal_resolution=temporal_resolution,
            location_strategy=location_strategy,
            n_stations=n_stations,
            search_radius_km=search_radius_km,
        )
        configuration = {
            "pollutant": pollutant,
            "country": country,
            "n_stations": n_stations,
            "search_radius_km": search_radius_km,
            "temporal_resolution": temporal_resolution,
            "location_strategy": location_strategy,
        }
        plan_id = state.register_run("exposure-plan", {
            "dataset_id": state.artifacts.get("cohort"), "configuration": configuration, "plan": plan
        })
        state.exposure_plans[plan_id] = {
            "configuration": configuration, "plan": plan, "approved": False
        }
        return {
            "status": "ok",
            "workspace_id": state.workspace.workspace_id if state.workspace else None,
            "plan_id": plan_id,
            "plan": plan,
        }
    except Exception as exc:
        return {"error": str(exc)}


def approve_exposure_plan(
    *, state: SessionState, plan_id: str, researcher_approved: bool
) -> dict:
    """Attach explicit approval to the exact plan shown to the researcher."""
    plan = state.exposure_plans.get(plan_id)
    if plan is None:
        return {"error": "Unknown exposure plan ID."}
    if not researcher_approved:
        return {"error": "Exposure plan approval was not granted."}
    plan["approved"] = True
    return {"status": "ok", "plan_id": plan_id, "configuration": plan["configuration"]}


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

TOOL_DISPATCH: dict = {
    "open_folder": open_folder,
    "load_cohort": load_cohort,
    "plan_exposure": plan_exposure,
    "approve_exposure_plan": approve_exposure_plan,
    "estimate_exposure": estimate_exposure,
    "estimate_boundary_exposure": estimate_boundary_exposure,
    "estimate_boundary_exposure_batch": estimate_boundary_exposure_batch,
    "get_exposure_summary": get_exposure_summary,
    "get_raw_data": get_raw_data,
    "get_daily_data": get_daily_data,
    "compare_metrics": compare_metrics,
    "convert_to_aqi": convert_to_aqi,
    "get_accuweather_air_quality": get_accuweather_air_quality,
    "export_results": export_results,
    "get_station_info": get_station_info,
    "web_search": web_search,
    "read_file": read_file,
    "list_directory": list_directory,
    "write_file": write_file,
    "run_code": run_code,
    "get_decision_log": get_decision_log,
    "record_study_design": record_study_design,
    "lock_reanalysis_invariants": lock_reanalysis_invariants,
    "update_research_notebook": update_research_notebook,
    "lock_exposure_contract": lock_exposure_contract,
    "amend_exposure_contract": amend_exposure_contract,
    "lock_agent_study_contract": lock_agent_study_contract,
    "record_reanalysis_fidelity": record_reanalysis_fidelity,
    "list_artifacts": list_artifacts,
    "describe_artifact": describe_artifact,
    "sample_artifact": sample_artifact,
    "query_artifact": query_artifact,
}
