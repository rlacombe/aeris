"""Run AERIS's documented centroid fallback for boundary records with no monitor.

The strict boundary result remains the primary record. This script only assigns
the nearest up-to-three monitors to a department representative point within
OpenAQ's maximum 25 km search radius, and labels each resulting record
``centroid_25km_fallback``.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import pandas as pd
from shapely.geometry import shape

from aeris.exposure.cache import ResponseCache
from aeris.exposure.config import Config
from aeris.exposure.estimators.static import ExposureEstimatorOpenAQStatic

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "aeris_department_pm25_2020_centroid_25km.csv"
TRACE = ROOT / "outputs" / "aeris_department_pm25_2020_centroid_25km_trace.jsonl"
ENV_PATH = Path(".env")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--department-code", action="append")
    parser.add_argument("--pause-seconds", type=float, default=5.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if load_dotenv is not None:
        load_dotenv(ENV_PATH, override=False)
    os.chdir(ROOT)
    strict = pd.read_csv(ROOT / "outputs" / "aeris_department_pm25_2020.csv", dtype={"department_code": str})
    required = set(strict.loc[strict["qc_flag"].eq("NO_STATIONS"), "department_code"])
    geometry = json.loads((ROOT / "data" / "derived" / "department_boundaries.geojson").read_text())
    features = {str(item["properties"]["department_code"]): item for item in geometry["features"]}
    existing = pd.read_csv(OUTPUT, dtype={"department_code": str}) if OUTPUT.exists() else pd.DataFrame()
    done = set(existing.get("department_code", pd.Series(dtype=str)).dropna())
    wanted = sorted(required - done)
    if args.department_code:
        wanted = [code for code in wanted if code in set(args.department_code)]
    if args.limit:
        wanted = wanted[: args.limit]
    config = Config.from_env()
    config.search_radius = 25_000
    config.station_limit = 20
    config.openaq_calls_per_minute = 10
    config.openaq_calls_per_hour = 400
    config.archive_fallback_enabled = True
    cache = ResponseCache(ROOT / ".aeris_openaq_cache.sqlite")
    rows: list[dict] = []
    for index, code in enumerate(wanted, start=1):
        feature = features[code]
        point = shape(feature["geometry"]).representative_point()
        subject = pd.DataFrame(
            [{
                "subject_id": code,
                "latitude": point.y,
                "longitude": point.x,
                "start_date": "2020-03-01",
                "end_date": "2020-12-31",
            }]
        )
        estimator = ExposureEstimatorOpenAQStatic(
            subject,
            pollutant="pm25",
            config=config,
            cache=cache,
            n_stations=3,
            temporal_resolution="daily",
            min_completeness=0,
            location_strategy="per_subject",
        )
        result_frame = estimator.run(skip_confirm=True)
        if result_frame.empty:
            record = {
                "department_code": code,
                "exposure_assignment": "centroid_25km_fallback",
                "qc_flag": "NO_USABLE_MEASUREMENTS",
            }
        else:
            record = {
                "department_code": code,
                "exposure_assignment": "centroid_25km_fallback",
                **result_frame.iloc[0].to_dict(),
            }
        rows.append(record)
        with TRACE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")
        pd.concat([existing, pd.DataFrame(rows)], ignore_index=True).to_csv(OUTPUT, index=False)
        print(f"{index}/{len(wanted)} {code}: {record.get('qc_flag')}")
        if index < len(wanted):
            time.sleep(args.pause_seconds)


if __name__ == "__main__":
    main()
