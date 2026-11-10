#!/usr/bin/env python3
"""Fit the paper's multipollutant lag scan with a negative-binomial likelihood."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
OUTPUTS = ROOT / "outputs"


def finite_hessian(function, point: np.ndarray, step: float = 1e-4) -> np.ndarray:
    size = len(point)
    hessian = np.empty((size, size))
    baseline = function(point)
    for i in range(size):
        for j in range(i, size):
            ei, ej = np.zeros(size), np.zeros(size)
            ei[i], ej[j] = step, step
            if i == j:
                value = (function(point + ei) - 2 * baseline + function(point - ei)) / step**2
            else:
                value = (function(point + ei + ej) - function(point + ei - ej) - function(point - ei + ej) + function(point - ei - ej)) / (4 * step**2)
            hessian[i, j] = hessian[j, i] = value
    return hessian


def fit(frame: pd.DataFrame, lag: int) -> dict:
    exposure_columns = [f"pm25_ug_m3_lag{lag}", f"no2_ug_m3_lag{lag}", f"o3_ug_m3_lag{lag}"]
    columns = ["admissions_b342", *exposure_columns, "temperature_c", "relative_humidity_pct", "day_index", "weekday"]
    data = frame.dropna(subset=columns).copy()
    y = data["admissions_b342"].to_numpy(float)
    continuous = [*exposure_columns, "temperature_c", "relative_humidity_pct", "day_index"]
    standardized = data[continuous].astype(float).copy()
    means, scales = standardized.mean(), standardized.std(ddof=0).replace(0, 1)
    standardized = (standardized - means) / scales
    weekdays = pd.get_dummies(data["weekday"].astype(int), prefix="weekday", drop_first=True).astype(float)
    design = np.column_stack([np.ones(len(data)), standardized.to_numpy(), weekdays.to_numpy()])

    def objective(params: np.ndarray) -> float:
        beta, log_alpha = params[:-1], params[-1]
        alpha = math.exp(log_alpha)
        eta = np.clip(design @ beta, -20, 20)
        mu = np.exp(eta)
        theta = 1 / alpha
        log_likelihood = gammaln(y + theta) - gammaln(theta) - gammaln(y + 1) + theta * (math.log(theta) - np.log(theta + mu)) + y * (np.log(mu) - np.log(theta + mu))
        return -float(log_likelihood.sum())

    initial = np.zeros(design.shape[1] + 1)
    initial[-1] = -2.0
    result = minimize(objective, initial, method="BFGS", options={"maxiter": 2000, "gtol": 1e-7})
    hessian = finite_hessian(objective, result.x)
    covariance = np.linalg.pinv(hessian)
    effects = {}
    increments = {exposure_columns[0]: 5.0, exposure_columns[1]: 10.0, exposure_columns[2]: 10.0}
    for index, column in enumerate(exposure_columns, start=1):
        beta = result.x[index] / scales[column]
        se = math.sqrt(max(0.0, covariance[index, index])) / scales[column]
        delta = increments[column]
        effects[column.split("_")[0]] = {
            "increment_ug_m3": delta,
            "rr": math.exp(beta * delta),
            "ci95_low": math.exp((beta - 1.96 * se) * delta),
            "ci95_high": math.exp((beta + 1.96 * se) * delta),
            "coefficient_per_ug_m3": beta,
            "standard_error_per_ug_m3": se,
        }
    return {"lag": lag, "n_days": len(data), "n_admissions": int(y.sum()), "optimizer_success": bool(result.success), "optimizer_message": result.message, "effects": effects}


def main() -> int:
    panel = pd.read_csv(DERIVED / "analysis_panel.csv")
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    records = [fit(panel, lag) for lag in range(8)]
    result = {
        "status": "OK",
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": "Multipollutant negative-binomial likelihood with daily PM2.5, NO2, O3, temperature, relative humidity, linear day index, and weekday indicators.",
        "published_targets": {"pm25_lag2_rr_per_5_ug_m3": 1.0216, "no2_lag7_rr_per_10_ug_m3": 1.0124},
        "results": records,
    }
    output = OUTPUTS / "effect_results.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    flat = []
    for record in records:
        for pollutant, effect in record["effects"].items():
            flat.append({"lag": record["lag"], "pollutant": pollutant, "n_days": record["n_days"], **effect})
    pd.DataFrame(flat).to_csv(OUTPUTS / "effect_results.csv", index=False)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
