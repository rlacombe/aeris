#!/usr/bin/env python3
"""Retrieve public daily weather for the metropolitan-boundary centroid."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
URL = "https://archive-api.open-meteo.com/v1/archive"
PARAMS = {"latitude": "-23.5505", "longitude": "-46.6333", "start_date": "2012-01-01", "end_date": "2015-12-31", "daily": "temperature_2m_mean,temperature_2m_min,temperature_2m_max,relative_humidity_2m_mean,precipitation_sum", "timezone": "America/Sao_Paulo"}


def main() -> int:
    DERIVED.mkdir(parents=True, exist_ok=True)
    url = f"{URL}?{urllib.parse.urlencode(PARAMS)}"
    request = urllib.request.Request(url, headers={"User-Agent": "AERIS-reproduction/1.0"})
    with urllib.request.urlopen(request, timeout=180) as response:
        payload = json.loads(response.read())
    daily = payload["daily"]
    frame = pd.DataFrame({"date": daily["time"], "temperature_c": daily["temperature_2m_mean"], "temperature_min_c": daily["temperature_2m_min"], "temperature_max_c": daily["temperature_2m_max"], "relative_humidity_pct": daily["relative_humidity_2m_mean"], "rainfall_mm": daily["precipitation_sum"]})
    if len(frame) != 1461 or frame.drop(columns="date").isna().any().any():
        raise RuntimeError(f"Expected 1,461 complete days, received {len(frame)}")
    frame.to_csv(DERIVED / "weather_daily_open_meteo.csv", index=False)
    manifest = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "source_url": url, "n_days": len(frame), "departure_from_paper": "The paper used BDMEP weather. This reconstruction uses the documented no-auth Open-Meteo archive at the metropolitan-boundary centroid."}
    (DERIVED / "weather_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
