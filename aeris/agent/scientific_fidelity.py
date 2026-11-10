"""Validation for scientific-fidelity artifacts in autonomous reanalysis."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

ARTICLE_SECTIONS = frozenset({
    "methods", "results", "data_availability", "supplements", "repositories",
})
SECTION_STATUSES = frozenset({"located", "absent_after_full_text_search", "not_applicable"})
COMPARISON_STATUSES = frozenset({
    "exact", "derived_equivalent", "reported_sensitivity", "exploratory",
})
OUTCOME_COMPARISON_STATUSES = frozenset({
    "consistent", "explained_difference", "not_reported",
})

DATA_AVAILABILITY_HEADING = re.compile(
    r"(?:^|[\n\r])\s*(?:#+\s*)?data availability(?: statement)?\s*[:\n\r]",
    flags=re.IGNORECASE,
)
REPOSITORY_REFERENCE = re.compile(
    r"\b10\.\d{4,9}/\S+|\b(?:repository|data set|dataset|archive|figshare|"
    r"zenodo|mendeley|dryad|osf)\b",
    flags=re.IGNORECASE,
)


def _read_searchable_article(path: Path) -> str:
    """Read bounded plain-text article representations for semantic checks."""
    if path.suffix.lower() not in {".md", ".txt", ".xml", ".html", ".htm"}:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:10_000_000]
    except OSError:
        return ""


def _data_availability_excerpt(text: str) -> str:
    match = DATA_AVAILABILITY_HEADING.search(text)
    if match is None:
        return ""
    return text[match.start():match.end() + 2_000]


def validate_article_evidence_map(value: Any, article_evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """Require evidence that the complete article was searched before design lock."""
    if not isinstance(value, dict):
        raise ValueError("Reanalysis requires a structured article_evidence_map.")
    artifact = Path(str(value.get("complete_article_artifact", "")))
    if not artifact.is_file():
        raise ValueError("article_evidence_map.complete_article_artifact must exist.")
    cited = {str(item.get("artifact", "")) for item in article_evidence if isinstance(item, dict)}
    if str(artifact) not in cited:
        raise ValueError("The complete article artifact must also appear in article_evidence.")
    status = value.get("complete_article_status")
    if status not in {"complete", "partial_after_exhaustive_search"}:
        raise ValueError("Complete-article status must be complete or partial_after_exhaustive_search.")
    sections = value.get("sections_checked")
    if not isinstance(sections, dict) or set(sections) != ARTICLE_SECTIONS:
        raise ValueError(
            "sections_checked must cover methods, results, data_availability, supplements, and repositories."
        )
    invalid = sorted(name for name, section_status in sections.items()
                     if section_status not in SECTION_STATUSES)
    if invalid:
        raise ValueError("Invalid article-section status for: " + ", ".join(invalid))
    for field in ("repository_identifiers", "outcome_sources", "reported_covariates",
                  "principal_models"):
        if not isinstance(value.get(field), list):
            raise ValueError(f"article_evidence_map.{field} must be a list.")
    principal_effect = value.get("principal_effect")
    if not isinstance(principal_effect, dict):
        raise ValueError("article_evidence_map.principal_effect must be a structured object.")
    for field in ("reference", "effect_measure", "exposure_label", "exposure_role"):
        if not isinstance(principal_effect.get(field), str) or not principal_effect[field].strip():
            raise ValueError(f"article_evidence_map.principal_effect.{field} is required.")
    effect_pollutants = principal_effect.get("pollutants")
    if (not isinstance(effect_pollutants, list) or not effect_pollutants
            or any(not isinstance(item, str) or not item.strip() for item in effect_pollutants)):
        raise ValueError("article_evidence_map.principal_effect.pollutants is required.")
    if principal_effect["exposure_role"] != "fitted_predictor_or_contrast":
        raise ValueError(
            "The principal effect must estimate pollution as a fitted predictor or contrast."
        )
    estimate = principal_effect.get("estimate")
    if not isinstance(estimate, (int, float)) or isinstance(estimate, bool):
        raise ValueError("article_evidence_map.principal_effect.estimate must be numeric.")
    uncertainty = principal_effect.get("uncertainty")
    if not isinstance(uncertainty, dict) or not isinstance(uncertainty.get("type"), str):
        raise ValueError("article_evidence_map.principal_effect.uncertainty is required.")
    uncertainty_values = [uncertainty.get(name) for name in ("value", "lower", "upper")]
    has_numeric_uncertainty = any(
        isinstance(item, (int, float)) and not isinstance(item, bool)
        for item in uncertainty_values
    )
    if uncertainty["type"] == "not_reported":
        if not isinstance(uncertainty.get("evidence"), str) or not uncertainty["evidence"].strip():
            raise ValueError("Unreported uncertainty requires article evidence.")
    elif not has_numeric_uncertainty:
        raise ValueError("Reported uncertainty requires a numeric value or interval.")
    article_text = _read_searchable_article(artifact)
    availability_excerpt = _data_availability_excerpt(article_text)
    if (sections["data_availability"] == "absent_after_full_text_search"
            and availability_excerpt):
        raise ValueError(
            "The cited article artifact contains a data-availability section; "
            "inspect and record it before locking the design."
        )
    if (sections["repositories"] == "absent_after_full_text_search"
            and availability_excerpt
            and REPOSITORY_REFERENCE.search(availability_excerpt)):
        raise ValueError(
            "The cited article artifact names a repository or identifier in its "
            "data-availability section; inspect and record it before locking the design."
        )
    data_statement = value.get("data_availability_statement")
    if sections["data_availability"] == "located":
        if not isinstance(data_statement, str) or not data_statement.strip():
            raise ValueError(
                "A located data-availability section must be transcribed in "
                "article_evidence_map.data_availability_statement."
            )
        names_repository = bool(REPOSITORY_REFERENCE.search(data_statement))
        if names_repository and not value["repository_identifiers"]:
            raise ValueError(
                "The data-availability statement names a repository or identifier; "
                "record it in article_evidence_map.repository_identifiers."
            )
    return value


def _require_run_artifact(reference: Any, *, evidence_root: Path, label: str) -> Path:
    path = Path(str(reference))
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"{label} requires a saved evidence artifact.")
    try:
        path.resolve().relative_to(evidence_root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} evidence must belong to the active run.") from exc
    return path


def _validate_design_fidelity(value: Any, *, evidence_root: Path) -> None:
    required = {
        "article_model_logic", "final_model_logic", "article_contrast",
        "final_contrast", "comparison_status", "agent_defined_thresholds",
        "preserved_dimensions", "changed_dimensions", "justification",
        "evidence_artifact", "sample_membership_status",
        "public_eligible_units", "agent_selected_sample",
    }
    if not isinstance(value, dict) or not required.issubset(value):
        raise ValueError("design_fidelity is incomplete.")
    if value["comparison_status"] not in COMPARISON_STATUSES:
        raise ValueError("design_fidelity.comparison_status is invalid.")
    _require_run_artifact(
        value["evidence_artifact"], evidence_root=evidence_root, label="design_fidelity"
    )
    for field in (
        "article_model_logic", "final_model_logic", "article_contrast",
        "final_contrast", "justification",
    ):
        if not str(value[field]).strip():
            raise ValueError(f"design_fidelity.{field} must be nonempty.")
    for field in ("preserved_dimensions", "changed_dimensions"):
        if not isinstance(value[field], list):
            raise ValueError(f"design_fidelity.{field} must be a list.")
    if value["comparison_status"] == "exploratory":
        raise ValueError("An exploratory replacement model cannot be the final reanalysis.")
    if value["agent_defined_thresholds"] is True:
        raise ValueError(
            "Agent-created bins, thresholds, or cutoffs cannot define the final reanalysis."
        )
    if value["sample_membership_status"] not in {"known", "article_rule", "unknown"}:
        raise ValueError("design_fidelity.sample_membership_status is invalid.")
    public_eligible_units = value["public_eligible_units"]
    if not isinstance(public_eligible_units, int) or public_eligible_units < 1:
        raise ValueError("design_fidelity.public_eligible_units must be a positive integer.")
    if value["agent_selected_sample"] is True:
        raise ValueError(
            "An agent-selected subset cannot replace unknown article sample membership; "
            "use all eligible public records for the primary analysis."
        )


def validate_execution_commitment(changed: dict[str, Any]) -> None:
    """Validate a compact, article-derived executable plan."""
    plan = changed.get("analysis_plan")
    if not isinstance(plan, dict):
        raise ValueError("The first design amendment requires analysis_plan.")
    required = {
        "article_model_logic", "planned_model_logic", "article_contrast",
        "planned_contrast", "comparison_status", "agent_defined_thresholds",
        "preserved_dimensions", "changed_dimensions", "evidence",
    }
    if not required.issubset(plan):
        raise ValueError("analysis_plan is incomplete.")
    if plan["comparison_status"] not in COMPARISON_STATUSES - {"exploratory"}:
        raise ValueError(
            "The committed analysis must be exact, derived-equivalent, or an "
            "article-reported sensitivity."
        )
    if plan["agent_defined_thresholds"] is True:
        raise ValueError("The committed analysis cannot depend on agent-created thresholds.")
    for field in ("article_model_logic", "planned_model_logic", "article_contrast",
                  "planned_contrast"):
        if not str(plan[field]).strip():
            raise ValueError(f"analysis_plan.{field} must be nonempty.")
    for field in ("preserved_dimensions", "changed_dimensions", "evidence"):
        if not isinstance(plan[field], list):
            raise ValueError(f"analysis_plan.{field} must be a list.")
    if not plan["evidence"]:
        raise ValueError("analysis_plan requires article evidence.")


def validate_final_analysis_checklist(
    checklist: Any, *, contract_payload: dict[str, Any], evidence_root: Path,
    fidelity_class: str,
) -> None:
    """Validate adequacy, design fidelity, and one skeptical scientific review."""
    if not isinstance(checklist, dict):
        raise ValueError("Fitted autonomous reanalysis requires final_analysis_checklist.")
    required = {
        "analysis_adequacy", "outcome_accounting", "design_fidelity",
        "scientific_review",
    }
    if not required.issubset(checklist):
        raise ValueError("final_analysis_checklist is incomplete.")

    adequacy = checklist["analysis_adequacy"]
    required_adequacy = {
        "observations", "estimated_parameters", "coverage_summary",
        "variation_summary", "justification", "evidence_artifact",
        "eligible_units", "included_units",
    }
    if not isinstance(adequacy, dict) or not required_adequacy.issubset(adequacy):
        raise ValueError("analysis_adequacy is incomplete.")
    _require_run_artifact(
        adequacy["evidence_artifact"], evidence_root=evidence_root,
        label="analysis_adequacy",
    )
    observations = adequacy["observations"]
    parameters = adequacy["estimated_parameters"]
    if any(not isinstance(value, int) or value < 0 for value in (observations, parameters)):
        raise ValueError("analysis_adequacy counts must be nonnegative integers.")
    if observations <= parameters:
        raise ValueError("The fitted analysis must have more observations than parameters.")
    eligible_units = adequacy["eligible_units"]
    included_units = adequacy["included_units"]
    if any(not isinstance(value, int) or value < 1 for value in (eligible_units, included_units)):
        raise ValueError("analysis_adequacy geographic-unit counts must be positive integers.")
    if included_units > eligible_units:
        raise ValueError("analysis_adequacy.included_units cannot exceed eligible_units.")
    if included_units < eligible_units and fidelity_class in {
        "matched_fit", "source_substitution_fit",
    }:
        raise ValueError(
            "A fit using fewer eligible geographic units must use a reduced-coverage "
            "fidelity class."
        )
    for field in ("coverage_summary", "variation_summary", "justification"):
        if not str(adequacy[field]).strip():
            raise ValueError(f"analysis_adequacy.{field} must be nonempty.")

    accounting = checklist["outcome_accounting"]
    required_accounting = {
        "source_events_total", "analysis_events_total", "aggregation_status",
        "article_events_total", "article_comparison_status", "explanation",
        "evidence_artifact",
    }
    if not isinstance(accounting, dict) or not required_accounting.issubset(accounting):
        raise ValueError("outcome_accounting is incomplete.")
    _require_run_artifact(
        accounting["evidence_artifact"], evidence_root=evidence_root,
        label="outcome_accounting",
    )
    source_total = accounting["source_events_total"]
    analysis_total = accounting["analysis_events_total"]
    if any(not isinstance(value, int) or value < 0 for value in (source_total, analysis_total)):
        raise ValueError("outcome_accounting event totals must be nonnegative integers.")
    if accounting["aggregation_status"] not in {"exact", "explained_difference"}:
        raise ValueError("outcome_accounting.aggregation_status is invalid.")
    if source_total != analysis_total and accounting["aggregation_status"] != "explained_difference":
        raise ValueError(
            "Different source and analysis event totals require an explained aggregation difference."
        )
    article_total = accounting["article_events_total"]
    comparison = accounting["article_comparison_status"]
    if comparison not in OUTCOME_COMPARISON_STATUSES:
        raise ValueError("outcome_accounting.article_comparison_status is invalid.")
    if article_total is None:
        if comparison != "not_reported":
            raise ValueError("A missing article total requires article_comparison_status=not_reported.")
    else:
        if not isinstance(article_total, int) or article_total < 0:
            raise ValueError("outcome_accounting.article_events_total must be null or nonnegative.")
        if comparison == "not_reported":
            raise ValueError("A reported article total must be compared with the extracted outcome.")
        if article_total and analysis_total:
            ratio = analysis_total / article_total
            if not 0.5 <= ratio <= 2.0 and comparison != "explained_difference":
                raise ValueError(
                    "A large difference from the article event total requires evidence and an explanation."
                )
    if not str(accounting["explanation"]).strip():
        raise ValueError("outcome_accounting.explanation must be nonempty.")

    _validate_design_fidelity(checklist["design_fidelity"], evidence_root=evidence_root)
    design = checklist["design_fidelity"]
    if (
        design["sample_membership_status"] == "unknown"
        and included_units < design["public_eligible_units"]
    ):
        raise ValueError(
            "Unknown article sample membership requires all eligible public records in "
            "the primary analysis."
        )

    review = checklist["scientific_review"]
    required_review = {
        "completed", "issues_found", "repairs_made", "unresolved_limitations",
        "strongest_supported_analysis", "evidence_artifact",
    }
    if not isinstance(review, dict) or not required_review.issubset(review):
        raise ValueError("scientific_review is incomplete.")
    if review["completed"] is not True or review["strongest_supported_analysis"] is not True:
        raise ValueError("The skeptical scientific review must be completed before finalization.")
    for field in ("issues_found", "repairs_made", "unresolved_limitations"):
        if not isinstance(review[field], list):
            raise ValueError(f"scientific_review.{field} must be a list.")
    _require_run_artifact(
        review["evidence_artifact"], evidence_root=evidence_root,
        label="scientific_review",
    )
