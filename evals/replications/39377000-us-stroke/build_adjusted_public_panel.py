#!/usr/bin/env python3
"""Build the fully public county panel for PMID 39377000.

The cited CDC Atlas export identifies all-stroke mortality, rather than a
separate ischemic-stroke outcome. This script keeps that distinction explicit
while assembling the authors' stated risk-factor, socioeconomic, insurance,
and green-space covariate families for counties with audited AERIS exposure.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pandas as pd


RUN_DIR = Path(__file__).resolve().parent
PLACES_URL = (
    "https://data.cdc.gov/resource/pqpp-u99h.json?$limit=50000&$where="
    "year=%272019%27%20AND%20locationid%20like%20%27_____%27%20AND%20"
    "datavaluetypeid=%27CrdPrv%27%20AND%20measureid%20in(%27CHD%27,%27BPHIGH%27,"
    "%27DIABETES%27,%27HIGHCHOL%27,%27OBESITY%27,%27CSMOKING%27,%27ACCESS2%27)"
)
CHR_URL = (
    "https://www.countyhealthrankings.org/sites/default/files/media/document/"
    "analytic_data2020.csv"
)
PLACES_FILE = RUN_DIR / "cdc_places_2019_stroke_covariates.json"
CHR_FILE = RUN_DIR / "chr_2020_analytic_data.csv"


def download_if_missing(url: str, path: Path) -> None:
    if path.exists():
        return
    with urllib.request.urlopen(url, timeout=180) as response:
        path.write_bytes(response.read())


def main() -> None:
    download_if_missing(PLACES_URL, PLACES_FILE)
    download_if_missing(CHR_URL, CHR_FILE)

    outcomes = pd.read_csv(
        RUN_DIR / "atlas_all_stroke_65plus_county_2019.csv", dtype={"fips": str}
    )
    exposure = pd.read_csv(
        RUN_DIR / "aeris_pm25_2019_systematic_10pct.csv", dtype={"subject_id": str}
    )
    exposure["subject_id"] = exposure["subject_id"].str.zfill(5)
    exposure = exposure.loc[
        (exposure["qc_flag"] == "PASS") & (exposure["completeness_pct"] >= 50),
        ["subject_id", "mean", "completeness_pct", "n_samples", "station_id"],
    ].rename(
        columns={
            "subject_id": "fips",
            "mean": "aeris_pm25_ug_m3",
            "n_samples": "n_days",
            "station_id": "station_id",
        }
    )

    places = pd.DataFrame(json.loads(PLACES_FILE.read_text(encoding="utf-8")))
    places["fips"] = places["locationid"].astype(str).str.zfill(5)
    places["data_value"] = pd.to_numeric(places["data_value"], errors="coerce")
    health = places.pivot(index="fips", columns="measureid", values="data_value").reset_index()
    health = health.rename(
        columns={
            "CHD": "coronary_heart_disease_pct",
            "BPHIGH": "hypertension_pct",
            "DIABETES": "diabetes_pct",
            "HIGHCHOL": "high_cholesterol_pct",
            "OBESITY": "obesity_pct",
            "CSMOKING": "smoking_pct",
            "ACCESS2": "uninsured_pct",
        }
    )

    # The second physical row contains County Health Rankings machine labels.
    chr_data = pd.read_csv(CHR_FILE, skiprows=[1], dtype={"5-digit FIPS Code": str})
    chr_data["fips"] = chr_data["5-digit FIPS Code"].str.zfill(5)
    chr_data = chr_data.loc[
        :,
        [
            "fips",
            "Median household income raw value",
            "Children in poverty raw value",
            "Income inequality raw value",
            "Access to exercise opportunities raw value",
        ],
    ].rename(
        columns={
            "Median household income raw value": "median_household_income_usd",
            "Children in poverty raw value": "child_poverty_pct",
            "Income inequality raw value": "income_inequality_ratio",
            "Access to exercise opportunities raw value": "exercise_access_pct",
        }
    )
    for column in chr_data.columns[1:]:
        chr_data[column] = pd.to_numeric(chr_data[column], errors="coerce")
    chr_data["child_poverty_pct"] *= 100
    chr_data["exercise_access_pct"] *= 100

    panel = outcomes.merge(exposure, on="fips", how="inner")
    panel = panel.merge(health, on="fips", how="left").merge(chr_data, on="fips", how="left")
    required = [
        "all_stroke_rate_per_100k_65plus",
        "aeris_pm25_ug_m3",
        "coronary_heart_disease_pct",
        "hypertension_pct",
        "diabetes_pct",
        "high_cholesterol_pct",
        "obesity_pct",
        "smoking_pct",
        "median_household_income_usd",
        "child_poverty_pct",
        "income_inequality_ratio",
        "uninsured_pct",
        "exercise_access_pct",
    ]
    panel = panel.dropna(subset=required).sort_values("fips")
    panel.to_csv(RUN_DIR / "adjusted_public_analysis_panel.csv", index=False)

    manifest = {
        "outcome": "CDC Atlas 2019 county all-stroke age-standardized mortality rate, adults 65+",
        "outcome_url": "https://data.cdc.gov/resource/7b9s-s8ck.json",
        "exposure": "AERIS/OpenAQ annual PM2.5, 2019; nearest monitor; 50% daily completeness",
        "health_covariates": "CDC PLACES 2021 release, 2019 county crude prevalence",
        "health_covariate_url": PLACES_URL,
        "socioeconomic_covariates": "County Health Rankings 2020 analytic data",
        "socioeconomic_covariate_url": CHR_URL,
        "poverty_proxy": "County Health Rankings percentage of children in poverty; the paper describes county poverty rate.",
        "green_space_proxy": "County Health Rankings access to exercise opportunities; the paper uses population within half a mile of a park.",
        "n_counties_after_complete_case_join": int(len(panel)),
        "columns": required,
    }
    (RUN_DIR / "adjusted_public_panel_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"n_counties": len(panel), "output": "adjusted_public_analysis_panel.csv"}))


if __name__ == "__main__":
    main()
