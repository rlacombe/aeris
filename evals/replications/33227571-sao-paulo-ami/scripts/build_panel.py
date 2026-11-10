#!/usr/bin/env python3
"""Merge public daily outcomes, AERIS records, and weather into one panel."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"


def read_exposure(pollutant: str) -> pd.DataFrame:
    source_path = DERIVED / f"aeris_{pollutant}_daily.csv"
    source = pd.read_csv(source_path, dtype={"date": str})
    if "mean" in source and source["mean"].notna().any():
        return source[["date", "mean"]].rename(columns={"mean": pollutant}).groupby("date", as_index=False)[pollutant].mean()
    recovery_path = DERIVED / "cetesb_daily_recovery.csv"
    if recovery_path.exists():
        recovery = pd.read_csv(recovery_path, dtype={"date": str})
        if pollutant in recovery:
            return recovery[["date", pollutant]]
    return pd.DataFrame({"date": [], pollutant: []})


def main() -> int:
    panel = pd.read_csv(DERIVED / "sih_daily_i21_admissions.csv", dtype={"date": str})
    for pollutant in ("pm25", "pm10", "no2"):
        panel = panel.merge(read_exposure(pollutant), how="left", on="date")
    panel = panel.merge(pd.read_csv(DERIVED / "weather_daily_open_meteo.csv", dtype={"date": str}), how="left", on="date")
    panel["date"] = pd.to_datetime(panel["date"])
    panel["weekday"] = panel.date.dt.dayofweek
    panel["month"] = panel.date.dt.month
    panel["date"] = panel.date.dt.strftime("%Y-%m-%d")
    complete = panel.dropna(subset=["pm25", "pm10", "no2", "temperature_c", "relative_humidity_pct", "rainfall_mm"]).copy()
    complete.to_csv(DERIVED / "analysis_panel_complete.csv", index=False)
    panel.to_csv(DERIVED / "analysis_panel_all_days.csv", index=False)
    summary = {"calendar_days": len(panel), "complete_days": len(complete), "admissions_complete_days": int(complete.mi_admissions.sum()), "daily_coverage": {column: int(panel[column].notna().sum()) for column in ["pm25", "pm10", "no2", "temperature_c", "relative_humidity_pct", "rainfall_mm"]}, "exposure_rule": "Use AERIS boundary record when it contains observations; otherwise use recorded CETESB station recovery after AERIS returned no observations."}
    (DERIVED / "panel_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
