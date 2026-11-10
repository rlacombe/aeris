"""Fit a deliberately limited, exposure-source-substitution sensitivity model."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm


RUN_DIRECTORY = Path(__file__).resolve().parent
OUTCOME_PATH = (
    RUN_DIRECTORY.parent.parent
    / "data-acquisition/38182658-uk-covid/uk_nations_daily_cases_deaths_2020-03-26_to_2020-09-15.csv"
)
WEATHER_PATH = RUN_DIRECTORY / "ecad_weather_nation_day.csv"


def main() -> int:
    exposure = pd.DataFrame(json.loads((RUN_DIRECTORY / "aeris_pm25_daily.json").read_text()))
    exposure = exposure.rename(columns={"country": "area_name", "mean": "pm25"})
    exposure["date"] = pd.to_datetime(exposure["date"])
    outcomes = pd.read_csv(OUTCOME_PATH)
    outcomes["date"] = pd.to_datetime(outcomes["date"])
    outcomes = outcomes.sort_values(["area_name", "date"])

    # Paper reports a mean 7.92-day confirmation-to-death interval. This is a
    # rounded, transparent shift, not the paper's non-parametric back-projection.
    outcomes["deaths_shifted_8d"] = outcomes.groupby("area_name")[
        "newDeaths28DaysByPublishDate"
    ].shift(-8)
    panel = outcomes.merge(exposure[["area_name", "date", "pm25"]], on=["area_name", "date"])
    weather = pd.read_csv(WEATHER_PATH, parse_dates=["date"])
    panel = panel.merge(weather, on=["area_name", "date"], how="inner")
    panel = panel.dropna(subset=["pm25", "newCasesByPublishDate", "deaths_shifted_8d"]).copy()
    panel = panel.loc[panel["newCasesByPublishDate"] > 0].copy()
    panel["log_shifted_cfr"] = np.log(
        (panel["deaths_shifted_8d"] + 0.5) / (panel["newCasesByPublishDate"] + 1.0)
    )

    countries = pd.get_dummies(panel["area_name"], drop_first=True, dtype=float)
    X = np.column_stack([
        np.ones(len(panel)),
        panel["pm25"].to_numpy() / 10,
        panel["temperature_c"].to_numpy(),
        panel["sunshine_hours"].to_numpy(),
        countries.to_numpy(),
    ])
    y = panel["log_shifted_cfr"].to_numpy()
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    residuals = y - X @ beta
    bread = np.linalg.inv(X.T @ X)
    hc1 = (len(panel) / (len(panel) - X.shape[1])) * bread @ (
        X.T @ np.diag(residuals**2) @ X
    ) @ bread
    se = float(np.sqrt(hc1[1, 1]))
    estimate = float(beta[1])
    ci = [estimate - norm.ppf(0.975) * se, estimate + norm.ppf(0.975) * se]
    result = {
        "analysis": "exploratory exposure-source-substitution sensitivity analysis",
        "model": "OLS log((deaths shifted 8 days + 0.5)/(cases + 1)) ~ PM2.5 per 10 ug/m3 + temperature + sunshine + country fixed effects",
        "n_nation_days": int(len(panel)),
        "n_nations": int(panel["area_name"].nunique()),
        "pm25_log_effect_per_10_ug_m3": estimate,
        "pm25_robust_se": se,
        "pm25_log_effect_95_ci": ci,
        "pm25_ratio_per_10_ug_m3": float(np.exp(estimate)),
        "pm25_ratio_95_ci": [float(np.exp(value)) for value in ci],
        "limitations": [
            "Uses AERIS/OpenAQ boundary PM2.5 rather than the paper's DEFRA exposure series.",
            "Uses a rounded 8-day death shift rather than the paper's non-parametric back-projection.",
            "Includes ECA&D temperature and sunshine, but not the paper's distributed-lag parameterization.",
            "This is not the published distributed-lag iCFR model and is not a replication estimate.",
        ],
    }
    panel.to_csv(RUN_DIRECTORY / "exploratory_analysis_panel.csv", index=False)
    (RUN_DIRECTORY / "exploratory_model_result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
