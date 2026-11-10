#!/usr/bin/env python3
"""Fit the national weighted conditional case-crossover reconstruction."""
from __future__ import annotations

import json
import math
import argparse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import logsumexp

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
OUTPUTS = ROOT / "outputs"


def objective(beta: np.ndarray, groups: list[np.ndarray], observed: np.ndarray, weights: np.ndarray):
    loss, gradient = 0.0, np.zeros_like(beta)
    hessian = np.zeros((len(beta), len(beta)))
    for matrix, index, weight in zip(groups, observed, weights, strict=True):
        linear = matrix @ beta
        probabilities = np.exp(linear - logsumexp(linear))
        expected = probabilities @ matrix
        loss -= weight * (linear[index] - logsumexp(linear))
        gradient -= weight * (matrix[index] - expected)
        centered = matrix - expected
        hessian += weight * (centered.T * probabilities) @ centered
    return loss, gradient, hessian


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, default=DERIVED / "national_analysis_panel_openaq.csv")
    parser.add_argument("--label", default="openaq")
    parser.add_argument("--exposure-record", default="AERIS/OpenAQ daily national monitor-network mean.")
    parser.add_argument("--weather-record", default="Open-Meteo daily mean across AERIS monitor coordinates.")
    args = parser.parse_args()
    panel = pd.read_csv(args.panel)
    needed = ["date", "cancer_deaths", "month", "weekday", "holiday", "pm25_ug_m3_lag0_2", "temperature_c_lag0_2", "relative_humidity_pct_lag0_2"]
    panel = panel.dropna(subset=needed).copy()
    panel["date"] = pd.to_datetime(panel.date)
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    result = {"run_at_utc": datetime.now(timezone.utc).isoformat(), "status": None,
              "published_2015_2019_or_per_10": 1.01,
              "effect_scale": "Odds ratio per 10 ug/m3 PM2.5 (lag 0--2)",
              "model": "Weighted conditional logistic likelihood; same-weekday and same-month referents.",
              "exposure_record": args.exposure_record,
              "weather_record": args.weather_record,
              "eligible_days": len(panel), "cancer_deaths": int(panel.cancer_deaths.sum())}
    if len(panel) < 180 or result["cancer_deaths"] < 20:
        result["status"] = "BLOCKED_INSUFFICIENT_COMPLETE_PANEL"
        (OUTPUTS / f"effect_result_{args.label}.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        return 0
    columns = ["pm25_ug_m3_lag0_2", "temperature_c_lag0_2", "relative_humidity_pct_lag0_2", "holiday"]
    values = panel[columns].astype(float).copy()
    values["pm25_ug_m3_lag0_2"] /= 10
    for column in columns[1:3]:
        values[column] = (values[column] - values[column].mean()) / values[column].std(ddof=0)
    panel["_row"] = np.arange(len(panel))
    groups, observed, weights = [], [], []
    retained = dropped = 0
    for _, row in panel.loc[panel.cancer_deaths > 0].iterrows():
        candidates = panel[(panel.month == row.month) & (panel.weekday == row.weekday)]
        if len(candidates) < 4:
            dropped += int(row.cancer_deaths)
            continue
        rows = candidates._row.to_numpy(dtype=int)
        groups.append(values.iloc[rows].to_numpy())
        observed.append(int(np.where(rows == row._row)[0][0]))
        weights.append(int(row.cancer_deaths))
        retained += int(row.cancer_deaths)
    if not groups:
        result["status"] = "BLOCKED_NO_CASE_CROSSOVER_STRATA"
        (OUTPUTS / f"effect_result_{args.label}.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        return 0
    observed_array, weights_array = np.asarray(observed), np.asarray(weights, dtype=float)
    # Normalize the optimizer's objective by total case weight. The original
    # information matrix is retained below for uncertainty estimation.
    scale = weights_array.sum()
    fit = minimize(
        lambda beta: objective(beta, groups, observed_array, weights_array)[0] / scale,
        np.zeros(len(columns)),
        jac=lambda beta: objective(beta, groups, observed_array, weights_array)[1] / scale,
        hess=lambda beta: objective(beta, groups, observed_array, weights_array)[2] / scale,
        method="trust-exact", options={"gtol": 1e-11, "maxiter": 1000},
    )
    _, score, information = objective(fit.x, groups, observed_array, weights_array)
    covariance = np.linalg.pinv(information)
    beta, se = float(fit.x[0]), float(math.sqrt(max(0, covariance[0, 0])))
    normalized_score = float(np.linalg.norm(score) / scale)
    result.update({"status": "OK" if fit.success or normalized_score <= 1e-9 else "OPTIMIZER_WARNING", "optimizer_message": str(fit.message), "score_norm": float(np.linalg.norm(score)), "normalized_score_norm": normalized_score, "information_min_eigenvalue": float(np.linalg.eigvalsh(information).min()), "n_case_dates": len(groups), "retained_cancer_deaths": retained, "dropped_cancer_deaths": dropped, "effect": {"odds_ratio_per_10_ug_m3": math.exp(beta), "ci95_low": math.exp(beta - 1.96 * se), "ci95_high": math.exp(beta + 1.96 * se), "log_or": beta, "standard_error": se}, "coefficients": dict(zip(columns, fit.x.tolist(), strict=True))})
    (OUTPUTS / f"effect_result_{args.label}.json").write_text(json.dumps(result, indent=2) + "\n")
    result_md = f"# Result\n\nStatus: {result['status'].lower()}.\n\nBrazil, 2015--2019: **OR {result['effect']['odds_ratio_per_10_ug_m3']:.3f}** per 10 ug/m3 PM2.5 (95% CI {result['effect']['ci95_low']:.3f}--{result['effect']['ci95_high']:.3f}).\n\nThe fitted panel contains {result['eligible_days']} complete lagged days and {result['cancer_deaths']:,} cancer deaths. The published 2015--2019 estimate is OR 1.01 per 10 ug/m3.\n\nExposure: {args.exposure_record}\n\nWeather: {args.weather_record}\n\nThe AERIS/OpenAQ audit and the IEMA recovery are documented in `source_manifest.json` and the step manifests.\n"
    (ROOT / f"RESULT_{args.label}.md").write_text(result_md)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
