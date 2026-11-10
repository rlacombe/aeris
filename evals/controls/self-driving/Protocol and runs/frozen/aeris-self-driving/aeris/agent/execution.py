"""Execution policy for interactive and self-driving AERIS sessions."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

ESTIMATION_TOOLS = frozenset(
    {"estimate_exposure", "estimate_boundary_exposure", "estimate_boundary_exposure_batch"}
)

COVERAGE_POLICY_MODES = frozenset({"report_only", "threshold"})
COVERAGE_THRESHOLD_SOURCES = frozenset(
    {"article", "researcher", "source_standard"}
)


def validate_coverage_policy(policy: Any, *, self_driving: bool = True) -> dict[str, Any]:
    """Validate how temporal coverage may affect inclusion in an analysis."""
    if not isinstance(policy, dict):
        raise ValueError("coverage_policy must be an object.")
    mode = policy.get("mode")
    if mode not in COVERAGE_POLICY_MODES:
        raise ValueError("coverage_policy.mode must be report_only or threshold.")

    threshold = policy.get("minimum_percent")
    source = policy.get("threshold_source")
    evidence = str(policy.get("evidence", "")).strip()
    if mode == "report_only":
        if threshold is not None:
            raise ValueError("Report-only coverage policy cannot set minimum_percent.")
        if source not in {None, "none"}:
            raise ValueError("Report-only coverage policy cannot name a threshold source.")
        return {
            "mode": "report_only",
            "minimum_percent": None,
            "threshold_source": "none",
            "evidence": evidence or "Coverage is reported without excluding records.",
        }

    if not isinstance(threshold, (int, float)) or not 0 <= threshold <= 100:
        raise ValueError("Threshold coverage policy requires minimum_percent in [0, 100].")
    if source not in COVERAGE_THRESHOLD_SOURCES:
        raise ValueError(
            "Threshold coverage policy requires article, researcher, or source_standard provenance."
        )
    if self_driving and source == "researcher":
        raise ValueError("An agent-authored contract cannot claim a researcher-set threshold.")
    if not evidence:
        raise ValueError("Threshold coverage policy requires exact supporting evidence.")
    return {
        "mode": "threshold",
        "minimum_percent": float(threshold),
        "threshold_source": source,
        "evidence": evidence,
    }

BOUNDARY_TOOLS = frozenset(
    {"estimate_boundary_exposure", "estimate_boundary_exposure_batch"}
)


@dataclass(frozen=True)
class StudyContract:
    """Frozen authorization for one autonomous study run."""

    path: Path
    payload: dict[str, Any]
    digest: str

    @classmethod
    def load(cls, path: str | Path) -> StudyContract:
        contract_path = Path(path).expanduser().resolve()
        payload = json.loads(contract_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") not in {
            "aeris-study-contract/v1", "aeris-study-contract/v2", "aeris-study-contract/v3"
        }:
            raise ValueError("Study contract must use a supported AERIS study-contract schema.")
        if not payload.get("contract_id") or payload.get("approved") is not True:
            raise ValueError("Study contract requires a contract_id and approved=true.")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return cls(contract_path, payload, hashlib.sha256(canonical).hexdigest())

    def authorize(self, tool: str, arguments: dict[str, Any]) -> list[str]:
        allowed_tools = set(self.payload.get("allowed_tools", ESTIMATION_TOOLS))
        if tool not in allowed_tools:
            raise PermissionError(f"Tool {tool!r} is outside the approved study contract.")

        design = self.payload.get("execution_design", self.payload.get("agent_design", {}))
        representation = design.get("geographic_representation")
        assignment = design.get("assignment_method")
        if representation == "administrative_area" and assignment == "within_boundary_monitor_mean":
            if tool not in BOUNDARY_TOOLS:
                raise PermissionError(
                    "The locked within-boundary assignment requires a boundary exposure tool."
                )
        elif (
            representation in {"fixed_location", "mobility_trajectory"}
            or assignment == "nearest_monitor_to_unit_reference"
        ) and tool in BOUNDARY_TOOLS:
            raise PermissionError(
                f"The locked {representation} design cannot use an administrative-boundary tool."
            )

        locked_radius = design.get("maximum_monitor_distance_km")
        if assignment in {"nearest_monitor", "nearest_monitor_to_unit_reference"}:
            requested_radius = arguments.get("search_radius_km")
            if locked_radius is None:
                raise PermissionError("The locked nearest-monitor design lacks a maximum distance.")
            if requested_radius is None or abs(float(requested_radius) - float(locked_radius)) > 1e-9:
                raise PermissionError(
                    "search_radius_km must equal the maximum monitor distance locked in the contract."
                )

        pollutants = set(self.payload.get("pollutants", []))
        pollutant = arguments.get("pollutant")
        if pollutants and pollutant not in pollutants:
            raise PermissionError(f"Pollutant {pollutant!r} is outside the approved study contract.")

        window = self.payload.get("date_window", {})
        for argument, bound, comparison in (
            ("start_date", "start", lambda value, limit: value >= limit),
            ("end_date", "end", lambda value, limit: value <= limit),
        ):
            value = arguments.get(argument)
            limit = window.get(bound)
            try:
                parsed_value = date.fromisoformat(value) if value else None
                parsed_limit = date.fromisoformat(limit) if limit else None
            except (TypeError, ValueError) as exc:
                raise PermissionError(f"{argument} and its contract bound must be ISO dates.") from exc
            if parsed_value and parsed_limit and not comparison(parsed_value, parsed_limit):
                raise PermissionError(f"{argument}={value} exceeds the approved date window.")

        if (
            arguments.get("start_date")
            and arguments.get("end_date")
            and date.fromisoformat(arguments["start_date"])
            > date.fromisoformat(arguments["end_date"])
        ):
            raise PermissionError("start_date must be on or before end_date.")

        if tool == "estimate_boundary_exposure_batch":
            names = arguments.get("boundary_names")
            maximum = self.payload.get("resource_limits", {}).get("maximum_boundary_units")
            maximum_per_call = self.payload.get("resource_limits", {}).get(
                "maximum_boundary_units_per_call"
            )
            requested_units = len(set(names)) if names is not None else None
            if maximum is not None and requested_units is None:
                boundary_path = arguments.get("boundary_geojson_path")
                if boundary_path:
                    try:
                        geojson = json.loads(Path(boundary_path).read_text(encoding="utf-8"))
                        requested_units = len(geojson.get("features", []))
                    except (OSError, json.JSONDecodeError) as exc:
                        raise PermissionError(
                            "The boundary GeoJSON must be readable before authorizing an implicit batch."
                        ) from exc
            if maximum is not None and requested_units is not None and requested_units > maximum:
                raise PermissionError(
                    f"The batch requests {requested_units} boundaries; the contract allows {maximum}."
                )
            if (
                maximum_per_call is not None
                and requested_units is not None
                and requested_units > maximum_per_call
            ):
                raise PermissionError(
                    f"One call may request at most {maximum_per_call} boundaries; "
                    "split the deterministic name list into checkpointed chunks."
                )

        resolutions = set(self.payload.get("temporal_resolutions", []))
        resolution = arguments.get("temporal_resolution", "daily")
        if resolutions and resolution not in resolutions:
            raise PermissionError(
                f"Temporal resolution {resolution!r} is outside the approved study contract."
            )

        coverage_policy = self.payload.get("coverage_policy")
        if coverage_policy is None:
            # Read v1 prescribed contracts created before coverage provenance.
            approved_minimum = self.payload.get("minimum_completeness")
        else:
            normalized_coverage = validate_coverage_policy(
                coverage_policy,
                self_driving=self.payload.get("author") == "agent",
            )
            approved_minimum = normalized_coverage["minimum_percent"]
        requested = arguments.get("min_completeness")
        if coverage_policy is not None and approved_minimum is None and requested is not None:
            raise PermissionError(
                "The locked report-only coverage policy cannot exclude records by completeness."
            )
        if approved_minimum is not None and requested is None:
            raise PermissionError(
                "The estimation call must state the completeness threshold locked in the contract."
            )
        if (
            approved_minimum is not None
            and requested is not None
            and abs(float(requested) - float(approved_minimum)) > 1e-9
        ):
            raise PermissionError(
                f"min_completeness={requested} differs from the locked value {approved_minimum}."
            )
        return []

    @property
    def invariants(self) -> dict[str, Any]:
        """Return the scientific dimensions protected across contract amendments."""
        return self.payload.get("scientific_invariants", {})


@dataclass(frozen=True)
class SafetyEnvelope:
    """Study-independent limits within which an agent may author a contract."""

    path: Path
    payload: dict[str, Any]
    digest: str

    @classmethod
    def load(cls, path: str | Path) -> SafetyEnvelope:
        envelope_path = Path(path).expanduser().resolve()
        payload = json.loads(envelope_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != "aeris-safety-envelope/v1":
            raise ValueError("Safety envelope must use schema_version aeris-safety-envelope/v1.")
        if not payload.get("envelope_id"):
            raise ValueError("Safety envelope requires an envelope_id.")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return cls(envelope_path, payload, hashlib.sha256(canonical).hexdigest())

    def validate_contract(self, payload: dict[str, Any]) -> None:
        invariant_only = bool(payload.get("scientific_invariants")) and not payload.get("agent_design")
        design = payload.get("agent_design", {})
        required_design = {
            "geographic_representation",
            "assignment_method",
            "source_strategy",
            "exposure_metric",
            "daily_aggregation",
            "analysis_aggregation",
        }
        if payload.get("profile") == "reanalysis":
            required_design.update({
                "principal_analysis_reference", "principal_effect_measure",
                "pollutant_combination", "design_evidence",
            })
        missing = [] if invariant_only else sorted(name for name in required_design if not design.get(name))
        if missing:
            raise ValueError(
                "Agent contract lacks structured principal-analysis fields: " + ", ".join(missing)
            )
        if payload.get("profile") == "reanalysis" and not invariant_only:
            evidence = design.get("design_evidence", {})
            evidence_fields = {
                "exposure", "outcome", "model", "covariates", "contrast",
                "published_estimate"
            }
            missing_evidence = sorted(name for name in evidence_fields if not evidence.get(name))
            if missing_evidence:
                raise ValueError(
                    "Agent contract lacks principal-analysis evidence for: "
                    + ", ".join(missing_evidence)
                )

        representation = design.get("geographic_representation")
        assignment = design.get("assignment_method")
        valid_assignments = {
            "fixed_location": {"nearest_monitor", "idw_monitors", "provider_coordinate_model", "hyperlocal_model"},
            "mobility_trajectory": {"provider_coordinate_model", "hyperlocal_model"},
            "administrative_area": {
                "within_boundary_monitor_mean",
                "nearest_monitor_to_unit_reference",
            },
        }
        if not invariant_only and assignment not in valid_assignments.get(representation, set()):
            raise ValueError(
                f"Assignment method {assignment!r} is incompatible with {representation!r}."
            )
        if (
            assignment == "nearest_monitor_to_unit_reference"
            and not design.get("representative_location_rule")
        ):
            raise ValueError(
                "A city or area reference-point assignment requires representative_location_rule."
            )
        if assignment in {"nearest_monitor", "nearest_monitor_to_unit_reference"}:
            radius = design.get("maximum_monitor_distance_km")
            if not isinstance(radius, (int, float)) or not 0 < radius <= 200:
                raise ValueError(
                    "A nearest-monitor assignment requires maximum_monitor_distance_km in (0, 200]."
                )
            if payload.get("author") == "agent" and not str(
                design.get("monitor_distance_evidence", "")
            ).strip():
                raise ValueError(
                    "An agent-authored nearest-monitor assignment requires monitor-distance evidence."
                )

        pollutants = set(payload.get("pollutants", []))
        allowed_pollutants = set(self.payload.get("allowed_pollutants", []))
        if not pollutants or not pollutants.issubset(allowed_pollutants):
            raise ValueError("Agent contract requests a pollutant outside the safety envelope.")

        window = payload.get("date_window", {})
        try:
            start = date.fromisoformat(window["start"])
            end = date.fromisoformat(window["end"])
            earliest = date.fromisoformat(self.payload["date_bounds"]["earliest"])
            latest = date.fromisoformat(self.payload["date_bounds"]["latest"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Agent contract and envelope require valid ISO date bounds.") from exc
        if start > end or start < earliest or end > latest:
            raise ValueError("Agent contract date window falls outside the safety envelope.")

        resolutions = set(payload.get("temporal_resolutions", []))
        allowed_resolutions = set(self.payload.get("allowed_temporal_resolutions", []))
        if not resolutions or not resolutions.issubset(allowed_resolutions):
            raise ValueError("Agent contract requests a temporal resolution outside the safety envelope.")

        if payload.get("coverage_policy") is None:
            if payload.get("author") == "agent" and not invariant_only:
                raise ValueError("Agent-authored contracts require coverage_policy provenance.")
            # Compatibility for prescribed v1 contracts.
            completeness = payload.get("minimum_completeness")
        else:
            coverage_policy = validate_coverage_policy(
                payload["coverage_policy"],
                self_driving=payload.get("author") == "agent",
            )
            completeness = coverage_policy["minimum_percent"]
        limits = self.payload.get("completeness_bounds", {})
        if completeness is not None and (
            completeness < limits.get("minimum", 0)
            or completeness > limits.get("maximum", 100)
        ):
            raise ValueError("Agent contract completeness falls outside the safety envelope.")

        requested = payload.get("resource_limits", {})
        ceilings = self.payload.get("resource_ceilings", {})
        for name, ceiling in ceilings.items():
            value = requested.get(name)
            if value is None or value > ceiling:
                raise ValueError(f"Agent contract resource limit {name!r} exceeds its ceiling.")


class ExecutionPolicy:
    """Authorize scientific operations without changing their implementation."""

    def __init__(
        self,
        mode: str = "interactive",
        contract_path: str | None = None,
        safety_envelope_path: str | None = None,
    ):
        if mode not in {"interactive", "self-driving"}:
            raise ValueError("AERIS execution mode must be interactive or self-driving.")
        self.mode = mode
        self.contract = StudyContract.load(contract_path) if contract_path else None
        self.safety_envelope = (
            SafetyEnvelope.load(safety_envelope_path) if safety_envelope_path else None
        )
        if mode == "self-driving" and self.contract is None and self.safety_envelope is None:
            raise ValueError(
                "Self-driving mode requires AERIS_STUDY_CONTRACT or AERIS_SAFETY_ENVELOPE."
            )

    @classmethod
    def from_env(cls) -> ExecutionPolicy:
        return cls(
            os.getenv("AERIS_EXECUTION_MODE", "interactive"),
            os.getenv("AERIS_STUDY_CONTRACT"),
            os.getenv("AERIS_SAFETY_ENVELOPE"),
        )

    def lock_agent_contract(self, path: str | Path, payload: dict[str, Any]) -> StudyContract:
        """Validate and attach one immutable agent-authored study contract."""
        if self.mode != "self-driving" or self.safety_envelope is None:
            raise PermissionError("Agent-authored contracts require self-driving bootstrap mode.")
        if self.contract is not None:
            raise PermissionError("The study contract is already locked and cannot be revised.")
        self.safety_envelope.validate_contract(payload)
        contract_path = Path(path).expanduser().resolve()
        contract_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with contract_path.open("x", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
                handle.write("\n")
        except FileExistsError as exc:
            raise PermissionError("The study contract path already exists and cannot be replaced.") from exc
        self.contract = StudyContract.load(contract_path)
        return self.contract

    def restore_agent_contract(self, path: str | Path) -> StudyContract:
        """Reattach a durable agent-authored contract after a process restart."""
        if self.mode != "self-driving" or self.safety_envelope is None:
            raise PermissionError("Contract restoration requires self-driving bootstrap mode.")
        if self.contract is not None:
            raise PermissionError("A study contract is already attached to this session.")
        contract = StudyContract.load(path)
        if contract.payload.get("author") != "agent":
            raise ValueError("Only an agent-authored contract may be restored from a workspace.")
        self.safety_envelope.validate_contract(contract.payload)
        self.contract = contract
        return contract

    def amend_agent_contract(
        self,
        path: str | Path,
        *,
        changed_dimensions: dict[str, Any],
        evidence: list[dict[str, Any]],
        scientific_justification: str,
        fidelity_impact: str,
        agreement_independent: bool,
    ) -> StudyContract:
        """Append an evidence-backed execution amendment without rewriting history."""
        if self.mode != "self-driving" or self.contract is None:
            raise PermissionError("Contract amendments require a locked self-driving contract.")
        if not changed_dimensions:
            raise ValueError("An amendment must change at least one dimension.")
        if not evidence or not all(
            isinstance(item, dict) and item.get("artifact") and item.get("finding")
            for item in evidence
        ):
            raise ValueError("An amendment requires saved evidence artifacts and findings.")
        if not scientific_justification.strip():
            raise ValueError("An amendment requires scientific justification.")
        if fidelity_impact not in {
            "none", "source_substitution", "coverage_subset", "covariate_omission",
            "construct_change", "supported_sensitivity",
        }:
            raise ValueError("Unknown amendment fidelity impact.")
        if agreement_independent is not True:
            raise ValueError("Confirm that the amendment ignored agreement with the published estimate.")

        protected = set(self.contract.invariants)
        changed_protected = protected.intersection(changed_dimensions)
        if changed_protected and fidelity_impact not in {"construct_change", "supported_sensitivity"}:
            raise ValueError(
                "Changing scientific invariants requires construct_change or supported_sensitivity fidelity."
            )
        payload = json.loads(json.dumps(self.contract.payload))
        amendments = payload.setdefault("amendments", [])
        amendment = {
            "sequence": len(amendments) + 1,
            "changed_dimensions": changed_dimensions,
            "evidence": evidence,
            "scientific_justification": scientific_justification,
            "fidelity_impact": fidelity_impact,
            "agreement_independent": True,
        }
        amendments.append(amendment)
        execution_design = payload.setdefault(
            "execution_design", dict(payload.get("agent_design", {}))
        )
        execution_design.update(changed_dimensions)
        if payload.get("schema_version") != "aeris-study-contract/v3":
            payload["schema_version"] = "aeris-study-contract/v2"
        payload["parent_contract_sha256"] = self.contract.digest
        amendment_path = Path(path).expanduser().resolve()
        amendment_path.parent.mkdir(parents=True, exist_ok=True)
        with amendment_path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
        self.contract = StudyContract.load(amendment_path)
        return self.contract

    def authorize(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool not in ESTIMATION_TOOLS:
            return self.metadata()
        if self.mode == "interactive":
            if not arguments.get("researcher_approved", False):
                raise PermissionError(
                    "Exposure estimation requires explicit researcher approval after review of "
                    "the pollutant, source, assignment, time window, and completeness policy."
                )
        else:
            if self.contract is None:
                raise PermissionError(
                    "Exposure estimation is locked until the agent records its study contract."
                )
            self.contract.authorize(tool, arguments)
            arguments["researcher_approved"] = True
        return self.metadata()

    def metadata(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "contract_id": self.contract.payload["contract_id"] if self.contract else None,
            "contract_sha256": self.contract.digest if self.contract else None,
            "contract_author": self.contract.payload.get("author") if self.contract else None,
            "planning_phase": self.mode == "self-driving" and self.contract is None,
            "safety_envelope_id": (
                self.safety_envelope.payload["envelope_id"] if self.safety_envelope else None
            ),
            "safety_envelope_sha256": self.safety_envelope.digest if self.safety_envelope else None,
        }
