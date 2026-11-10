#!/usr/bin/env python3
"""Fit the closest public-data version of the paper's daily cluster analysis."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu
from sklearn.cluster import AgglomerativeClustering
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
OUTPUTS = ROOT / "outputs"
FEATURES = ["temperature_variation_c", "rainfall_mm", "relative_humidity_pct", "no2", "pm25", "pm10"]


def bootstrap_mean_difference(high: np.ndarray, comparison: np.ndarray, seed: int = 33227571) -> tuple[float, float]:
    generator = np.random.default_rng(seed)
    draws = np.empty(20_000)
    for index in range(len(draws)):
        draws[index] = generator.choice(high, size=len(high), replace=True).mean() - generator.choice(comparison, size=len(comparison), replace=True).mean()
    return float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def bootstrap_effect_ratio(high: np.ndarray, comparison: np.ndarray, seed: int = 33227571) -> tuple[float, float]:
    generator = np.random.default_rng(seed)
    draws = np.empty(20_000)
    for index in range(len(draws)):
        draws[index] = (
            generator.choice(high, size=len(high), replace=True).mean()
            / generator.choice(comparison, size=len(comparison), replace=True).mean()
        )
    return float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def main() -> int:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    panel = pd.read_csv(DERIVED / "analysis_panel_all_days.csv")
    result: dict[str, object] = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "published": {
            "high_pollution_cluster_days": 218,
            "high_pollution_cluster_daily_admissions": 30.5,
            "reported_increase_percent": 9.0,
            "reported_p_value": "<0.01"
        },
        "model": "Ward hierarchical clustering on standardized daily environmental variables, followed by a cluster-level comparison of daily I21 admissions.",
        "features": FEATURES,
        "departure": "AERIS replaces the original CETESB exposure record and Open-Meteo replaces BDMEP weather. Cluster membership is reconstructed from those inputs."
    }
    panel["temperature_variation_c"] = panel["temperature_max_c"] - panel["temperature_min_c"]
    full_panel = panel.dropna(subset=FEATURES).copy()
    reduced_features = ["temperature_variation_c", "rainfall_mm", "relative_humidity_pct", "no2"]
    reduced_panel = panel.dropna(subset=reduced_features).copy()
    if len(full_panel) >= 180:
        panel = full_panel
        features = FEATURES
        analysis_type = "six-variable cluster reconstruction"
    elif len(reduced_panel) >= 180:
        panel = reduced_panel
        features = reduced_features
        analysis_type = "reduced-input cluster sensitivity: temperature variation, rainfall, humidity, and NO2; PM2.5 and PM10 are unavailable in the recovered historical record"
    else:
        panel = full_panel
        features = FEATURES
        analysis_type = "not fit"
    result["analysis_type"] = analysis_type
    result["features_used"] = features
    if len(panel) < 180:
        result.update({"status": "BLOCKED_INSUFFICIENT_COMPLETE_PANEL", "complete_days": len(panel)})
        (OUTPUTS / "effect_result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        return 0
    values = panel[features].to_numpy(dtype=float)
    standardized = StandardScaler().fit_transform(values)
    labels = AgglomerativeClustering(n_clusters=3, linkage="ward").fit_predict(standardized)
    panel["cluster"] = labels
    cluster_summary = panel.groupby("cluster").agg(days=("date", "size"), admissions_mean=("mi_admissions", "mean"), admissions_median=("mi_admissions", "median"), admissions_q25=("mi_admissions", lambda series: series.quantile(0.25)), admissions_q75=("mi_admissions", lambda series: series.quantile(0.75)), pm25_mean=("pm25", "mean"), pm10_mean=("pm10", "mean"), no2_mean=("no2", "mean"), temperature_variation_mean=("temperature_variation_c", "mean"), humidity_mean=("relative_humidity_pct", "mean"), rainfall_mean=("rainfall_mm", "mean")).reset_index()
    # The article's named exposure pattern is selected using its three pollutant means.
    pollution_columns = [column for column in ["pm25_mean", "pm10_mean", "no2_mean"] if column in cluster_summary]
    cluster_summary["pollution_rank"] = cluster_summary[pollution_columns].rank().mean(axis=1)
    high_cluster = int(cluster_summary.loc[cluster_summary.pollution_rank.idxmax(), "cluster"])
    high = panel.loc[panel.cluster == high_cluster, "mi_admissions"].to_numpy(dtype=float)
    comparison = panel.loc[panel.cluster != high_cluster, "mi_admissions"].to_numpy(dtype=float)
    difference = float(high.mean() - comparison.mean())
    percent = float(100 * difference / comparison.mean())
    ci_low, ci_high = bootstrap_mean_difference(high, comparison)
    ratio_ci_low, ratio_ci_high = bootstrap_effect_ratio(high, comparison)
    test = mannwhitneyu(high, comparison, alternative="two-sided")
    cluster_summary.to_csv(OUTPUTS / "cluster_summary.csv", index=False)
    panel.to_csv(OUTPUTS / "analysis_panel_with_clusters.csv", index=False)
    result.update({
        "status": "OK",
        "complete_days": int(len(panel)),
        "admissions": int(panel.mi_admissions.sum()),
        "high_pollution_cluster": high_cluster,
        "high_pollution_cluster_days": int(len(high)),
        "high_pollution_cluster_daily_admissions": float(high.mean()),
        "comparison_cluster_daily_admissions": float(comparison.mean()),
        "mean_difference_admissions_per_day": difference,
        "bootstrap_ci95_difference": [ci_low, ci_high],
        "bootstrap_ci95_ratio": [ratio_ci_low, ratio_ci_high],
        "percent_increase_vs_other_clusters": percent,
        "mann_whitney_p_value": float(test.pvalue),
        "outputs": {"cluster_summary": "outputs/cluster_summary.csv", "analysis_panel": "outputs/analysis_panel_with_clusters.csv"}
    })
    (OUTPUTS / "effect_result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
