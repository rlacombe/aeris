#!/usr/bin/env python3
"""Merge public outcome, AERIS exposure, and public weather into the analysis panel."""

from __future__ import annotations

import json
import argparse
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"

# National statutory holidays. Carnaval and municipal holidays are not included.
NATIONAL_HOLIDAYS_2019 = {
    "2019-01-01", "2019-04-21", "2019-05-01", "2019-09-07", "2019-10-12",
    "2019-11-02", "2019-11-15", "2019-12-25",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exposure", type=Path, default=DERIVED / "aeris_pm25_daily.csv")
    parser.add_argument("--output", type=Path, default=DERIVED / "analysis_panel.csv")
    parser.add_argument("--summary", type=Path, default=DERIVED / "panel_summary.json")
    args = parser.parse_args()
    outcomes = pd.read_csv(DERIVED / "sim_daily_all_cancer.csv", dtype={"date": str})
    exposure = pd.read_csv(args.exposure, dtype={"date": str})
    weather = pd.read_csv(DERIVED / "weather_daily_open_meteo.csv", dtype={"date": str})
    exposure = exposure.rename(columns={"mean": "pm25_ug_m3"})
    expected = {"date", "pm25_ug_m3"}
    missing = expected - set(exposure.columns)
    if missing:
        raise RuntimeError(f"AERIS daily exposure lacks required columns: {sorted(missing)}")
    panel = outcomes.merge(exposure, how="left", on="date").merge(weather, how="left", on="date")
    panel["date"] = pd.to_datetime(panel["date"])
    panel["month"] = panel["date"].dt.month
    panel["weekday"] = panel["date"].dt.dayofweek
    panel["holiday"] = panel["date"].dt.strftime("%Y-%m-%d").isin(NATIONAL_HOLIDAYS_2019).astype(int)
    for column in ("pm25_ug_m3", "temperature_c", "relative_humidity_pct"):
        panel[f"{column}_lag0_2"] = panel[column].rolling(3, min_periods=3).mean()
    panel["date"] = panel["date"].dt.strftime("%Y-%m-%d")
    output = args.output
    panel.to_csv(output, index=False)
    complete = panel.dropna(subset=["pm25_ug_m3_lag0_2", "temperature_c_lag0_2", "relative_humidity_pct_lag0_2"])
    summary = {
        "output": str(output),
        "exposure_input": str(args.exposure),
        "calendar_days": len(panel),
        "complete_lagged_days": len(complete),
        "exposure_days": int(panel["pm25_ug_m3"].notna().sum()),
        "deaths_on_complete_lagged_days": int(complete["cancer_deaths"].sum()),
        "holiday_definition": "Brazilian national statutory holidays only; municipal holidays omitted.",
    }
    args.summary.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
