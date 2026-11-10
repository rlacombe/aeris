"""Check whether AERIS/OpenAQ can reconstruct 2019 PM2.5 for French departments."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from shapely.geometry import shape

from aeris.exposure.boundaries import AdministrativeBoundary
from aeris.exposure.cache import ResponseCache
from aeris.exposure.config import Config
from aeris.exposure.estimators.boundary import ExposureEstimatorOpenAQBoundary

ROOT = Path(__file__).resolve().parent
SAMPLE_DEPARTMENTS = {"Paris", "Nord", "Bouches-du-Rhône", "Haut-Rhin", "Rhône", "Gironde"}


def main() -> None:
    requested = set(sys.argv[1:]) or SAMPLE_DEPARTMENTS
    geojson = json.loads((ROOT / "france_departments.geojson").read_text())
    cache = ResponseCache(ROOT / ".aeris_openaq_cache.sqlite")
    config = Config.from_env()
    config.openaq_calls_per_minute = 15
    config.openaq_calls_per_hour = 600
    results = []
    for feature in geojson["features"]:
        name = feature["properties"]["shapeName"]
        if name not in requested:
            continue
        boundary = AdministrativeBoundary(
            name=name,
            geometry=shape(feature["geometry"]),
            source="geoBoundaries_gbOpen",
            metadata={"properties": feature["properties"]},
        )
        estimator = ExposureEstimatorOpenAQBoundary(
            boundary=boundary,
            start_date="2019-01-01",
            end_date="2019-12-31",
            pollutant="pm25",
            temporal_resolution="daily",
            cache=cache,
            config=config,
        )
        result = estimator.run().iloc[0].to_dict()
        results.append(result)
        print(json.dumps(result, default=str, sort_keys=True))
    (ROOT / "aeris_pm25_2019_probe.json").write_text(json.dumps(results, indent=2, default=str) + "\n")


if __name__ == "__main__":
    main()
