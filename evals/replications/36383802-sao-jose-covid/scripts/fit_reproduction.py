#!/usr/bin/env python3
"""Fit the closest supported negative-binomial daily model for PMID 36383802."""

from __future__ import annotations

import json
import math
import argparse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
OUTPUTS = ROOT / "outputs"
POLLUTANTS = {"o3_lag2": 1.061, "no2_lag3": 1.125, "pm10_lag0": None}


def result_for(model, term: str, published: float | None) -> dict[str, float | None]:
    beta = float(model.params[term])
    se = float(model.bse[term])
    return {
        "published_rr_per_10_ug_m3": published,
        "aeris_rr_per_10_ug_m3": math.exp(beta * 10),
        "ci95_low": math.exp((beta - 1.96 * se) * 10),
        "ci95_high": math.exp((beta + 1.96 * se) * 10),
        "coefficient_per_ug_m3": beta,
        "standard_error": se,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, default=DERIVED / "analysis_panel.csv")
    parser.add_argument("--output", type=Path, default=OUTPUTS / "effect_results.json")
    parser.add_argument("--outcome-source", default="SIH/SUS B34.2 admissions")
    args = parser.parse_args()
    panel = pd.read_csv(args.panel)
    exposure_terms = list(POLLUTANTS)
    required = ["covid_admissions", "temperature_c", "relative_humidity_pct", "weekday", "calendar_day", *exposure_terms]
    frame = panel.dropna(subset=required).copy()
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    output = args.output
    base = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": "Negative-binomial GLM with concurrent weather, weekday indicators, and linear calendar-day adjustment.",
        "published_model": "Negative-binomial regression with PM10, NO2, O3, temperature, relative humidity, day of week, calendar day, and lags 0-7.",
        "selected_lags": {"o3": 2, "no2": 3, "pm10": 0},
        "observation_window": [str(panel.date.min()), str(panel.date.max())],
        "eligible_days": int(len(frame)),
        "eligible_admissions": int(frame.covid_admissions.sum()),
        "calendar_days": int(len(panel)),
        "outcome_source": args.outcome_source,
    }
    if len(frame) < 40 or frame.covid_admissions.sum() < 20:
        base["status"] = "INSUFFICIENT_COMPLETE_EXPOSURE_PANEL"
        output.write_text(json.dumps(base, indent=2) + "\n")
        print(json.dumps(base, indent=2))
        return 0
    weekday = pd.get_dummies(frame.weekday.astype(int), prefix="weekday", drop_first=True, dtype=float)
    covariates = frame[[*exposure_terms, "temperature_c", "relative_humidity_pct", "calendar_day"]].astype(float)
    covariates = pd.concat([covariates, weekday], axis=1)
    covariates = sm.add_constant(covariates, has_constant="add")
    try:
        model = sm.NegativeBinomial(frame.covid_admissions.astype(float), covariates, loglike_method="nb2").fit(disp=False, maxiter=1000)
        status = "OK" if model.mle_retvals.get("converged", False) else "OPTIMIZER_WARNING"
        base.update(
            {
                "status": status,
                "converged": bool(model.mle_retvals.get("converged", False)),
                "model_terms": list(covariates.columns),
                "effects": {term: result_for(model, term, published) for term, published in POLLUTANTS.items()},
                "overdispersion_alpha": float(model.params["alpha"]),
                "log_likelihood": float(model.llf),
            }
        )
    except Exception as exc:
        base.update({"status": "MODEL_FAILURE", "error": str(exc)})
    output.write_text(json.dumps(base, indent=2) + "\n")
    print(json.dumps(base, indent=2))


if __name__ == "__main__":
    main()
