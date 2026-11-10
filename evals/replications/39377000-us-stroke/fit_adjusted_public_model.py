#!/usr/bin/env python3
"""Fit the closest fully public multivariable model for PMID 39377000."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import statsmodels.api as sm


RUN_DIR = Path(__file__).resolve().parent
PREDICTORS = [
    "aeris_pm25_ug_m3",
    "coronary_heart_disease_pct",
    "hypertension_pct",
    "diabetes_pct",
    "high_cholesterol_pct",
    "obesity_pct",
    "smoking_pct",
    "median_household_income_usd",
    "child_poverty_pct",
    "income_inequality_ratio",
    "uninsured_pct",
    "exercise_access_pct",
]


def main() -> None:
    panel = pd.read_csv(RUN_DIR / "adjusted_public_analysis_panel.csv", dtype={"fips": str})
    design = panel[PREDICTORS].copy()
    # Center and scale only adjustment covariates. PM2.5 remains in ug/m3, so
    # its coefficient retains the paper's reported scale.
    for column in PREDICTORS[1:]:
        design[column] = (design[column] - design[column].mean()) / design[column].std(ddof=0)
    model = sm.OLS(panel["all_stroke_rate_per_100k_65plus"], sm.add_constant(design)).fit(
        cov_type="HC3"
    )
    coefficient = float(model.params["aeris_pm25_ug_m3"])
    confidence_interval = model.conf_int().loc["aeris_pm25_ug_m3"].astype(float).tolist()
    result = {
        "analysis": "Adjusted OLS: 2019 all-stroke mortality rate age 65+ on AERIS annual PM2.5",
        "published_target": "Adjusted ischemic-stroke mortality beta 1.89 additional deaths per 100,000 per 1 ug/m3 PM2.5, 2016-2020",
        "outcome_substitution": "Public CDC Atlas identifies all stroke, rather than ischemic stroke, and 2019 is the common exposure/outcome year.",
        "covariate_substitution": "CDC PLACES supplies the seven stated health risk factors; County Health Rankings supplies income, child-poverty proxy, income inequality, uninsured, and exercise-access proxy.",
        "n_counties": int(len(panel)),
        "n_parameters": int(len(model.params)),
        "pm25_beta_per_1_ug_m3": coefficient,
        "pm25_95_ci_hc3": confidence_interval,
        "p_value_hc3": float(model.pvalues["aeris_pm25_ug_m3"]),
        "r_squared": float(model.rsquared),
        "adjusted_r_squared": float(model.rsquared_adj),
        "condition_number": float(model.condition_number),
        "covariate_scaling": "All adjustment covariates were centered and scaled; PM2.5 remains in ug/m3.",
        "predictors": PREDICTORS,
    }
    pd.DataFrame(
        {
            "term": model.params.index,
            "estimate": model.params.values,
            "std_error_hc3": model.bse.values,
            "p_value_hc3": model.pvalues.values,
            "ci_low_hc3": model.conf_int().iloc[:, 0].values,
            "ci_high_hc3": model.conf_int().iloc[:, 1].values,
        }
    ).to_csv(RUN_DIR / "adjusted_public_model_coefficients.csv", index=False)
    (RUN_DIR / "adjusted_public_model_result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
