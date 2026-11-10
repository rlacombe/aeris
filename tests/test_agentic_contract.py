import asyncio
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from aeris.agent.execution import ExecutionPolicy
from aeris.agent.fidelity import FidelityRecord
from aeris.agent.scientific_fidelity import (
    validate_article_evidence_map,
    validate_execution_commitment,
    validate_final_analysis_checklist,
)
from aeris.agent.state import SessionState, _checkpoint_lock
from aeris.agent.tools import estimate_boundary_exposure_batch, estimate_exposure, plan_exposure
from aeris.agentic.contract import (
    CORE_TOOL_NAMES,
    PUBLIC_TOOL_NAMES,
    execute,
    tool_definitions,
    tool_schemas,
)
from aeris.mcp import server as mcp_server
from aeris.mcp.server import _server

PRINCIPAL_ANALYSIS = {
    "principal_analysis_reference": "Table 2, principal model",
    "principal_effect_measure": "rate ratio per doubling",
    "geographic_representation": "administrative_area",
    "assignment_method": "within_boundary_monitor_mean",
    "source_strategy": "public_monitor_network",
    "exposure_metric": "annual PM10 exceedance-day count",
    "daily_aggregation": "daily mean",
    "analysis_aggregation": "annual exceedance-day count",
    "pollutant_combination": "single",
    "design_evidence": {
        "exposure": "Methods, exposure paragraph",
        "outcome": "Methods, outcome paragraph",
        "model": "Table 2 footnote",
        "covariates": "Table 2 footnote",
        "contrast": "Table 2 column heading",
        "published_estimate": "Table 2: RR 1.20 (95% CI 1.05--1.37)",
    },
}

PRINCIPAL_EFFECT = {
    "reference": "Table 2, principal model",
    "effect_measure": "rate ratio per doubling",
    "exposure_label": "PM2.5 per 10 ug/m3",
    "pollutants": ["pm25"],
    "estimate": 1.2,
    "uncertainty": {"type": "confidence_interval", "lower": 1.05, "upper": 1.37},
    "exposure_role": "fitted_predictor_or_contrast",
}


def test_reanalysis_profile_preserves_authority_and_scientific_fidelity():
    profile = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "aeris" / "agent" / "profiles" / "reanalysis.md"
    ).read_text(encoding="utf-8")
    prose = " ".join(profile.split())

    assert "Proceed without human approval" in profile
    assert "write retrieval and analysis code" in profile
    assert "scientifically equivalent public" in profile
    assert "Four phases" in profile
    assert "Challenge the completed analysis once" in profile
    assert "catalog discovery, transfer, and decoding as separate steps" in profile
    assert "legacy public subdomains and reporting forms" in prose
    assert "public client's request implementation" in prose
    assert "resumable downloads" in prose
    assert "only one instance of a long retrieval or analysis job" in prose
    assert "never invoke the same script again" in prose
    assert "Record the current phase" in prose
    assert "Create an estimand ledger" in prose
    assert "Never combine pollutants" in prose
    assert "Keep additive slopes in outcome units" in prose
    assert "Preserve the estimand before maximizing row count" in prose
    assert "host's deterministic packaging and validation" in prose
    assert "Never use them to select data" in prose


def test_reanalysis_profile_uses_permitted_fields_from_mixed_author_deposits():
    profile = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "aeris" / "agent" / "profiles" / "reanalysis.md"
    ).read_text(encoding="utf-8").lower()
    prose = " ".join(profile.split())

    assert "interpret prohibited evidence narrowly" in profile
    assert "sample identities, outcomes" in prose
    assert "remove prohibited exposure fields before fitting" in prose
    assert "source checksum and removed" in prose
    assert "copy permitted fields into a clean table" in prose


def test_public_contract_matches_exposed_tool_definitions():
    definitions = tool_definitions()

    assert {tool.name for tool in definitions} == CORE_TOOL_NAMES
    assert all("type" in tool.input_schema for tool in definitions)
    assert any(tool.name == "estimate_exposure" and tool.requires_researcher_approval for tool in definitions)


def test_reanalysis_profile_adds_reanalysis_controls(monkeypatch):
    monkeypatch.setenv("AERIS_PROFILE", "reanalysis")
    names = {tool.name for tool in tool_definitions()}
    assert names == PUBLIC_TOOL_NAMES - {"lock_exposure_contract"}
    assert names.difference(CORE_TOOL_NAMES) == {
        "lock_reanalysis_invariants", "record_reanalysis_fidelity",
        "amend_exposure_contract"
    }

    schemas = {tool.name: tool.input_schema for tool in tool_definitions()}
    article_evidence = schemas["lock_reanalysis_invariants"]["properties"]["article_evidence"]
    amendment_evidence = schemas["amend_exposure_contract"]["properties"]["evidence"]
    assert article_evidence["items"]["required"] == ["artifact", "finding"]
    assert "article_evidence_map" not in schemas["lock_reanalysis_invariants"]["required"]
    assert amendment_evidence["items"]["required"] == ["artifact", "finding"]


def test_mcp_reanalysis_contract_accepts_geographic_unit_invariants():
    source = inspect.getsource(mcp_server._server)
    wrapper = source[source.index("def lock_reanalysis_invariants("):
                     source.index("def update_research_notebook(")]
    assert "target_geographic_units: int | None = None" in wrapper
    assert '"target_geographic_units": target_geographic_units' in wrapper
    assert "target_geographic_unit_type: str | None = None" in wrapper
    assert '"target_geographic_unit_type": target_geographic_unit_type' in wrapper


def test_mcp_registration_follows_profile(monkeypatch):
    monkeypatch.setenv("AERIS_PROFILE", "exposure")
    exposure_names = {tool.name for tool in asyncio.run(_server().list_tools())}
    monkeypatch.setenv("AERIS_PROFILE", "reanalysis")
    reanalysis_names = {tool.name for tool in asyncio.run(_server().list_tools())}

    assert "lock_exposure_contract" in exposure_names
    assert "lock_agent_study_contract" not in exposure_names
    assert "record_reanalysis_fidelity" not in exposure_names
    assert "lock_exposure_contract" not in reanalysis_names
    assert reanalysis_names == (
        exposure_names - {"lock_exposure_contract"}
    ) | {"lock_reanalysis_invariants", "amend_exposure_contract", "record_reanalysis_fidelity"}


def test_static_exposure_tools_do_not_advertise_boundary_station_budget(monkeypatch):
    monkeypatch.setenv("AERIS_PROFILE", "reanalysis")
    tools = {tool.name: tool for tool in asyncio.run(_server().list_tools())}

    assert "max_stations" not in tools["plan_exposure"].inputSchema["properties"]
    assert "max_stations" not in tools["estimate_exposure"].inputSchema["properties"]
    assert "max_stations" in tools["estimate_boundary_exposure_batch"].inputSchema["properties"]


def test_serializable_schemas_and_rejects_private_tools():
    schemas = tool_schemas()

    assert all("input_schema" in schema for schema in schemas)
    result = execute(SessionState(), "run_code", {"code": "print('no')"})
    assert "not part of the public AERIS contract" in result["error"]
    assert result["contract"]["tool"] == "run_code"


def test_estimation_requires_researcher_approval():
    result = execute(SessionState(), "estimate_exposure", {"pollutant": "pm25"})

    assert "requires explicit researcher approval" in result["error"]


def test_self_driving_mode_uses_frozen_contract(tmp_path, monkeypatch):
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({
        "schema_version": "aeris-study-contract/v1",
        "contract_id": "test-study",
        "approved": True,
        "allowed_tools": ["estimate_boundary_exposure"],
        "pollutants": ["pm25"],
        "date_window": {"start": "2019-01-01", "end": "2019-12-31"},
        "temporal_resolutions": ["daily"],
        "minimum_completeness": 75,
    }))
    policy = ExecutionPolicy("self-driving", str(contract_path))
    arguments = {
        "pollutant": "pm25", "start_date": "2019-02-01", "end_date": "2019-03-01",
        "temporal_resolution": "daily", "min_completeness": 75,
    }

    metadata = policy.authorize("estimate_boundary_exposure", arguments)

    assert arguments["researcher_approved"] is True
    assert metadata["mode"] == "self-driving"
    assert len(metadata["contract_sha256"]) == 64


def test_self_driving_contract_rejects_completeness_drift(tmp_path):
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({
        "schema_version": "aeris-study-contract/v1", "contract_id": "threshold-study",
        "approved": True, "pollutants": ["pm25"], "minimum_completeness": 75,
    }))
    policy = ExecutionPolicy("self-driving", str(contract_path))
    for requested in (None, 80):
        try:
            policy.authorize("estimate_exposure", {
                "pollutant": "pm25", "min_completeness": requested,
            })
        except PermissionError as exc:
            assert "completeness" in str(exc)
        else:
            raise AssertionError("Completeness drift was accepted")


def test_agent_authors_and_irreversibly_locks_self_driving_contract(tmp_path, monkeypatch):
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps({
        "schema_version": "aeris-safety-envelope/v1",
        "envelope_id": "global-v1",
        "allowed_pollutants": ["pm25", "pm10", "no2", "o3", "so2", "co"],
        "date_bounds": {"earliest": "1990-01-01", "latest": "2026-12-31"},
        "allowed_temporal_resolutions": ["daily", "hourly"],
        "completeness_bounds": {"minimum": 50, "maximum": 100},
        "allowed_estimation_tools": [
            "estimate_exposure", "estimate_boundary_exposure",
            "estimate_boundary_exposure_batch",
        ],
        "allowed_fidelity_levels": ["matched", "source_substitution", "reduced_coverage"],
        "resource_ceilings": {"maximum_boundary_units": 500},
    }))
    monkeypatch.setenv("AERIS_EXECUTION_MODE", "self-driving")
    monkeypatch.setenv("AERIS_PROFILE", "reanalysis")
    monkeypatch.delenv("AERIS_STUDY_CONTRACT", raising=False)
    monkeypatch.setenv("AERIS_SAFETY_ENVELOPE", str(envelope_path))
    monkeypatch.setenv("AERIS_WORKSPACE", str(tmp_path / "workspace"))
    state = SessionState()

    blocked = execute(state, "estimate_boundary_exposure", {
        "pollutant": "pm10", "start_date": "2018-01-01", "end_date": "2018-12-31",
    })
    assert "locked until the agent records" in blocked["error"]

    arguments = {
        "study_id": "example", "research_question": "Does PM10 predict an outcome?",
        "outcome": "Annual outcome", "pollutants": ["pm10"],
        "location_unit": "municipality", "start_date": "2018-01-01",
        "end_date": "2018-12-31", "temporal_resolutions": ["daily"],
        "coverage_policy": {
            "mode": "threshold", "minimum_percent": 80,
            "threshold_source": "article", "evidence": "Methods specify 80% coverage.",
        },
        "assignment_rule": "Municipal monitor mean",
        "aggregation_rule": "Count daily means above 50 ug/m3", "covariates": ["density"],
        "model": "Log-log OLS", "comparison_contrasts": ["ratio per doubling"],
        "decision_rationale": "Annual estimates need broad seasonal representation.",
        "evidence_basis": ["article methods", "general annual-coverage principle"],
        **PRINCIPAL_ANALYSIS,
    }
    locked = execute(state, "lock_agent_study_contract", arguments)
    assert "not part of the public AERIS contract" in locked["error"]
    return
    assert locked["study_design"]["minimum_completeness"] == 80
    assert locked["study_design"]["locked_before_exposure"] is True
    assert locked["design_provenance"] == {
        "contract_id": locked["contract_id"],
        "contract_sha256": locked["contract_sha256"],
        "contract_author": "agent",
            "minimum_completeness": 80.0,
            "coverage_policy": {
                "mode": "threshold", "minimum_percent": 80.0,
                "threshold_source": "article", "evidence": "Methods specify 80% coverage.",
            },
            "principal_analysis_reference": PRINCIPAL_ANALYSIS["principal_analysis_reference"],
            "principal_effect_measure": PRINCIPAL_ANALYSIS["principal_effect_measure"],
            "geographic_representation": "administrative_area",
            "assignment_method": "within_boundary_monitor_mean",
            "representative_location_rule": None,
            "maximum_monitor_distance_km": None,
            "exposure_metric": PRINCIPAL_ANALYSIS["exposure_metric"],
            "pollutant_combination": PRINCIPAL_ANALYSIS["pollutant_combination"],
        "decision_rationale": arguments["decision_rationale"],
        "evidence_basis": arguments["evidence_basis"],
        "locked_before_exposure": True,
    }
    assert state.execution_policy.metadata()["contract_author"] == "agent"

    authorized = state.execution_policy.authorize("estimate_boundary_exposure", {
        "pollutant": "pm10", "start_date": "2018-01-01", "end_date": "2018-12-31",
        "temporal_resolution": "daily", "min_completeness": 80,
    })
    assert authorized["contract_id"] == "example-agent-authored"

    second = execute(state, "lock_agent_study_contract", arguments)
    assert "already locked" in second["error"]


def test_agent_contract_defaults_to_report_only_without_supported_threshold(tmp_path, monkeypatch):
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps({
        "schema_version": "aeris-safety-envelope/v1", "envelope_id": "global-v1",
        "allowed_pollutants": ["pm10"],
        "date_bounds": {"earliest": "2000-01-01", "latest": "2020-12-31"},
        "allowed_temporal_resolutions": ["daily"],
        "completeness_bounds": {"minimum": 0, "maximum": 100},
        "resource_ceilings": {"maximum_boundary_units": 500},
    }))
    monkeypatch.setenv("AERIS_EXECUTION_MODE", "self-driving")
    monkeypatch.setenv("AERIS_PROFILE", "reanalysis")
    monkeypatch.setenv("AERIS_SAFETY_ENVELOPE", str(envelope_path))
    monkeypatch.setenv("AERIS_WORKSPACE", str(tmp_path / "workspace"))
    state = SessionState()
    arguments = {
        "study_id": "report-only", "research_question": "Does PM10 predict an outcome?",
        "outcome": "Annual outcome", "pollutants": ["pm10"],
        "location_unit": "municipality", "start_date": "2018-01-01",
        "end_date": "2018-12-31", "temporal_resolutions": ["daily"],
        "coverage_policy": {
            "mode": "report_only", "minimum_percent": None,
            "threshold_source": "none", "evidence": "The article supplies no cutoff.",
        },
        "assignment_rule": "Municipal monitor mean", "aggregation_rule": "Annual mean",
        "model": "OLS", "comparison_contrasts": ["per 10 ug/m3"],
        "decision_rationale": "Preserve all retrieved units.",
        "evidence_basis": ["article methods"], **PRINCIPAL_ANALYSIS,
    }
    locked = execute(state, "lock_agent_study_contract", arguments)
    assert "not part of the public AERIS contract" in locked["error"]
    return
    assert locked["study_design"]["minimum_completeness"] is None
    state.execution_policy.authorize("estimate_boundary_exposure", {
        "pollutant": "pm10", "start_date": "2018-01-01", "end_date": "2018-12-31",
        "temporal_resolution": "daily", "min_completeness": None,
    })
    try:
        state.execution_policy.authorize("estimate_boundary_exposure", {
            "pollutant": "pm10", "start_date": "2018-01-01", "end_date": "2018-12-31",
            "temporal_resolution": "daily", "min_completeness": 75,
        })
    except PermissionError as exc:
        assert "report-only" in str(exc)
    else:
        raise AssertionError("Report-only contract accepted a hidden exclusion threshold")


def test_agent_contract_rejects_unsupported_numeric_coverage_threshold(tmp_path):
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps({
        "schema_version": "aeris-safety-envelope/v1", "envelope_id": "global-v1",
        "allowed_pollutants": ["pm10"],
        "date_bounds": {"earliest": "2000-01-01", "latest": "2020-12-31"},
        "allowed_temporal_resolutions": ["daily"],
        "completeness_bounds": {"minimum": 0, "maximum": 100},
        "resource_ceilings": {"maximum_boundary_units": 500},
    }))
    policy = ExecutionPolicy("self-driving", safety_envelope_path=str(envelope_path))
    payload = {
        "author": "agent", "pollutants": ["pm10"],
        "date_window": {"start": "2018-01-01", "end": "2018-12-31"},
        "temporal_resolutions": ["daily"],
        "coverage_policy": {
            "mode": "threshold", "minimum_percent": 75,
            "threshold_source": "none", "evidence": "Common heuristic",
        },
        "resource_limits": {"maximum_boundary_units": 500},
        "agent_design": PRINCIPAL_ANALYSIS,
    }
    try:
        policy.safety_envelope.validate_contract(payload)
    except ValueError as exc:
        assert "provenance" in str(exc)
    else:
        raise AssertionError("Unsupported autonomous threshold was accepted")


def test_contract_amendments_are_append_only_and_evidence_backed(tmp_path):
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({
        "schema_version": "aeris-study-contract/v2", "contract_id": "study-v1",
        "approved": True, "author": "agent", "pollutants": ["pm25"],
        "date_window": {"start": "2020-01-01", "end": "2020-12-31"},
        "scientific_invariants": {"pollutants": ["pm25"], "period": "2020"},
        "execution_design": {}, "resource_limits": {},
    }))
    original = contract_path.read_text()
    policy = ExecutionPolicy("self-driving", contract_path=str(contract_path))
    amended = policy.amend_agent_contract(
        tmp_path / "amendment-001.json",
        changed_dimensions={"source_strategy": "public_monitor_network"},
        evidence=[{"artifact": "probe.json", "finding": "Historical rows available."}],
        scientific_justification="The public monitor series preserves the pollutant construct.",
        fidelity_impact="source_substitution", agreement_independent=True,
    )
    assert contract_path.read_text() == original
    assert amended.payload["parent_contract_sha256"]
    assert amended.payload["amendments"][0]["changed_dimensions"]["source_strategy"] == "public_monitor_network"


def test_reanalysis_invariant_lock_leaves_execution_choices_open(tmp_path, monkeypatch):
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps({
        "schema_version": "aeris-safety-envelope/v1", "envelope_id": "global-v1",
        "allowed_pollutants": ["pm25"],
        "date_bounds": {"earliest": "2000-01-01", "latest": "2026-12-31"},
        "allowed_temporal_resolutions": ["daily", "hourly"],
        "completeness_bounds": {"minimum": 0, "maximum": 100},
        "allowed_estimation_tools": ["estimate_exposure", "estimate_boundary_exposure"],
        "allowed_fidelity_levels": ["source_substitution", "bounded"],
        "resource_ceilings": {"maximum_boundary_units": 500},
    }))
    article = tmp_path / "article.pdf"
    article.write_text("paper")
    monkeypatch.setenv("AERIS_EXECUTION_MODE", "self-driving")
    monkeypatch.setenv("AERIS_PROFILE", "reanalysis")
    monkeypatch.setenv("AERIS_SAFETY_ENVELOPE", str(envelope_path))
    monkeypatch.setenv("AERIS_WORKSPACE", str(tmp_path / "workspace"))
    state = SessionState()
    evidence_map = {
        "complete_article_artifact": str(article),
        "complete_article_status": "complete",
        "sections_checked": {
            "methods": "located", "results": "located",
            "data_availability": "absent_after_full_text_search",
            "supplements": "not_applicable", "repositories": "absent_after_full_text_search",
        },
        "repository_identifiers": [], "outcome_sources": ["Public mortality data"],
        "reported_covariates": [], "principal_models": ["County model"],
        "principal_effect": PRINCIPAL_EFFECT,
    }
    result = execute(state, "lock_reanalysis_invariants", {
        "study_id": "paper", "research_question": "Does PM2.5 predict mortality?",
        "target_outcome_and_population": "County mortality in adults",
        "pollutants": ["pm25"], "principal_contrast": "RR per 10 ug/m3",
        "principal_variants": ["Primary county mortality model"],
        "broad_geography": "United States counties", "start_date": "2019-01-01",
        "end_date": "2019-12-31",
        "prohibited_evidence": ["author exposure values"],
        "article_evidence": [{"artifact": str(article), "finding": "Methods specify target."}],
        "article_evidence_map": evidence_map,
    })
    assert result["status"] == "ok"
    assert result["scientific_invariants"]["principal_variants"] == [
        "Primary county mortality model"
    ]
    assert state.execution_policy.contract.payload["execution_design"] == {}
    state.execution_policy.authorize("estimate_boundary_exposure", {
        "pollutant": "pm25", "start_date": "2019-01-01", "end_date": "2019-12-31",
        "temporal_resolution": "daily", "min_completeness": None,
    })

def _candidate_commitment() -> dict:
    return {
        "analysis_plan": {
            "article_model_logic": "Poisson regression",
            "planned_model_logic": "Poisson regression",
            "article_contrast": "RR per 10 ug/m3",
            "planned_contrast": "RR per 10 ug/m3",
            "comparison_status": "exact",
            "agent_defined_thresholds": False,
            "preserved_dimensions": ["outcome", "geography", "period", "model"],
            "changed_dimensions": [],
            "evidence": ["article-methods.txt"],
        },
    }


def test_execution_commitment_requires_article_aligned_plan():
    commitment = _candidate_commitment()
    validate_execution_commitment(commitment)
    commitment["analysis_plan"]["comparison_status"] = "exploratory"
    with pytest.raises(ValueError, match="exact, derived-equivalent"):
        validate_execution_commitment(commitment)


def test_execution_commitment_rejects_agent_thresholds():
    commitment = _candidate_commitment()
    commitment["analysis_plan"]["agent_defined_thresholds"] = True
    with pytest.raises(ValueError, match="agent-created thresholds"):
        validate_execution_commitment(commitment)


def test_article_evidence_map_requires_named_repository_identifier(tmp_path):
    article = tmp_path / "article.txt"
    article.write_text("Data availability: Mendeley Data doi:10.17632/example.1")
    evidence = [{"artifact": str(article), "finding": "Complete article."}]
    mapping = {
        "complete_article_artifact": str(article),
        "complete_article_status": "complete",
        "sections_checked": {
            "methods": "located", "results": "located",
            "data_availability": "located", "supplements": "not_applicable",
            "repositories": "located",
        },
        "repository_identifiers": [], "outcome_sources": [],
        "reported_covariates": [], "principal_models": [],
        "principal_effect": PRINCIPAL_EFFECT,
        "data_availability_statement": "Mendeley Data doi:10.17632/example.1",
    }
    with pytest.raises(ValueError, match="record it"):
        validate_article_evidence_map(mapping, evidence)
    mapping["repository_identifiers"] = ["doi:10.17632/example.1"]
    validate_article_evidence_map(mapping, evidence)

    wrong_role = dict(mapping)
    wrong_role["principal_effect"] = {
        **PRINCIPAL_EFFECT, "exposure_role": "stratifier",
    }
    with pytest.raises(ValueError, match="fitted predictor or contrast"):
        validate_article_evidence_map(wrong_role, evidence)

    missing_estimate = dict(mapping)
    missing_estimate["principal_effect"] = {
        key: value for key, value in PRINCIPAL_EFFECT.items() if key != "estimate"
    }
    with pytest.raises(ValueError, match="estimate must be numeric"):
        validate_article_evidence_map(missing_estimate, evidence)


def test_article_evidence_map_rejects_missed_data_availability_section(tmp_path):
    article = tmp_path / "article.md"
    article.write_text(
        "# Methods\nPublic outcomes were analyzed.\n\n"
        "# Data availability\nMendeley Data, v1 10.17632/example.1.\n"
    )
    evidence = [{"artifact": str(article), "finding": "Complete article."}]
    mapping = {
        "complete_article_artifact": str(article),
        "complete_article_status": "complete",
        "sections_checked": {
            "methods": "located", "results": "located",
            "data_availability": "absent_after_full_text_search",
            "supplements": "not_applicable",
            "repositories": "absent_after_full_text_search",
        },
        "repository_identifiers": [], "outcome_sources": [],
        "reported_covariates": [], "principal_models": [],
        "principal_effect": PRINCIPAL_EFFECT,
    }
    with pytest.raises(ValueError, match="contains a data-availability section"):
        validate_article_evidence_map(mapping, evidence)


def test_article_evidence_map_ignores_data_availability_words_in_body(tmp_path):
    article = tmp_path / "article.md"
    article.write_text("# Methods\nWe discuss data availability as a general problem.\n")
    evidence = [{"artifact": str(article), "finding": "Complete article."}]
    mapping = {
        "complete_article_artifact": str(article),
        "complete_article_status": "complete",
        "sections_checked": {
            "methods": "located", "results": "located",
            "data_availability": "absent_after_full_text_search",
            "supplements": "not_applicable",
            "repositories": "absent_after_full_text_search",
        },
        "repository_identifiers": [], "outcome_sources": [],
        "reported_covariates": [], "principal_models": [],
        "principal_effect": PRINCIPAL_EFFECT,
    }
    validate_article_evidence_map(mapping, evidence)


def _final_checklist(evidence: str) -> dict:
    return {
        "analysis_adequacy": {
            "observations": 31,
            "estimated_parameters": 3,
            "eligible_units": 1,
            "included_units": 1,
            "coverage_summary": "31 daily observations across the target month.",
            "variation_summary": "Exposure and outcome both vary.",
            "justification": "The sample supports the planned model.",
            "evidence_artifact": evidence,
        },
        "outcome_accounting": {
            "source_events_total": 100,
            "analysis_events_total": 100,
            "aggregation_status": "exact",
            "article_events_total": 100,
            "article_comparison_status": "consistent",
            "explanation": "All qualifying source events enter the analysis.",
            "evidence_artifact": evidence,
        },
        "design_fidelity": {
            "article_model_logic": "Poisson regression",
            "final_model_logic": "Poisson regression",
            "article_contrast": "RR per 10 ug/m3",
            "final_contrast": "RR per 10 ug/m3",
            "comparison_status": "exact",
            "agent_defined_thresholds": False,
            "sample_membership_status": "known",
            "public_eligible_units": 1,
            "agent_selected_sample": False,
            "preserved_dimensions": ["outcome", "geography", "period", "model"],
            "changed_dimensions": [],
            "justification": "The model and contrast match.",
            "evidence_artifact": evidence,
        },
        "scientific_review": {
            "completed": True,
            "issues_found": [],
            "repairs_made": [],
            "unresolved_limitations": [],
            "strongest_supported_analysis": True,
            "evidence_artifact": evidence,
        },
    }


def test_final_analysis_requires_adequacy_fidelity_and_review(tmp_path):
    evidence = tmp_path / "review.json"
    evidence.write_text("{}")
    payload = {
        "article_evidence_map": {"reported_covariates": ["temperature"]},
        "execution_design": _candidate_commitment(),
    }
    checklist = _final_checklist(str(evidence))
    validate_final_analysis_checklist(
        checklist, contract_payload=payload, evidence_root=tmp_path,
        fidelity_class="source_substitution_fit",
    )
    checklist["analysis_adequacy"]["observations"] = 3
    with pytest.raises(ValueError, match="more observations than parameters"):
        validate_final_analysis_checklist(
            checklist, contract_payload=payload, evidence_root=tmp_path,
            fidelity_class="source_substitution_fit",
        )
    checklist = _final_checklist(str(evidence))
    checklist["scientific_review"]["completed"] = False
    with pytest.raises(ValueError, match="must be completed"):
        validate_final_analysis_checklist(
            checklist, contract_payload=payload, evidence_root=tmp_path,
            fidelity_class="source_substitution_fit",
        )


def test_final_analysis_rejects_agent_invented_replacement_contrast(tmp_path):
    evidence = tmp_path / "review.json"
    evidence.write_text("{}")
    payload = {"execution_design": _candidate_commitment()}
    checklist = _final_checklist(str(evidence))
    checklist["design_fidelity"].update({
        "final_model_logic": "Poisson regression on exposure tertiles",
        "final_contrast": "High versus low agent-created exposure tertile",
        "comparison_status": "exploratory",
        "agent_defined_thresholds": True,
    })
    with pytest.raises(ValueError, match="exploratory replacement"):
        validate_final_analysis_checklist(
            checklist, contract_payload=payload, evidence_root=tmp_path,
            fidelity_class="source_substitution_fit",
        )


def test_final_analysis_reconciles_outcome_events_and_article_total(tmp_path):
    evidence = tmp_path / "outcomes.json"
    evidence.write_text("{}")
    payload = {"execution_design": _candidate_commitment()}
    checklist = _final_checklist(str(evidence))
    checklist["outcome_accounting"].update({
        "source_events_total": 30_423,
        "analysis_events_total": 3_410,
        "article_events_total": 30_423,
    })
    with pytest.raises(ValueError, match="aggregation difference"):
        validate_final_analysis_checklist(
            checklist, contract_payload=payload, evidence_root=tmp_path,
            fidelity_class="source_substitution_fit",
        )

    checklist["outcome_accounting"]["aggregation_status"] = "explained_difference"
    with pytest.raises(ValueError, match="large difference"):
        validate_final_analysis_checklist(
            checklist, contract_payload=payload, evidence_root=tmp_path,
            fidelity_class="source_substitution_fit",
        )


def test_final_analysis_labels_reduced_geographic_coverage(tmp_path):
    evidence = tmp_path / "coverage.json"
    evidence.write_text("{}")
    checklist = _final_checklist(str(evidence))
    checklist["analysis_adequacy"].update({"eligible_units": 39, "included_units": 1})
    with pytest.raises(ValueError, match="reduced-coverage fidelity class"):
        validate_final_analysis_checklist(
            checklist, contract_payload={}, evidence_root=tmp_path,
            fidelity_class="source_substitution_fit",
        )
    validate_final_analysis_checklist(
        checklist, contract_payload={}, evidence_root=tmp_path,
        fidelity_class="reduced_coverage_fit",
    )


def test_final_analysis_rejects_agent_subset_for_unknown_article_sample(tmp_path):
    evidence = tmp_path / "sample.json"
    evidence.write_text("{}")
    checklist = _final_checklist(str(evidence))
    checklist["analysis_adequacy"].update({"eligible_units": 67, "included_units": 55})
    checklist["design_fidelity"].update({
        "sample_membership_status": "unknown",
        "public_eligible_units": 67,
        "agent_selected_sample": True,
    })
    with pytest.raises(ValueError, match="agent-selected subset"):
        validate_final_analysis_checklist(
            checklist, contract_payload={}, evidence_root=tmp_path,
            fidelity_class="bounded_fit",
        )

    checklist["design_fidelity"]["agent_selected_sample"] = False
    with pytest.raises(ValueError, match="all eligible public records"):
        validate_final_analysis_checklist(
            checklist, contract_payload={}, evidence_root=tmp_path,
            fidelity_class="bounded_fit",
        )

    checklist["analysis_adequacy"]["included_units"] = 67
    validate_final_analysis_checklist(
        checklist, contract_payload={}, evidence_root=tmp_path,
        fidelity_class="bounded_fit",
    )


def test_fidelity_record_persists_final_analysis_checklist():
    checklist = {"outcome_accounting": {"source_events_total": 100}}
    record = FidelityRecord(
        study_id="example", fidelity_class="source_substitution_fit",
        status="fitted", preserved_dimensions=("outcome",), deviations=(),
        evidence_artifacts=(), final_analysis_checklist=checklist,
    )
    assert record.to_dict()["final_analysis_checklist"] == checklist


def test_self_driving_restart_restores_latest_workspace_contract(tmp_path, monkeypatch):
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps({
        "schema_version": "aeris-safety-envelope/v1", "envelope_id": "global-v1",
        "allowed_pollutants": ["pm10"],
        "date_bounds": {"earliest": "2000-01-01", "latest": "2026-12-31"},
        "allowed_temporal_resolutions": ["daily"],
        "completeness_bounds": {"minimum": 0, "maximum": 100},
        "resource_ceilings": {"maximum_boundary_units": 500},
    }))
    workspace = tmp_path / "workspace"
    contracts = workspace / ".aeris" / "contracts"
    contracts.mkdir(parents=True)
    base = {
        "schema_version": "aeris-study-contract/v2", "contract_id": "paper",
        "approved": True, "author": "agent", "profile": "reanalysis",
        "pollutants": ["pm10"],
        "date_window": {"start": "2018-01-01", "end": "2018-12-31"},
        "temporal_resolutions": ["daily"],
        "coverage_policy": {"mode": "report_only", "minimum_percent": None,
                            "threshold_source": "none", "evidence": "Report all coverage."},
        "scientific_invariants": {"pollutants": ["pm10"]},
        "agent_design": PRINCIPAL_ANALYSIS,
        "execution_design": {**PRINCIPAL_ANALYSIS, "revision": "latest"},
        "resource_limits": {"maximum_boundary_units": 500},
        "amendments": [{"sequence": 1}],
    }
    (contracts / "reanalysis-invariants.json").write_text(json.dumps({
        **base, "execution_design": {}, "agent_design": {}, "amendments": [],
    }))
    amendment = contracts / "agent-contract-amendment-001.json"
    amendment.write_text(json.dumps(base))
    monkeypatch.setenv("AERIS_EXECUTION_MODE", "self-driving")
    monkeypatch.setenv("AERIS_SAFETY_ENVELOPE", str(envelope_path))
    monkeypatch.setenv("AERIS_WORKSPACE", str(workspace))

    state = SessionState()
    state.ensure_workspace()

    assert state.execution_policy.contract.path == amendment.resolve()
    assert state.execution_policy.contract.payload["execution_design"]["revision"] == "latest"


def test_interactive_restart_does_not_restore_workspace_contract(tmp_path, monkeypatch):
    contracts = tmp_path / "workspace" / ".aeris" / "contracts"
    contracts.mkdir(parents=True)
    (contracts / "reanalysis-invariants.json").write_text("{}")
    monkeypatch.setenv("AERIS_EXECUTION_MODE", "interactive")
    monkeypatch.setenv("AERIS_WORKSPACE", str(tmp_path / "workspace"))

    state = SessionState()
    state.ensure_workspace()

    assert state.execution_policy.contract is None


def test_loaded_cohort_keeps_configured_durable_workspace(tmp_path, monkeypatch):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    cohort = inputs / "cohort.csv"
    cohort.write_text(
        "subject_id,latitude,longitude,start_date,end_date\n"
        "1,48.8,2.3,2020-01-01,2020-01-31\n"
    )
    durable = tmp_path / "durable-workspace"
    monkeypatch.setenv("AERIS_EXECUTION_MODE", "interactive")
    monkeypatch.setenv("AERIS_WORKSPACE", str(durable))

    state = SessionState()
    state.load_cohort(str(cohort))

    assert state.workspace.root == durable / ".aeris"
    assert Path(state.cache.db_path).parent == durable


def test_contract_amendment_protects_scientific_invariants(tmp_path):
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({
        "schema_version": "aeris-study-contract/v2", "contract_id": "study-v1",
        "approved": True, "author": "agent", "pollutants": ["pm25"],
        "scientific_invariants": {"pollutants": ["pm25"]},
        "date_window": {}, "execution_design": {}, "resource_limits": {},
    }))
    policy = ExecutionPolicy("self-driving", contract_path=str(contract_path))
    with pytest.raises(ValueError, match="scientific invariants"):
        policy.amend_agent_contract(
            tmp_path / "bad.json", changed_dimensions={"pollutants": ["no2"]},
            evidence=[{"artifact": "probe.json", "finding": "NO2 exists."}],
            scientific_justification="Use another pollutant.", fidelity_impact="none",
            agreement_independent=True,
        )


def test_core_exposure_contract_does_not_require_reanalysis_fields(tmp_path, monkeypatch):
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps({
        "schema_version": "aeris-safety-envelope/v1", "envelope_id": "global-v1",
        "allowed_pollutants": ["pm25"],
        "date_bounds": {"earliest": "2000-01-01", "latest": "2026-12-31"},
        "allowed_temporal_resolutions": ["daily"],
        "completeness_bounds": {"minimum": 0, "maximum": 100},
        "allowed_estimation_tools": ["estimate_exposure"],
        "resource_ceilings": {"maximum_boundary_units": 500},
    }))
    monkeypatch.setenv("AERIS_EXECUTION_MODE", "self-driving")
    monkeypatch.delenv("AERIS_PROFILE", raising=False)
    monkeypatch.setenv("AERIS_SAFETY_ENVELOPE", str(envelope_path))
    monkeypatch.setenv("AERIS_WORKSPACE", str(tmp_path / "workspace"))
    result = execute(SessionState(), "lock_exposure_contract", {
        "study_id": "cohort", "research_question": "Estimate annual PM2.5 exposure",
        "pollutants": ["pm25"], "location_unit": "participant residence",
        "geographic_representation": "fixed_location",
        "assignment_method": "nearest_monitor", "maximum_monitor_distance_km": 25,
        "monitor_distance_evidence": "OpenAQ point queries support a 25 km radius.",
        "source_strategy": "public_monitor_network", "exposure_metric": "annual mean PM2.5",
        "daily_aggregation": "daily mean", "analysis_aggregation": "annual mean",
        "start_date": "2020-01-01", "end_date": "2020-12-31",
        "temporal_resolutions": ["daily"],
        "coverage_policy": {"mode": "report_only", "minimum_percent": None,
                            "threshold_source": "none", "evidence": "No protocol cutoff."},
        "assignment_rule": "Nearest monitor within search radius",
        "aggregation_rule": "Mean of observed daily means",
        "intended_use": "Exposure covariate", "decision_rationale": "Cohort protocol",
        "evidence_basis": ["cohort data dictionary"],
    })
    assert result["status"] == "ok"
    assert "principal_analysis_reference" not in result["exposure_design"]
    assert "published_estimate" not in result["exposure_design"]


def test_reanalysis_hides_broad_exposure_contract(tmp_path, monkeypatch):
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps({
        "schema_version": "aeris-safety-envelope/v1", "envelope_id": "global-v1",
        "allowed_pollutants": ["pm10", "o3"],
        "date_bounds": {"earliest": "2000-01-01", "latest": "2026-12-31"},
        "allowed_temporal_resolutions": ["daily"],
        "completeness_bounds": {"minimum": 0, "maximum": 100},
        "allowed_estimation_tools": ["estimate_exposure"],
        "resource_ceilings": {"maximum_static_units_per_call": 5},
    }))
    monkeypatch.setenv("AERIS_EXECUTION_MODE", "self-driving")
    monkeypatch.setenv("AERIS_PROFILE", "reanalysis")
    monkeypatch.setenv("AERIS_SAFETY_ENVELOPE", str(envelope_path))
    monkeypatch.setenv("AERIS_WORKSPACE", str(tmp_path / "workspace"))
    sample_evidence = tmp_path / "analytic-sample.csv"
    sample_evidence.write_text("city\nA\n")
    arguments = {
        "study_id": "paper", "research_question": "Does PM10 predict disease?",
        "pollutants": ["pm10"], "location_unit": "city",
        "geographic_representation": "fixed_location",
        "assignment_method": "nearest_monitor", "source_strategy": "public_monitor_network",
        "maximum_monitor_distance_km": 25,
        "monitor_distance_evidence": "Source-supported search radius.",
        "exposure_metric": "annual PM10 exceedance days", "daily_aggregation": "daily mean",
        "analysis_aggregation": "annual exceedance count", "start_date": "2018-01-01",
        "end_date": "2018-12-31", "temporal_resolutions": ["daily"],
        "coverage_policy": {"mode": "report_only", "minimum_percent": None,
                            "threshold_source": "none", "evidence": "No cutoff."},
        "assignment_rule": "Nearest monitor", "aggregation_rule": "Count exceedances",
        "intended_use": "Reanalysis", "decision_rationale": "Principal fitted model",
        "evidence_basis": ["Table 6"],
    }
    missing = execute(SessionState(), "lock_exposure_contract", arguments)
    assert "not part of the public AERIS contract" in missing["error"]
    return

    mismatch = execute(SessionState(), "lock_exposure_contract", {
        **arguments,
        "comparison_target": {
            "reference": "Table 6", "exposure_definition": "PM10 exceedance days",
            "pollutants": ["pm10", "o3"], "effect_measure": "ratio per doubling",
            "model": "log-log OLS", "covariates": ["density"], "evidence": "Table 6 row",
            "analytic_sample_definition": "Article cities", "analytic_sample_source": "Supplement",
            "analytic_sample_evidence_artifact": str(sample_evidence),
        },
    })
    assert "must exactly match" in mismatch["error"]

    accepted = execute(SessionState(), "lock_exposure_contract", {
        **arguments,
        "comparison_target": {
            "reference": "Table 6", "exposure_definition": "PM10 exceedance days",
            "pollutants": ["pm10"], "effect_measure": "ratio per doubling",
            "model": "log-log OLS", "covariates": ["density"], "evidence": "Table 6 row",
            "analytic_sample_definition": "Article cities", "analytic_sample_source": "Supplement",
            "analytic_sample_evidence_artifact": str(sample_evidence),
        },
    })
    assert accepted["status"] == "ok", accepted.get("error")


def test_agent_contract_rejects_spatial_tool_drift(tmp_path, monkeypatch):
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps({
        "schema_version": "aeris-safety-envelope/v1", "envelope_id": "global-v1",
        "allowed_pollutants": ["pm10"],
        "date_bounds": {"earliest": "2000-01-01", "latest": "2020-12-31"},
        "allowed_temporal_resolutions": ["daily"],
        "completeness_bounds": {"minimum": 50, "maximum": 100},
        "resource_ceilings": {"maximum_boundary_units": 500},
    }))
    policy = ExecutionPolicy("self-driving", safety_envelope_path=str(envelope_path))
    payload = {
        "schema_version": "aeris-study-contract/v1", "contract_id": "spatial-study",
        "approved": True, "pollutants": ["pm10"],
        "date_window": {"start": "2018-01-01", "end": "2018-12-31"},
        "temporal_resolutions": ["daily"], "minimum_completeness": 75,
        "resource_limits": {"maximum_boundary_units": 500},
        "agent_design": PRINCIPAL_ANALYSIS,
    }
    policy.lock_agent_contract(tmp_path / "locked.json", payload)
    try:
        policy.authorize("estimate_exposure", {"pollutant": "pm10", "min_completeness": 75})
    except PermissionError as exc:
        assert "boundary exposure tool" in str(exc)
    else:
        raise AssertionError("Spatial assignment drift was accepted")


def test_city_reference_assignment_uses_static_exposure_tool(tmp_path):
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps({
        "schema_version": "aeris-safety-envelope/v1", "envelope_id": "global-v1",
        "allowed_pollutants": ["pm10"],
        "date_bounds": {"earliest": "2000-01-01", "latest": "2020-12-31"},
        "allowed_temporal_resolutions": ["daily"],
        "completeness_bounds": {"minimum": 50, "maximum": 100},
        "resource_ceilings": {"maximum_boundary_units": 500},
    }))
    policy = ExecutionPolicy("self-driving", safety_envelope_path=str(envelope_path))
    design = {
        **PRINCIPAL_ANALYSIS,
        "assignment_method": "nearest_monitor_to_unit_reference",
        "representative_location_rule": "Official municipal centroid; preserve monitor distance.",
        "maximum_monitor_distance_km": 50,
    }
    payload = {
        "schema_version": "aeris-study-contract/v1", "contract_id": "city-study",
        "approved": True,
        "allowed_tools": ["estimate_exposure", "estimate_boundary_exposure_batch"],
        "pollutants": ["pm10"],
        "date_window": {"start": "2018-01-01", "end": "2018-12-31"},
        "temporal_resolutions": ["daily"], "minimum_completeness": 75,
        "resource_limits": {"maximum_boundary_units": 500}, "agent_design": design,
    }
    policy.lock_agent_contract(tmp_path / "locked.json", payload)

    policy.authorize("estimate_exposure", {
        "pollutant": "pm10", "min_completeness": 75, "search_radius_km": 50,
    })
    try:
        policy.authorize("estimate_exposure", {
            "pollutant": "pm10", "min_completeness": 75, "search_radius_km": 25,
        })
    except PermissionError as exc:
        assert "maximum monitor distance" in str(exc)
    else:
        raise AssertionError("Exposure estimation accepted distance drift")
    try:
        policy.authorize(
            "estimate_boundary_exposure_batch",
            {"pollutant": "pm10", "min_completeness": 75, "boundary_names": ["Rome"]},
        )
    except PermissionError as exc:
        assert "cannot use an administrative-boundary tool" in str(exc)
    else:
        raise AssertionError("City reference-point assignment accepted a polygon exposure tool")


def test_city_reference_assignment_requires_coordinate_rule(tmp_path):
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps({
        "schema_version": "aeris-safety-envelope/v1", "envelope_id": "global-v1",
        "allowed_pollutants": ["pm10"],
        "date_bounds": {"earliest": "2000-01-01", "latest": "2020-12-31"},
        "allowed_temporal_resolutions": ["daily"],
        "completeness_bounds": {"minimum": 50, "maximum": 100},
        "resource_ceilings": {"maximum_boundary_units": 500},
    }))
    policy = ExecutionPolicy("self-driving", safety_envelope_path=str(envelope_path))
    design = {
        **PRINCIPAL_ANALYSIS,
        "assignment_method": "nearest_monitor_to_unit_reference",
        "maximum_monitor_distance_km": 50,
    }
    payload = {
        "pollutants": ["pm10"],
        "date_window": {"start": "2018-01-01", "end": "2018-12-31"},
        "temporal_resolutions": ["daily"], "minimum_completeness": 75,
        "resource_limits": {"maximum_boundary_units": 500}, "agent_design": design,
    }
    try:
        policy.safety_envelope.validate_contract(payload)
    except ValueError as exc:
        assert "representative_location_rule" in str(exc)
    else:
        raise AssertionError("City reference-point assignment omitted its coordinate rule")


def test_agent_contract_respects_study_independent_safety_envelope(tmp_path):
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps({
        "schema_version": "aeris-safety-envelope/v1", "envelope_id": "global-v1",
        "allowed_pollutants": ["pm10"],
        "date_bounds": {"earliest": "2000-01-01", "latest": "2020-12-31"},
        "allowed_temporal_resolutions": ["daily"],
        "completeness_bounds": {"minimum": 50, "maximum": 100},
        "resource_ceilings": {"maximum_boundary_units": 500},
    }))
    policy = ExecutionPolicy("self-driving", safety_envelope_path=str(envelope_path))
    payload = {
        "pollutants": ["pm25"], "date_window": {"start": "2018-01-01", "end": "2018-12-31"},
        "temporal_resolutions": ["daily"], "minimum_completeness": 75,
        "resource_limits": {"maximum_boundary_units": 500},
        "agent_design": PRINCIPAL_ANALYSIS,
    }
    try:
        policy.safety_envelope.validate_contract(payload)
    except ValueError as exc:
        assert "pollutant outside" in str(exc)
    else:
        raise AssertionError("Safety envelope accepted an unauthorized pollutant")


def test_self_driving_contract_authorizes_boundary_batch(tmp_path):
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({
        "schema_version": "aeris-study-contract/v1",
        "contract_id": "batch-study",
        "approved": True,
        "allowed_tools": ["estimate_boundary_exposure_batch"],
        "pollutants": ["pm25"],
        "date_window": {"start": "2019-01-01", "end": "2019-12-31"},
        "temporal_resolutions": ["daily"],
        "minimum_completeness": 50,
    }))
    policy = ExecutionPolicy("self-driving", str(contract_path))
    arguments = {
        "pollutant": "pm25", "start_date": "2019-01-01", "end_date": "2019-12-31",
        "boundary_geojson_path": "/study/boundaries.geojson",
        "temporal_resolution": "daily", "min_completeness": 50,
    }

    metadata = policy.authorize("estimate_boundary_exposure_batch", arguments)

    assert arguments["researcher_approved"] is True
    assert metadata["contract_id"] == "batch-study"


def test_self_driving_contract_rejects_malformed_dates_and_reversed_window(tmp_path):
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({
        "schema_version": "aeris-study-contract/v1", "contract_id": "date-study",
        "approved": True, "allowed_tools": ["estimate_boundary_exposure"],
        "pollutants": ["pm25"],
        "date_window": {"start": "2019-01-01", "end": "2019-12-31"},
    }))
    policy = ExecutionPolicy("self-driving", str(contract_path))
    for start, end in (("not-a-date", "2019-02-01"), ("2019-03-01", "2019-02-01")):
        try:
            policy.authorize("estimate_boundary_exposure", {
                "pollutant": "pm25", "start_date": start, "end_date": end,
            })
        except PermissionError:
            pass
        else:
            raise AssertionError(f"Invalid date window was accepted: {start} to {end}")


def test_self_driving_contract_bounds_boundary_batch_size(tmp_path):
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({
        "schema_version": "aeris-study-contract/v1", "contract_id": "bounded-batch",
        "approved": True, "allowed_tools": ["estimate_boundary_exposure_batch"],
        "pollutants": ["pm25"], "resource_limits": {"maximum_boundary_units": 2},
    }))
    policy = ExecutionPolicy("self-driving", str(contract_path))
    try:
        policy.authorize("estimate_boundary_exposure_batch", {
            "pollutant": "pm25", "boundary_names": ["A", "B", "C"],
        })
    except PermissionError as exc:
        assert "contract allows 2" in str(exc)
    else:
        raise AssertionError("Oversized boundary batch was accepted")

    boundaries = tmp_path / "boundaries.geojson"
    boundaries.write_text(json.dumps({
        "type": "FeatureCollection", "features": [{}, {}, {}],
    }))
    try:
        policy.authorize("estimate_boundary_exposure_batch", {
            "pollutant": "pm25", "boundary_geojson_path": str(boundaries),
        })
    except PermissionError as exc:
        assert "contract allows 2" in str(exc)
    else:
        raise AssertionError("Oversized implicit boundary batch was accepted")


def test_self_driving_contract_bounds_each_boundary_batch_call(tmp_path):
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({
        "schema_version": "aeris-study-contract/v1", "contract_id": "chunked-batch",
        "approved": True, "allowed_tools": ["estimate_boundary_exposure_batch"],
        "pollutants": ["pm25"],
        "resource_limits": {
            "maximum_boundary_units": 500,
            "maximum_boundary_units_per_call": 5,
        },
    }))
    policy = ExecutionPolicy("self-driving", str(contract_path))

    policy.authorize("estimate_boundary_exposure_batch", {
        "pollutant": "pm25", "boundary_names": [f"unit-{i}" for i in range(5)],
    })
    try:
        policy.authorize("estimate_boundary_exposure_batch", {
            "pollutant": "pm25", "boundary_names": [f"unit-{i}" for i in range(6)],
        })
    except PermissionError as exc:
        assert "at most 5 boundaries" in str(exc)
    else:
        raise AssertionError("Oversized single batch call was accepted")


def test_self_driving_contract_bounds_each_static_exposure_call(tmp_path):
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({
        "schema_version": "aeris-study-contract/v1", "contract_id": "chunked-static",
        "approved": True, "allowed_tools": ["estimate_exposure"],
        "pollutants": ["pm25"],
        "resource_limits": {"maximum_static_units_per_call": 2},
    }))
    state = SessionState()
    state.execution_policy = ExecutionPolicy("self-driving", str(contract_path))
    state.cohort = pd.DataFrame({
        "participant_id": ["A", "B", "C"],
        "latitude": [37.0, 37.1, 37.2],
        "longitude": [-122.0, -122.1, -122.2],
    })

    result = estimate_exposure(state=state, pollutant="pm25")

    assert "at most 2 static units" in result["error"]


def test_monitor_catalog_country_code_is_normalized(monkeypatch):
    state = SessionState()
    observed = {}

    def fake_plan(**arguments):
        observed.update(arguments)
        return {"estimated_calls_upper_bound": 1}

    monkeypatch.setattr(state, "plan_exposure", fake_plan)
    monkeypatch.setattr(state, "register_run", lambda *args, **kwargs: "plan-1")

    result = plan_exposure(state=state, pollutant="pm10", country="IT")

    assert result["status"] == "ok"
    assert observed["country"] == "it"
    assert state.exposure_plans["plan-1"]["configuration"]["country"] == "it"


def test_estimate_exposure_persists_daily_observations(monkeypatch):
    state = SessionState()
    state.execution_policy.mode = "test"
    state.mode = "static"
    state.cohort = pd.DataFrame({"subject_id": ["A"]})
    state.workspace = SimpleNamespace(workspace_id="study-1")

    def run_estimation(**kwargs):
        state.estimator = SimpleNamespace(get_daily_data=lambda: pd.DataFrame({
            "subject_id": ["A", "A"],
            "date": ["2018-01-01", "2018-01-02"],
            "parameter": ["pm10", "pm10"],
            "mean": [42.0, 58.0],
        }))
        state.results["pm10"] = pd.DataFrame({"subject_id": ["A"], "mean": [50.0]})
        return state.results["pm10"]

    registered = []

    def register(name, frame, provenance):
        registered.append((name, frame.copy(), provenance))
        return f"artifact-{len(registered)}"

    monkeypatch.setattr(state, "run_estimation", run_estimation)
    monkeypatch.setattr(state, "register_result_artifact", register)
    monkeypatch.setattr(state, "register_run", lambda *args, **kwargs: "run-1")

    result = estimate_exposure(state=state, pollutant="pm10", temporal_resolution="daily")

    assert result["artifact_id"] == "artifact-1"
    assert result["daily_artifact_id"] == "artifact-2"
    assert result["daily_records"] == 2
    assert registered[1][0] == "pm10-daily-observations"
    assert registered[1][1]["mean"].tolist() == [42.0, 58.0]
    assert registered[1][2]["summary_artifact_id"] == "artifact-1"


def test_boundary_batch_is_deterministic_resumable_and_persists_daily_data(tmp_path, monkeypatch):
    boundaries = tmp_path / "boundaries.geojson"
    boundaries.write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"name": "Beta"}, "geometry": {
                "type": "Polygon", "coordinates": [[[1, 0], [2, 0], [2, 1], [1, 1], [1, 0]]]
            }},
            {"type": "Feature", "properties": {"name": "Alpha"}, "geometry": {
                "type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]
            }},
        ],
    }))
    checkpoint = tmp_path / "batch.json"
    state = SessionState()
    calls = []

    def fake_run(**kwargs):
        name = kwargs["boundary_name"]
        calls.append(name)
        state.estimator = SimpleNamespace(get_daily_data=lambda: pd.DataFrame({
            "date": ["2019-01-01"], "mean": [1.0 if name == "Alpha" else 2.0]
        }))
        return pd.DataFrame([{"mean": 1.0, "qc_flag": "PASS"}])

    monkeypatch.setattr(state, "run_boundary_estimation", fake_run)
    summaries, daily, errors = state.run_boundary_batch_estimation(
        pollutant="pm25", start_date="2019-01-01", end_date="2019-01-01",
        boundary_geojson_path=str(boundaries), checkpoint_path=str(checkpoint),
    )
    assert calls == ["Alpha", "Beta"]
    assert summaries["boundary_name"].tolist() == ["Alpha", "Beta"]
    assert daily["boundary_name"].tolist() == ["Alpha", "Beta"]
    assert errors == []
    assert checkpoint.with_suffix(".json.daily.csv").exists()

    calls.clear()
    resumed_summaries, resumed_daily, resumed_errors = state.run_boundary_batch_estimation(
        pollutant="pm25", start_date="2019-01-01", end_date="2019-01-01",
        boundary_geojson_path=str(boundaries), checkpoint_path=str(checkpoint),
    )
    assert calls == []
    assert len(resumed_summaries) == 2
    assert len(resumed_daily) == 2
    assert resumed_errors == []

    changed = json.loads(boundaries.read_text())
    changed["features"][0]["geometry"]["coordinates"][0][1][0] = 2.1
    boundaries.write_text(json.dumps(changed))
    try:
        state.run_boundary_batch_estimation(
            pollutant="pm25", start_date="2019-01-01", end_date="2019-01-01",
            boundary_geojson_path=str(boundaries), checkpoint_path=str(checkpoint),
        )
    except ValueError as exc:
        assert "Checkpoint request does not match" in str(exc)
    else:
        raise AssertionError("Changed boundary geometry reused an incompatible checkpoint")


def test_boundary_batch_rejects_a_second_checkpoint_writer(tmp_path, monkeypatch):
    boundaries = tmp_path / "boundaries.geojson"
    boundaries.write_text(json.dumps({
        "type": "FeatureCollection", "features": [{
            "type": "Feature", "properties": {"name": "Only"},
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
        }],
    }))
    checkpoint = tmp_path / "batch.json"
    state = SessionState()
    monkeypatch.setattr(
        state,
        "run_boundary_estimation",
        lambda **kwargs: pd.DataFrame([{"mean": 1.0, "qc_flag": "PASS"}]),
    )

    with _checkpoint_lock(checkpoint):
        try:
            state.run_boundary_batch_estimation(
                pollutant="pm25", start_date="2019-01-01", end_date="2019-01-01",
                boundary_geojson_path=str(boundaries), checkpoint_path=str(checkpoint),
            )
        except RuntimeError as exc:
            assert "already updating checkpoint" in str(exc)
        else:
            raise AssertionError("A second checkpoint writer was accepted")


def test_boundary_batch_reports_all_unit_failures(tmp_path, monkeypatch):
    boundaries = tmp_path / "boundaries.geojson"
    boundaries.write_text(json.dumps({
        "type": "FeatureCollection", "features": [{
            "type": "Feature", "properties": {"name": "Only"},
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
        }]
    }))
    state = SessionState()
    monkeypatch.setattr(
        state, "run_boundary_estimation",
        lambda **kwargs: (_ for _ in ()).throw(TimeoutError("upstream timeout")),
    )
    summaries, daily, errors = state.run_boundary_batch_estimation(
        pollutant="pm25", start_date="2019-01-01", end_date="2019-01-01",
        boundary_geojson_path=str(boundaries), checkpoint_path=str(tmp_path / "batch.json"),
    )
    assert summaries.empty
    assert daily.empty
    assert errors == [{"boundary_name": "Only", "error": "upstream timeout"}]


def test_boundary_batch_response_is_bounded_and_reports_partial_status(monkeypatch):
    state = SessionState()
    monkeypatch.setattr(state, "ensure_workspace", lambda: None)
    monkeypatch.setattr(
        state,
        "run_boundary_batch_estimation",
        lambda **kwargs: (
            pd.DataFrame([{"boundary_name": f"Unit {index}", "mean": index} for index in range(25)]),
            pd.DataFrame(),
            [{"boundary_name": "Failed", "error": "timeout"}],
        ),
    )
    monkeypatch.setattr(state, "register_result_artifact", lambda *args, **kwargs: "artifact-1")
    result = estimate_boundary_exposure_batch(
        state=state, pollutant="pm25", start_date="2019-01-01", end_date="2019-12-31",
        boundary_geojson_path="boundaries.geojson", researcher_approved=True,
    )
    assert result["status"] == "partial"
    assert len(result["results"]) == 20
    assert result["results_truncated"] is True


def test_self_driving_mode_rejects_contract_drift(tmp_path):
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({
        "schema_version": "aeris-study-contract/v1", "contract_id": "test-study",
        "approved": True, "pollutants": ["pm25"],
    }))
    policy = ExecutionPolicy("self-driving", str(contract_path))

    try:
        policy.authorize("estimate_exposure", {"pollutant": "no2"})
    except PermissionError as exc:
        assert "outside the approved study contract" in str(exc)
    else:
        raise AssertionError("Contract drift was accepted")


def test_accuweather_source_tool_is_public_and_requires_a_key():
    assert "get_accuweather_air_quality" in PUBLIC_TOOL_NAMES
    result = execute(
        SessionState(), "get_accuweather_air_quality", {"latitude": 40.7, "longitude": -74.0}
    )
    assert "Missing AccuWeather API key" in result["error"]


def test_workspace_artifacts_are_durable_and_bounded(tmp_path):
    cohort_path = tmp_path / "cohort.csv"
    cohort_path.write_text(
        "subject_id,latitude,longitude,start_date,end_date\n"
        "a,37.0,-122.0,2024-01-01,2024-01-02\n"
        "b,37.1,-122.1,2024-01-01,2024-01-02\n"
    )
    state = SessionState()
    loaded = execute(state, "load_cohort", {"path": str(cohort_path)})

    assert loaded["workspace_id"].startswith("study_")
    assert loaded["dataset_id"].startswith("dataset_")
    listed = execute(state, "list_artifacts", {})
    assert listed["artifacts"][0]["artifact_id"] == loaded["dataset_id"]
    assert len(listed["artifacts"][0]["sha256"]) == 64

    sample = execute(state, "sample_artifact", {"artifact_id": loaded["dataset_id"], "limit": 1})
    assert sample["total_rows"] == 2
    assert len(sample["rows"]) == 1
    assert sample["truncated"] is True

    missingness = execute(
        state, "query_artifact", {"artifact_id": loaded["dataset_id"], "operation": "missingness"}
    )
    assert missingness["result"]["missingness"]["subject_id"] == 0


def test_interactive_estimation_is_bound_to_approved_plan(tmp_path, monkeypatch):
    cohort_path = tmp_path / "cohort.csv"
    cohort_path.write_text(
        "subject_id,latitude,longitude,start_date,end_date\n"
        "a,37.0,-122.0,2024-01-01,2024-01-02\n"
    )
    state = SessionState()
    execute(state, "load_cohort", {"path": str(cohort_path)})
    monkeypatch.setattr(state, "plan_exposure", lambda **kwargs: {"estimated_calls": 1})
    plan = execute(state, "plan_exposure", {"pollutant": "pm25"})
    approved = execute(state, "approve_exposure_plan", {
        "plan_id": plan["plan_id"], "researcher_approved": True,
    })
    assert approved["status"] == "ok"
    drifted = execute(state, "estimate_exposure", {
        "pollutant": "pm25", "country": "ca", "researcher_approved": True,
        "approved_plan_id": plan["plan_id"],
    })
    assert "differs from the approved exposure plan" in drifted["error"]


def test_study_design_requires_approval_and_persists(tmp_path):
    cohort_path = tmp_path / "cohort.csv"
    cohort_path.write_text(
        "subject_id,latitude,longitude,start_date,end_date\n"
        "a,37.0,-122.0,2024-01-01,2024-01-02\n"
    )
    state = SessionState()
    execute(state, "load_cohort", {"path": str(cohort_path)})
    arguments = {
        "research_question": "Is PM2.5 associated with daily asthma admissions?",
        "outcome": "Daily asthma admissions",
        "pollutant": "pm25",
        "location_unit": "residential ZIP code",
        "time_window": "same day",
        "assignment_rule": "nearest reporting monitor",
        "researcher_approved": False,
    }
    rejected = execute(state, "record_study_design", arguments)
    assert "requires explicit researcher approval" in rejected["error"]

    approved = execute(state, "record_study_design", {**arguments, "researcher_approved": True})
    assert approved["artifact_id"].startswith("study-design_")
    design = execute(state, "describe_artifact", {"artifact_id": approved["artifact_id"]})
    assert design["artifact"]["kind"] == "study-design"
    assert len(state.decision_log) == 2


def test_self_driving_study_design_needs_no_cohort(tmp_path, monkeypatch):
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({
        "schema_version": "aeris-study-contract/v1", "contract_id": "design-study",
        "approved": True, "pollutants": ["pm25"],
    }))
    monkeypatch.setenv("AERIS_EXECUTION_MODE", "self-driving")
    monkeypatch.setenv("AERIS_STUDY_CONTRACT", str(contract_path))
    monkeypatch.setenv("AERIS_WORKSPACE", str(tmp_path / "workspace"))
    result = execute(SessionState(), "record_study_design", {
        "research_question": "Is PM2.5 associated with mortality?",
        "outcome": "Mortality", "pollutant": "pm25", "location_unit": "county",
        "time_window": "2019", "assignment_rule": "county boundary mean",
        "researcher_approved": True,
    })
    assert result["status"] == "ok"
    assert result["artifact_id"].startswith("study-design_")


def test_research_notebook_is_durable_and_replaceable(tmp_path, monkeypatch):
    monkeypatch.setenv("AERIS_WORKSPACE", str(tmp_path / "workspace"))
    state = SessionState()
    arguments = {
        "phase": "recover",
        "objective": "Reconstruct the principal PM2.5 analysis.",
        "invariants": ["PM2.5", "county mortality"],
        "evidence": [{"artifact": "article.pdf", "finding": "Methods recovered."}],
        "hypotheses": ["The archive contains the missing years."],
        "routes_attempted": [], "decisions": [], "unresolved_blockers": [],
        "next_actions": ["Inspect the archive catalog."],
    }
    first = execute(state, "update_research_notebook", arguments)
    assert first["status"] == "ok"
    second = execute(state, "update_research_notebook", {
        **arguments, "next_actions": ["Download the identified objects."],
    })
    assert second["status"] == "ok"
    saved = json.loads((tmp_path / "workspace" / ".aeris" / "research-notebook.json").read_text())
    assert saved["next_actions"] == ["Download the identified objects."]


def test_fidelity_record_requires_evidence_for_autonomous_stop(tmp_path, monkeypatch):
    monkeypatch.setenv("AERIS_PROFILE", "reanalysis")
    cohort_path = tmp_path / "cohort.csv"
    cohort_path.write_text(
        "subject_id,latitude,longitude,start_date,end_date\n"
        "a,37.0,-122.0,2024-01-01,2024-01-02\n"
    )
    state = SessionState()
    execute(state, "load_cohort", {"path": str(cohort_path)})
    base = {
        "study_id": "example", "fidelity_class": "evidenced_stop", "status": "stopped",
        "preserved_dimensions": ["pollutant"], "deviations": [], "evidence_artifacts": [],
    }
    rejected = execute(state, "record_reanalysis_fidelity", base)
    assert "require at least one evidence artifact" in rejected["error"]

    accepted = execute(state, "record_reanalysis_fidelity", {
        **base, "evidence_artifacts": [state.artifacts["cohort"]],
    })
    assert accepted["fidelity"]["fidelity_class"] == "evidenced_stop"
    assert accepted["artifact_id"].startswith("reanalysis-fidelity_")


def test_first_reanalysis_amendment_requires_complete_executable_design(tmp_path, monkeypatch):
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({
        "schema_version": "aeris-study-contract/v2", "contract_id": "design-study",
        "approved": True, "author": "agent", "pollutants": ["pm25"],
        "allowed_fidelity_levels": ["source_substitution"],
        "execution_design": {}, "amendments": [],
    }))
    monkeypatch.setenv("AERIS_EXECUTION_MODE", "self-driving")
    monkeypatch.setenv("AERIS_STUDY_CONTRACT", str(contract_path))
    monkeypatch.setenv("AERIS_WORKSPACE", str(tmp_path / "workspace"))
    monkeypatch.setenv("AERIS_PROFILE", "reanalysis")
    state = SessionState()
    evidence = tmp_path / "probe.json"
    evidence.write_text("{}")
    result = execute(state, "amend_exposure_contract", {
        "changed_dimensions": {"source_strategy": "public_monitor_network"},
        "evidence": [{"artifact": str(evidence), "finding": "Probe completed."}],
        "scientific_justification": "Public monitors preserve the pollutant.",
        "fidelity_impact": "source_substitution",
        "agreement_independent": True,
    })
    assert "complete executable exposure design" in result["error"]
    assert "geographic_representation" in result["error"]
    complete = execute(state, "amend_exposure_contract", {
        "changed_dimensions": {
            "geographic_representation": "administrative_area",
            "assignment_method": "area monitor mean",
            "source_strategy": "public_monitor_network",
            "exposure_metric": "daily PM2.5 mean",
            "daily_aggregation": "daily arithmetic mean",
            "analysis_aggregation": "annual area mean",
            "coverage_policy": {"mode": "report_only"},
            "intended_use": "exposure predictor",
        },
        "evidence": [{"artifact": str(evidence), "finding": "Probe completed."}],
        "scientific_justification": "The design preserves the locked administrative-area estimand.",
        "fidelity_impact": "source_substitution",
        "agreement_independent": True,
    })
    assert complete["status"] == "ok"


def test_self_driving_stop_records_evidence_for_host_review_without_cohort(tmp_path, monkeypatch):
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({
        "schema_version": "aeris-study-contract/v1", "contract_id": "stop-study",
        "approved": True, "pollutants": ["pm25"],
    }))
    monkeypatch.setenv("AERIS_EXECUTION_MODE", "self-driving")
    monkeypatch.setenv("AERIS_STUDY_CONTRACT", str(contract_path))
    monkeypatch.setenv("AERIS_WORKSPACE", str(tmp_path / "workspace"))
    monkeypatch.setenv("AERIS_PROFILE", "reanalysis")
    state = SessionState()
    evidence = tmp_path / "blocker-ledger.json"
    evidence.write_text(
        "Search query: archive.csv mirror. Result: no compatible public file."
    )
    checklist = {
        "outcome_routes_attempted": 3,
        "executable_attempts": [{
            "source_role": "exposure",
            "request_url": "https://example.org/archive.csv",
            "attempt_count": 2,
            "response_status": 404,
            "bytes_returned": 0,
            "schema_or_format_inspection": "HTML response, not CSV data.",
            "evidence_artifact": str(evidence),
        }],
    }
    accepted = execute(state, "record_reanalysis_fidelity", {
        "study_id": "example", "fidelity_class": "evidenced_stop", "status": "stopped",
        "preserved_dimensions": ["pollutant"], "deviations": [],
        "evidence_artifacts": [str(evidence)],
        "recovery_checklist": checklist,
    })
    assert accepted["status"] == "ok"
    assert accepted["fidelity"]["recovery_checklist"] == checklist


def test_self_driving_fidelity_must_be_contract_authorized(tmp_path, monkeypatch):
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({
        "schema_version": "aeris-study-contract/v1", "contract_id": "fit-study",
        "approved": True, "pollutants": ["pm25"],
        "allowed_fidelity_levels": ["source_substitution"],
    }))
    monkeypatch.setenv("AERIS_EXECUTION_MODE", "self-driving")
    monkeypatch.setenv("AERIS_STUDY_CONTRACT", str(contract_path))
    monkeypatch.setenv("AERIS_WORKSPACE", str(tmp_path / "workspace"))
    monkeypatch.setenv("AERIS_PROFILE", "reanalysis")
    state = SessionState()
    base = {
        "study_id": "example", "status": "fitted", "preserved_dimensions": ["pollutant"],
        "deviations": [], "evidence_artifacts": [],
    }
    rejected = execute(state, "record_reanalysis_fidelity", {
        **base, "fidelity_class": "bounded_fit",
    })
    assert "outside the approved study contract" in rejected["error"]
    accepted = execute(state, "record_reanalysis_fidelity", {
        **base, "fidelity_class": "source_substitution_fit",
    })
    assert accepted["status"] == "ok"


def test_fitted_reanalysis_must_report_every_locked_principal_variant(tmp_path, monkeypatch):
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({
        "schema_version": "aeris-study-contract/v2", "contract_id": "variants",
        "approved": True, "pollutants": ["pm25"],
        "allowed_fidelity_levels": ["source_substitution"],
        "scientific_invariants": {
            "principal_variants": ["Day 30 cases", "Day 60 cases"],
        },
    }))
    monkeypatch.setenv("AERIS_EXECUTION_MODE", "self-driving")
    monkeypatch.setenv("AERIS_STUDY_CONTRACT", str(contract_path))
    monkeypatch.setenv("AERIS_WORKSPACE", str(tmp_path / "workspace"))
    monkeypatch.setenv("AERIS_PROFILE", "reanalysis")
    state = SessionState()
    base = {
        "study_id": "example", "status": "fitted",
        "fidelity_class": "source_substitution_fit",
        "preserved_dimensions": ["outcome"], "deviations": [],
        "evidence_artifacts": [],
    }
    rejected = execute(state, "record_reanalysis_fidelity", {
        **base, "reported_variants": ["Day 60 cases"],
    })
    assert "reports fewer variants than the locked target" in rejected["error"]

    accepted = execute(state, "record_reanalysis_fidelity", {
        **base, "reported_variants": ["Day 30 cases", "Day 60 cases"],
    })
    assert accepted["status"] == "ok"


def test_stopped_run_cannot_bypass_recovery_with_fit_class(tmp_path, monkeypatch):
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({
        "schema_version": "aeris-study-contract/v1", "contract_id": "stop-bypass",
        "approved": True, "pollutants": ["pm25"],
    }))
    monkeypatch.setenv("AERIS_EXECUTION_MODE", "self-driving")
    monkeypatch.setenv("AERIS_STUDY_CONTRACT", str(contract_path))
    monkeypatch.setenv("AERIS_WORKSPACE", str(tmp_path / "workspace"))
    monkeypatch.setenv("AERIS_PROFILE", "reanalysis")
    state = SessionState()
    evidence = tmp_path / "blocker.json"
    evidence.write_text("{}")
    result = execute(state, "record_reanalysis_fidelity", {
        "study_id": "example",
        "fidelity_class": "source_substitution_fit",
        "status": "stopped",
        "preserved_dimensions": ["pollutant"],
        "deviations": [],
        "evidence_artifacts": [str(evidence)],
    })
    assert "Stopped runs require fidelity_class=evidenced_stop" in result["error"]
    assert result["terminal_completion_authorized"] is False


def test_fidelity_class_must_cover_recorded_deviations(tmp_path, monkeypatch):
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({
        "schema_version": "aeris-study-contract/v1", "contract_id": "fidelity-class",
        "approved": True, "pollutants": ["pm10"],
        "allowed_fidelity_levels": ["source_substitution", "reduced_adjustment"],
    }))
    monkeypatch.setenv("AERIS_EXECUTION_MODE", "self-driving")
    monkeypatch.setenv("AERIS_STUDY_CONTRACT", str(contract_path))
    monkeypatch.setenv("AERIS_WORKSPACE", str(tmp_path / "workspace"))
    monkeypatch.setenv("AERIS_PROFILE", "reanalysis")
    state = SessionState()
    base = {
        "study_id": "example", "status": "fitted",
        "preserved_dimensions": ["outcome"], "evidence_artifacts": [],
        "deviations": [{
            "dimension": "covariate", "change_type": "covariate_omission",
            "published": "adjusted", "reanalysis": "unadjusted",
            "reason": "covariate unavailable",
        }],
    }
    rejected = execute(state, "record_reanalysis_fidelity", {
        **base, "fidelity_class": "source_substitution_fit",
    })
    assert "cannot contain changes: covariate_omission" in rejected["error"]
    correctly_classified = execute(state, "record_reanalysis_fidelity", {
        **base, "fidelity_class": "reduced_adjustment_fit",
    })
    assert correctly_classified["status"] == "ok"


def test_bounded_fit_records_deviation_without_agent_side_compliance_gate(tmp_path, monkeypatch):
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({
        "schema_version": "aeris-study-contract/v1", "contract_id": "bounded-study",
        "approved": True, "pollutants": ["pm25"],
        "allowed_fidelity_levels": ["bounded"],
    }))
    monkeypatch.setenv("AERIS_EXECUTION_MODE", "self-driving")
    monkeypatch.setenv("AERIS_STUDY_CONTRACT", str(contract_path))
    monkeypatch.setenv("AERIS_WORKSPACE", str(tmp_path / "workspace"))
    monkeypatch.setenv("AERIS_PROFILE", "reanalysis")
    state = SessionState()
    base = {
        "study_id": "example", "status": "fitted", "fidelity_class": "bounded_fit",
        "preserved_dimensions": ["pollutant"],
        "deviations": [{"dimension": "geography", "change_type": "construct_change"}],
        "evidence_artifacts": [],
    }
    recorded = execute(state, "record_reanalysis_fidelity", base)
    assert recorded["status"] == "ok"
    assert list(recorded["fidelity"]["deviations"]) == base["deviations"]


def test_reduced_coverage_fit_defers_compliance_validation_to_host(tmp_path, monkeypatch):
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps({
        "schema_version": "aeris-study-contract/v1", "contract_id": "coverage-study",
        "approved": True, "pollutants": ["pm25"],
        "allowed_fidelity_levels": ["reduced_coverage"],
    }))
    monkeypatch.setenv("AERIS_EXECUTION_MODE", "self-driving")
    monkeypatch.setenv("AERIS_STUDY_CONTRACT", str(contract_path))
    monkeypatch.setenv("AERIS_WORKSPACE", str(tmp_path / "workspace"))
    monkeypatch.setenv("AERIS_PROFILE", "reanalysis")
    state = SessionState()

    recorded = execute(state, "record_reanalysis_fidelity", {
        "study_id": "example", "status": "fitted",
        "fidelity_class": "reduced_coverage_fit",
        "preserved_dimensions": ["pollutant"],
        "deviations": [{"dimension": "period", "change_type": "coverage_subset"}],
        "evidence_artifacts": [],
    })

    assert recorded["status"] == "ok"
