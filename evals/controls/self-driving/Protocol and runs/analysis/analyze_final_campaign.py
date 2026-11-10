#!/usr/bin/env python3
"""Post hoc agreement analysis for the frozen r8404 autonomous campaign."""

from __future__ import annotations

import csv
import json
import math
import statistics
from pathlib import Path


OUT = Path(__file__).resolve().parent
RUNS = OUT / "run-registry" / "r8404"

# Publication values are joined only after each autonomous run is final. Labels
# identify directly comparable pollutant and contrast definitions.
COMPARISONS = [
    ("33398753", "2020-04-07 infections: adjusted outcome ratio per doubling PM10 exceedance days", 1.76),
    ("33484722", "Day-60 case-rate ratio", 1.020),
    ("33484722", "Day-60 death-rate ratio", 1.030),
    ("33484722", "Day-80 case-rate ratio", 1.020),
    ("33484722", "Day-80 death-rate ratio", 1.009),
    ("34004167", "NO2 STAP—incident cases", 1.000),
    ("34004167", "NO2 STAP—incident deaths", 1.000),
    ("34488764", "Continuous PM2.5, fully adjusted", 1.240),
    ("36383802", "O3 lag 2 (bounded sensitivity)", 1.061),
    ("36383802", "NO2 lag 3 (bounded sensitivity)", 1.125),
    ("38182658", "Bounded PM2.5 lag-10 sensitivity", 1.130),
    ("38788590", "All-cancer mortality, Sao Paulo 2019 bounded slice", 1.010),
]


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    x_mean, y_mean = statistics.mean(xs), statistics.mean(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    denominator = math.sqrt(
        sum((x - x_mean) ** 2 for x in xs)
        * sum((y - y_mean) ** 2 for y in ys)
    )
    return numerator / denominator if denominator else None


def main() -> None:
    results: dict[str, dict] = {}
    for directory in RUNS.iterdir():
        if not directory.is_dir():
            continue
        result = json.loads((directory / "result.json").read_text())
        manifest = json.loads((directory / "run_manifest.json").read_text())
        results[str(manifest["study"]["pmid"])] = result

    rows = []
    for pmid, label, published in COMPARISONS:
        effects = {
            effect["label"]: effect for effect in results.get(pmid, {}).get("effects", [])
        }
        if label not in effects:
            continue
        autonomous = float(effects[label]["estimate"])
        error = abs(math.log(autonomous) - math.log(published))
        rows.append({
            "pmid": pmid,
            "effect_label": label,
            "published": published,
            "autonomous": autonomous,
            "absolute_log_difference": error,
            "multiplicative_separation": math.exp(error),
            "same_direction_around_one": (published - 1) * (autonomous - 1) >= 0,
        })

    with (OUT / "r8404-effect-agreement.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    published = [row["published"] for row in rows]
    autonomous = [row["autonomous"] for row in rows]
    errors = [row["absolute_log_difference"] for row in rows]
    summary = {
        "comparison_rule": "same pollutant and directly normalized published contrast",
        "comparable_contrasts": len(rows),
        "studies_with_comparable_contrasts": len({row["pmid"] for row in rows}),
        "excluded": {
            "33227571": "autonomous blocker; no pollutant fit",
            "39377000": "bounded all-stroke outcome-ratio presentation is not directly comparable to the published ischemic-stroke contrast",
        },
        "same_direction_around_one": sum(row["same_direction_around_one"] for row in rows),
        "median_absolute_log_difference": statistics.median(errors),
        "mean_absolute_log_difference": statistics.mean(errors),
        "median_multiplicative_separation": math.exp(statistics.median(errors)),
        "pearson_ratio": pearson(published, autonomous),
        "pearson_log_ratio": pearson(
            [math.log(value) for value in published],
            [math.log(value) for value in autonomous],
        ),
    }
    (OUT / "r8404-effect-agreement-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
