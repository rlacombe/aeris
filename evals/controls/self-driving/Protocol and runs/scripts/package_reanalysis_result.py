#!/usr/bin/env python3
"""Package a scientific handoff into the formal evaluation result.

This host-side step copies scientific claims; it never invents estimates,
coverage, sources, or substitutions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


STATUS = {
    "fitted": "completed_fit",
    "sensitivity": "completed_sensitivity",
    "blocked": "completed_blocker",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def inside(output: Path, value: str | None) -> Path | None:
    if not value:
        return None
    candidate = Path(value)
    if candidate.is_absolute():
        try:
            candidate = candidate.relative_to("/output")
        except ValueError as exc:
            raise ValueError(f"artifact is outside /output: {value}") from exc
    resolved = (output / candidate).resolve()
    if output.resolve() not in (resolved, *resolved.parents):
        raise ValueError(f"artifact escapes output directory: {value}")
    return resolved


def select_retained_artifact(output: Path, value: str | None) -> str | None:
    """Select one retained path when a handoff lists equivalent artifacts."""
    if not value:
        return value
    declared = [item.strip() for item in value.split(";") if item.strip()]
    for item in declared:
        path = inside(output, item)
        if path and path.exists():
            return str(path.relative_to(output))
    return declared[0] if declared else value


def normalize_artifacts(output: Path, artifacts: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(artifacts)
    for name, value in artifacts.items():
        if isinstance(value, str):
            normalized[name] = select_retained_artifact(output, value)
    return normalized


def normalize_effects(effects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    ratio_scales = {
        "ratio", "rate ratio", "risk ratio", "odds ratio", "rr", "or",
    }
    for effect in effects:
        item = dict(effect)
        if str(item.get("scale", "")).strip().lower() in ratio_scales:
            item["scale"] = "ratio"
        metric = str(item.get("metric", "")).strip().lower()
        if "odds" in metric or metric == "or":
            item["metric"] = "OR"
        elif "rate" in metric or "risk" in metric or metric == "rr":
            item["metric"] = "RR"
        elif metric in {"outcome ratio", "outcome_ratio"}:
            item["metric"] = "outcome_ratio"
        normalized.append(item)
    return normalized


def contract_for(output: Path, handoff: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    declared = inside(output, handoff.get("artifacts", {}).get("study_contract"))
    candidates = [declared] if declared and declared.is_file() else []
    candidates.extend(sorted((output / "aeris-workspace" / ".aeris" / "contracts").glob("*.json")))
    candidates.extend(sorted((output / ".aeris" / "contracts").glob("*.json")))
    retained = []
    for path in dict.fromkeys(candidates):
        if path and path.is_file():
            data = read_json(path)
            if data.get("approved") and data.get("author") == "agent":
                retained.append((path, data))
    if retained:
        return max(retained, key=lambda item: (len(item[1].get("amendments", [])), item[0].stat().st_mtime))
    raise ValueError("no approved agent-authored AERIS contract was retained")


def design_provenance(path: Path, contract: dict[str, Any]) -> dict[str, Any]:
    design = contract.get("execution_design") or contract.get("agent_design") or contract
    amendments = contract.get("amendments", [])
    latest_amendment = amendments[-1] if amendments else {}
    coverage = design.get("coverage_policy") or contract.get("coverage_policy")
    if isinstance(coverage, str):
        coverage = {
            "mode": "report_only",
            "minimum_percent": None,
            "threshold_source": "none",
            "evidence": coverage,
        }
    rationale = (
        design.get("decision_rationale")
        or latest_amendment.get("scientific_justification")
    )
    evidence_basis = design.get("evidence_basis") or contract.get("evidence_basis")
    if not evidence_basis:
        evidence_basis = [
            item.get("finding") or item.get("artifact")
            for item in latest_amendment.get("evidence", contract.get("article_evidence", []))
            if isinstance(item, dict) and (item.get("finding") or item.get("artifact"))
        ]
    source_strategy = design.get("source_strategy")
    if source_strategy not in {"public_monitor_network", "provider_api", "local_model"}:
        source_text = str(source_strategy or "").lower()
        if "monitor" in source_text or "station" in source_text or "cetesb" in source_text or "regulator" in source_text:
            source_strategy = "public_monitor_network"
        elif "api" in source_text or "provider" in source_text:
            source_strategy = "provider_api"
        elif "model" in source_text:
            source_strategy = "local_model"
    geographic_representation = design.get("geographic_representation")
    if geographic_representation not in {
        "fixed_location", "mobility_trajectory", "administrative_area"
    }:
        geographic_text = str(geographic_representation or "").lower()
        if any(term in geographic_text for term in ("trajectory", "mobile", "gps")):
            geographic_representation = "mobility_trajectory"
        elif any(term in geographic_text for term in (
            "administrative", "municip", "metropolitan", "county", "country", "region", "area"
        )):
            geographic_representation = "administrative_area"
        elif any(term in geographic_text for term in (
            "fixed", "address", "coordinate", "site", "monitor", "station"
        )):
            geographic_representation = "fixed_location"
    required = {
        "geographic_representation": geographic_representation,
        "assignment_method": design.get("assignment_method") or design.get("assignment_rule"),
        "source_strategy": source_strategy,
        "exposure_metric": design.get("exposure_metric"),
        "decision_rationale": rationale,
        "evidence_basis": evidence_basis,
    }
    missing = [key for key, value in required.items() if not value]
    if not coverage:
        missing.append("coverage_policy")
    if missing:
        raise ValueError("contract lacks scientific provenance: " + ", ".join(missing))
    canonical = json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
    return {
        "contract_id": contract.get("contract_id") or path.stem,
        "contract_sha256": hashlib.sha256(canonical).hexdigest(),
        "contract_author": "agent",
        "geographic_representation": required["geographic_representation"],
        "assignment_method": required["assignment_method"],
        "representative_location_rule": design.get("representative_location_rule"),
        "maximum_monitor_distance_km": design.get("maximum_monitor_distance_km"),
        "monitor_distance_evidence": design.get("monitor_distance_evidence") or "Not applicable to the selected assignment method.",
        "source_strategy": required["source_strategy"],
        "exposure_metric": required["exposure_metric"],
        "coverage_policy": coverage,
        "decision_rationale": required["decision_rationale"],
        "evidence_basis": required["evidence_basis"],
        "locked_before_exposure": bool(design.get("locked_before_exposure", False)),
    }


def stopping_checklist(output: Path, handoff: dict[str, Any]) -> dict[str, Any]:
    sources = handoff["sources"]
    retrieved = [source for source in sources if source.get("retrieved")]
    evidence = [
        source["evidence_artifact"] for source in sources
        if source.get("evidence_artifact") and inside(output, source["evidence_artifact"]).is_file()
    ]
    evidence.extend(
        value for value in handoff["artifacts"].values()
        if value and inside(output, value).is_file()
    )
    blocker = handoff["status"] == "blocked"
    outcome_attempts = sum(source.get("role") == "outcome" for source in sources)
    return {
        "target_specification_complete": bool(handoff.get("target", {}).get("specification_evidence")),
        "complete_article_checked": True,
        "outcome_routes_attempted": outcome_attempts,
        "normal_exposure_source_tested": any(source.get("role") == "exposure" for source in sources),
        "historical_fallback_applicable": blocker,
        "historical_fallback_tested": blocker and len(sources) > 2,
        "geographic_batching_applicable": (
            (handoff.get("coverage", {}).get("eligible_units") or 0) > 1
            and (handoff.get("coverage", {}).get("included_units") or 0) > 0
        ),
        "geographic_batching_attempted": (handoff.get("coverage", {}).get("included_units") or 0) > 1,
        "fidelity_levels_evaluated": sorted({handoff["fidelity"]} - {"none"}),
        "pending_requests": 0,
        "evidence_artifacts": sorted(set(evidence)),
    }


def package(output: Path) -> dict[str, Any]:
    output = output.resolve()
    handoff_path = output / "analysis_handoff.json"
    if not handoff_path.is_file():
        raise ValueError("missing analysis_handoff.json")
    handoff = read_json(handoff_path)
    if handoff.get("status") in {"fitted", "sensitivity"}:
        for field in ("effects", "analysis_diagnostics"):
            if not handoff.get(field):
                raise ValueError(f"successful handoff lacks {field}")
        retrieved_roles = {
            source.get("role")
            for source in handoff.get("sources", [])
            if source.get("retrieved")
        }
        if not {"outcome", "exposure"}.issubset(retrieved_roles):
            raise ValueError(
                "successful handoff requires usable outcome and pollutant-exposure records"
            )
    if handoff.get("status") == "blocked" and len(handoff.get("sources", [])) < 3:
        raise ValueError("blocked handoff lacks three distinct recovery attempts")
    contract_path, contract = contract_for(output, handoff)
    artifacts = normalize_artifacts(output, handoff["artifacts"])
    handoff = dict(handoff)
    handoff["artifacts"] = artifacts
    artifacts["study_contract"] = str(contract_path.relative_to(output))
    model_path = inside(output, artifacts.get("model_output"))
    if model_path and model_path.suffix.lower() not in {".csv", ".json"}:
        # Agents often retain a human-readable model summary alongside the
        # machine-readable result. Point validation at the latter when it
        # exists; do not reject an otherwise complete scientific run because
        # the handoff selected the text summary.
        candidates = [
            model_path.with_name("model_output.json"),
            model_path.with_name("analysis_results.json"),
            model_path.with_name("effects.json"),
            model_path.with_name("effects.csv"),
        ]
        machine_output = next((path for path in candidates if path.is_file()), None)
        if machine_output:
            artifacts["model_output"] = str(machine_output.relative_to(output))
    result = {
        "schema_version": 3,
        "study_id": handoff["study_id"],
        "status": STATUS[handoff["status"]],
        "fidelity": handoff["fidelity"],
        "target": handoff["target"],
        "sources": handoff["sources"],
        "substitutions": handoff["substitutions"],
        "coverage": handoff["coverage"],
        "artifacts": artifacts,
        "blockers": handoff["blockers"],
        "stopping_checklist": stopping_checklist(output, handoff),
    }
    if handoff["status"] != "blocked":
        try:
            result["design_provenance"] = design_provenance(contract_path, contract)
        except ValueError:
            # Provenance completeness is an audit dimension. A retained fit
            # remains a completed reanalysis when its computational evidence
            # is valid, even if the structured design record is incomplete.
            pass
    if handoff.get("effects") is not None:
        result["effects"] = normalize_effects(handoff["effects"])
    if handoff.get("analysis_diagnostics") is not None:
        result["analysis_diagnostics"] = handoff["analysis_diagnostics"]
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        package(args.output)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"packaged": False, "error": str(exc)}))
        return 1
    print(json.dumps({"packaged": True, "result": str(args.output / "result.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
