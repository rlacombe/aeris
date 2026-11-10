"""Fit the closest public Israeli municipal model supported by AERIS NO2 data.

This is a sensitivity model, not a direct estimate of the paper's NOx result:
OpenAQ supplies NO2 and has no 2016 observations. The model uses the July 24,
2020 public municipal outcome, 2018 AERIS NO2, and 2019 population. It reports
a standardized NO2 coefficient.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as student_t

RUN_DIRECTORY = Path(__file__).resolve().parent
TARGET_DATE = "2020-07-24"
MIN_DAILY_VALUES = 180


def zscore(values: pd.Series) -> pd.Series:
    return (values - values.mean()) / values.std(ddof=0)


def fit_ols(outcome: pd.Series, predictors: pd.DataFrame) -> dict[str, object]:
    """Fit OLS and return the coefficient statistics needed for the audit."""
    names = ["intercept", *predictors.columns]
    design = np.column_stack([np.ones(len(predictors)), predictors.to_numpy(dtype=float)])
    values = outcome.to_numpy(dtype=float)
    coefficients, _, _, _ = np.linalg.lstsq(design, values, rcond=None)
    residuals = values - design @ coefficients
    degrees_of_freedom = len(values) - design.shape[1]
    mse = float(np.sum(residuals**2) / degrees_of_freedom)
    covariance = mse * np.linalg.inv(design.T @ design)
    standard_errors = np.sqrt(np.diag(covariance))
    t_values = coefficients / standard_errors
    p_values = 2 * student_t.sf(np.abs(t_values), degrees_of_freedom)
    critical_value = float(student_t.ppf(0.975, degrees_of_freedom))
    total_sum_squares = float(np.sum((values - values.mean()) ** 2))
    r_squared = 1 - float(np.sum(residuals**2)) / total_sum_squares
    return {
        "names": names,
        "coefficients": dict(zip(names, coefficients, strict=True)),
        "standard_errors": dict(zip(names, standard_errors, strict=True)),
        "p_values": dict(zip(names, p_values, strict=True)),
        "confidence_intervals": {
            name: [float(value - critical_value * error), float(value + critical_value * error)]
            for name, value, error in zip(names, coefficients, standard_errors, strict=True)
        },
        "r_squared": r_squared,
        "degrees_of_freedom": degrees_of_freedom,
    }


def main() -> int:
    outcomes = pd.read_csv(
        RUN_DIRECTORY / "public_outcomes_four_peaks.csv", dtype={"city_code": str}
    )
    exposure = pd.read_csv(RUN_DIRECTORY / "aeris_no2_2018.csv", dtype={"subject_id": str})
    exposure = exposure.rename(columns={"subject_id": "city_code", "mean": "no2_2018_value"})
    panel = outcomes.loc[outcomes["date"] == TARGET_DATE].merge(
        exposure, on="city_code", how="inner", validate="one_to_one"
    )
    panel["n_samples"] = pd.to_numeric(panel["n_samples"], errors="coerce")
    panel["no2_2018_value"] = pd.to_numeric(panel["no2_2018_value"], errors="coerce")
    panel["log_population"] = np.log(pd.to_numeric(panel["population_2019"], errors="coerce"))
    panel = panel.loc[
        panel["no2_2018_value"].notna()
        & (panel["n_samples"] >= MIN_DAILY_VALUES)
        & panel["log_cumulative_case_rate"].notna()
    ].copy()
    panel["z_log_cumulative_case_rate"] = zscore(panel["log_cumulative_case_rate"])
    panel["z_no2_2018"] = zscore(panel["no2_2018_value"])
    panel["z_log_population"] = zscore(panel["log_population"])
    panel.to_csv(RUN_DIRECTORY / "no2_2018_public_model_panel.csv", index=False)

    if len(panel) < 10 or panel["no2_2018_value"].nunique() < 2:
        result = {
            "study_pmid": "34260961",
            "effect_estimated": False,
            "reason": "The reconstructed NO2 panel has insufficient covered municipal variation.",
            "municipalities": int(len(panel)),
            "unique_no2_values": int(panel["no2_2018_value"].nunique()),
        }
    else:
        model = fit_ols(
            panel["z_log_cumulative_case_rate"], panel[["z_no2_2018", "z_log_population"]]
        )
        result = {
            "study_pmid": "34260961",
            "effect_estimated": True,
            "analysis": "closest public measured-pollutant sensitivity model",
            "target_date": TARGET_DATE,
            "outcome": "standardized log cumulative municipal COVID-19 case rate",
            "exposure": "standardized AERIS/OpenAQ NO2 annual mean, 2018 (provider unit)",
            "source_substitution": "The paper reports NOx averaged over 2016-2019. This model uses NO2 for 2018 because OpenAQ S3 contains broad measured Israeli NO2 coverage in 2018 and no 2016 observations.",
            "covariates": ["standardized log 2019 population"],
            "omitted_original_covariates": [
                "population density",
                "matriculation eligibility",
                "socioeconomic cluster",
            ],
            "minimum_daily_values": MIN_DAILY_VALUES,
            "municipalities": int(len(panel)),
            "unique_no2_values": int(panel["no2_2018_value"].nunique()),
            "no2_mean_provider_unit": float(panel["no2_2018_value"].mean()),
            "no2_sd_provider_unit": float(panel["no2_2018_value"].std(ddof=1)),
            "standardized_no2_beta": float(model["coefficients"]["z_no2_2018"]),
            "standardized_no2_ci_95": model["confidence_intervals"]["z_no2_2018"],
            "standardized_no2_p_value": float(model["p_values"]["z_no2_2018"]),
            "model_r_squared": float(model["r_squared"]),
            "model_degrees_of_freedom": int(model["degrees_of_freedom"]),
        }
    (RUN_DIRECTORY / "no2_2018_public_model_result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: value for key, value in result.items() if key != "model_summary"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
