"""Merge the independently reconstructed PM2.5 series with official outcomes."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


RUN_DIRECTORY = Path(__file__).resolve().parent
WINDOW_START = pd.Timestamp("2020-02-24")
WINDOW_END = pd.Timestamp("2020-05-19")
REGIONS = ("Lombardia", "Veneto")


def main() -> int:
    exposure = pd.read_csv(RUN_DIRECTORY / "aeris_pm25_daily.csv")
    outcomes = pd.read_csv(RUN_DIRECTORY / "dpc-covid19-ita-regioni.csv")
    outcomes["date"] = pd.to_datetime(outcomes["data"], utc=True).dt.tz_localize(None).dt.normalize()
    outcomes = outcomes.loc[
        outcomes["denominazione_regione"].isin(REGIONS)
        & outcomes["date"].between(WINDOW_START, WINDOW_END),
        ["date", "denominazione_regione", "totale_casi", "deceduti", "nuovi_positivi"],
    ].rename(columns={"denominazione_regione": "region"})
    exposure["date"] = pd.to_datetime(exposure["date"])
    panel = outcomes.merge(exposure, on=["region", "date"], how="left", validate="one_to_one")
    panel = panel.sort_values(["region", "date"]).reset_index(drop=True)
    panel.to_csv(RUN_DIRECTORY / "daily_panel.csv", index=False)

    expected_days = (WINDOW_END - WINDOW_START).days + 1
    coverage = (
        panel.assign(pm25_available=panel["mean"].notna())
        .groupby("region", as_index=False)
        .agg(
            expected_days=("date", "size"),
            pm25_days=("pm25_available", "sum"),
            mean_pm25=("mean", "mean"),
            sd_pm25=("mean", "std"),
            mean_daily_stations=("n_stations", "mean"),
        )
    )
    coverage["pm25_coverage_pct"] = 100 * coverage["pm25_days"] / expected_days
    coverage.to_csv(RUN_DIRECTORY / "panel_coverage.csv", index=False)
    payload = {
        "window": {"start_date": str(WINDOW_START.date()), "end_date": str(WINDOW_END.date())},
        "expected_days_per_region": expected_days,
        "panel_rows": len(panel),
        "regions": coverage.to_dict(orient="records"),
        "outcome_source": (
            "Italian Civil Protection Department regional COVID-19 daily reports, "
            "downloaded as dpc-covid19-ita-regioni.csv in this directory"
        ),
    }
    (RUN_DIRECTORY / "panel_manifest.json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
