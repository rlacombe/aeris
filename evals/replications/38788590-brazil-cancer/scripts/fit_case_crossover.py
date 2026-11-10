#!/usr/bin/env python3
"""Fit a weighted conditional-logit approximation to the paper's case-crossover model."""

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


def conditional_objective(beta: np.ndarray, groups: list[np.ndarray], case_index: np.ndarray, weights: np.ndarray):
    """Negative conditional log likelihood, its gradient, and observed information."""
    loss = 0.0
    gradient = np.zeros_like(beta)
    hessian = np.zeros((len(beta), len(beta)))
    for matrix, observed, weight in zip(groups, case_index, weights, strict=True):
        linear = matrix @ beta
        log_denominator = logsumexp(linear)
        probabilities = np.exp(linear - log_denominator)
        expected = probabilities @ matrix
        difference = matrix[observed] - expected
        loss -= weight * (linear[observed] - log_denominator)
        gradient -= weight * difference
        centered = matrix - expected
        hessian += weight * (centered.T * probabilities) @ centered
    return loss, gradient, hessian


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, default=DERIVED / "analysis_panel.csv")
    parser.add_argument("--output", type=Path, default=OUTPUTS / "effect_result.json")
    parser.add_argument(
        "--exposure-label",
        default="AERIS PM2.5 3-day average, lag 0-2, scaled per 10 ug/m3.",
    )
    args = parser.parse_args()
    panel = pd.read_csv(args.panel)
    required = [
        "date", "cancer_deaths", "month", "weekday", "holiday",
        "pm25_ug_m3_lag0_2", "temperature_c_lag0_2", "relative_humidity_pct_lag0_2",
    ]
    missing = sorted(set(required) - set(panel.columns))
    if missing:
        raise RuntimeError(f"Panel is missing: {missing}")
    panel = panel.dropna(subset=required).copy()
    panel["date"] = pd.to_datetime(panel["date"])
    eligible_days = len(panel)
    deaths = int(panel["cancer_deaths"].sum())
    result: dict[str, object] = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "eligible_days": eligible_days,
        "cancer_deaths": deaths,
        "published_full_period_or_per_10": 1.04,
        "published_2015_2019_or_per_10": 1.01,
        "model": "Weighted conditional logistic likelihood with same-weekday, same-month referents.",
        "exposure": args.exposure_label,
        "covariates": "Linear 3-day average temperature, linear 3-day average relative humidity, national-holiday indicator.",
        "departure": "The paper used a distributed-lag temperature cross-basis and population-weighted ERA5 covariates; this run uses a linear no-auth weather substitute.",
    }
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    if eligible_days < 180 or deaths < 20:
        result.update({"status": "BLOCKED_INSUFFICIENT_COMPLETE_PANEL", "fit": None})
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        return 0

    covariate_columns = [
        "pm25_ug_m3_lag0_2", "temperature_c_lag0_2", "relative_humidity_pct_lag0_2", "holiday",
    ]
    values = panel[covariate_columns].astype(float).copy()
    values["pm25_ug_m3_lag0_2"] /= 10.0
    for column in ("temperature_c_lag0_2", "relative_humidity_pct_lag0_2"):
        values[column] = (values[column] - values[column].mean()) / values[column].std(ddof=0)
    panel["_row"] = np.arange(len(panel))
    groups: list[np.ndarray] = []
    case_index: list[int] = []
    weights: list[int] = []
    retained_deaths = 0
    dropped_deaths_no_referent = 0
    for _, row in panel.loc[panel["cancer_deaths"] > 0].iterrows():
        candidates = panel[(panel["month"] == row["month"]) & (panel["weekday"] == row["weekday"])]
        if len(candidates) < 4:
            dropped_deaths_no_referent += int(row["cancer_deaths"])
            continue
        ordered_rows = candidates["_row"].to_numpy(dtype=int)
        observed = int(np.where(ordered_rows == int(row["_row"]))[0][0])
        groups.append(values.iloc[ordered_rows].to_numpy())
        case_index.append(observed)
        weights.append(int(row["cancer_deaths"]))
        retained_deaths += int(row["cancer_deaths"])
    if retained_deaths < 20 or not groups:
        result.update({"status": "BLOCKED_NO_CASE_CROSSOVER_STRATA", "fit": None})
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        return 0

    case_array = np.asarray(case_index, dtype=int)
    weight_array = np.asarray(weights, dtype=float)

    optimization = minimize(
        fun=lambda beta: conditional_objective(beta, groups, case_array, weight_array)[0],
        x0=np.zeros(len(covariate_columns)),
        jac=lambda beta: conditional_objective(beta, groups, case_array, weight_array)[1],
        hess=lambda beta: conditional_objective(beta, groups, case_array, weight_array)[2],
        method="trust-exact",
        options={"gtol": 1e-8, "maxiter": 1000},
    )
    _, _, information = conditional_objective(optimization.x, groups, case_array, weight_array)
    _, score, _ = conditional_objective(optimization.x, groups, case_array, weight_array)
    score_norm = float(np.linalg.norm(score))
    information_eigenvalues = np.linalg.eigvalsh(information)
    covariance = np.linalg.pinv(information)
    pm_beta = float(optimization.x[0])
    pm_se = float(math.sqrt(max(0.0, covariance[0, 0])))
    result.update(
        {
            "status": "OK" if optimization.success or score_norm <= 1e-5 else "OPTIMIZER_WARNING",
            "optimizer": "trust-exact",
            "optimizer_message": optimization.message,
            "score_norm": score_norm,
            "information_min_eigenvalue": float(information_eigenvalues.min()),
            "n_case_dates": len(groups),
            "retained_cancer_deaths": retained_deaths,
            "dropped_deaths_no_referent": dropped_deaths_no_referent,
            "effect": {
                "odds_ratio_per_10_ug_m3": math.exp(pm_beta),
                "ci95_low": math.exp(pm_beta - 1.96 * pm_se),
                "ci95_high": math.exp(pm_beta + 1.96 * pm_se),
                "log_or": pm_beta,
                "standard_error": pm_se,
            },
            "coefficients": dict(zip(covariate_columns, optimization.x.tolist(), strict=True)),
        }
    )
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
