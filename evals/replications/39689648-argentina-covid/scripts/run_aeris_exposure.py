"""Reconstruct department PM2.5 through AERIS with resumable checkpoints.

The source paper used a gridded satellite-model product. This runner instead
uses AERIS boundary estimates from OpenAQ v3 and its historical archive for
the paper's 2020 outcome window. It never reads the paper's PM2.5 values.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import pandas as pd
from shapely.geometry import shape

from aeris.exposure.boundaries import AdministrativeBoundary
from aeris.exposure.cache import ResponseCache
from aeris.exposure.config import Config
from aeris.exposure.estimators.boundary import ExposureEstimatorOpenAQBoundary


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "aeris_department_pm25_2020.csv"
TRACE = ROOT / "outputs" / "aeris_department_pm25_2020_trace.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--department-code", action="append")
    parser.add_argument("--pause-seconds", type=float, default=5.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    os.chdir(ROOT)
    outcomes = pd.read_csv(ROOT / "data" / "derived" / "department_covid_outcomes_2020.csv", dtype={"department_code": str})
    geojson = json.loads((ROOT / "data" / "derived" / "department_boundaries.geojson").read_text())
    features = {
        str(feature["properties"]["department_code"]): feature
        for feature in geojson["features"]
    }
    existing = pd.read_csv(OUTPUT, dtype={"department_code": str}) if OUTPUT.exists() else pd.DataFrame()
    complete = set(existing.get("department_code", pd.Series(dtype=str)).dropna())
    wanted = outcomes.loc[~outcomes["department_code"].isin(complete)].copy()
    if args.department_code:
        wanted = wanted.loc[wanted["department_code"].isin(args.department_code)]
    if args.limit:
        wanted = wanted.head(args.limit)
    config = Config.from_env()
    config.openaq_calls_per_minute = 10
    config.openaq_calls_per_hour = 400
    config.archive_fallback_enabled = True
    cache = ResponseCache(ROOT / ".aeris_openaq_cache.sqlite")
    rows: list[dict] = []
    for index, source_row in wanted.reset_index(drop=True).iterrows():
        code = str(source_row["department_code"])
        feature = features.get(code)
        if feature is None:
            record = {"department_code": code, "status": "unmatched_boundary_code"}
        else:
            boundary = AdministrativeBoundary(
                name=str(feature["properties"]["georef_name"]),
                geometry=shape(feature["geometry"]),
                source="geoBoundaries ARG ADM2 2020",
                metadata={"shapeID": feature["properties"].get("source_boundary_shape_id")},
            )
            result = ExposureEstimatorOpenAQBoundary(
                boundary=boundary,
                start_date="2020-03-01",
                end_date="2020-12-31",
                pollutant="pm25",
                temporal_resolution="daily",
                cache=cache,
                config=config,
            ).run().iloc[0].to_dict()
            record = {"department_code": code, **result}
        rows.append(record)
        TRACE.parent.mkdir(parents=True, exist_ok=True)
        with TRACE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")
        combined = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True)
        combined.to_csv(OUTPUT, index=False)
        print(f"{index + 1}/{len(wanted)} {code}: {record.get('qc_flag', record.get('status'))}")
        if index + 1 < len(wanted):
            time.sleep(args.pause_seconds)


if __name__ == "__main__":
    main()
