"""Fit the pre-specified France department negative-binomial model."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln

ROOT = Path(__file__).resolve().parent


def numerical_hessian(function, parameters, step=1e-4):
    n_parameters = len(parameters)
    hessian = np.empty((n_parameters, n_parameters))
    for i in range(n_parameters):
        for j in range(n_parameters):
            ei = np.zeros(n_parameters)
            ej = np.zeros(n_parameters)
            ei[i] = step * max(1.0, abs(parameters[i]))
            ej[j] = step * max(1.0, abs(parameters[j]))
            hessian[i, j] = (
                function(parameters + ei + ej)
                - function(parameters + ei - ej)
                - function(parameters - ei + ej)
                + function(parameters - ei - ej)
            ) / (4 * ei[i] * ej[j])
    return hessian


def main() -> None:
    panel = pd.read_csv(ROOT / "analysis_panel_pre_exposure.csv")
    exposures = pd.read_csv(ROOT / "aeris_pm25_2019.csv")
    panel = panel.merge(
        exposures[["boundary_name", "mean", "n_stations", "network_temporal_coverage_pct", "qc_flag"]],
        left_on="department_name",
        right_on="boundary_name",
        how="inner",
        validate="one_to_one",
    ).rename(columns={"mean": "pm25_aeris_2019"})
    eligible = panel.loc[
        (panel["qc_flag"] == "NOT_SET")
        & (panel["network_temporal_coverage_pct"] >= 75)
    ].copy()

    # Published model family and target: May 1 department death rate. This
    # independent run uses the public covariates available in the authors'
    # shared workbook, while PM2.5 is replaced by the AERIS record.
    predictors = [
        "pm25_aeris_2019",
        "mean_temperature",
        "intensive_care_beds_per_100k",
        "share_60_plus",
        "share_female",
        "population_density",
        "diabetes_prevalence",
    ]
    model_data = eligible.dropna(subset=["covid_deaths", "population", *predictors]).copy()
    scaled_predictors = [column for column in predictors if column != "pm25_aeris_2019"]
    for column in scaled_predictors:
        model_data[column] = (model_data[column] - model_data[column].mean()) / model_data[column].std()

    x = np.column_stack([np.ones(len(model_data)), *[model_data[column] for column in predictors]])
    y = model_data["covid_deaths"].to_numpy(dtype=float)
    offset = np.log(model_data["population"].to_numpy(dtype=float))

    def negative_log_likelihood(parameters):
        beta = parameters[:-1]
        alpha = np.exp(parameters[-1])
        size = 1.0 / alpha
        mu = np.exp(np.clip(offset + x @ beta, -30, 30))
        log_likelihood = (
            gammaln(y + size)
            - gammaln(size)
            - gammaln(y + 1)
            + size * (np.log(size) - np.log(size + mu))
            + y * (np.log(mu) - np.log(size + mu))
        )
        return -float(log_likelihood.sum())

    initial = np.r_[np.zeros(x.shape[1]), np.log(0.5)]
    optimizer_method = "BFGS"
    fitted = minimize(negative_log_likelihood, initial, method=optimizer_method)
    if not fitted.success:
        # BFGS often reaches the optimum but reports precision loss while
        # estimating the overdispersion parameter. L-BFGS-B stabilizes that
        # parameter without changing the study model or covariates.
        bounds = [(None, None)] * (len(initial) - 1) + [(-12.0, 6.0)]
        optimizer_method = "L-BFGS-B"
        fitted = minimize(
            negative_log_likelihood,
            fitted.x,
            method=optimizer_method,
            bounds=bounds,
            options={"maxiter": 10_000, "ftol": 1e-12, "gtol": 1e-8},
        )
    if not fitted.success:
        raise RuntimeError(f"Negative-binomial optimizer failed: {fitted.message}")
    covariance = np.linalg.inv(numerical_hessian(negative_log_likelihood, fitted.x))
    pm_index = 1
    coefficient = float(fitted.x[pm_index])
    standard_error = float(np.sqrt(covariance[pm_index, pm_index]))
    result = {
        "study": "PMID 34488764",
        "target_date": "2020-05-01",
        "model": "negative_binomial_count_with_log_population_offset",
        "n_departments_with_aeris_pm25": int(len(eligible)),
        "n_complete_case_departments": int(len(model_data)),
        "pm25_rate_ratio_per_1_ug_m3": float(np.exp(coefficient)),
        "pm25_rate_ratio_95_ci": [
            float(np.exp(coefficient - 1.96 * standard_error)),
            float(np.exp(coefficient + 1.96 * standard_error)),
        ],
        "published_pm25_rate_ratio_per_1_ug_m3": 1.244,
        "published_pm25_rate_ratio_95_ci": [1.083, 1.428],
        "exposure_source_substitution": "AERIS/OpenAQ 2019 monitor-network annual PM2.5 replaces the paper's 1999-2016 satellite-derived department mean.",
        "predictors": predictors,
        "optimizer": {"method": optimizer_method, "negative_log_likelihood": float(fitted.fun)},
    }
    model_data.to_csv(ROOT / "analysis_panel_with_aeris_exposure.csv", index=False)
    (ROOT / "exploratory_model_result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
