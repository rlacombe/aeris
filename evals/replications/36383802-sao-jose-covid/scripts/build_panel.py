#!/usr/bin/env python3
"""Join daily SIH/SUS admissions, AERIS exposure, and weather."""

from __future__ import annotations

import json
import argparse
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"


def daily_aeris(pollutant: str) -> pd.DataFrame:
    candidates = sorted(DERIVED.glob(f"*{pollutant}*daily*.csv")) + sorted(DERIVED.glob(f"*daily*{pollutant}*.csv"))
    candidates = list(dict.fromkeys(candidates))
    if not candidates:
        raise FileNotFoundError(f"No AERIS daily output found for {pollutant}")
    for path in candidates:
        frame = pd.read_csv(path)
        if "date" in frame and "mean" in frame:
            frame = frame[["date", "mean"]].rename(columns={"mean": pollutant})
            return frame.groupby("date", as_index=False)[pollutant].mean()
    raise RuntimeError(f"AERIS daily output for {pollutant} has no date/mean columns: {candidates}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outcomes", type=Path, default=DERIVED / "sih_daily_b342_admissions.csv")
    parser.add_argument("--output", type=Path, default=DERIVED / "analysis_panel.csv")
    args = parser.parse_args()
    outcomes = pd.read_csv(args.outcomes, dtype={"date": str})
    weather = pd.read_csv(DERIVED / "weather_daily_open_meteo.csv", dtype={"date": str})
    panel = outcomes.merge(weather, on="date", how="left")
    sources = {}
    for pollutant in ("pm10", "no2", "o3"):
        exposure = daily_aeris(pollutant)
        sources[pollutant] = len(exposure)
        panel = panel.merge(exposure, on="date", how="left")
        for lag in range(8):
            panel[f"{pollutant}_lag{lag}"] = panel[pollutant].shift(lag)
    panel["date"] = pd.to_datetime(panel["date"])
    panel["weekday"] = panel["date"].dt.dayofweek
    panel["calendar_day"] = (panel["date"] - panel["date"].min()).dt.days
    panel["month"] = panel["date"].dt.month
    panel["date"] = panel["date"].dt.strftime("%Y-%m-%d")
    panel.to_csv(args.output, index=False)
    summary = {
        "rows": len(panel),
        "admissions": int(panel.covid_admissions.sum()),
        "aeris_daily_rows": sources,
        "complete_rows_by_lag": {
            f"{pollutant}_lag{lag}": int(panel[[f"{pollutant}_lag{lag}", "temperature_c", "relative_humidity_pct"]].notna().all(axis=1).sum())
            for pollutant in ("pm10", "no2", "o3") for lag in range(8)
        },
        "outcomes_input": str(args.outcomes),
        "output": str(args.output),
    }
    (DERIVED / "panel_manifest.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
