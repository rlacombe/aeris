#!/usr/bin/env python3
"""Combine frozen PubMed slices into an immutable-input screening ledger."""

from __future__ import annotations

import csv
import glob
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"


def main() -> None:
    entries: list[dict[str, str]] = []
    manifests: list[dict[str, object]] = []
    citation_map: dict[str, dict[str, str]] = {}
    citation_path = RAW / "Q4_primary_deduplicated.citations.csv"
    if citation_path.exists():
        with citation_path.open(newline="") as handle:
            citation_map = {row["pmid"]: row for row in csv.DictReader(handle)}
    seen: set[str] = set()
    for manifest_path in sorted(glob.glob(str(RAW / "Q4_primary_*.manifest.json"))):
        manifest = json.loads(Path(manifest_path).read_text())
        manifests.append(manifest)
        ledger_path = RAW / f"{manifest['label']}.screening-ledger.csv"
        with ledger_path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                pmid = row["pmid"]
                if pmid in seen:
                    continue
                seen.add(pmid)
                row["query_slice"] = str(manifest["label"])
                row["pubmed_url"] = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                citation = citation_map.get(pmid, {})
                row["citation"] = f"{citation.get('title', '')} ({citation.get('journal', '')}; {citation.get('publication_date', '')})"
                for field in ("title", "journal", "publication_date", "doi", "pmc_id", "abstract"):
                    row[field] = citation.get(field, "")
                entries.append(row)

    fields = ["query_slice", "pmid", "pubmed_url", "citation", "title", "journal", "publication_date", "doi", "pmc_id", "abstract", "title_abstract_screen", "full_text_screen",
              "human_health_study_evidence", "ambient_pollutant_evidence", "publication_date_evidence", "observation_start_year", "observation_start_evidence_url",
              "outcome_covariate_data_public", "outcome_covariate_data_url", "area_location_time_public",
              "area_location_time_evidence_url", "author_exposure_public_background", "author_exposure_evidence_url",
              "historical_openaq_retrievable", "openaq_evidence_url", "eligibility_decision", "exclusion_reason",
              "screener", "screened_at_utc", "notes"]
    for filename in ("PUBMED_CANDIDATES.csv", "PUBMED_SCREENING_LEDGER.csv"):
        with (ROOT / filename).open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(entries)
    summary = {
        "primary_run": "Q4",
        "publication_window": "2020-01-01 through 2026-06-30",
        "slices": manifests,
        "sum_of_slice_counts": sum(int(item["count"]) for item in manifests),
        "unique_pmids": len(entries),
        "deduplicated_pmids": sum(int(item["count"]) for item in manifests) - len(entries),
    }
    (ROOT / "PRIMARY_PUBMED_RETRIEVAL.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
