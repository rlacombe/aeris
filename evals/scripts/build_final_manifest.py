#!/usr/bin/env python3
"""Build and validate the public AERIS reproduction benchmark inventory."""

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "reproducibility_audit_queue.csv"
OUTPUT = ROOT / "benchmark" / "studies.csv"


def main() -> None:
    with INPUT.open(newline="", encoding="utf-8") as handle:
        audit = list(csv.DictReader(handle))
    runnable = [row for row in audit if row["overall_reproducibility_status"] == "rerunnable_with_adapter"]
    coverage_limited = [row for row in audit if row["overall_reproducibility_status"] == "coverage_limited_candidate"]
    if len(runnable) != 14 or len(coverage_limited) != 1:
        raise SystemExit(
            f"Expected 14 runnable studies and one coverage-limited candidate, found "
            f"{len(runnable)} and {len(coverage_limited)}"
        )
    selected = runnable + coverage_limited
    fields = [
        "benchmark_id", "master_id", "title", "publication_date", "doi", "candidate_origin",
        "outcome_source", "reported_retrieval_url", "outcome_retrieval_evidence",
        "outcome_variable_evidence", "date_key_evidence", "geography_key_evidence",
        "covariate_evidence", "analysis_specification_evidence", "aeris_exposure_evidence",
        "implementation_requirements",
    ]
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for index, row in enumerate(selected, start=1):
            writer.writerow({
                "benchmark_id": index,
                "master_id": row["master_id"],
                "title": row["title"],
                "publication_date": row["publication_date"],
                "doi": row["doi"],
                "candidate_origin": row["candidate_origin"],
                "outcome_source": row["outcome_source"],
                "reported_retrieval_url": row["reported_retrieval_url"],
                "outcome_retrieval_evidence": row["outcome_retrieval_evidence"],
                "outcome_variable_evidence": row["outcome_variable_evidence"],
                "date_key_evidence": row["date_key_evidence"],
                "geography_key_evidence": row["geography_key_evidence"],
                "covariate_evidence": row["covariate_evidence"],
                "analysis_specification_evidence": row["analysis_specification_evidence"],
                "aeris_exposure_evidence": row["aeris_exposure_evidence"],
                "implementation_requirements": row["blocking_issue"],
            })
    print(f"Wrote {len(runnable)} runnable studies and {len(coverage_limited)} coverage-limited candidate to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
