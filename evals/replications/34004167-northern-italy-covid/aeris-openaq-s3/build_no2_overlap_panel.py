"""Build the exact NO2 overlap panel with public Northern Italy outcomes."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


RUN_DIRECTORY = Path(__file__).resolve().parent
WINDOW = (pd.Timestamp("2020-05-06"), pd.Timestamp("2020-05-19"))
REGIONS = ("Lombardia", "Veneto")


def main() -> int:
    exposure = pd.read_csv(RUN_DIRECTORY / "aeris_no2_overlap_daily.csv", parse_dates=["date"])
    # OpenAQ's V3 daily endpoint can emit an adjacent local-calendar day.
    # The predeclared Italian analysis window is retained explicitly here.
    exposure = exposure.loc[exposure["date"].between(*WINDOW)].copy()
    exposure = exposure.sort_values(["region", "date"])
    duplicate = exposure.duplicated(["region", "date"], keep=False)
    if duplicate.any():
        raise RuntimeError("AERIS daily output contains duplicate region-date rows.")

    outcomes = pd.read_csv(RUN_DIRECTORY / "dpc-covid19-ita-regioni.csv")
    outcomes["date"] = pd.to_datetime(outcomes["data"], utc=True).dt.tz_localize(None).dt.normalize()
    outcomes = outcomes.loc[outcomes["denominazione_regione"].isin(REGIONS)].copy()
    outcomes = outcomes.sort_values(["denominazione_regione", "date"])
    outcomes["daily_deaths"] = outcomes.groupby("denominazione_regione")["deceduti"].diff()
    outcomes = outcomes.loc[
        outcomes["date"].between(*WINDOW),
        ["date", "denominazione_regione", "nuovi_positivi", "daily_deaths"],
    ].rename(columns={"denominazione_regione": "region", "nuovi_positivi": "daily_cases"})

    panel = outcomes.merge(exposure, on=["region", "date"], how="inner", validate="one_to_one")
    panel = panel.sort_values(["region", "date"]).reset_index(drop=True)
    expected_rows = len(REGIONS) * ((WINDOW[1] - WINDOW[0]).days + 1)
    if len(panel) != expected_rows:
        raise RuntimeError(f"Expected {expected_rows} complete region-days, found {len(panel)}.")
    if panel[["mean", "daily_cases", "daily_deaths"]].isna().any().any():
        raise RuntimeError("The AERIS NO2 and outcome overlap panel contains missing values.")
    panel.to_csv(RUN_DIRECTORY / "no2_overlap_panel.csv", index=False)

    manifest = {
        "study": "PMID 34004167",
        "window": {"start_date": str(WINDOW[0].date()), "end_date": str(WINDOW[1].date())},
        "rows": len(panel),
        "regions": panel.groupby("region").size().to_dict(),
        "exposure": "AERIS/OpenAQ monitor-weighted boundary mean of daily NO2 means",
        "outcomes": {
            "daily_cases": "Italian Civil Protection nuovi_positivi",
            "daily_deaths": "first difference of Italian Civil Protection deceduti",
        },
    }
    (RUN_DIRECTORY / "no2_overlap_panel_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
