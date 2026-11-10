"""Fit the published OECD study's closest public-input AERIS models.

The paper's Table 1 used log country case/death rates at day 60 and day 80.
This fit retains those outcomes and the reported public demographic/health
covariates.  It replaces only the paper's World Bank PM2.5 measure with the
2017 AERIS/OpenAQ country-boundary monitor-network mean, and omits the paper's
separate percentage-above-guideline PM2.5 variable because it cannot be derived
from the AERIS network estimand without a population surface.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t


RUN_DIRECTORY = Path(__file__).resolve().parent
INPUT_DIRECTORY = RUN_DIRECTORY / "public-inputs"
PUBLISHED_PREDICTORS = [
    "pm25_ug_m3",
    "older_65_pct_2018",
    "density_per_km2",
    "gdp_per_capita_thousand_usd_2019",
    "physicians_per_10000",
    "hospital_beds_per_10000",
]
CLOSEST_PUBLIC_PREDICTORS = [
    "pm25_ug_m3",
    "older_65_pct_2018",
    "density_per_km2",
    "gdp_per_capita_thousand_usd_2019",
]
EXPOSURE_COVERAGE_THRESHOLDS = {
    "strict_75pct_annual_coverage": 75.0,
    "sensitivity_65pct_annual_coverage": 65.0,
}
PUBLISHED_PM_COEFFICIENTS = {
    (60, "case_rate_per_100k"): {"coefficient": 0.02, "p_value": 0.17},
    (60, "death_rate_per_100k"): {"coefficient": 0.03, "p_value": 0.10},
    (80, "case_rate_per_100k"): {"coefficient": 0.02, "p_value": 0.17},
    (80, "death_rate_per_100k"): {"coefficient": 0.009, "p_value": 0.58},
}


def ols(frame: pd.DataFrame, outcome: str, predictors: list[str]) -> dict[str, object]:
    design = frame[predictors].astype(float).copy()
    design.insert(0, "intercept", 1.0)
    y = np.log(frame[outcome].astype(float).to_numpy())
    x = design.to_numpy()
    coefficients, _, _, _ = np.linalg.lstsq(x, y, rcond=None)
    residuals = y - x @ coefficients
    degrees_freedom = len(y) - x.shape[1]
    if degrees_freedom <= 0:
        raise ValueError(f"Insufficient rows ({len(y)}) for {x.shape[1]} fitted parameters.")
    sigma_squared = float(residuals @ residuals / degrees_freedom)
    covariance = sigma_squared * np.linalg.inv(x.T @ x)
    standard_errors = np.sqrt(np.diag(covariance))
    t_values = coefficients / standard_errors
    p_values = 2 * t.sf(np.abs(t_values), degrees_freedom)
    critical = t.ppf(0.975, degrees_freedom)
    pm_index = list(design.columns).index("pm25_ug_m3")
    rmse = float(np.sqrt(np.mean(residuals**2)))
    return {
        "n": int(len(y)),
        "df_residual": int(degrees_freedom),
        "rmse_log_rate": rmse,
        "r_squared": float(1 - (residuals @ residuals) / np.sum((y - y.mean()) ** 2)),
        "pm25_coefficient_log_rate_per_ug_m3": float(coefficients[pm_index]),
        "pm25_standard_error": float(standard_errors[pm_index]),
        "pm25_95_ci": [
            float(coefficients[pm_index] - critical * standard_errors[pm_index]),
            float(coefficients[pm_index] + critical * standard_errors[pm_index]),
        ],
        "pm25_p_value": float(p_values[pm_index]),
        "pm25_rate_ratio_per_ug_m3": float(math.exp(coefficients[pm_index])),
        "pm25_rate_ratio_95_ci": [
            float(math.exp(coefficients[pm_index] - critical * standard_errors[pm_index])),
            float(math.exp(coefficients[pm_index] + critical * standard_errors[pm_index])),
        ],
        "coefficients": {key: float(value) for key, value in zip(design.columns, coefficients)},
    }


def main() -> int:
    exposure = pd.read_csv(RUN_DIRECTORY / "aeris_pm25_2017_country_summary.csv")
    covariates = pd.read_csv(INPUT_DIRECTORY / "country_covariates.csv")
    outcomes = pd.read_csv(INPUT_DIRECTORY / "country_outcomes_event_days.csv")
    exposure = exposure.loc[exposure["mean"].notna()].copy()
    exposure = exposure.rename(columns={"mean": "pm25_ug_m3"})
    base_frame = outcomes.merge(covariates, on=["iso3", "country"], how="inner").merge(
        exposure[["iso3", "pm25_ug_m3", "n_stations", "network_temporal_coverage_pct"]],
        on="iso3",
        how="inner",
    )
    base_frame["gdp_per_capita_thousand_usd_2019"] = base_frame["gdp_per_capita_usd_2019"] / 1000
    base_frame["physicians_per_10000"] = base_frame["physicians_per_1000"] * 10
    base_frame["hospital_beds_per_10000"] = base_frame["hospital_beds_per_1000"] * 10
    specifications = {
        "published_covariate_specification": {
            "predictors": PUBLISHED_PREDICTORS,
            "description": (
                "PM2.5, age 65+, density, GDP, physicians, and hospital beds; "
                "the paper's PM2.5-above-guideline term remains unavailable from the "
                "AERIS monitor-network estimand."
            ),
        },
        "closest_complete_public_specification": {
            "predictors": CLOSEST_PUBLIC_PREDICTORS,
            "description": (
                "PM2.5, age 65+, density, and GDP. These country covariates are "
                "available for the full OECD study set from the recorded public sources."
            ),
        },
    }
    results: dict[str, object] = {
        "study": "PMID 33484722",
        "exposure_estimand": "AERIS/OpenAQ unweighted mean of 2017 station means within each country boundary",
        "published_model_difference": "The paper additionally included percentage of population exposed above the WHO PM2.5 guideline; this run omits it.",
        "exposure_records": {},
        "specifications": specifications,
        "models": {},
    }
    rows: list[dict[str, object]] = []
    for coverage_name, coverage_threshold in EXPOSURE_COVERAGE_THRESHOLDS.items():
        frame = base_frame.loc[
            base_frame["network_temporal_coverage_pct"].ge(coverage_threshold)
        ].copy()
        eligible_countries = sorted(frame["iso3"].unique().tolist())
        results["exposure_records"][coverage_name] = {
            "minimum_network_temporal_coverage_pct": coverage_threshold,
            "n_countries": len(eligible_countries),
            "countries": eligible_countries,
        }
        for specification_name, specification in specifications.items():
            predictors = specification["predictors"]
            specification_results: dict[str, object] = {}
            for day in (60, 80):
                for outcome in ("case_rate_per_100k", "death_rate_per_100k"):
                    model_frame = frame.loc[frame["event_day"].eq(day)].dropna(
                        subset=[*predictors, outcome]
                    )
                    if len(model_frame) < len(predictors) + 2:
                        continue
                    fit = ols(model_frame, outcome, predictors)
                    published = PUBLISHED_PM_COEFFICIENTS[(day, outcome)]
                    key = f"day_{day}_{outcome}"
                    specification_results[key] = {**fit, "published_pm25": published}
                    rows.append(
                        {
                            "exposure_coverage_rule": coverage_name,
                            "specification": specification_name,
                            "event_day": day,
                            "outcome": outcome,
                            "n_countries": fit["n"],
                            "aeris_pm25_coefficient_log_rate_per_ug_m3": fit["pm25_coefficient_log_rate_per_ug_m3"],
                            "aeris_pm25_ci_low": fit["pm25_95_ci"][0],
                            "aeris_pm25_ci_high": fit["pm25_95_ci"][1],
                            "aeris_pm25_p_value": fit["pm25_p_value"],
                            "aeris_pm25_rate_ratio_per_ug_m3": fit["pm25_rate_ratio_per_ug_m3"],
                            "aeris_pm25_rate_ratio_ci_low": fit["pm25_rate_ratio_95_ci"][0],
                            "aeris_pm25_rate_ratio_ci_high": fit["pm25_rate_ratio_95_ci"][1],
                            "published_pm25_coefficient": published["coefficient"],
                            "published_pm25_rate_ratio_per_ug_m3": math.exp(published["coefficient"]),
                            "published_pm25_p_value": published["p_value"],
                        }
                    )
            if specification_results:
                results["models"].setdefault(coverage_name, {})[specification_name] = specification_results
    results["status"] = "fit" if results["models"] else "not_fit"
    if not results["models"]:
        results["reason"] = "No specification retained enough complete countries after covariate matching."
    base_frame.to_csv(RUN_DIRECTORY / "analysis_panel.csv", index=False)
    pd.DataFrame(
        rows,
        columns=[
            "exposure_coverage_rule",
            "specification",
            "event_day",
            "outcome",
            "n_countries",
            "aeris_pm25_coefficient_log_rate_per_ug_m3",
            "aeris_pm25_ci_low",
            "aeris_pm25_ci_high",
            "aeris_pm25_p_value",
            "aeris_pm25_rate_ratio_per_ug_m3",
            "aeris_pm25_rate_ratio_ci_low",
            "aeris_pm25_rate_ratio_ci_high",
            "published_pm25_coefficient",
            "published_pm25_rate_ratio_per_ug_m3",
            "published_pm25_p_value",
        ],
    ).to_csv(RUN_DIRECTORY / "reproduction_model_results.csv", index=False)
    (RUN_DIRECTORY / "reproduction_model_results.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": results["status"],
                "exposure_eligible_countries": len(exposure),
                "analysis_rows": len(base_frame),
                "fitted_specifications": list(results["models"]),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
