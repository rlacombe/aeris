#!/usr/bin/env python3
"""Retrieve no-auth historical weather at AERIS-selected monitor locations."""
from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
BASE = "https://archive-api.open-meteo.com/v1/archive"


def location_columns(frame: pd.DataFrame) -> tuple[str, str]:
    candidates = (("latitude", "longitude"), ("lat", "lon"), ("coordinates.latitude", "coordinates.longitude"))
    for lat, lon in candidates:
        if {lat, lon}.issubset(frame.columns):
            return lat, lon
    raise RuntimeError(f"AERIS station output lacks coordinate columns: {frame.columns.tolist()}")


def main() -> int:
    stations = pd.read_csv(DERIVED / "aeris_national_pm25_stations.csv")
    lat_col, lon_col = location_columns(stations)
    locations = stations[[lat_col, lon_col]].dropna().drop_duplicates().rename(columns={lat_col: "latitude", lon_col: "longitude"})
    records, calls = [], []
    for index, location in locations.reset_index(drop=True).iterrows():
        params = {"latitude": location.latitude, "longitude": location.longitude, "start_date": "2015-01-01", "end_date": "2019-12-31", "daily": "temperature_2m_mean,relative_humidity_2m_mean", "timezone": "UTC"}
        url = f"{BASE}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers={"User-Agent": "AERIS-reproduction/1.0"})
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = response.read()
        decoded = json.loads(payload)
        daily = decoded.get("daily", {})
        frame = pd.DataFrame({"date": daily.get("time", []), "temperature_c": daily.get("temperature_2m_mean", []), "relative_humidity_pct": daily.get("relative_humidity_2m_mean", [])})
        if len(frame) != 1826:
            raise RuntimeError(f"Unexpected coverage for monitor {index}: {len(frame)} days")
        frame["monitor_index"] = index
        records.append(frame)
        calls.append({"monitor_index": index, "latitude": location.latitude, "longitude": location.longitude, "url": url, "sha256": hashlib.sha256(payload).hexdigest()})
        time.sleep(0.25)
    weather = pd.concat(records, ignore_index=True)
    aggregate = weather.groupby("date", as_index=False)[["temperature_c", "relative_humidity_pct"]].mean()
    aggregate.to_csv(DERIVED / "aeris_network_weather_daily.csv", index=False)
    manifest = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "n_monitor_locations": len(locations), "n_days": len(aggregate), "calls": calls, "aggregation": "Unweighted daily mean across retained AERIS monitor locations."}
    (DERIVED / "network_weather_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"n_monitor_locations": len(locations), "n_days": len(aggregate)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
