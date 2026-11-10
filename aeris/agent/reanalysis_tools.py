"""Optional tools for published-study reanalysis."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import SessionState

from .fidelity import (
    FIDELITY_LEVEL_BY_CLASS,
    FidelityRecord,
)

def record_reanalysis_fidelity(
    *,
    state: SessionState,
    study_id: str,
    fidelity_class: str,
    status: str,
    preserved_dimensions: list[str],
    deviations: list[dict],
    evidence_artifacts: list[str],
    notes: str = "",
    recovery_checklist: dict | None = None,
    reported_variants: list[str] | None = None,
    final_analysis_checklist: dict | None = None,
) -> dict:
    """Persist a reviewable account of reanalysis fidelity."""
    try:
        workspace = state.ensure_workspace()
        if state.execution_policy.mode == "self-driving":
            if fidelity_class == "unsupported_fit":
                raise ValueError("Self-driving mode cannot record an unsupported fit.")
            level = FIDELITY_LEVEL_BY_CLASS.get(fidelity_class)
            allowed = set(
                (state.execution_policy.contract.payload if state.execution_policy.contract else {})
                .get("allowed_fidelity_levels", [])
            )
            if level and allowed and level not in allowed:
                raise ValueError(f"Fidelity level {level!r} is outside the approved study contract.")
            if status == "fitted":
                expected_variants = list(
                    (state.execution_policy.contract.invariants
                     if state.execution_policy.contract else {}).get("principal_variants", [])
                )
                if len(reported_variants or []) < len(expected_variants):
                    raise ValueError(
                        "Fitted reanalysis reports fewer variants than the locked target: "
                        f"expected {len(expected_variants)}, received {len(reported_variants or [])}."
                    )
        # The agent records the scientific account here. The clean-room host
        # checks retained blocker attempts, panels, models, coverage, and target
        # preservation after the research turn.
        record = FidelityRecord(
            study_id=study_id,
            fidelity_class=fidelity_class,
            status=status,
            preserved_dimensions=tuple(preserved_dimensions),
            deviations=tuple(deviations),
            evidence_artifacts=tuple(evidence_artifacts),
            reported_variants=tuple(reported_variants or []),
            notes=notes,
            recovery_checklist=recovery_checklist,
            final_analysis_checklist=final_analysis_checklist,
        )
    except ValueError as exc:
        response = {"error": str(exc)}
        if state.execution_policy.mode == "self-driving":
            response.update({
                "terminal_completion_authorized": False,
                "required_action": (
                    "Continue recovery and correct the scientific record before writing "
                    "a terminal result."
                ),
            })
        return response
    payload = record.to_dict()
    artifact_id = workspace.register_json(
        "reanalysis-fidelity",
        payload,
        kind="reanalysis-fidelity",
        provenance={
            "dataset_id": state.artifacts.get("cohort"),
            **state.execution_policy.metadata(),
        },
    )
    state.artifacts["reanalysis_fidelity"] = artifact_id
    return {"status": "ok", "artifact_id": artifact_id, "fidelity": payload}
