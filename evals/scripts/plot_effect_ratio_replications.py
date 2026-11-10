#!/usr/bin/env python3
"""Plot all fitted published/AERIS effect-ratio pairs."""

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "benchmark" / "effect_ratio_comparisons.csv"
METRICS = ROOT / "benchmark" / "effect_ratio_replication_metrics.json"
OUTPUT = ROOT.parent / "aeris-genai4health" / "figures" / "effect_calibration.png"

LABELS = [
    "UK", "IT", "FR", "O60-C", "O60-D", "O80-C", "O80-D", "IL",
    "NI-I", "NI-M", "SJ-O3", "SJ-NO2", "SP-AMI", "BR", "US",
]


def value(row, key):
    return float(row[key]) if row[key] else None


def main():
    with INPUT.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    metrics = json.loads(METRICS.read_text())

    fig, (ax, summary) = plt.subplots(
        1, 2, figsize=(10.2, 4.5), gridspec_kw={"width_ratios": [1.45, 1]}
    )
    low, high = 0.94, 1.9
    ax.plot([low, high], [low, high], "--", color="#666666", linewidth=1.1)

    for i, row in enumerate(rows):
        published = value(row, "published_ratio")
        aeris = value(row, "aeris_ratio")
        p_low, p_high = value(row, "published_ci_low"), value(row, "published_ci_high")
        a_low, a_high = value(row, "aeris_ci_low"), value(row, "aeris_ci_high")
        xerr = [[published - p_low], [p_high - published]] if p_low and p_high else None
        yerr = [[aeris - a_low], [a_high - aeris]] if a_low and a_high else None
        ax.errorbar(
            published, aeris, xerr=xerr, yerr=yerr, fmt="o", markersize=5.5,
            color="#007c91", ecolor="#007c91", elinewidth=0.9, capsize=2,
            zorder=3,
        )
        ax.annotate(LABELS[i], (published, aeris), xytext=(4, 4),
                    textcoords="offset points", fontsize=7)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(low, high)
    ax.set_ylim(low, high)
    ax.set_xlabel("Published OR or RR")
    ax.set_ylabel("AERIS OR or RR")
    ax.grid(alpha=0.2)

    summary.axis("off")
    summary.text(0, 0.95, "Meta-replication", fontsize=13, fontweight="bold")
    lines = [
        f"Effect pairs  {metrics['effect_pairs']}",
        f"Pearson r  {metrics['pearson_r']:.3f}",
        f"Spearman rho  {metrics['spearman_rho']:.3f}",
        f"Identity R2  {metrics['identity_r_squared']:.3f}",
        f"Mean |log error|  {metrics['mean_absolute_log_effect_error']:.3f}",
        f"Geometric mean ratio  {metrics['geometric_mean_reconstructed_to_published_ratio']:.3f}",
        f"Direction agreement  9/13",
        f"CI overlap  {metrics['confidence_interval_overlap']}/{metrics['confidence_interval_pairs']}",
    ]
    for i, line in enumerate(lines):
        summary.text(0, 0.80 - i * 0.095, line, fontsize=10.5)
    summary.text(0, 0.03, "Labels: UK, IT, FR, OECD, IL, NI, SJ, SP, BR, US", fontsize=7.5, color="#555555")

    fig.tight_layout()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, dpi=300, bbox_inches="tight")


if __name__ == "__main__":
    main()
