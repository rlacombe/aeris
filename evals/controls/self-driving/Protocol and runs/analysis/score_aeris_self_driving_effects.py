#!/usr/bin/env python3
"""Score predeclared article-matched contrasts from the frozen AERIS-self-driving runs."""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis" / "final-campaign"
CONFIG = OUT / "AERIS-self-driving-comparison-map.json"


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


def direction(value: float, tolerance: float = 1e-12) -> int:
    if value > 1 + tolerance:
        return 1
    if value < 1 - tolerance:
        return -1
    return 0


def numerical_summary(rows: list[dict]) -> dict:
    by_study: defaultdict[tuple[int, str], list[dict]] = defaultdict(list)
    for row in rows:
        if row.get("include_effect_size", True):
            by_study[(int(row["replicate"]), str(row["pmid"]))].append(row)

    studies = []
    for (replicate, pmid), contrasts in sorted(by_study.items()):
        published_logs = [math.log(float(row["published"])) for row in contrasts]
        reconstructed_logs = [math.log(float(row["reconstructed"])) for row in contrasts]
        studies.append(
            {
                "replicate": replicate,
                "pmid": pmid,
                "published": math.exp(statistics.mean(published_logs)),
                "reconstructed": math.exp(statistics.mean(reconstructed_logs)),
                "absolute_log_difference": statistics.mean(
                    abs(reconstructed - published)
                    for published, reconstructed in zip(
                        published_logs, reconstructed_logs
                    )
                ),
                "signed_log_ratio": statistics.mean(
                    reconstructed - published
                    for published, reconstructed in zip(
                        published_logs, reconstructed_logs
                    )
                ),
            }
        )

    published = [row["published"] for row in studies]
    reconstructed = [row["reconstructed"] for row in studies]
    return {
        "effect_size_contrasts": sum(len(value) for value in by_study.values()),
        "effect_size_studies": len(studies),
        "median_study_absolute_log_difference": statistics.median(
            row["absolute_log_difference"] for row in studies
        ),
        "geometric_mean_reconstructed_to_published": math.exp(
            statistics.mean(row["signed_log_ratio"] for row in studies)
        ),
        "pearson_ratio_study_level": pearson(published, reconstructed),
    }


def main() -> None:
    config = json.loads(CONFIG.read_text())
    rows = []
    for item in config["comparisons"]:
        published = float(item["published"])
        reconstructed = float(item["reconstructed"])
        ci_low = item.get("ci_low")
        ci_high = item.get("ci_high")
        conclusion = item["published_conclusion"]
        row = {
            **item,
            "absolute_log_difference": abs(math.log(reconstructed) - math.log(published)),
            "signed_log_ratio": math.log(reconstructed / published),
            "same_positive_direction": conclusion == "positive"
            and direction(reconstructed) == direction(published),
            "null_conclusion_retained": conclusion == "null"
            and ci_low is not None
            and ci_high is not None
            and float(ci_low) <= 1 <= float(ci_high),
        }
        rows.append(row)

    with (OUT / "AERIS-self-driving-effect-comparisons.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    summaries = {}
    by_replicate: defaultdict[int, list[dict]] = defaultdict(list)
    for row in rows:
        by_replicate[int(row["replicate"])].append(row)

    for replicate, replicate_rows in sorted(by_replicate.items()):
        positive = [row for row in replicate_rows if row["published_conclusion"] == "positive"]
        null = [row for row in replicate_rows if row["published_conclusion"] == "null"]
        summaries[replicate] = {
            "comparable_contrasts": len(replicate_rows),
            "positive_same_direction": sum(row["same_positive_direction"] for row in positive),
            "positive_denominator": len(positive),
            "null_retained": sum(row["null_conclusion_retained"] for row in null),
            "null_denominator": len(null),
            **numerical_summary(replicate_rows),
        }

    positive = [row for row in rows if row["published_conclusion"] == "positive"]
    null = [row for row in rows if row["published_conclusion"] == "null"]
    aggregate = {
        "comparison_rule": config["comparison_rule"],
        "campaigns": summaries,
        "pooled": {
            "comparable_contrasts": len(rows),
            "positive_same_direction": sum(row["same_positive_direction"] for row in positive),
            "positive_denominator": len(positive),
            "null_retained": sum(row["null_conclusion_retained"] for row in null),
            "null_denominator": len(null),
            **numerical_summary(rows),
        },
    }
    (OUT / "AERIS-self-driving-effect-agreement-summary.json").write_text(
        json.dumps(aggregate, indent=2) + "\n"
    )
    print(json.dumps(aggregate, indent=2))


if __name__ == "__main__":
    main()
