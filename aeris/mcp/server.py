"""Expose AERIS scientific tools over the local Model Context Protocol.

Run with ``aeris-mcp`` after installing ``pip install -e '.[mcp]'``. The server
uses stdio, so MCP-compatible hosts can launch it locally without exposing
cohort data over the network.
"""

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from aeris.agent.state import SessionState
from aeris.agentic.contract import execute, tool_schemas


@dataclass
class _ExposureJob:
    future: Future


class _ExposureJobs:
    """Run long exposure calls without blocking MCP status requests."""

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="aeris-exposure")
        self._jobs: dict[str, _ExposureJob] = {}
        self._lock = threading.Lock()

    def start(self, operation) -> str:
        job_id = f"exposure-job-{uuid.uuid4().hex}"
        job = _ExposureJob(future=self._executor.submit(operation))
        with self._lock:
            self._jobs[job_id] = job
        return job_id

    def status(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            return {"status": "error", "error": f"Unknown exposure job: {job_id}"}
        if not job.future.done():
            return {"status": "running", "job_id": job_id}
        try:
            result = job.future.result()
        except Exception as exc:  # pragma: no cover - defensive process boundary
            return {"status": "failed", "job_id": job_id, "error": str(exc)}
        return {"status": "completed", "job_id": job_id, "result": result}


def _server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "The MCP server requires the optional dependency. "
            "Install it with: pip install -e '.[mcp]'"
        ) from exc

    mcp = FastMCP("AERIS")
    state = SessionState()
    exposure_jobs = _ExposureJobs()

    @mcp.tool()
    def describe_aeris_tools() -> dict[str, Any]:
        """Return the canonical AERIS tool contract and approval requirement."""
        return {"tools": tool_schemas()}

    @mcp.tool()
    def load_cohort(path: str) -> dict[str, Any]:
        """Load a local cohort CSV and summarize available locations and dates."""
        return execute(state, "load_cohort", {"path": path})

    @mcp.tool()
    def plan_exposure(
        pollutant: str,
        country: str = "us",
        n_stations: int = 1,
        temporal_resolution: str = "daily",
        location_strategy: str = "auto",
        search_radius_km: float | None = None,
    ) -> dict[str, Any]:
        """Plan a static-cohort exposure run without downloading measurements."""
        return execute(
            state,
            "plan_exposure",
            {
                "pollutant": pollutant,
                "country": country,
                "n_stations": n_stations,
                "temporal_resolution": temporal_resolution,
                "location_strategy": location_strategy,
                "search_radius_km": search_radius_km,
            },
        )

    @mcp.tool()
    def approve_exposure_plan(plan_id: str, researcher_approved: bool) -> dict[str, Any]:
        """Approve the exact immutable plan previously returned by plan_exposure."""
        return execute(state, "approve_exposure_plan", {
            "plan_id": plan_id, "researcher_approved": researcher_approved,
        })

    @mcp.tool()
    def estimate_exposure(
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
    ) -> dict[str, Any]:
        """Estimate exposure after the host has shown the configuration to the researcher."""
        return execute(
            state,
            "estimate_exposure",
            {
                "pollutant": pollutant,
                "backend": backend,
                "country": country,
                "n_stations": n_stations,
                "outlier_detection": outlier_detection,
                "min_completeness": min_completeness,
                "researcher_approved": researcher_approved,
                "temporal_resolution": temporal_resolution,
                "location_strategy": location_strategy,
                "approved_plan_id": approved_plan_id,
                "search_radius_km": search_radius_km,
            },
        )

    @mcp.tool()
    def estimate_boundary_exposure(
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
    ) -> dict[str, Any]:
        """Estimate an explicit administrative-boundary exposure record through OpenAQ."""
        return execute(
            state,
            "estimate_boundary_exposure",
            {
                "pollutant": pollutant,
                "start_date": start_date,
                "end_date": end_date,
                "iso3": iso3,
                "adm_level": adm_level,
                "boundary_name": boundary_name,
                "boundary_geojson_path": boundary_geojson_path,
                "min_completeness": min_completeness,
                "researcher_approved": researcher_approved,
                "temporal_resolution": temporal_resolution,
            },
        )

    @mcp.tool()
    def estimate_boundary_exposure_batch(
        pollutant: str, start_date: str, end_date: str, boundary_geojson_path: str,
        boundary_names: list[str] | None = None, min_completeness: float | None = None,
        researcher_approved: bool = False, temporal_resolution: str = "daily",
        checkpoint_path: str | None = None,
        max_stations: int | None = None,
    ) -> dict[str, Any]:
        """Estimate a resumable panel across named GeoJSON boundary features."""
        return execute(state, "estimate_boundary_exposure_batch", {
            "pollutant": pollutant, "start_date": start_date, "end_date": end_date,
            "boundary_geojson_path": boundary_geojson_path, "boundary_names": boundary_names,
            "min_completeness": min_completeness, "researcher_approved": researcher_approved,
            "temporal_resolution": temporal_resolution, "checkpoint_path": checkpoint_path,
            "max_stations": max_stations,
        })

    @mcp.tool()
    def start_boundary_exposure_batch(
        pollutant: str, start_date: str, end_date: str, boundary_geojson_path: str,
        boundary_names: list[str] | None = None, min_completeness: float | None = None,
        researcher_approved: bool = False, temporal_resolution: str = "daily",
        checkpoint_path: str | None = None,
        max_stations: int | None = None,
    ) -> dict[str, Any]:
        """Start a checkpointed boundary panel and return immediately with a job ID."""
        arguments = {
            "pollutant": pollutant, "start_date": start_date, "end_date": end_date,
            "boundary_geojson_path": boundary_geojson_path, "boundary_names": boundary_names,
            "min_completeness": min_completeness, "researcher_approved": researcher_approved,
            "temporal_resolution": temporal_resolution, "checkpoint_path": checkpoint_path,
            "max_stations": max_stations,
        }
        job_id = exposure_jobs.start(
            lambda: execute(state, "estimate_boundary_exposure_batch", arguments)
        )
        return {"status": "running", "job_id": job_id, "checkpoint_path": checkpoint_path}

    @mcp.tool()
    def get_exposure_job(job_id: str) -> dict[str, Any]:
        """Poll a long-running exposure job until it completes or fails."""
        return exposure_jobs.status(job_id)

    @mcp.tool()
    def get_exposure_summary(pollutant: str | None = None) -> dict[str, Any]:
        """Summarize current exposure output and available quality-control fields."""
        return execute(state, "get_exposure_summary", {"pollutant": pollutant})

    @mcp.tool()
    def get_daily_data(subject_id: str | None = None, pollutant: str | None = None) -> dict[str, Any]:
        """Inspect daily exposure observations for one study subject or unit."""
        return execute(state, "get_daily_data", {"subject_id": subject_id, "pollutant": pollutant})

    @mcp.tool()
    def get_raw_data(subject_id: str | None = None, pollutant: str | None = None) -> dict[str, Any]:
        """Inspect normalized source observations for one study subject or unit."""
        return execute(state, "get_raw_data", {"subject_id": subject_id, "pollutant": pollutant})

    @mcp.tool()
    def get_station_info(subject_id: str | None = None) -> dict[str, Any]:
        """Inspect contributing monitor metadata and assignment distances."""
        return execute(state, "get_station_info", {"subject_id": subject_id})

    @mcp.tool()
    def compare_metrics(pollutants: list[str] | None = None) -> dict[str, Any]:
        """Compare summary metrics across selected pollutants."""
        return execute(state, "compare_metrics", {"pollutants": pollutants})

    @mcp.tool()
    def convert_to_aqi(pollutant: str, concentration: float) -> dict[str, Any]:
        """Convert a concentration to its EPA AQI value and category."""
        return execute(
            state,
            "convert_to_aqi",
            {"pollutant": pollutant, "concentration": concentration},
        )

    @mcp.tool()
    def get_accuweather_air_quality(latitude: float, longitude: float) -> dict[str, Any]:
        """Inspect AccuWeather's air-quality index for a coordinate."""
        return execute(
            state,
            "get_accuweather_air_quality",
            {"latitude": latitude, "longitude": longitude},
        )

    @mcp.tool()
    def web_search(query: str, num_results: int = 5) -> dict[str, Any]:
        """Search literature or source documentation needed for study design."""
        return execute(
            state,
            "web_search",
            {"query": query, "num_results": num_results},
        )

    @mcp.tool()
    def export_results(path: str, format: str = "csv", pollutant: str | None = None) -> dict[str, Any]:
        """Export the current exposure table after researcher review."""
        return execute(
            state,
            "export_results",
            {"path": path, "format": format, "pollutant": pollutant},
        )

    @mcp.tool()
    def get_decision_log() -> dict[str, Any]:
        """Return the analytical decision log for the current AERIS session."""
        return execute(state, "get_decision_log", {})

    @mcp.tool()
    def record_study_design(
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
    ) -> dict[str, Any]:
        """Record a researcher-approved design before running exposure estimation."""
        return execute(
            state,
            "record_study_design",
            {
                "research_question": research_question,
                "outcome": outcome,
                "pollutant": pollutant,
                "location_unit": location_unit,
                "time_window": time_window,
                "assignment_rule": assignment_rule,
                "researcher_approved": researcher_approved,
                "temporal_aggregation": temporal_aggregation,
                "covariates": covariates,
                "analysis_handoff": analysis_handoff,
                "sensitivity_analyses": sensitivity_analyses,
            },
        )

    def lock_reanalysis_invariants(
        study_id: str, research_question: str, target_outcome_and_population: str,
        pollutants: list[str], principal_contrast: str, principal_variants: list[str],
        broad_geography: str,
        start_date: str, end_date: str, prohibited_evidence: list[str],
        article_evidence: list[dict[str, Any]],
        target_geographic_units: int | None = None,
        target_geographic_unit_type: str | None = None,
        article_evidence_map: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Lock scientific invariants while leaving implementation choices open."""
        return execute(state, "lock_reanalysis_invariants", {
            "study_id": study_id, "research_question": research_question,
            "target_outcome_and_population": target_outcome_and_population,
            "pollutants": pollutants, "principal_contrast": principal_contrast,
            "principal_variants": principal_variants,
            "broad_geography": broad_geography, "start_date": start_date,
            "end_date": end_date, "prohibited_evidence": prohibited_evidence,
            "article_evidence": article_evidence,
            "article_evidence_map": article_evidence_map,
            "target_geographic_units": target_geographic_units,
            "target_geographic_unit_type": target_geographic_unit_type,
        })

    @mcp.tool()
    def update_research_notebook(
        phase: str, objective: str, invariants: list[str], evidence: list[dict[str, Any]],
        hypotheses: list[str], routes_attempted: list[dict[str, Any]],
        decisions: list[dict[str, Any]], unresolved_blockers: list[dict[str, Any]],
        next_actions: list[str],
    ) -> dict[str, Any]:
        """Persist restart-safe research state during a long autonomous run."""
        return execute(state, "update_research_notebook", {
            "phase": phase, "objective": objective, "invariants": invariants, "evidence": evidence,
            "hypotheses": hypotheses, "routes_attempted": routes_attempted,
            "decisions": decisions, "unresolved_blockers": unresolved_blockers,
            "next_actions": next_actions,
        })

    def amend_exposure_contract(
        changed_dimensions: dict[str, Any], evidence: list[dict[str, Any]],
        scientific_justification: str, fidelity_impact: str,
        agreement_independent: bool,
    ) -> dict[str, Any]:
        """Append an evidence-backed execution amendment."""
        return execute(state, "amend_exposure_contract", {
            "changed_dimensions": changed_dimensions, "evidence": evidence,
            "scientific_justification": scientific_justification,
            "fidelity_impact": fidelity_impact,
            "agreement_independent": agreement_independent,
        })

    def lock_exposure_contract(
        study_id: str, research_question: str, pollutants: list[str],
        location_unit: str, geographic_representation: str, assignment_method: str,
        source_strategy: str, exposure_metric: str, daily_aggregation: str,
        analysis_aggregation: str, start_date: str, end_date: str,
        temporal_resolutions: list[str], coverage_policy: dict[str, Any],
        assignment_rule: str, aggregation_rule: str, intended_use: str,
        decision_rationale: str, evidence_basis: list[str],
        representative_location_rule: str | None = None,
        maximum_monitor_distance_km: float | None = None,
        monitor_distance_evidence: str = "",
        comparison_target: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Lock an agent-authored exposure design before retrieval."""
        return execute(state, "lock_exposure_contract", {
            "study_id": study_id, "research_question": research_question,
            "pollutants": pollutants, "location_unit": location_unit,
            "geographic_representation": geographic_representation,
            "assignment_method": assignment_method,
            "representative_location_rule": representative_location_rule,
            "maximum_monitor_distance_km": maximum_monitor_distance_km,
            "monitor_distance_evidence": monitor_distance_evidence,
            "comparison_target": comparison_target,
            "source_strategy": source_strategy, "exposure_metric": exposure_metric,
            "daily_aggregation": daily_aggregation,
            "analysis_aggregation": analysis_aggregation,
            "start_date": start_date, "end_date": end_date,
            "temporal_resolutions": temporal_resolutions,
            "coverage_policy": coverage_policy, "assignment_rule": assignment_rule,
            "aggregation_rule": aggregation_rule, "intended_use": intended_use,
            "decision_rationale": decision_rationale, "evidence_basis": evidence_basis,
        })

    def lock_agent_study_contract(
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
        design_evidence: dict[str, Any],
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
        representative_location_rule: str | None = None,
        maximum_monitor_distance_km: float | None = None,
        covariates: list[str] | None = None,
        exceedance_thresholds: list[dict[str, Any]] | None = None,
        monitor_distance_evidence: str = "",
    ) -> dict[str, Any]:
        """Lock an agent-authored study contract before exposure retrieval."""
        return execute(
            state,
            "lock_agent_study_contract",
            {
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
                "design_evidence": design_evidence,
                "start_date": start_date,
                "end_date": end_date,
                "temporal_resolutions": temporal_resolutions,
                "coverage_policy": coverage_policy,
                "assignment_rule": assignment_rule,
                "aggregation_rule": aggregation_rule,
                "model": model,
                "comparison_contrasts": comparison_contrasts,
                "decision_rationale": decision_rationale,
                "evidence_basis": evidence_basis,
                "covariates": covariates,
                "exceedance_thresholds": exceedance_thresholds,
            },
        )

    def record_reanalysis_fidelity(
        study_id: str,
        fidelity_class: str,
        status: str,
        preserved_dimensions: list[str],
        deviations: list[dict[str, Any]],
        evidence_artifacts: list[str],
        reported_variants: list[str],
        notes: str = "",
        recovery_checklist: dict[str, Any] | None = None,
        final_analysis_checklist: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record how closely a completed or stopped reanalysis matched the article."""
        return execute(
            state,
            "record_reanalysis_fidelity",
            {
                "study_id": study_id,
                "fidelity_class": fidelity_class,
                "status": status,
                "preserved_dimensions": preserved_dimensions,
                "deviations": deviations,
                "evidence_artifacts": evidence_artifacts,
                "reported_variants": reported_variants,
                "notes": notes,
                "recovery_checklist": recovery_checklist,
                "final_analysis_checklist": final_analysis_checklist,
            },
        )

    @mcp.tool()
    def list_artifacts() -> dict[str, Any]:
        """List durable study datasets and result artifacts."""
        return execute(state, "list_artifacts", {})

    @mcp.tool()
    def describe_artifact(artifact_id: str) -> dict[str, Any]:
        """Describe a dataset or result table without returning all rows."""
        return execute(state, "describe_artifact", {"artifact_id": artifact_id})

    @mcp.tool()
    def sample_artifact(
        artifact_id: str, limit: int = 20, columns: list[str] | None = None
    ) -> dict[str, Any]:
        """Read at most 200 selected rows from a durable artifact."""
        return execute(
            state, "sample_artifact", {"artifact_id": artifact_id, "limit": limit, "columns": columns}
        )

    @mcp.tool()
    def query_artifact(artifact_id: str, operation: str, column: str | None = None) -> dict[str, Any]:
        """Compute a bounded summary over a durable artifact."""
        return execute(
            state,
            "query_artifact",
            {"artifact_id": artifact_id, "operation": operation, "column": column},
        )

    if os.getenv("AERIS_PROFILE", "exposure") == "reanalysis":
        mcp.tool()(lock_reanalysis_invariants)
        mcp.tool()(amend_exposure_contract)
        mcp.tool()(record_reanalysis_fidelity)
    else:
        mcp.tool()(lock_exposure_contract)

    return mcp


def main() -> None:
    """Start the local stdio MCP server."""
    _server().run()


if __name__ == "__main__":
    main()
