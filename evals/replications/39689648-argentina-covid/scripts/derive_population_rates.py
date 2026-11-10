"""Derive 2020 department populations and COVID-19 rates from public inputs."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import rasterio
from rasterio.mask import mask
from shapely.geometry import shape
from shapely.ops import transform
from math import cos, pi, sin


ROOT = Path(__file__).resolve().parents[1]
OUTCOMES = ROOT / "data" / "derived" / "department_covid_outcomes_2020.csv"
BOUNDARIES = ROOT / "data" / "derived" / "department_boundaries.geojson"
POPULATION = ROOT / "data" / "raw" / "arg_ppp_2020_1km_Aggregated_UNadj.tif"
OUTPUT = ROOT / "data" / "derived" / "department_covid_rates_2020.csv"


def population_in_geometry(dataset: rasterio.io.DatasetReader, geometry: dict) -> float:
    data, _ = mask(dataset, [geometry], crop=True, filled=False)
    return float(data[0].sum())


def area_km2(geometry: dict) -> float:
    # Cylindrical equal-area projection with a 30 degree standard parallel.
    radius_m = 6_371_007.181
    standard_parallel = pi / 6

    def project(lon: float, lat: float) -> tuple[float, float]:
        return (
            radius_m * lon * pi / 180 * cos(standard_parallel),
            radius_m * sin(lat * pi / 180) / cos(standard_parallel),
        )

    return float(transform(project, shape(geometry)).area / 1_000_000)


def main() -> None:
    outcomes = pd.read_csv(OUTCOMES, dtype={"department_code": str})
    features = json.loads(BOUNDARIES.read_text(encoding="utf-8"))["features"]
    rows: list[dict] = []
    with rasterio.open(POPULATION) as dataset:
        for feature in features:
            properties = feature["properties"]
            geometry = feature["geometry"]
            population = population_in_geometry(dataset, geometry)
            area = area_km2(geometry)
            rows.append(
                {
                    "department_code": str(properties["department_code"]),
                    "department_population_2020": population,
                    "area_km2": area,
                    "population_density_per_km2": population / area if area else None,
                }
            )
    frame = outcomes.merge(pd.DataFrame(rows), on="department_code", how="inner")
    for column in ("confirmed_cases", "icu_admissions", "deaths"):
        frame[f"{column}_per_100k"] = 100_000 * frame[column] / frame["department_population_2020"]
    frame.to_csv(OUTPUT, index=False)
    print(f"Wrote {len(frame)} department records to {OUTPUT}")


if __name__ == "__main__":
    main()
