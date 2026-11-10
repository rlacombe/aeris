#!/usr/bin/env python3
"""Fetch daily municipal-centroid weather from Open-Meteo's archive API."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
PARAMS = {
    "latitude": "-23.1791",
    "longitude": "-45.8872",
    "start_date": "2020-04-01",
    "end_date": "2021-04-30",
    "daily": "temperature_2m_mean,relative_humidity_2m_mean",
    "timezone": "America/Sao_Paulo",
}


def main() -> int:
    DERIVED.mkdir(parents=True, exist_ok=True)
    url = "https://archive-api.open-meteo.com/v1/archive?" + urllib.parse.urlencode(PARAMS)
    request = urllib.request.Request(url, headers={"User-Agent": "AERIS-reproduction/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read())
    daily = payload["daily"]
    frame = pd.DataFrame({
        "date": daily["time"],
        "temperature_c": daily["temperature_2m_mean"],
        "relative_humidity_pct": daily["relative_humidity_2m_mean"],
    })
    if len(frame) != 395 or frame.isna().any().any():
        raise RuntimeError(f"Unexpected Open-Meteo coverage: {len(frame)} rows")
    output = DERIVED / "weather_daily_open_meteo.csv"
    frame.to_csv(output, index=False)
    manifest = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "source_url": url, "rows": len(frame), "output": str(output)}
    (DERIVED / "weather_download_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
