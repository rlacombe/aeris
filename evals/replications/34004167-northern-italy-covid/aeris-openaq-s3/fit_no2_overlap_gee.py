"""Fit the closest supported short-term NO2 model for PMID 34004167."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import root
from scipy.stats import norm


RUN_DIRECTORY = Path(__file__).resolve().parent


def ar1(size: int, rho: float) -> np.ndarray:
    index = np.arange(size)
    return rho ** np.abs(index[:, None] - index[None, :])


def fit_gee(panel: pd.DataFrame, outcome: str) -> dict[str, object]:
    """Poisson GEE with AR(1) working correlation and a regional intercept."""
    groups = [frame.reset_index(drop=True) for _, frame in panel.groupby("region", sort=True)]
    design, values = [], []
    for frame in groups:
        # The published LTAP term is fixed within each region. A Veneto
        # intercept supplies the available two-region adjustment without
        # importing the authors' long-term pollutant field.
        veneto = (frame["region"] == "Veneto").astype(float).to_numpy()
        design.append(np.column_stack([np.ones(len(frame)), frame["mean"].to_numpy(float), veneto]))
        values.append(frame[outcome].to_numpy(float))
    x_all, y_all = np.concatenate(design), np.concatenate(values)

    def independent_score(beta: np.ndarray) -> np.ndarray:
        mean = np.exp(np.clip(x_all @ beta, -30, 30))
        return x_all.T @ (y_all - mean)

    beta = root(independent_score, np.array([6.0, 0.0, 0.0])).x
    rho = 0.0
    for _ in range(100):
        def score(candidate: np.ndarray) -> np.ndarray:
            result = np.zeros_like(candidate)
            for x, y in zip(design, values):
                mean = np.exp(np.clip(x @ candidate, -30, 30))
                variance = np.sqrt(mean)[:, None] * ar1(len(y), rho) * np.sqrt(mean)[None, :]
                derivative = mean[:, None] * x
                result += derivative.T @ np.linalg.solve(variance, y - mean)
            return result

        solved = root(score, beta)
        if not solved.success:
            raise RuntimeError(f"GEE solver failed for {outcome}: {solved.message}")
        next_beta = solved.x
        products = []
        for x, y in zip(design, values):
            mean = np.exp(np.clip(x @ next_beta, -30, 30))
            residual = (y - mean) / np.sqrt(mean)
            products.extend((residual[:-1] * residual[1:]).tolist())
        next_rho = float(np.clip(np.mean(products), -0.95, 0.95))
        if np.max(np.abs(next_beta - beta)) < 1e-10 and abs(next_rho - rho) < 1e-10:
            beta, rho = next_beta, next_rho
            break
        beta, rho = next_beta, next_rho

    bread = np.zeros((3, 3))
    meat = np.zeros((3, 3))
    for x, y in zip(design, values):
        mean = np.exp(np.clip(x @ beta, -30, 30))
        variance = np.sqrt(mean)[:, None] * ar1(len(y), rho) * np.sqrt(mean)[None, :]
        derivative = mean[:, None] * x
        inverse_derivative = np.linalg.solve(variance, derivative)
        bread += derivative.T @ inverse_derivative
        contribution = derivative.T @ np.linalg.solve(variance, y - mean)
        meat += np.outer(contribution, contribution)
    covariance = np.linalg.inv(bread) @ meat @ np.linalg.inv(bread)
    coefficient = float(beta[1])
    standard_error = float(np.sqrt(covariance[1, 1]))
    interval = norm.ppf(0.975) * standard_error
    return {
        "outcome": outcome,
        "coefficient_log_rate_ratio_per_ug_m3": coefficient,
        "rate_ratio_per_ug_m3": float(np.exp(coefficient)),
        "cluster_sandwich_95_ci": [
            float(np.exp(coefficient - interval)),
            float(np.exp(coefficient + interval)),
        ],
        "cluster_sandwich_se": standard_error,
        "rho_ar1": rho,
    }


def main() -> int:
    panel = pd.read_csv(RUN_DIRECTORY / "no2_overlap_panel.csv", parse_dates=["date"])
    result = {
        "study": "PMID 34004167",
        "published_comparator": {
            "model": "Poisson log-link GEE with STAP NO2, LTAP NO2, and lockdown",
            "single_pollutant_stap_rate_ratios_per_ug_m3": {"incidence": 1.00, "mortality": 1.00},
            "source": "Article Table 2; values are rounded to two decimals in the article",
        },
        "reconstruction": {
            "model": "Poisson log-link GEE with AR(1) working correlation, AERIS daily NO2, and a regional intercept",
            "analysis_window": "2020-05-06 to 2020-05-19",
            "rows": len(panel),
            "regions": panel.groupby("region").size().to_dict(),
            "omitted_terms": [
                "Published eight-year NO2 field",
                "Lockdown indicator, which is constant during the public OpenAQ overlap",
            ],
        },
        "results": {
            "incidence": fit_gee(panel, "daily_cases"),
            "mortality": fit_gee(panel, "daily_deaths"),
        },
    }
    (RUN_DIRECTORY / "no2_overlap_model_results.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
