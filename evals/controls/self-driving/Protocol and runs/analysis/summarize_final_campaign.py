#!/usr/bin/env python3
"""Summarize the frozen autonomous campaign from retained result bundles."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


OUTPUT = Path(__file__).resolve().parent
INPUT = OUTPUT / "run-registry" / "r8404"


def read_optional(path: Path) -> dict:
    return json.loads(path.read_text()) if path.is_file() else {}


def main() -> None:
    rows = []
    for run in sorted(path for path in INPUT.iterdir() if path.is_dir()):
        result = read_optional(run / "result.json")
        manifest = read_optional(run / "run_manifest.json")
        validation = read_optional(run / "semantic_validation.json")
        if not validation:
            validation = read_optional(run / "posthoc-semantic-validation-AERIS-self-driving.json")
        effects = result.get("effects") or []
        primary = next((item for item in effects if item.get("primary")), {})
        started = manifest.get("started_at")
        ended = manifest.get("ended_at")
        duration = ""
        if started and ended:
            duration = round(
                (datetime.fromisoformat(ended) - datetime.fromisoformat(started)).total_seconds() / 60,
                3,
            )
        rows.append({
            "run_id": run.name,
            "pmid": (manifest.get("study") or {}).get("pmid", ""),
            "result_status": result.get("status", "missing"),
            "wrapper_status": manifest.get("status", "missing"),
            "fidelity": result.get("fidelity", "none"),
            "effect_count": len(effects),
            "primary_estimate": primary.get("estimate", ""),
            "primary_ci_low": primary.get("ci_low", ""),
            "primary_ci_high": primary.get("ci_high", ""),
            "primary_contrast": primary.get("contrast", ""),
            "eligible_units": (result.get("coverage") or {}).get("eligible_units", ""),
            "included_units": (result.get("coverage") or {}).get("included_units", ""),
            "semantic_valid": validation.get("valid", False),
            "warning_count": len(validation.get("warnings", [])),
            "human_scientific_interventions": manifest.get("human_scientific_interventions", ""),
            "autonomous_review_passes": manifest.get("autonomous_review_passes", 0),
            "duration_minutes": duration,
        })

    OUTPUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT / "r8404-study-results.csv"
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "studies": len(rows),
        "result_statuses": Counter(row["result_status"] for row in rows),
        "fitted_or_sensitivity": sum(
            row["result_status"] in {"completed_fit", "completed_sensitivity"}
            for row in rows
        ),
        "semantic_valid": sum(row["semantic_valid"] for row in rows),
        "zero_intervention": sum(row["human_scientific_interventions"] == 0 for row in rows),
        "total_effects": sum(row["effect_count"] for row in rows),
        "total_warnings": sum(row["warning_count"] for row in rows),
        "total_duration_minutes": round(sum(row["duration_minutes"] or 0 for row in rows), 3),
    }
    (OUTPUT / "r8404-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
