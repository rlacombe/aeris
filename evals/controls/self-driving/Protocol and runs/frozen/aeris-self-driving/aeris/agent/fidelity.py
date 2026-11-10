"""Structured fidelity records for source-substitution reanalysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

FIDELITY_CLASSES = frozenset({
    "matched_fit",
    "source_substitution_fit",
    "reduced_coverage_fit",
    "reduced_adjustment_fit",
    "bounded_fit",
    "supported_sensitivity_fit",
    "bounded_proxy_fit",
    "unsupported_fit",
    "evidenced_stop",
})
FIDELITY_LEVEL_BY_CLASS = {
    "matched_fit": "matched",
    "source_substitution_fit": "source_substitution",
    "reduced_coverage_fit": "reduced_coverage",
    "reduced_adjustment_fit": "reduced_adjustment",
    "bounded_fit": "bounded",
    "bounded_proxy_fit": "bounded",
    "supported_sensitivity_fit": "supported_sensitivity",
}
REQUIRED_FIDELITY_LEVELS = frozenset({
    "matched", "source_substitution", "reduced_coverage", "reduced_adjustment",
    "bounded", "supported_sensitivity",
})
ALLOWED_CHANGE_TYPES_BY_CLASS = {
    "matched_fit": frozenset(),
    "source_substitution_fit": frozenset({"source"}),
    "reduced_coverage_fit": frozenset({"source", "coverage_subset"}),
    "reduced_adjustment_fit": frozenset({
        "source", "coverage_subset", "covariate_omission"
    }),
    "bounded_fit": frozenset({
        "source", "coverage_subset", "covariate_omission", "construct_change"
    }),
    "bounded_proxy_fit": frozenset({
        "source", "coverage_subset", "covariate_omission", "construct_change"
    }),
    "supported_sensitivity_fit": frozenset({
        "source", "coverage_subset", "covariate_omission", "construct_change"
    }),
    "unsupported_fit": frozenset({
        "source", "coverage_subset", "covariate_omission", "construct_change"
    }),
    "evidenced_stop": frozenset({
        "source", "coverage_subset", "covariate_omission", "construct_change"
    }),
}


def _validate_client_source_evidence(value: Any, label: str) -> None:
    """Require retained client implementation evidence, rather than repository metadata."""
    path = Path(str(value))
    try:
        text = path.read_text(encoding="utf-8", errors="replace").lower()
    except OSError:
        text = ""
    metadata_only = (
        path.suffix.lower() == ".json"
        and '"full_name"' in text
        and '"contents_url"' in text
        and not any(marker in text for marker in ('"content"', 'requests.', 'httr::', 'curl '))
    )
    implementation_markers = (
        "requests.get", "requests.post", "httpx.get", "httpx.post",
        "httr::get", "httr::post", "curl ", "fetch(", "urlopen(",
        "request(", "axios.", "xmlhttprequest", "form.action",
    )
    if metadata_only or not any(marker in text for marker in implementation_markers):
        raise ValueError(
            f"{label} evidence must retain an inspected client implementation and its "
            "request logic; repository metadata alone is insufficient."
        )


def validate_recovery_checklist(checklist: dict[str, Any]) -> None:
    """Reject an autonomous stop that has not exhausted approved recovery paths."""
    attempts = checklist.get("executable_attempts", [])
    if not isinstance(attempts, list) or not attempts:
        raise ValueError("Autonomous stops require executable attempt records.")
    invalid_attempts = []
    for index, attempt in enumerate(attempts):
        if not isinstance(attempt, dict):
            invalid_attempts.append(index)
            continue
        executable = str(attempt.get("request_url") or attempt.get("command") or "").strip()
        source_role = str(attempt.get("source_role", "")).strip().lower()
        observed = any(
            key in attempt for key in
            ("response_status", "captured_error", "bytes_returned", "records_returned")
        )
        inspected = bool(attempt.get("schema_or_format_inspection"))
        attempt_count = attempt.get("attempt_count")
        transient = any(
            token in str(attempt.get("captured_error", "")).lower()
            for token in ("timeout", "timed out", "connection", "dns", "rate limit", "server error")
        )
        client_error = any(
            token in str(attempt.get("captured_error", "")).lower()
            for token in (
                "no connection adapters", "unsupported protocol", "unknown url type",
                "command not found", "module not found", "no module named",
            )
        )
        retried = isinstance(attempt_count, int) and attempt_count >= (3 if transient else 1)
        if (source_role not in {"outcome", "exposure", "covariate", "article"}
                or not executable or not observed or not inspected or client_error
                or not attempt.get("evidence_artifact") or not retried):
            invalid_attempts.append(index)
    if invalid_attempts:
        raise ValueError(
            "Executable attempt records need a URL or command, an observed result, "
            "format inspection, a saved artifact, and sufficient attempt_count "
            "(at least three for transient failures). Client or parser errors do not "
            "establish source unavailability; invalid indexes: "
            + ", ".join(map(str, invalid_attempts))
        )
    downloadable_suffixes = {
        ".7z", ".bz2", ".csv", ".dbc", ".dbf", ".feather", ".gz", ".json",
        ".nc", ".parquet", ".rar", ".tar", ".tif", ".tiff", ".tsv", ".xls",
        ".xlsx", ".xz", ".zip",
    }
    failed_file_attempts = []
    for attempt in attempts:
        request_tokens = str(attempt.get("request_url", "")).split()
        if not request_tokens:
            continue
        request_url = request_tokens[0]
        suffix = Path(urlparse(request_url).path).suffix.lower()
        failed = bool(attempt.get("captured_error")) or (
            attempt.get("bytes_returned") == 0 and attempt.get("records_returned", 0) == 0
        )
        if suffix in downloadable_suffixes and failed:
            failed_file_attempts.append(request_url)
    if failed_file_attempts:
        if checklist.get("exact_file_mirror_search_attempted") is not True:
            raise ValueError(
                "A failed downloadable-file route requires an exact-filename mirror search: "
                + ", ".join(failed_file_attempts)
            )
        if not checklist.get("exact_file_mirror_search_evidence"):
            raise ValueError("Exact-filename mirror searches require saved evidence.")
        if checklist.get("exact_file_search_results_followed") is not True:
            raise ValueError(
                "Plausible exact-filename mirror results must be opened and exercised."
            )
        queries = checklist.get("exact_file_mirror_queries", [])
        normalized_queries = {
            str(query).strip().lower() for query in queries if str(query).strip()
        } if isinstance(queries, list) else set()
        if len(normalized_queries) < 2:
            raise ValueError(
                "Exact-filename recovery requires at least two distinct literal queries "
                "across independent discovery routes."
            )
        missing_names = []
        for failed_url in failed_file_attempts:
            basename = Path(urlparse(failed_url).path).name.lower()
            if not any(basename in query for query in normalized_queries):
                missing_names.append(basename)
        if missing_names:
            raise ValueError(
                "Exact-filename queries did not contain the failed basename(s): "
                + ", ".join(missing_names)
            )
        evidence_path = Path(str(checklist["exact_file_mirror_search_evidence"]))
        try:
            evidence_text = evidence_path.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            evidence_text = ""
        if not all(Path(urlparse(url).path).name.lower() in evidence_text
                   for url in failed_file_attempts):
            raise ValueError(
                "Exact-filename search evidence must record each failed basename and its results."
            )
    if "oversized_public_source_applicable" not in checklist:
        raise ValueError(
            "Blocker review must state whether a large public corpus or mirror was found."
        )
    if checklist.get("oversized_public_source_applicable"):
        if checklist.get("partition_or_selective_access_tested") is not True:
            raise ValueError(
                "A large public corpus requires tests of partitions, object listings, range "
                "access, or query endpoints before size can establish a blocker."
            )
        if not checklist.get("partition_or_selective_access_evidence"):
            raise ValueError("Selective-access tests require a saved evidence artifact.")
    required_true = ("target_specification_complete", "complete_article_checked", "normal_exposure_source_tested")
    missing = [name for name in required_true if checklist.get(name) is not True]
    if missing:
        raise ValueError(f"Recovery checklist is incomplete: {', '.join(missing)}")
    if int(checklist.get("outcome_routes_attempted", 0)) < 3:
        raise ValueError("Autonomous stops require at least three outcome recovery routes.")
    search_attempts = checklist.get("public_dataset_search_attempts", [])
    if not isinstance(search_attempts, list) or len(search_attempts) < 2:
        raise ValueError(
            "Autonomous stops require at least two distinct public data/code repository searches."
        )
    allowed_routes = {"dataset_catalog", "code_repository", "web_search", "package_registry"}
    queries: set[str] = set()
    routes: set[str] = set()
    strategies: set[str] = set()
    broad_search_roles: set[str] = set()
    invalid_searches: list[int] = []
    for index, search in enumerate(search_attempts):
        if not isinstance(search, dict):
            invalid_searches.append(index)
            continue
        query = str(search.get("query", "")).strip().lower()
        strategy = str(search.get("query_strategy", "")).strip().lower()
        source_role = str(search.get("source_role", "")).strip().lower()
        route = str(search.get("route_type", "")).strip().lower()
        evidence = str(search.get("evidence_artifact", "")).strip()
        candidates = search.get("candidates", [])
        valid_candidates = isinstance(candidates, list)
        if valid_candidates:
            for candidate in candidates:
                if (not isinstance(candidate, dict)
                        or not str(candidate.get("url", "")).strip()
                        or candidate.get("disposition") not in {
                            "exercised_usable", "exercised_unusable", "irrelevant"
                        }
                        or not str(candidate.get("evidence_artifact", "")).strip()):
                    valid_candidates = False
                    break
                if candidate["disposition"] == "irrelevant":
                    if not str(candidate.get("rationale", "")).strip():
                        valid_candidates = False
                        break
                    continue
                executable = str(
                    candidate.get("request_url") or candidate.get("command") or ""
                ).strip()
                observed = any(
                    key in candidate for key in (
                        "response_status", "captured_error", "bytes_returned", "records_returned"
                    )
                )
                if (not executable or not observed
                        or not str(candidate.get("schema_or_format_inspection", "")).strip()):
                    valid_candidates = False
                    break
        if (not query or source_role not in {
                "outcome", "exposure", "covariate", "article"
            } or strategy not in {
                "artifact_exact", "source_ecosystem", "native_language", "package_registry"
            } or route not in allowed_routes or not evidence
                or not valid_candidates):
            invalid_searches.append(index)
            continue
        queries.add(query)
        routes.add(route)
        strategies.add(strategy)
        if strategy in {"source_ecosystem", "native_language"}:
            broad_search_roles.add(source_role)
    if invalid_searches:
        raise ValueError(
            "Public dataset searches require a query, query strategy, route type, saved "
            "search response, and an evidence-backed disposition for every returned "
            "candidate. Usable and unusable dispositions require an executed request or "
            "command and observed response; invalid indexes: "
            + ", ".join(map(str, invalid_searches))
        )
    if len(queries) < 2 or len(routes) < 2:
        raise ValueError(
            "Public dataset recovery requires distinct queries across at least two route types."
        )
    if not strategies.intersection({"source_ecosystem", "native_language"}):
        raise ValueError(
            "Public dataset recovery requires a source-level or native-language search, "
            "rather than filename searches alone."
        )
    failed_roles = {
        str(attempt.get("source_role", "")).strip().lower()
        for attempt in attempts
        if attempt.get("captured_error") or (
            attempt.get("bytes_returned") == 0 and attempt.get("records_returned", 0) == 0
        )
    }
    missing_broad_search = failed_roles.difference(broad_search_roles)
    if missing_broad_search:
        raise ValueError(
            "Each failed source role requires a source-level or native-language search: "
            + ", ".join(sorted(missing_broad_search))
        )
    if not any(search.get("candidates") for search in search_attempts):
        raise ValueError(
            "A terminal blocker requires preserved search responses and candidate dispositions; "
            "empty self-reported searches are insufficient."
        )
    if checklist.get("historical_fallback_applicable") and not checklist.get("historical_fallback_tested"):
        raise ValueError("Historical exposure fallback was applicable but not tested.")
    if checklist.get("article_named_regulator_applicable") is not False:
        if checklist.get("article_named_regulator_attempted") is not True:
            raise ValueError("The article-named exposure regulator must be attempted before stopping.")
        if not checklist.get("article_named_regulator_evidence"):
            raise ValueError("A stopped run requires saved evidence from the article-named regulator.")
        if checklist.get("article_named_regulator_interface_inspected") is not True:
            raise ValueError(
                "A regulator landing or login page must be inspected for public forms, "
                "scripts, request targets, reports, archives, and legacy interfaces."
            )
        if int(checklist.get("article_named_regulator_routes_attempted", 0)) < 3:
            raise ValueError(
                "A stopped run requires at least three distinct regulator recovery routes."
            )
        if int(checklist.get("article_named_regulator_search_queries", 0)) < 2:
            raise ValueError(
                "A stopped run requires public discovery searches for the regulator's "
                "historical data and legacy interfaces."
            )
        if not checklist.get("article_named_regulator_search_evidence"):
            raise ValueError("Regulator discovery searches require saved evidence.")
        if checklist.get("article_named_regulator_results_followed") is not True:
            raise ValueError(
                "Plausible regulator search results must be opened and exercised before stopping."
            )
        if checklist.get("article_named_regulator_public_client_inspected") is not True:
            raise ValueError(
                "Search public clients or source code for regulator request routes before stopping."
            )
        if not checklist.get("article_named_regulator_client_evidence"):
            raise ValueError("Public-client inspection requires saved evidence.")
        _validate_client_source_evidence(
            checklist["article_named_regulator_client_evidence"],
            "Regulator public-client",
        )
    elif not checklist.get("article_named_regulator_applicability_evidence"):
        raise ValueError(
            "Declaring no article-named exposure source requires saved article evidence."
        )
    if checklist.get("official_bulk_endpoint_failed"):
        if checklist.get("exact_file_mirror_search_attempted") is not True:
            raise ValueError("A failed official bulk endpoint requires an exact-file mirror search.")
        if not checklist.get("exact_file_mirror_search_evidence"):
            raise ValueError("A stopped run requires saved evidence from the exact-file mirror search.")
        if checklist.get("exact_file_search_results_followed") is not True:
            raise ValueError(
                "Exact-file search results and applicable open-source clients must be inspected "
                "before closing a failed bulk-data route."
            )
        route_types = set(checklist.get("exact_file_mirror_route_types", []))
        if len(route_types) < 2 or route_types.issubset({"code_repository"}):
            raise ValueError(
                "Bulk-file recovery requires at least two distinct search route types, "
                "including an institutional portal, general web search, dataset catalog, "
                "or public archive rather than code-host search alone."
            )
        if checklist.get("bulk_public_client_inspected") is not True:
            raise ValueError(
                "A failed bulk-data route requires inspection of a public client or parser."
            )
        if not checklist.get("bulk_public_client_evidence"):
            raise ValueError("Bulk public-client inspection requires saved evidence.")
        _validate_client_source_evidence(
            checklist["bulk_public_client_evidence"],
            "Bulk-data public-client",
        )
    if checklist.get("geographic_batching_applicable"):
        if not checklist.get("geographic_batching_attempted"):
            raise ValueError("Geographic batching was applicable but not attempted.")
        if not checklist.get("geographic_batches_exhausted"):
            raise ValueError("Every deterministic geographic batch must be exhausted before stopping.")
    eligible_units = checklist.get("eligible_units")
    attempted_units = checklist.get("exposure_units_attempted")
    if not isinstance(eligible_units, int) or eligible_units < 1:
        raise ValueError("Autonomous stops require the target eligible-unit count.")
    if not isinstance(attempted_units, int) or attempted_units < 0:
        raise ValueError("Autonomous stops require the number of exposure units attempted.")
    if attempted_units < eligible_units:
        raise ValueError(
            f"Exposure retrieval attempted {attempted_units} of {eligible_units} eligible units."
        )
    evaluated = set(checklist.get("fidelity_levels_evaluated", []))
    if evaluated != REQUIRED_FIDELITY_LEVELS:
        raise ValueError("Autonomous stops must evaluate the complete fidelity ladder.")
    if int(checklist.get("pending_requests", -1)) != 0:
        raise ValueError("Autonomous stops require zero pending requests.")
    if not checklist.get("evidence_artifacts"):
        raise ValueError("Autonomous stops require recovery evidence artifacts.")
    counterexamples = checklist.get("stop_counterexamples_tested", [])
    if not isinstance(counterexamples, list) or not counterexamples:
        raise ValueError("Autonomous stops must test concrete counterexamples to the blocker.")
    if not checklist.get("stop_counterexample_evidence"):
        raise ValueError("Autonomous stops require saved evidence for blocker counterexamples.")


def validate_construct_change_recovery(checklist: dict[str, Any]) -> None:
    """Require article-designated data routes before accepting a changed construct."""
    if checklist.get("author_repository_applicable") is not False:
        if checklist.get("author_repository_attempted") is not True:
            raise ValueError(
                "A construct change requires an attempt to recover the article-designated repository."
            )
        if not checklist.get("author_repository_evidence"):
            raise ValueError(
                "A construct change requires saved evidence from the article-designated repository."
            )


@dataclass(frozen=True)
class FidelityRecord:
    """Machine-readable account of what a reanalysis preserved and changed."""

    study_id: str
    fidelity_class: str
    status: str
    preserved_dimensions: tuple[str, ...]
    deviations: tuple[dict[str, Any], ...]
    evidence_artifacts: tuple[str, ...]
    reported_variants: tuple[str, ...] = ()
    notes: str = ""
    recovery_checklist: dict[str, Any] | None = None
    final_analysis_checklist: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.fidelity_class not in FIDELITY_CLASSES:
            raise ValueError(f"Unknown fidelity class: {self.fidelity_class}")
        if self.status not in {"fitted", "stopped"}:
            raise ValueError("Fidelity status must be fitted or stopped.")
        if self.fidelity_class == "evidenced_stop" and self.status != "stopped":
            raise ValueError("evidenced_stop requires status=stopped.")
        if self.status == "stopped" and self.fidelity_class != "evidenced_stop":
            raise ValueError("Stopped runs require fidelity_class=evidenced_stop.")
        if self.status == "stopped" and not self.evidence_artifacts:
            raise ValueError("Stopped runs require at least one evidence artifact.")
        change_types = {
            str(item.get("change_type", "")) for item in self.deviations
            if isinstance(item, dict)
        }
        unknown = change_types.difference({
            "source", "coverage_subset", "covariate_omission", "construct_change"
        })
        if unknown:
            raise ValueError("Unknown fidelity change types: " + ", ".join(sorted(unknown)))
        unsupported = change_types.difference(ALLOWED_CHANGE_TYPES_BY_CLASS[self.fidelity_class])
        if unsupported:
            raise ValueError(
                f"{self.fidelity_class} cannot contain changes: "
                + ", ".join(sorted(unsupported))
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
