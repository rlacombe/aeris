#!/usr/bin/env python3
"""Combine daily national SIM counts with AERIS exposure and network weather."""
from __future__ import annotations

import json
import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
HOLIDAYS = {f"{year}-{month_day}" for year in range(2015, 2020) for month_day in ("01-01", "04-21", "05-01", "09-07", "10-12", "11-02", "11-15", "12-25")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exposure", type=Path, default=DERIVED / "aeris_national_pm25_daily.csv")
    parser.add_argument("--weather", type=Path, default=DERIVED / "aeris_network_weather_daily.csv")
    parser.add_argument("--label", default="openaq")
    args = parser.parse_args()
    outcomes = pd.read_csv(DERIVED / "sim_national_daily_cancer_deaths.csv", dtype={"date": str})
    exposure = pd.read_csv(args.exposure, dtype={"date": str})
    weather = pd.read_csv(args.weather, dtype={"date": str})
    if "mean" in exposure.columns:
        exposure = exposure.rename(columns={"mean": "pm25_ug_m3"})
    if "pm25_ug_m3" not in exposure.columns:
        raise RuntimeError(f"Cannot identify AERIS daily PM2.5 column: {exposure.columns.tolist()}")
    exposure = exposure.groupby("date", as_index=False).pm25_ug_m3.mean()
    panel = outcomes.merge(exposure, how="left", on="date").merge(weather, how="left", on="date")
    panel["date"] = pd.to_datetime(panel.date)
    panel["month"] = panel.date.dt.month
    panel["weekday"] = panel.date.dt.dayofweek
    panel["holiday"] = panel.date.dt.strftime("%Y-%m-%d").isin(HOLIDAYS).astype(int)
    for column in ("pm25_ug_m3", "temperature_c", "relative_humidity_pct"):
        panel[f"{column}_lag0_2"] = panel[column].rolling(3, min_periods=3).mean()
    panel["date"] = panel.date.dt.strftime("%Y-%m-%d")
    output = DERIVED / f"national_analysis_panel_{args.label}.csv"
    panel.to_csv(output, index=False)
    complete = panel.dropna(subset=["pm25_ug_m3_lag0_2", "temperature_c_lag0_2", "relative_humidity_pct_lag0_2"])
    summary = {"calendar_days": len(panel), "exposure_days": int(panel.pm25_ug_m3.notna().sum()), "complete_lagged_days": len(complete), "cancer_deaths": int(panel.cancer_deaths.sum()), "complete_lagged_cancer_deaths": int(complete.cancer_deaths.sum()), "output": str(output)}
    summary["label"] = args.label
    (DERIVED / f"national_panel_summary_{args.label}.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
