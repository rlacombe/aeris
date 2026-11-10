#!/usr/bin/env python3
"""Plot published and AERIS-reconstructed effects from the benchmark ledger."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr


def _errorbar_bounds(row: pd.Series, prefix: str) -> tuple[float, float]:
    lower = row.get(f"{prefix}_ci_low")
    upper = row.get(f"{prefix}_ci_high")
    value = row[f"{prefix}_effect"]
    if pd.isna(lower) or pd.isna(upper):
        return 0.0, 0.0
    return value - lower, upper - value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--metrics-output",
        type=Path,
        help="Optional JSON file for the reproducibility-calibration metrics.",
    )
    args = parser.parse_args()

    effects = pd.read_csv(args.input)
    if effects.empty:
        raise SystemExit("Effect-comparison ledger is empty.")

    absolute_log_error = (
        effects["aeris_effect"].map(math.log) - effects["published_effect"].map(math.log)
    ).abs()
    signed_log_error = (
        effects["aeris_effect"].map(math.log) - effects["published_effect"].map(math.log)
    )
    mean_absolute_log_error = absolute_log_error.mean()
    geometric_mean_ratio = math.exp(signed_log_error.mean())
    ci_rows = effects.dropna(subset=["aeris_ci_low", "aeris_ci_high"])
    ci_coverage = (
        ((ci_rows["published_effect"] >= ci_rows["aeris_ci_low"])
        & (ci_rows["published_effect"] <= ci_rows["aeris_ci_high"])).sum()
        if not ci_rows.empty
        else 0
    )
    if len(effects) >= 2:
        published = effects["published_effect"].to_numpy()
        reconstructed = effects["aeris_effect"].to_numpy()
        slope, intercept = np.polyfit(published, reconstructed, 1)
        fitted = intercept + slope * published
        total = float(((reconstructed - reconstructed.mean()) ** 2).sum())
        raw_r_squared = 1 - float(((reconstructed - fitted) ** 2).sum()) / total if total else float("nan")
        pearson_r, pearson_p_value = pearsonr(published, reconstructed)
        spearman_rho, spearman_p_value = spearmanr(published, reconstructed)
    else:
        slope = intercept = raw_r_squared = pearson_r = pearson_p_value = spearman_rho = spearman_p_value = float("nan")
    metrics = {
        "n_studies": int(len(effects)),
        "mean_absolute_log_effect_error": float(mean_absolute_log_error),
        "mean_signed_log_effect_error": float(signed_log_error.mean()),
        "geometric_mean_reconstructed_to_published_ratio": float(geometric_mean_ratio),
        "published_effect_within_aeris_ci": int(ci_coverage),
        "studies_with_aeris_ci": int(len(ci_rows)),
        "raw_scale_calibration_intercept": float(intercept),
        "raw_scale_calibration_slope": float(slope),
        "raw_scale_r_squared": float(raw_r_squared),
        "pearson_r_raw_effects": float(pearson_r),
        "pearson_p_value": float(pearson_p_value),
        "spearman_rho_raw_effects": float(spearman_rho),
        "spearman_p_value": float(spearman_p_value),
    }
    if args.metrics_output:
        args.metrics_output.parent.mkdir(parents=True, exist_ok=True)
        args.metrics_output.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    fig, (ax, metric_ax) = plt.subplots(
        1, 2, figsize=(10.0, 4.5), gridspec_kw={"width_ratios": [1.5, 0.9]}
    )
    low = min(effects["published_effect"].min(), effects["aeris_effect"].min()) * 0.88
    high = max(effects["published_effect"].max(), effects["aeris_effect"].max()) * 1.15
    identity = [low, high]
    ax.plot(identity, identity, color="#626262", linewidth=1.2, linestyle="--", label="Exact agreement")

    for _, row in effects.iterrows():
        xerr = _errorbar_bounds(row, "published")
        yerr = _errorbar_bounds(row, "aeris")
        ax.errorbar(
            row["published_effect"],
            row["aeris_effect"],
            xerr=[[xerr[0]], [xerr[1]]] if any(xerr) else None,
            yerr=[[yerr[0]], [yerr[1]]] if any(yerr) else None,
            fmt="o",
            markersize=7,
            color="#007c91",
            ecolor="#007c91",
            capsize=3,
            zorder=3,
        )
        ax.annotate(
            row["study_label"],
            (row["published_effect"], row["aeris_effect"]),
            xytext=(6, 6),
            textcoords="offset points",
            fontsize=9,
        )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(low, high)
    ax.set_ylim(low, high)
    ax.set_xlabel("Published effect ratio")
    ax.set_ylabel("AERIS-reconstructed effect ratio")
    ax.legend(frameon=False, loc="lower right")
    ax.grid(alpha=0.2)

    metric_ax.axis("off")
    metric_ax.text(0.0, 0.92, "Current benchmark", fontsize=13, fontweight="bold")
    metric_ax.text(0.0, 0.70, f"Completed studies  {len(effects)}", fontsize=11)
    metric_ax.text(0.0, 0.52, f"Mean absolute\nlog-effect error  {mean_absolute_log_error:.3f}", fontsize=11)
    metric_ax.text(0.0, 0.27, f"Geometric mean\neffect ratio  {geometric_mean_ratio:.3f}", fontsize=11)
    metric_ax.text(0.0, 0.11, f"Published-effect CI coverage  {ci_coverage}/{len(ci_rows)}", fontsize=11)
    metric_ax.text(0.0, -0.06, f"Raw-scale R2 {raw_r_squared:.3f}; r {pearson_r:.3f}; rho {spearman_rho:.3f}", fontsize=10, color="#626262")

    fig.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=300, bbox_inches="tight")


if __name__ == "__main__":
    main()
