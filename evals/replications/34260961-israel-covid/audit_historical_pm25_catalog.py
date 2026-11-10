"""Audit 2016--2019 PM2.5 availability for every current OpenAQ Israel location.

The AERIS static workflow selects stations from OpenAQ's country catalogue and
then uses the public S3 archive to recover historical measurements. This audit
tests both stages separately: it extracts every current Israeli location marked
with a PM2.5 sensor from the study-scoped AERIS cache, then lists the historical
S3 objects for each location. It does not read the paper's exposure surface.
"""

from __future__ import annotations

import csv
import json
import pickle
import sqlite3
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any

from aeris.exposure.api_clients.openaq_archive import OpenAQArchiveClient


RUN_DIRECTORY = Path(__file__).resolve().parent
CACHE_PATH = RUN_DIRECTORY / ".aeris_openaq_cache.sqlite"
START_DATE = date(2016, 1, 1)
END_DATE = date(2019, 12, 31)


def load_country_catalog() -> list[Any]:
    """Return the largest cached list of Israeli OpenAQ locations."""
    with sqlite3.connect(CACHE_PATH) as connection:
        blobs = [row[0] for row in connection.execute("SELECT value FROM cache")]

    candidates: list[list[Any]] = []
    for blob in blobs:
        try:
            value = pickle.loads(blob)
        except Exception:
            continue
        if not isinstance(value, list) or not value:
            continue
        first = value[0]
        country = getattr(getattr(first, "country", None), "code", None)
        if country == "IL" and hasattr(first, "sensors"):
            candidates.append(value)
    if not candidates:
        raise RuntimeError(f"No cached Israeli OpenAQ country catalogue in {CACHE_PATH}")
    return max(candidates, key=len)


def has_parameter(location: Any, parameter: str) -> bool:
    return any(
        str(getattr(getattr(sensor, "parameter", None), "name", "")).lower() == parameter
        for sensor in (getattr(location, "sensors", None) or [])
    )


def coordinate(location: Any, field: str) -> float | None:
    value = getattr(location, "coordinates", None)
    value = value.get(field) if isinstance(value, dict) else getattr(value, field, None)
    return float(value) if value is not None else None


def scan_location(location: Any, parameter: str) -> dict[str, object]:
    """List one station's S3 coverage without downloading measurements."""
    row: dict[str, object] = {
        "location_id": int(location.id),
        "location_name": str(location.name),
        "latitude": coordinate(location, "latitude"),
        "longitude": coordinate(location, "longitude"),
        f"{parameter}_sensor_ids": ";".join(
            str(sensor.id)
            for sensor in (location.sensors or [])
            if str(getattr(getattr(sensor, "parameter", None), "name", "")).lower() == parameter
        ),
    }
    archive = OpenAQArchiveClient(timeout=(5.0, 45.0), max_retries=3)
    try:
        dates = archive.list_available_dates(int(location.id), START_DATE, END_DATE)
        by_year = Counter(value.year for value in dates)
        row.update(
            {
                "s3_listing_status": "ok",
                "s3_total_days": len(dates),
                **{f"s3_days_{year}": by_year.get(year, 0) for year in range(2016, 2020)},
            }
        )
    except Exception as exc:
        row.update(
            {
                "s3_listing_status": "error",
                "s3_error": f"{type(exc).__name__}: {exc}",
                "s3_total_days": 0,
                **{f"s3_days_{year}": 0 for year in range(2016, 2020)},
            }
        )
    return row


def main() -> int:
    parameter = sys.argv[1].strip().lower() if len(sys.argv) > 1 else "pm25"
    if not parameter:
        raise ValueError("Usage: audit_historical_pm25_catalog.py [parameter]")
    catalogue = load_country_catalog()
    pollutant_locations = [location for location in catalogue if has_parameter(location, parameter)]
    rows: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(scan_location, location, parameter) for location in pollutant_locations]
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False))
    rows.sort(key=lambda row: int(row["location_id"]))

    fields = [
        "location_id",
        "location_name",
        "latitude",
        "longitude",
        f"{parameter}_sensor_ids",
        "s3_listing_status",
        "s3_total_days",
        "s3_days_2016",
        "s3_days_2017",
        "s3_days_2018",
        "s3_days_2019",
        "s3_error",
    ]
    with (RUN_DIRECTORY / f"openaq_{parameter}_catalog_audit.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    successful = [row for row in rows if row["s3_listing_status"] == "ok"]
    available = [row for row in successful if int(row["s3_total_days"]) > 0]
    report = {
        "study_pmid": "34260961",
        "retrieved_on": "2026-08-15",
        "catalogue_locations": len(catalogue),
        "parameter": parameter,
        "catalogue_parameter_locations": len(pollutant_locations),
        "s3_window": f"{START_DATE.isoformat()} through {END_DATE.isoformat()}",
        "locations_with_s3_objects": len(available),
        "location_ids_with_s3_objects": [row["location_id"] for row in available],
        "locations_with_s3_listing_errors": len(rows) - len(successful),
    }
    (RUN_DIRECTORY / f"openaq_{parameter}_catalog_audit.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
