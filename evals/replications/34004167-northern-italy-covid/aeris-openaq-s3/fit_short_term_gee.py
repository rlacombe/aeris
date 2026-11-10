"""Fit a reproducible short-term PM2.5 approximation to PMID 34004167.

The published model is a Poisson log-link GEE with AR(1) working correlation,
short- and long-term pollutant fields, and a lockdown indicator.  This run
independently reconstructs only the short-term PM2.5 field.  It therefore fits
the identifiable short-term component with the same log link and AR(1) GEE
working covariance.  Long-term PM2.5 is intentionally not imported from the
authors' EEA series.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import root
from scipy.stats import norm


RUN_DIRECTORY = Path(__file__).resolve().parent
OUTCOMES = {"incidence": "totale_casi", "mortality": "deceduti"}


def ar1_correlation(size: int, rho: float) -> np.ndarray:
    index = np.arange(size)
    return rho ** np.abs(index[:, None] - index[None, :])


def poisson_gee(panel: pd.DataFrame, outcome: str) -> dict[str, object]:
    """Solve a Poisson GEE with a common AR(1) working correlation.

    There are two study clusters (regions).  The implementation follows the
    standard quasi-score, estimating rho from adjacent Pearson residual pairs
    and returning model-based and cluster-sandwich standard errors.
    """
    groups = [frame.reset_index(drop=True) for _, frame in panel.groupby("region", sort=True)]
    # The public series begins after 22 February, so the article's stated
    # lockdown-from-22-February covariate is constant and cannot be identified.
    # Table 1 reports a one-day lockdown category; retain an explicit first-day
    # indicator to match that reported count while keeping the model estimable.
    X_groups = []
    y_groups = []
    for group in groups:
        first_day = (group["date"] == group["date"].min()).astype(float).to_numpy()
        X_groups.append(
            np.column_stack(
                [
                    np.ones(len(group)),
                    group["mean"].to_numpy(dtype=float),
                    first_day,
                ]
            )
        )
        y_groups.append(group[outcome].to_numpy(dtype=float))

    X_initial = np.concatenate(X_groups)
    y_initial = np.concatenate(y_groups)

    def independent_score(beta: np.ndarray) -> np.ndarray:
        mu = np.exp(np.clip(X_initial @ beta, -30, 30))
        return X_initial.T @ (y_initial - mu)

    beta = root(independent_score, np.array([6.0, 0.0, 0.0])).x
    rho = 0.0
    for _ in range(100):
        def gee_score(candidate: np.ndarray) -> np.ndarray:
            score = np.zeros_like(candidate)
            for X, y in zip(X_groups, y_groups):
                mu = np.exp(np.clip(X @ candidate, -30, 30))
                sqrt_a = np.sqrt(mu)
                V = sqrt_a[:, None] * ar1_correlation(len(y), rho) * sqrt_a[None, :]
                D = mu[:, None] * X
                score += D.T @ np.linalg.solve(V, y - mu)
            return score

        solved = root(gee_score, beta)
        if not solved.success:
            raise RuntimeError(f"GEE solver failed for {outcome}: {solved.message}")
        next_beta = solved.x
        residual_products = []
        for X, y in zip(X_groups, y_groups):
            mu = np.exp(np.clip(X @ next_beta, -30, 30))
            pearson = (y - mu) / np.sqrt(mu)
            residual_products.extend((pearson[:-1] * pearson[1:]).tolist())
        next_rho = float(np.clip(np.mean(residual_products), -0.95, 0.95))
        if np.max(np.abs(next_beta - beta)) < 1e-10 and abs(next_rho - rho) < 1e-10:
            beta, rho = next_beta, next_rho
            break
        beta, rho = next_beta, next_rho

    bread = np.zeros((len(beta), len(beta)))
    meat = np.zeros_like(bread)
    for X, y in zip(X_groups, y_groups):
        mu = np.exp(np.clip(X @ beta, -30, 30))
        sqrt_a = np.sqrt(mu)
        V = sqrt_a[:, None] * ar1_correlation(len(y), rho) * sqrt_a[None, :]
        D = mu[:, None] * X
        v_inv_d = np.linalg.solve(V, D)
        bread += D.T @ v_inv_d
        contribution = D.T @ np.linalg.solve(V, y - mu)
        meat += np.outer(contribution, contribution)
    model_covariance = np.linalg.inv(bread)
    sandwich_covariance = model_covariance @ meat @ model_covariance
    coefficient = float(beta[1])
    model_se = float(np.sqrt(model_covariance[1, 1]))
    sandwich_se = float(np.sqrt(sandwich_covariance[1, 1]))
    z = float(norm.ppf(0.975))
    return {
        "n_observations": int(len(panel)),
        "n_regions": int(len(groups)),
        "rho_ar1": rho,
        "coefficient_log_rate_ratio_per_ug_m3": coefficient,
        "rate_ratio_per_ug_m3": float(np.exp(coefficient)),
        "model_based_95_ci": [
            float(np.exp(coefficient - z * model_se)),
            float(np.exp(coefficient + z * model_se)),
        ],
        "cluster_sandwich_95_ci": [
            float(np.exp(coefficient - z * sandwich_se)),
            float(np.exp(coefficient + z * sandwich_se)),
        ],
        "model_based_se": model_se,
        "cluster_sandwich_se": sandwich_se,
    }


def main() -> int:
    panel = pd.read_csv(RUN_DIRECTORY / "daily_panel.csv", parse_dates=["date"])
    panel = panel.dropna(subset=["mean"]).sort_values(["region", "date"]).reset_index(drop=True)
    if panel.groupby("region").size().min() < 20:
        raise RuntimeError("Insufficient reconstructed PM2.5 days in at least one study region.")

    results = {
        "study": "PMID 34004167",
        "model": {
            "published": (
                "Poisson log-link GEE, AR(1), daily regional cases/deaths on STAP, LTAP, and LOCK."
            ),
            "reconstruction": (
                "Poisson log-link GEE, AR(1), daily regional outcome on independently reconstructed "
                "AERIS PM2.5 and a one-day indicator matching Table 1's reported lockdown count."
            ),
            "omitted_published_term": (
                "Eight-year LTAP PM2.5. It is not reconstructed here so no author exposure fields enter the fit."
            ),
            "outcome_definition": (
                "Official regional cumulative total cases (incidence) and cumulative deaths (mortality), "
                "matching the paper's accumulated outcome figures and Table 1 totals."
            ),
        },
        "analysis_rows": int(len(panel)),
        "coverage_by_region": panel.groupby("region").size().to_dict(),
        "published_primary_comparator": {
            "contrast": "PM2.5 STAP, single-pollutant GEE, per 1 ug/m3",
            "incidence_rate_ratio": 1.01,
            "mortality_rate_ratio": 1.00,
            "source": "Article Table 2",
        },
        "results": {label: poisson_gee(panel, column) for label, column in OUTCOMES.items()},
    }
    (RUN_DIRECTORY / "model_results.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
