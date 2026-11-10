#!/usr/bin/env python3
"""Build a no-login CDC Atlas exploratory panel for PMID 39377000.

The direct public Atlas export provides all-stroke, rather than ischemic-stroke,
rates for adults 65+ through 2019. This script creates a 2019 county panel for
an exploratory AERIS run; it is not the paper's published outcome extraction.
"""

from __future__ import annotations

import csv
import json
import urllib.request
import zipfile
from pathlib import Path


RUN_DIR = Path(__file__).resolve().parent
ATLAS_URL = (
    "https://data.cdc.gov/resource/7b9s-s8ck.json?$limit=500000&$where="
    "geographiclevel=%27County%27%20AND%20topic=%27All%20stroke%27%20AND%20"
    "stratification1=%27Ages%2065%20years%20and%20older%27%20AND%20"
    "stratification2=%27Overall%27%20AND%20stratification3=%27Overall%27%20AND%20"
    "year=%272019%27"
)
GAZETTEER_ARCHIVE = RUN_DIR / "2019_Gaz_counties_national.zip"
GAZETTEER_MEMBER = "2019_Gaz_counties_national.txt"


def atlas_rows() -> list[dict]:
    path = RUN_DIR / "cdc_atlas_all_stroke_65plus_2019.json"
    if not path.exists():
        with urllib.request.urlopen(ATLAS_URL, timeout=180) as response:
            path.write_bytes(response.read())
    return json.loads(path.read_text(encoding="utf-8"))


def county_coordinates() -> dict[str, tuple[float, float]]:
    if not GAZETTEER_ARCHIVE.exists():
        raise FileNotFoundError(f"Missing {GAZETTEER_ARCHIVE}; download the Census gazetteer first.")
    with zipfile.ZipFile(GAZETTEER_ARCHIVE) as archive:
        with archive.open(GAZETTEER_MEMBER) as raw:
            reader = csv.reader((line.decode("utf-8") for line in raw), delimiter="\t")
            header = [field.strip() for field in next(reader)]
            coordinates = {}
            for values in reader:
                row = dict(zip(header, (field.strip() for field in values)))
                if row.get("GEOID"):
                    coordinates[row["GEOID"]] = (float(row["INTPTLAT"]), float(row["INTPTLONG"]))
            return coordinates


def main() -> None:
    coordinates = county_coordinates()
    outcomes = []
    for row in atlas_rows():
        value = row.get("data_value")
        fips = row.get("locationid")
        if not value or value == "NA" or not fips or fips not in coordinates:
            continue
        latitude, longitude = coordinates[fips]
        outcomes.append(
            {
                "fips": fips,
                "county_name": row["locationdesc"],
                "state": row["locationabbr"],
                "year": 2019,
                "all_stroke_rate_per_100k_65plus": float(value),
                "latitude": latitude,
                "longitude": longitude,
            }
        )
    outcomes.sort(key=lambda row: row["fips"])
    output = RUN_DIR / "atlas_all_stroke_65plus_county_2019.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(outcomes[0]))
        writer.writeheader()
        writer.writerows(outcomes)

    cohort = RUN_DIR / "aeris_cohort_2019.csv"
    with cohort.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["subject_id", "latitude", "longitude", "start_date", "end_date"],
        )
        writer.writeheader()
        for row in outcomes:
            writer.writerow(
                {
                    "subject_id": row["fips"],
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "start_date": "2019-01-01",
                    "end_date": "2019-12-31",
                }
            )
    manifest = {
        "outcome_source": "CDC Rates and Trends in Heart Disease and Stroke Mortality, dataset 7b9s-s8ck",
        "outcome_url": ATLAS_URL,
        "outcome": "All-stroke mortality, adults 65+, age-standardized spatiotemporally smoothed county rate",
        "outcome_year": 2019,
        "location_source": "2019 Census Gazetteer county internal points",
        "location_url": "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2019_Gazetteer/2019_Gaz_counties_national.zip",
        "n_counties": len(outcomes),
    }
    (RUN_DIR / "atlas_proxy_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"n_counties": len(outcomes), "outcome_panel": str(output)}))


if __name__ == "__main__":
    main()
