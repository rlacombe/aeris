#!/usr/bin/env python3
"""Apply semantic completion rules beyond JSON-schema validation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path


FIT_STATUSES = {"completed_fit", "completed_sensitivity"}
ALL_LEVELS = {
    "matched", "source_substitution", "reduced_coverage", "reduced_adjustment",
    "bounded", "supported_sensitivity",
}

COVERAGE_COLUMNS = {
    "unit_name", "window_start", "window_end", "coverage_pct",
    "inclusion_status", "exclusion_reason", "boundary_source", "boundary_level",
}

EXECUTABLE_SUFFIXES = {
    ".py", ".r", ".sh", ".ipynb", ".jl", ".do", ".js", ".mjs", ".ts"
}


def _normalized_pollutants(text: str) -> set[str]:
    value = text.lower().replace("₂", "2").replace("₁₀", "10").replace("-", " ")
    aliases = {
        "pm25": ("pm2.5", "pm25", "fine particulate"),
        "pm10": ("pm10", "coarse particulate"),
        "no2": ("no2", "nitrogen dioxide"),
        "o3": ("o3", "ozone"),
        "so2": ("so2", "sulfur dioxide", "sulphur dioxide"),
        "co": ("carbon monoxide",),
    }
    return {name for name, forms in aliases.items() if any(form in value for form in forms)}


def validate_article_target(output: Path, result: dict) -> list[str]:
    """Audit the agent result against an article-derived target hidden from the run."""
    manifest = json.loads((output / "run_manifest.json").read_text())
    slug = manifest.get("study", {}).get("slug")
    pmid = str(manifest.get("study", {}).get("pmid", ""))
    if not slug or not pmid:
        return []
    root = output.parents[2]
    brief_path = root / "briefs" / f"{pmid}-{slug}.json"
    if not brief_path.is_file():
        return []
    target = json.loads(brief_path.read_text()).get("target", {})
    contrasts = target.get("comparison_contrasts") or []
    expected_pollutants = _normalized_pollutants(" ".join(contrasts))
    final_text = json.dumps({
        "target": result.get("target", {}),
        "effects": result.get("effects", []),
    })
    final_pollutants = _normalized_pollutants(final_text)
    missing = sorted(expected_pollutants - final_pollutants)
    errors = []
    if missing:
        errors.append(
            "article-target audit: missing principal pollutant(s): " + ", ".join(missing)
        )
    if result.get("status") in FIT_STATUSES and len(result.get("effects") or []) < len(contrasts):
        errors.append(
            f"article-target audit: {len(contrasts)} principal contrasts are required; "
            f"the result reports {len(result.get('effects') or [])}"
        )
    return errors


def artifact_exists(output: Path, value: str | None) -> bool:
    if not value:
        return False
    candidate = Path(value)
    if len(candidate.parts) == 1 and "/" not in value and not candidate.suffix:
        matches = list(output.glob(f"**/.aeris/artifacts/{value}.json"))
        return len(matches) == 1 and matches[0].is_file()
    if candidate.is_absolute() and candidate.parts[:2] == ("/", "output"):
        candidate = output.joinpath(*candidate.parts[2:])
    elif not candidate.is_absolute():
        candidate = output / candidate
    try:
        candidate.resolve().relative_to(output.resolve())
    except ValueError:
        return False
    return candidate.is_file()


def artifact_path(output: Path, value: str | None) -> Path | None:
    if not value:
        return None
    candidate = Path(value)
    if candidate.is_absolute() and candidate.parts[:2] == ("/", "output"):
        candidate = output.joinpath(*candidate.parts[2:])
    elif not candidate.is_absolute():
        candidate = output / candidate
    try:
        candidate.resolve().relative_to(output.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def code_artifact_exists(output: Path, value: str | None) -> bool:
    if artifact_exists(output, value):
        return True
    if not value:
        return False
    candidate = Path(value)
    if candidate.is_absolute() and candidate.parts[:2] == ("/", "output"):
        candidate = output.joinpath(*candidate.parts[2:])
    elif not candidate.is_absolute():
        candidate = output / candidate
    try:
        candidate.resolve().relative_to(output.resolve())
    except ValueError:
        return False
    return candidate.is_dir() and any(item.is_file() for item in candidate.rglob("*"))


def executable_code_exists(output: Path, value: str | None) -> bool:
    path = artifact_path(output, value)
    if path is not None:
        return path.suffix.lower() in EXECUTABLE_SUFFIXES and path.stat().st_size > 0
    if not value:
        return False
    candidate = Path(value)
    if candidate.is_absolute() and candidate.parts[:2] == ("/", "output"):
        candidate = output.joinpath(*candidate.parts[2:])
    elif not candidate.is_absolute():
        candidate = output / candidate
    try:
        candidate.resolve().relative_to(output.resolve())
    except ValueError:
        return False
    return candidate.is_dir() and any(
        item.is_file() and item.suffix.lower() in EXECUTABLE_SUFFIXES and item.stat().st_size > 0
        for item in candidate.rglob("*")
    )


def numeric_model_values(path: Path) -> list[float]:
    """Read retained model numbers without assuming a study-specific format."""
    values: list[float] = []

    def visit(value):
        if isinstance(value, bool):
            return
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            values.append(float(value))
        elif isinstance(value, dict):
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    if path.suffix.lower() == ".json":
        visit(json.loads(path.read_text()))
    elif path.suffix.lower() == ".csv":
        with path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                for value in row.values():
                    try:
                        number = float(value)
                    except (TypeError, ValueError):
                        continue
                    if math.isfinite(number):
                        values.append(number)
    elif path.suffix.lower() in {".txt", ".md"}:
        for value in re.findall(r"(?<![A-Za-z])[-+]?(?:\d+\.\d+|\d+)(?:[eE][-+]?\d+)?", path.read_text()):
            number = float(value)
            if math.isfinite(number):
                values.append(number)
    return values


def validate_computational_artifacts(output: Path, result: dict) -> list[str]:
    """Cross-check reported fit metadata against retained executable artifacts."""
    errors: list[str] = []
    artifacts = result.get("artifacts", {})
    if not executable_code_exists(output, artifacts.get("code")):
        errors.append("code artifact contains no executable analysis source")

    panel_path = artifact_path(output, artifacts.get("analysis_panel"))
    observations = (result.get("analysis_diagnostics") or {}).get("observations", 0)
    if panel_path is not None and panel_path.suffix.lower() == ".csv":
        try:
            with panel_path.open(newline="") as handle:
                panel_rows = sum(1 for _ in csv.DictReader(handle))
        except (OSError, csv.Error) as exc:
            errors.append(f"could not read analysis_panel: {exc}")
        else:
            if panel_rows < observations:
                errors.append(
                    f"analysis_panel has {panel_rows} rows; fitted result reports {observations}"
                )
    else:
        errors.append("analysis_panel must be a readable CSV file")

    model_path = artifact_path(output, artifacts.get("model_output"))
    if model_path is None or model_path.suffix.lower() not in {".csv", ".json", ".txt", ".md"}:
        errors.append("model_output must be a readable CSV, JSON, or text file")
        return errors
    try:
        values = numeric_model_values(model_path)
    except (OSError, csv.Error, json.JSONDecodeError) as exc:
        errors.append(f"could not read model_output: {exc}")
        return errors
    if not values:
        errors.append("model_output contains no finite numeric values")
        return errors
    for effect in result.get("effects", []):
        reported = [effect.get(field) for field in ("estimate", "ci_low", "ci_high")]
        native = [
            effect.get(field) for field in ("native_estimate", "native_ci_low", "native_ci_high")
        ]
        def retained(series: list[object]) -> bool:
            text_output = model_path.suffix.lower() in {".txt", ".md"}
            # Handoffs commonly round machine-readable estimates to six
            # decimals. Verify numerical agreement without requiring an
            # identical serialization of the same fitted result.
            rel_tol = 5e-3 if text_output else 1e-6
            abs_tol = 5e-4 if text_output else 5e-7
            return all(
                value is None or any(
                    math.isclose(float(value), candidate, rel_tol=rel_tol, abs_tol=abs_tol)
                    for candidate in values
                )
                for value in series
            )
        if not retained(reported) and not retained(native):
            errors.append(
                f"{effect.get('label', 'unlabeled effect')}: effect and interval "
                "are absent from model_output"
            )
    return errors


def registered_fidelity_artifact(output: Path, value: str | None) -> Path | None:
    """Resolve an MCP-registered fidelity record and verify its manifest."""
    path = artifact_path(output, value)
    if path is None and value:
        matches = list(output.glob(f"**/.aeris/artifacts/{value}.json"))
        path = matches[0] if len(matches) == 1 else None
    if path is None:
        return None
    expected_parent = output / "aeris-workspace" / ".aeris" / "artifacts"
    try:
        path.resolve().relative_to(expected_parent.resolve())
    except ValueError:
        return None
    if not path.name.startswith("reanalysis-fidelity_"):
        return None
    manifest_path = path.with_suffix(".manifest.json")
    if not manifest_path.is_file():
        return None
    try:
        payload = json.loads(path.read_text())
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    required = {"study_id", "fidelity_class", "status", "preserved_dimensions", "deviations"}
    provenance = manifest.get("provenance", {})
    if not required.issubset(payload):
        return None
    if manifest.get("kind") != "reanalysis-fidelity":
        return None
    if manifest.get("artifact_id") != path.stem:
        return None
    if manifest.get("sha256") != hashlib.sha256(path.read_bytes()).hexdigest():
        return None
    if provenance.get("mode") != "self-driving" or provenance.get("planning_phase") is not False:
        return None
    if provenance.get("contract_author") != "agent" or not provenance.get("contract_sha256"):
        return None
    return path


def fidelity_artifact_exists(output: Path, value: str | None) -> bool:
    """Require a complete fidelity record registered by the AERIS MCP tool."""
    return registered_fidelity_artifact(output, value) is not None


def fidelity_payload(output: Path, value: str | None) -> dict:
    path = registered_fidelity_artifact(output, value)
    if path is None:
        return {}
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def validate_coverage_diagnostics(output: Path, value: str | None, coverage: dict) -> list[str]:
    path = artifact_path(output, value)
    if path is None:
        return ["missing or external required artifact: coverage_diagnostics"]
    if path.suffix.lower() != ".csv":
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return [f"could not read coverage_diagnostics: {exc}"]
        expected = [
            str(value) for name in ("eligible_times", "included_times")
            if (value := coverage.get(name)) is not None
        ]
        normalized_text = text.replace(",", "")
        if len(text) < 100 or any(value not in normalized_text for value in expected):
            return [
                "aggregate coverage_diagnostics must explain eligible and included time coverage"
            ]
        return []
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = COVERAGE_COLUMNS.difference(reader.fieldnames or [])
            rows = list(reader)
    except (OSError, csv.Error) as exc:
        return [f"could not read coverage_diagnostics: {exc}"]
    errors = []
    if missing:
        return ["coverage_diagnostics lacks columns: " + ", ".join(sorted(missing))]
    names = [row["unit_name"].strip() for row in rows if row["unit_name"].strip()]
    if len(names) != len(set(names)):
        errors.append("coverage_diagnostics contains duplicate unit names")
    eligible = coverage.get("eligible_units")
    if eligible is not None and len(set(names)) != eligible:
        errors.append(
            f"coverage_diagnostics has {len(set(names))} unique units; expected {eligible}"
        )
    windows = {(row["window_start"], row["window_end"]) for row in rows}
    if len(windows) != 1:
        errors.append("coverage_diagnostics does not use one complete requested window")
    brief_path = output / "frozen-inputs" / "study-brief.json"
    if brief_path.is_file():
        authorization = json.loads(brief_path.read_text()).get("authorization", {})
        expected_window = {
            (authorization.get("exposure_start"), authorization.get("exposure_end"))
        }
        if windows != expected_window:
            errors.append("coverage_diagnostics window differs from the authorized window")
    statuses = [row["inclusion_status"].strip().lower() for row in rows]
    allowed_statuses = {"include", "included", "pass", "exclude", "excluded", "fail"}
    if any(status not in allowed_statuses for status in statuses):
        errors.append("coverage_diagnostics contains an unknown inclusion status")
    included = sum(status in {"include", "included", "pass"} for status in statuses)
    if coverage.get("included_units") is not None and included != coverage["included_units"]:
        errors.append(
            f"coverage_diagnostics marks {included} included units; "
            f"result reports {coverage['included_units']}"
        )
    for row in rows:
        try:
            percentage = float(row["coverage_pct"])
        except (TypeError, ValueError):
            errors.append(f"{row['unit_name']}: coverage_pct is not numeric")
        else:
            if not 0 <= percentage <= 100:
                errors.append(f"{row['unit_name']}: coverage_pct falls outside 0--100")
        status = row["inclusion_status"].strip().lower()
        if status in {"exclude", "excluded", "fail"} and not row["exclusion_reason"].strip():
            errors.append(f"{row['unit_name']}: excluded unit lacks a reason")
        if not row["boundary_source"].strip() or not row["boundary_level"].strip():
            errors.append(f"{row['unit_name']}: boundary provenance is incomplete")
    return errors


def validate_agent_contract(output: Path, result: dict) -> list[str]:
    errors = []
    contract_path = artifact_path(output, result.get("artifacts", {}).get("study_contract"))
    if contract_path is None:
        candidates = sorted((output / "aeris-workspace" / ".aeris" / "contracts").glob("*.json"))
        contract_path = candidates[-1] if candidates else None
    if contract_path is None or not contract_path.is_file():
        return ["missing immutable agent-authored study contract"]
    try:
        contract = json.loads(contract_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [f"could not read agent-authored study contract: {exc}"]
    canonical = json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(canonical).hexdigest()
    provenance = result.get("design_provenance", {})
    design = contract.get("execution_design", contract.get("agent_design", {}))
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
    if contract.get("author") != "agent":
        errors.append("self-driving result does not use an agent-authored contract")
    if result.get("status") != "completed_blocker":
        comparisons = {
            "contract_id": contract.get("contract_id"),
            "contract_sha256": digest,
            "contract_author": contract.get("author"),
            "geographic_representation": geographic_representation,
            "maximum_monitor_distance_km": design.get("maximum_monitor_distance_km"),
            "source_strategy": source_strategy,
        }
        for name, expected in comparisons.items():
            if provenance.get(name) != expected:
                errors.append(f"design_provenance {name} differs from the locked contract")
        required_design = {
            "geographic_representation", "assignment_method", "source_strategy",
            "exposure_metric", "daily_aggregation", "analysis_aggregation",
            "coverage_policy", "intended_use",
        }
        missing = sorted(name for name in required_design if not design.get(name))
        if missing:
            errors.append("locked contract lacks principal-analysis fields: " + ", ".join(missing))
    if contract.get("scientific_invariants") and not contract.get("amendments"):
        errors.append("reanalysis contract lacks an evidence-backed executable-design amendment")
    invariants = contract.get("scientific_invariants", {})
    target_units = invariants.get("target_geographic_units")
    if isinstance(target_units, int):
        eligible_units = result.get("coverage", {}).get("eligible_units")
        if eligible_units != target_units:
            errors.append(
                f"coverage eligible_units {eligible_units} differs from the locked "
                f"target count {target_units}"
            )
    result_text = json.dumps({
        "target": result.get("target", {}),
        "effects": result.get("effects", []),
        "design": provenance,
    }).lower()
    substitutions = result.get("substitutions", [])
    changed_dimensions = {
        (str(item.get("dimension", "")).lower(), str(item.get("change_type", "")))
        for item in substitutions if isinstance(item, dict)
    }
    contrast = str(invariants.get("principal_contrast", ""))
    date_pattern = re.compile(
        r"\b(?:[1-9]|[12]\d|3[01])\s+(?:january|february|march|april|may|june|"
        r"july|august|september|october|november|december)\b",
        re.IGNORECASE,
    )
    expected_dates = {match.group(0).lower() for match in date_pattern.finditer(contrast)}
    if any(date not in result_text for date in expected_dates) and not any(
        dimension in {"outcome", "period", "contrast"}
        and change_type in {"coverage_subset", "construct_change"}
        for dimension, change_type in changed_dimensions
    ):
        errors.append("final analysis does not preserve or disclose the principal contrast date")
    expected_pollutants = {
        str(value).lower().replace(".", "") for value in invariants.get("pollutants", [])
    }
    if any(value not in result_text.replace(".", "") for value in expected_pollutants) and not any(
        dimension in {"exposure", "pollutant"} and change_type == "construct_change"
        for dimension, change_type in changed_dimensions
    ):
        errors.append("final analysis changes the locked pollutant construct without disclosure")
    if "adjusted" in contrast.lower() and not result.get("target", {}).get("covariates") and not any(
        dimension == "covariate" and change_type == "covariate_omission"
        for dimension, change_type in changed_dimensions
    ):
        errors.append("final analysis omits the locked adjustment without disclosure")
    # Exploratory exposure probes may precede the executable-design amendment.
    # Scientific invariants must still be locked before any exposure retrieval.
    invariant_contract = output / "aeris-workspace" / ".aeris" / "contracts" / "reanalysis-invariants.json"
    exposure_artifacts = list((output / "aeris-workspace").glob(".aeris/artifacts/exposure_*.json"))
    if exposure_artifacts and invariant_contract.is_file() and any(
        item.stat().st_mtime_ns < invariant_contract.stat().st_mtime_ns
        for item in exposure_artifacts
    ):
        errors.append("an exposure artifact predates the locked scientific invariants")
    return errors


def validate(output: Path, minimum_blocker_seconds: int) -> list[str]:
    result = json.loads((output / "result.json").read_text())
    manifest = json.loads((output / "run_manifest.json").read_text())
    errors: list[str] = []
    status = result["status"]
    artifacts = result["artifacts"]
    required = ["code", "source_manifest", "decision_log", "research_notebook", "fidelity_record"]
    if result.get("schema_version") == 3:
        errors.extend(validate_agent_contract(output, result))
        errors.extend(validate_article_target(output, result))
    if status in FIT_STATUSES:
        required += ["exposure", "analysis_panel", "model_output"]
    if status == "completed_blocker":
        required += ["blocker_ledger"]
    for name in required:
        exists = (
            code_artifact_exists(output, artifacts.get(name))
            if name == "code"
            else fidelity_artifact_exists(output, artifacts.get(name))
            if name == "fidelity_record"
            else artifact_exists(output, artifacts.get(name))
        )
        if not exists:
            errors.append(f"missing or external required artifact: {name}")

    fidelity = fidelity_payload(output, artifacts.get("fidelity_record"))
    if status in FIT_STATUSES and fidelity:
        expected_classes = {
            "matched": {"matched_fit"},
            "source_substitution": {"source_substitution_fit"},
            "reduced_coverage": {"reduced_coverage_fit"},
            "reduced_adjustment": {"reduced_adjustment_fit"},
            "bounded": {"bounded_fit", "bounded_proxy_fit"},
            "supported_sensitivity": {"supported_sensitivity_fit"},
        }[result["fidelity"]]
        if fidelity.get("status") != "fitted":
            errors.append("fitted result does not have a fitted AERIS fidelity record")
        if fidelity.get("fidelity_class") not in expected_classes:
            errors.append("result fidelity differs from the AERIS fidelity record")
        result_changes = sorted(
            str(item.get("change_type", ""))
            for item in result.get("substitutions", []) if isinstance(item, dict)
        )
        fidelity_changes = sorted(
            str(item.get("change_type", ""))
            for item in fidelity.get("deviations", []) if isinstance(item, dict)
        )
        if result_changes != fidelity_changes:
            errors.append("result substitutions differ from the AERIS fidelity record")

    coverage = result["coverage"]
    for included, eligible in (
        (coverage["included_units"], coverage["eligible_units"]),
        (coverage["included_times"], coverage["eligible_times"]),
    ):
        if included is not None and eligible is not None and included > eligible:
            errors.append("included coverage exceeds eligible coverage")

    if status in FIT_STATUSES:
        errors.extend(validate_coverage_diagnostics(
            output, artifacts.get("coverage_diagnostics"), coverage
        ))
        errors.extend(validate_computational_artifacts(output, result))
        effects = result.get("effects") or []
        if not any(effect.get("primary") for effect in effects):
            errors.append("fitted result must identify at least one primary effect")
        labels = [effect.get("label") for effect in effects]
        if len(labels) != len(set(labels)):
            errors.append("effect labels must be unique")
        diagnostics = result.get("analysis_diagnostics") or {}
        observations = diagnostics.get("observations", 0)
        parameters = diagnostics.get("estimated_parameters", 0)
        if observations <= parameters:
            errors.append("model has no residual degrees of freedom")
        if diagnostics.get("exposure_unique_values", 0) < 2:
            errors.append("fitted exposure is constant")
        if diagnostics.get("outcome_unique_values", 0) < 2:
            errors.append("fitted outcome is constant")
        if diagnostics.get("joined_rows", 0) < observations:
            errors.append("joined row count is smaller than fitted observations")
        if diagnostics.get("contrast_transformation_verified") is not True:
            errors.append("contrast transformation was not verified in executable code")
        expected_variants = [
            variant for variant in fidelity.get("reported_variants", [])
            if not any(marker in str(variant).lower() for marker in (
                "not identifiable", "unavailable", "not reported"
            ))
        ]
        reported_variants = diagnostics.get("reported_variants", [])
        if len(reported_variants) < len(expected_variants):
            errors.append("analysis diagnostics omit locked principal variants")
        if len(effects) < len(expected_variants):
            errors.append(
                "reported variants exceed numerical effects; unavailable variants "
                "must remain limitations rather than completed results"
            )
        for effect in effects:
            label = effect.get("label", "unlabeled effect")
            numeric = [effect.get("estimate"), effect.get("ci_low"), effect.get("ci_high")]
            if any(value is not None and not math.isfinite(value) for value in numeric):
                errors.append(f"{label}: effect estimate or confidence interval is non-finite")
            estimate, low, high = numeric
            if low is not None and high is not None and low > high:
                errors.append(f"{label}: confidence interval lower bound exceeds upper bound")
            if estimate is not None and low is not None and estimate < low:
                errors.append(f"{label}: effect estimate falls below its confidence interval")
            if estimate is not None and high is not None and estimate > high:
                errors.append(f"{label}: effect estimate exceeds its confidence interval")
            if any(value is not None and value <= 0 for value in numeric):
                errors.append(f"{label}: comparable OR or RR values must be positive")
            native = [
                effect.get("native_estimate"), effect.get("native_ci_low"),
                effect.get("native_ci_high"),
            ]
            if any(value is not None and not math.isfinite(value) for value in native):
                errors.append(f"{label}: native effect or confidence interval is non-finite")
            native_estimate, native_low, native_high = native
            if native_low is not None and native_high is not None and native_low > native_high:
                errors.append(f"{label}: native confidence interval bounds are reversed")
            if native_estimate is not None and native_low is not None and native_estimate < native_low:
                errors.append(f"{label}: native effect falls below its confidence interval")
            if native_estimate is not None and native_high is not None and native_estimate > native_high:
                errors.append(f"{label}: native effect exceeds its confidence interval")
            native_scale = str(effect.get("native_scale", "")).lower()
            additive_markers = ("deaths per", "absolute", "additive", "linear slope")
            if (
                effect.get("scale") == "ratio"
                and native_estimate is not None
                and any(marker in native_scale for marker in additive_markers)
            ):
                if math.isclose(
                    float(effect["estimate"]), math.exp(float(native_estimate)),
                    rel_tol=1e-6, abs_tol=1e-9,
                ):
                    errors.append(
                        f"{label}: an additive outcome slope cannot be exponentiated into a ratio"
                    )
                if float(effect["estimate"]) > 20:
                    errors.append(
                        f"{label}: implausible ratio from additive outcome slope; retain the "
                        "native slope or use an explicit reference-outcome transformation"
                    )
        retrieved_roles = {
            source["role"] for source in result["sources"] if source.get("retrieved")
        }
        if not {"outcome", "exposure"}.issubset(retrieved_roles):
            errors.append("fit lacks retrieved outcome and exposure sources")
        if result["fidelity"] == "source_substitution" and not any(
            item["dimension"] == "exposure" for item in result["substitutions"]
        ):
            errors.append("source-substitution fit does not document an exposure substitution")
        change_types = {item["change_type"] for item in result["substitutions"]}
        if "construct_change" in change_types and not artifact_exists(
            output, artifacts.get("boundary_route_evidence")
        ):
            errors.append("geographic construct change lacks boundary_route_evidence")
        allowed_changes = {
            "matched": set(),
            "source_substitution": {"source"},
            "reduced_coverage": {"source", "coverage_subset"},
            "reduced_adjustment": {"source", "coverage_subset", "covariate_omission"},
            "bounded": {"source", "coverage_subset", "covariate_omission", "construct_change"},
            "supported_sensitivity": {
                "source", "coverage_subset", "covariate_omission", "construct_change"
            },
        }[result["fidelity"]]
        unsupported_changes = change_types.difference(allowed_changes)
        if unsupported_changes:
            errors.append(
                f"fidelity {result['fidelity']} cannot contain changes: "
                + ", ".join(sorted(unsupported_changes))
            )

    if status == "completed_blocker":
        check = result["stopping_checklist"]
        fidelity = fidelity_payload(output, artifacts.get("fidelity_record"))
        recovery = fidelity.get("recovery_checklist", {})
        started = manifest.get("started_at")
        ended = manifest.get("ended_at")
        if started and ended:
            from datetime import datetime
            seconds = (datetime.fromisoformat(ended) - datetime.fromisoformat(started)).total_seconds()
            if seconds < minimum_blocker_seconds:
                errors.append(
                    f"blocker declared after {seconds:.0f}s; minimum is {minimum_blocker_seconds}s"
                )
        if check["historical_fallback_applicable"] and not check["historical_fallback_tested"]:
            errors.append("historical fallback was applicable but not tested")
        for value in check["evidence_artifacts"]:
            if not artifact_exists(output, value):
                errors.append(f"missing stopping evidence artifact: {value}")
        retrieved_outcome = any(
            source.get("role") == "outcome" and source.get("retrieved")
            for source in result.get("sources", [])
        )
        if not retrieved_outcome:
            if check["outcome_routes_attempted"] < 3:
                errors.append("fewer than three outcome recovery routes attempted")
            client_path = artifact_path(output, recovery.get("bulk_public_client_evidence"))
            if recovery.get("bulk_public_client_inspected") is not True:
                errors.append(
                    "public outcome bulk-data blocker lacks inspection of a public client "
                    "or package catalog"
                )
            elif client_path is None:
                errors.append("missing public outcome client or package-catalog evidence")
            else:
                client_text = client_path.read_text(
                    encoding="utf-8", errors="replace"
                ).lower()
                source_markers = (
                    "github.com", "gitlab", "package", "catalog", "source code", "javascript"
                )
                request_markers = (
                    "request", "endpoint", "http", "post", "get", "form", "action", "download"
                )
                if not (
                    any(marker in client_text for marker in source_markers)
                    and any(marker in client_text for marker in request_markers)
                ):
                    errors.append(
                        "public outcome client evidence does not document source code "
                        "and its request route"
                    )
        named_exposure_sources = [
            source for source in result.get("sources", [])
            if source.get("role") == "exposure"
            and source.get("route_origin") == "article_named"
        ]
        retrieved_exposure = any(
            source.get("role") == "exposure" and source.get("retrieved")
            for source in result.get("sources", [])
        )
        if named_exposure_sources and not retrieved_exposure:
            if recovery.get("article_named_regulator_applicable") is not True:
                errors.append(
                    "article-named exposure source was declared inapplicable in the recovery record"
                )
            if recovery.get("article_named_regulator_interface_inspected") is not True:
                errors.append("article-named exposure interface was not deeply inspected")
            if int(recovery.get("article_named_regulator_routes_attempted", 0)) < 3:
                errors.append("fewer than three article-named exposure recovery routes attempted")
            client_path = artifact_path(
                output, recovery.get("article_named_regulator_client_evidence")
            )
            if recovery.get("article_named_regulator_public_client_inspected") is not True:
                errors.append("article-named exposure public client was not inspected")
            elif client_path is None:
                errors.append("missing article-named exposure public-client evidence")
            else:
                client_text = client_path.read_text(
                    encoding="utf-8", errors="replace"
                ).lower()
                source_markers = (
                    "github.com", "gitlab", "cran", "repository", "source code", "package"
                )
                request_markers = (
                    "request", "endpoint", "http", "post", "get", "form", "action"
                )
                if not (
                    any(marker in client_text for marker in source_markers)
                    and any(marker in client_text for marker in request_markers)
                ):
                    errors.append(
                        "public-client evidence does not document inspected source code "
                        "and its request route"
                    )
    return errors


def validate_completed_reanalysis(output: Path, result: dict) -> list[str]:
    """Validate the scientific evidence needed to count a fitted contrast.

    Coverage, fidelity, and structured provenance remain important audit
    dimensions, but deficiencies in those records do not erase an otherwise
    executable fitted reanalysis.
    """
    errors: list[str] = []
    artifacts = result.get("artifacts", {})
    required = ["code", "source_manifest", "exposure", "analysis_panel", "model_output"]
    for name in required:
        exists = (
            executable_code_exists(output, artifacts.get(name))
            if name == "code"
            else artifact_exists(output, artifacts.get(name))
        )
        if not exists:
            errors.append(f"missing or external required artifact: {name}")

    effects = result.get("effects") or []
    if not effects:
        errors.append("completed reanalysis has no fitted effects")
    for effect in effects:
        label = effect.get("label", "unlabeled effect")
        estimate, low, high = (
            effect.get("estimate"), effect.get("ci_low"), effect.get("ci_high")
        )
        if estimate is None or not math.isfinite(estimate):
            errors.append(f"{label}: a finite effect estimate is required")
            continue
        if low is not None and not math.isfinite(low):
            errors.append(f"{label}: confidence interval lower bound is not finite")
        if high is not None and not math.isfinite(high):
            errors.append(f"{label}: confidence interval upper bound is not finite")
        if low is not None and high is not None and (low > high or not low <= estimate <= high):
            errors.append(f"{label}: effect estimate is inconsistent with its confidence interval")
        if any(value is not None and value <= 0 for value in (estimate, low, high)):
            errors.append(f"{label}: comparable OR or RR values must be positive")

    diagnostics = result.get("analysis_diagnostics") or {}
    observations = diagnostics.get("observations", 0)
    parameters = diagnostics.get("estimated_parameters", 0)
    if observations <= parameters:
        errors.append("model has no residual degrees of freedom")
    if diagnostics.get("exposure_unique_values", 0) < 2:
        errors.append("fitted exposure is constant")
    if diagnostics.get("outcome_unique_values", 0) < 2:
        errors.append("fitted outcome is constant")
    if diagnostics.get("joined_rows", 0) < observations:
        errors.append("joined row count is smaller than fitted observations")

    retrieved_roles = {
        source.get("role") for source in result.get("sources", []) if source.get("retrieved")
    }
    if not {"outcome", "exposure"}.issubset(retrieved_roles):
        errors.append("fit lacks retrieved outcome and exposure sources")

    errors.extend(validate_computational_artifacts(output, result))
    return list(dict.fromkeys(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--schema", type=Path)
    parser.add_argument("--minimum-blocker-seconds", type=int, default=0)
    args = parser.parse_args()
    if args.schema is not None:
        try:
            import jsonschema
            jsonschema.validate(
                json.loads((args.output / "result.json").read_text()),
                json.loads(args.schema.read_text()),
            )
        except Exception as exc:
            print(json.dumps({"valid": False, "errors": [f"schema validation failed: {exc}"]}, indent=2))
            return 2
    result = json.loads((args.output / "result.json").read_text())
    audit_findings = validate(args.output, args.minimum_blocker_seconds)
    if result.get("status") in FIT_STATUSES:
        errors = validate_completed_reanalysis(args.output, result)
        warnings = [finding for finding in audit_findings if finding not in errors]
    else:
        errors = audit_findings
        warnings = []
    print(json.dumps({"valid": not errors, "errors": errors, "warnings": warnings}, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
