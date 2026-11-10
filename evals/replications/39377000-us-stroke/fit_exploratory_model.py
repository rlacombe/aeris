#!/usr/bin/env python3
"""Fit the pre-specified exploratory county model after the AERIS run."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


RUN_DIR = Path(__file__).resolve().parent


def main() -> None:
    outcomes = pd.read_csv(RUN_DIR / "atlas_all_stroke_65plus_county_2019.csv", dtype={"fips": str})
    exposure = pd.read_csv(
        RUN_DIR / "aeris_pm25_2019_systematic_10pct.csv", dtype={"subject_id": str}
    )
    panel = outcomes.merge(exposure, left_on="fips", right_on="subject_id", how="inner")
    panel = panel.dropna(subset=["mean", "all_stroke_rate_per_100k_65plus"])
    panel = panel[(panel["completeness_pct"] >= 50) & (panel["qc_flag"] == "PASS")]
    panel.to_csv(RUN_DIR / "exploratory_analysis_panel.csv", index=False)

    x = np.column_stack([np.ones(len(panel)), panel["mean"].to_numpy(float)])
    y = panel["all_stroke_rate_per_100k_65plus"].to_numpy(float)
    inverse_xtx = np.linalg.inv(x.T @ x)
    coefficients = inverse_xtx @ x.T @ y
    residuals = y - x @ coefficients
    leverage = np.sum((x @ inverse_xtx) * x, axis=1)
    # HC3 uses residuals inflated by the observation's leverage.
    robust_meat = (x.T * (residuals / (1 - leverage)) ** 2) @ x
    robust_se = np.sqrt(np.diag(inverse_xtx @ robust_meat @ inverse_xtx))
    beta = float(coefficients[1])
    ci = [beta - 1.96 * float(robust_se[1]), beta + 1.96 * float(robust_se[1])]
    r_squared = 1 - float(np.sum(residuals**2) / np.sum((y - y.mean()) ** 2))
    result = {
        "analysis": "Exploratory univariable OLS: 2019 all-stroke mortality rate age 65+ on AERIS annual PM2.5",
        "n_counties": int(len(panel)),
        "pm25_beta_per_1_ug_m3": beta,
        "pm25_95_ci_hc3": ci,
        "r_squared": r_squared,
        "paper_target": "1.89 adjusted ischemic-stroke deaths per 100,000 per 1 ug/m3 PM2.5",
        "comparison_status": "Exploratory only: CDC's no-login outcome is all stroke in 2019, not the paper's 2016-2020 ischemic-stroke outcome.",
    }
    (RUN_DIR / "exploratory_model_result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
