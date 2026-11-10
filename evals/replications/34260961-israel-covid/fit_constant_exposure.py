"""Fit the requested Israel model with the only available OpenAQ PM2.5 series."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


RUN_DIRECTORY = Path(__file__).resolve().parent
OUTCOMES = RUN_DIRECTORY / "public_outcomes_four_peaks.csv"


def main() -> int:
    panel = pd.read_csv(OUTCOMES)
    panel = panel.loc[panel["date"] == "2020-07-24"].copy()

    # The only historic OpenAQ PM2.5 location, SPARTAN--Weizmann Institute,
    # returned annual means of 14.7 (2016), 14.1 (2017), and 13.6 (2019).
    # The 2018 annual aggregate is absent. Its observed-year mean is assigned
    # uniformly because no other study-period spatial exposure is available.
    pm25 = float(np.mean([14.7, 14.1, 13.6]))
    panel["pm25_openaq_single_site"] = pm25
    design = np.column_stack([np.ones(len(panel)), panel["pm25_openaq_single_site"]])
    fit, _, rank, _ = np.linalg.lstsq(design, panel["log_cumulative_case_rate"], rcond=None)
    result = {
        "study": "PMID 34260961",
        "target_date": "2020-07-24",
        "n_municipalities": len(panel),
        "source": "OpenAQ location 1285358, sensor 6566251",
        "exposure_assignment": "same observed-year mean assigned to every municipality",
        "pm25_observed_year_means_ug_m3": {"2016": 14.7, "2017": 14.1, "2019": 13.6},
        "pm25_assigned_ug_m3": pm25,
        "design_matrix_columns": ["intercept", "pm25_openaq_single_site"],
        "design_matrix_rank": int(rank),
        "n_columns": int(design.shape[1]),
        "lstsq_solution": {"intercept": float(fit[0]), "pm25": float(fit[1])},
        "estimable_pm25_effect": False,
        "result": "PM2.5 is constant across municipalities and collinear with the intercept.",
        "published_standardized_pm25_beta": 0.403,
    }
    panel.to_csv(RUN_DIRECTORY / "constant_exposure_analysis_panel.csv", index=False)
    (RUN_DIRECTORY / "constant_exposure_fit.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
