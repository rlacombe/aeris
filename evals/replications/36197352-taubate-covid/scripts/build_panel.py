#!/usr/bin/env python3
"""Join the public outcome, AERIS-selected exposure, and weather records."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"


def main() -> int:
    outcomes = pd.read_csv(DERIVED / "sih_sus_daily_b342.csv", parse_dates=["date"])
    exposure = pd.read_csv(DERIVED / "cetesb_daily.csv", parse_dates=["date"])
    weather = pd.read_csv(DERIVED / "weather_daily_open_meteo.csv", parse_dates=["date"])
    panel = outcomes.merge(exposure, on="date", how="left").merge(weather, on="date", how="left")
    panel = panel.sort_values("date").reset_index(drop=True)
    for lag in range(8):
        for column in ("pm25_ug_m3", "no2_ug_m3", "o3_ug_m3"):
            panel[f"{column}_lag{lag}"] = panel[column].shift(lag)
    panel["day_index"] = range(len(panel))
    panel["weekday"] = panel["date"].dt.weekday
    panel["month"] = panel["date"].dt.month
    output = DERIVED / "analysis_panel.csv"
    panel.to_csv(output, index=False)
    summary = {
        "n_calendar_days": len(panel),
        "n_admissions": int(panel["admissions_b342"].sum()),
        "complete_multipollutant_days_lag7": int(panel[["pm25_ug_m3_lag7", "no2_ug_m3_lag7", "o3_ug_m3_lag7", "temperature_c", "relative_humidity_pct"]].notna().all(axis=1).sum()),
        "output": str(output),
    }
    (DERIVED / "panel_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
